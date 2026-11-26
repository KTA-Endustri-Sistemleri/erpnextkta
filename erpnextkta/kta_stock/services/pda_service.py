import base64
import hashlib
import hmac
import json
import re
import time
from urllib.parse import unquote

import frappe
from erpnext.stock.utils import get_incoming_rate
from frappe import _
from frappe.translate import get_all_translations
from frappe.utils import cint, flt, nowdate, nowtime
from frappe.utils.password import (
    check_password,
    get_decrypted_password,
    set_encrypted_password,
)

from erpnextkta.kta_stock.label_manager import enqueue_print_labels_by_names
from erpnextkta.kta_stock.services.relabeling_service import (
    create_package_merge_repack,
    create_package_split_repack,
    extract_base_lot,
    get_batch_ledger_balances,
    is_standard_kta_box_batch,
    sync_batch_label_to_ledger_balance,
)
from erpnextkta.kta_stock.setup import PDA_ROLE_STOCK_USER

_SAP_PREFIXED_WAREHOUSE_RE = re.compile(r"^(\d{2,4})-(.+)$")

PDA_STOCK_ROLES = {PDA_ROLE_STOCK_USER, "Stock Manager", "System Manager"}
PDA_MODULE_REGISTRY = [
    {
        "key": "stock",
        "title": "Stock",
        "icon": "📦",
        "allowed_roles": PDA_STOCK_ROLES,
        "items": [
            {
                "key": "picking",
                "title": "Hat İkmal Toplama",
                "subtitle": "Açık ikmal emirlerini okutarak topla ve hatta aktar",
                "icon": "📦",
                "accent": "accent-blue",
                "allowed_roles": PDA_STOCK_ROLES,
            },
            {
                "key": "split",
                "title": "Koli Bölme ve Etiketleme",
                "subtitle": "Mevcut koliyi böl, yeni parti oluştur ve etiket bas",
                "icon": "✂️",
                "accent": "accent-amber",
                "allowed_roles": PDA_STOCK_ROLES,
            },
            {
                "key": "merge",
                "title": "Koli Birleştirme",
                "subtitle": "Mevcut kolileri tek partide birleştir ve etiket bas",
                "icon": "🔗",
                "accent": "accent-purple",
                "allowed_roles": PDA_STOCK_ROLES,
            },
            {
                "key": "transfer",
                "title": "Depo Raf Transferi",
                "subtitle": "Koli ve hedef raf okutarak raflar arası tam kutu taşı",
                "icon": "🔄",
                "accent": "accent-green",
                "allowed_roles": PDA_STOCK_ROLES,
            },
            {
                "key": "lookup",
                "title": "Stok ve Etiket Sorgula",
                "subtitle": "Koli, raf veya ürün barkodu ile anlık bakiye görüntüle",
                "icon": "🔍",
                "accent": "accent-indigo",
                "allowed_roles": PDA_STOCK_ROLES,
            },
        ],
    }
]


def _compute_all_pda_roles() -> set[str]:
    roles: set[str] = set()
    for category in PDA_MODULE_REGISTRY:
        roles.update(category.get("allowed_roles") or ())
        for item in category.get("items") or ():
            roles.update(item.get("allowed_roles") or ())
    return roles


ALL_PDA_ROLES = _compute_all_pda_roles()
ALLOWED_PDA_ROLES = ALL_PDA_ROLES
PDA_DEVICE_COOKIE = "kta_pda_device"
PDA_DEVICE_TTL_SECONDS = 30 * 24 * 3600
PDA_INACTIVITY_TIMEOUT_SEC = 300
_EPSILON = 1e-6
_LABEL_TYPES = ("Depo Giriş Etiketi", "İş Emri Etiketi")

_PDA_PIN_MAX_FAILURES = 5
_PDA_PIN_LOCKOUT_SECONDS = 300
_PDA_PIN_RE = re.compile(r"^[0-9]{4}$")
_PDA_SUPPORTED_LANGS = ("tr", "en", "de")
_PDA_PIN_ADMIN_ROLES = {"Stock Manager", "System Manager"}
_PDA_PWD_LOCKOUT_PREFIX = "pda_pwd_fail:"


def _get_pda_signing_secret() -> bytes:
    """Resolve the HMAC signing secret from site config or System Settings fallback."""
    conf = getattr(frappe.local, "conf", None)
    secret = conf.get("secret_key") if conf else None
    if not secret:
        secret = frappe.get_site_config().get("encryption_key")
    if not secret:
        secret = frappe.db.get_value("System Settings", None, "modified")
    if not secret:
        secret = "kta-pda-fallback-secret"
    return str(secret).encode("utf-8")


def _sign_payload(payload_b64: str) -> str:
    """Return hex HMAC-SHA256 digest for a base64url-encoded token payload."""
    return hmac.new(
        _get_pda_signing_secret(),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def issue_pda_device_token(device_id: str | None = None) -> str:
    """Issue a 30-day HMAC-SHA256 signed device authorization token."""
    now = int(time.time())
    payload = {
        "did": (device_id or frappe.generate_hash(length=16)),
        "iat": now,
        "exp": now + PDA_DEVICE_TTL_SECONDS,
    }
    raw_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    payload_b64 = base64.urlsafe_b64encode(raw_json).decode("ascii").rstrip("=")
    return f"{payload_b64}.{_sign_payload(payload_b64)}"


def verify_pda_device_token(token: str | None) -> bool:
    """Validate HMAC signature and expiration timestamp of a PDA device token."""
    if not token or not isinstance(token, str) or "." not in token:
        return False

    payload_b64, sig_hex = token.split(".", 1)
    if (
        not payload_b64
        or not sig_hex
        or not payload_b64.isascii()
        or not sig_hex.isascii()
    ):
        return False

    expected_sig = _sign_payload(payload_b64)
    if not hmac.compare_digest(sig_hex, expected_sig):
        return False

    try:
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, TypeError, json.JSONDecodeError):
        return False

    if not isinstance(payload, dict):
        return False

    try:
        exp = int(payload.get("exp") or 0)
    except (ValueError, TypeError):
        return False

    return exp > int(time.time())


def has_valid_pda_device_cookie() -> bool:
    """Return True if the active HTTP request carries a valid kta_pda_device cookie."""
    req = getattr(frappe.local, "request", None)
    cookies = getattr(req, "cookies", None) if req else None
    if not cookies:
        return False
    raw_token = cookies.get(PDA_DEVICE_COOKIE)
    if not raw_token:
        return False
    return verify_pda_device_token(unquote(raw_token))


def set_pda_device_cookie(device_id: str | None = None) -> str:
    """Issue a PDA device token and write it as an HTTP-only cookie if available."""
    token = issue_pda_device_token(device_id=device_id)
    cookie_manager = getattr(frappe.local, "cookie_manager", None)
    if cookie_manager:
        cookie_manager.set_cookie(
            PDA_DEVICE_COOKIE,
            token,
            max_age=PDA_DEVICE_TTL_SECONDS,
            httponly=True,
            samesite="Lax",
        )
    return token


def _is_authorized_pda_user(user: str | None = None) -> bool:
    """Return True if user is authenticated and holds at least one ALL_PDA_ROLES."""
    target_user = user or getattr(frappe.session, "user", None)
    if not target_user or target_user == "Guest":
        return False
    return bool(set(frappe.get_roles(target_user)).intersection(ALL_PDA_ROLES))


_is_authorized_stock_user = _is_authorized_pda_user


def get_authorized_menu_categories(user: str | None = None) -> list[dict]:
    """Return JSON-serializable PDA menu categories/screens authorized for the user."""
    target_user = user or getattr(frappe.session, "user", None)
    if not target_user or target_user == "Guest":
        return []

    user_roles = set(frappe.get_roles(target_user))
    categories: list[dict] = []
    for category in PDA_MODULE_REGISTRY:
        cat_roles = set(category.get("allowed_roles") or ())
        if cat_roles and not user_roles.intersection(cat_roles):
            continue

        authorized_items = []
        for item in category.get("items") or ():
            item_roles = set(item.get("allowed_roles") or cat_roles)
            if item_roles and not user_roles.intersection(item_roles):
                continue
            authorized_items.append(
                {
                    "key": item["key"],
                    "title": item["title"],
                    "subtitle": item["subtitle"],
                    "icon": item["icon"],
                    "accent": item["accent"],
                }
            )

        if authorized_items:
            categories.append(
                {
                    "key": category["key"],
                    "title": category["title"],
                    "icon": category["icon"],
                    "items": authorized_items,
                }
            )
    return categories


def _require_authorized_device_or_user() -> None:
    """Reject Guest requests lacking a valid device cookie or unauthorized users."""
    if _is_authorized_pda_user():
        return
    if frappe.session.user == "Guest" and has_valid_pda_device_cookie():
        return
    frappe.throw(
        _("Bu PDA terminaline erişim yetkiniz bulunmamaktadır."),
        frappe.PermissionError,
    )


def _employee_has_pda_pin(employee_name: str) -> bool:
    """Return True if an encrypted PDA PIN is stored for the employee."""
    pin = get_decrypted_password(
        "Employee",
        employee_name,
        fieldname="custom_pda_pin",
        raise_exception=False,
    )
    return bool(pin)


def get_pda_operators() -> list[dict]:
    """Return active employees linked to enabled users holding any PDA module role."""
    employees = frappe.get_all(
        "Employee",
        filters={
            "status": "Active",
            "user_id": ["is", "set"],
        },
        fields=["name", "employee", "employee_name", "department", "user_id"],
        order_by="employee_name asc",
    )
    user_ids = list({emp.user_id for emp in employees if emp.user_id})
    if not user_ids:
        return []

    enabled_users = set(
        frappe.get_all(
            "User",
            filters={"name": ["in", user_ids], "enabled": 1},
            pluck="name",
        )
    )
    if not enabled_users:
        return []

    operators: list[dict] = []
    for emp in employees:
        if emp.user_id not in enabled_users:
            continue
        if not _is_authorized_pda_user(emp.user_id):
            continue
        operators.append(
            {
                "employee": emp.employee or emp.name,
                "name": emp.name,
                "employee_name": emp.employee_name,
                "department": emp.department,
                "user_id": emp.user_id,
                "has_pin": _employee_has_pda_pin(emp.name),
            }
        )
    return operators


def _get_active_operator_profile(
    user_id: str | None, operators: list[dict]
) -> dict | None:
    """Return operator dict for the current authenticated user, or None for Guest."""
    if not user_id or user_id == "Guest":
        return None

    for operator in operators:
        if operator["user_id"] == user_id:
            return operator

    emp = frappe.db.get_value(
        "Employee",
        {"user_id": user_id, "status": "Active"},
        ["name", "employee", "employee_name", "department", "user_id"],
        as_dict=True,
    )
    if not emp:
        return None

    return {
        "employee": emp.employee or emp.name,
        "name": emp.name,
        "employee_name": emp.employee_name,
        "department": emp.department,
        "user_id": emp.user_id,
        "has_pin": _employee_has_pda_pin(emp.name),
    }


def _ensure_login_manager():
    """Return active LoginManager, safely bootstrapping request/cookie state in tests."""
    from frappe.auth import CookieManager, LoginManager
    from frappe.utils import set_request

    if not getattr(frappe.local, "request", None):
        set_request(path="/")
    if not getattr(frappe.local, "request_ip", None):
        frappe.local.request_ip = "127.0.0.1"
    if not getattr(frappe.local, "cookie_manager", None):
        frappe.local.cookie_manager = CookieManager()

    login_manager = getattr(frappe.local, "login_manager", None)
    if not login_manager:
        current_user = getattr(frappe.session, "user", None)
        login_manager = LoginManager()
        frappe.local.login_manager = login_manager
        if current_user and current_user != "Guest" and frappe.session.user == "Guest":
            frappe.set_user(current_user)
            login_manager.user = current_user
    return login_manager


def _validate_pda_operator_record(employee: str) -> frappe._dict:
    """Validate that employee is active and linked to an enabled authorized PDA user."""
    emp = frappe.db.get_value(
        "Employee",
        employee,
        ["name", "employee_name", "status", "department", "user_id"],
        as_dict=True,
    )
    if (
        not emp
        or emp.status != "Active"
        or not emp.user_id
        or cint(frappe.db.get_value("User", emp.user_id, "enabled")) != 1
        or not _is_authorized_pda_user(emp.user_id)
    ):
        frappe.throw(
            _("Seçilen personel PDA girişi için yetkili veya aktif değil."),
            frappe.ValidationError,
        )
    return emp


def _verify_pin_with_rate_limit(employee_name: str, clean_pin: str) -> None:
    """Check 4-digit PIN with 5-attempt / 300s rate-limit lockout via cache."""
    fail_key = f"pda_pin_fail:{employee_name}"
    fail_count = cint(frappe.cache().get_value(fail_key, expires=True) or 0)
    if fail_count >= _PDA_PIN_MAX_FAILURES:
        frappe.throw(
            _("Çok fazla hatalı PIN denemesi. Lütfen 5 dakika sonra tekrar deneyin."),
            frappe.ValidationError,
        )

    stored_pin = get_decrypted_password(
        "Employee",
        employee_name,
        fieldname="custom_pda_pin",
        raise_exception=False,
    )
    if not stored_pin:
        frappe.throw(
            _("Bu personel için henüz PDA PIN kodu tanımlanmamış."),
            frappe.ValidationError,
        )

    if not hmac.compare_digest(str(stored_pin), clean_pin):
        new_count = fail_count + 1
        frappe.cache().set_value(
            fail_key, new_count, expires_in_sec=_PDA_PIN_LOCKOUT_SECONDS
        )
        if new_count >= _PDA_PIN_MAX_FAILURES:
            frappe.throw(
                _("Çok fazla hatalı PIN denemesi. Hesap 5 dakika süreyle kilitlendi."),
                frappe.ValidationError,
            )
        remaining = _PDA_PIN_MAX_FAILURES - new_count
        frappe.throw(
            _("Hatalı PIN kodu. Kalan deneme hakkı: {0}.").format(remaining),
            frappe.ValidationError,
        )

    frappe.cache().delete_value(fail_key)


@frappe.whitelist(allow_guest=True)
def get_pda_boot_data() -> dict:
    """Return PDA hub boot payload including lock state, operators, menu tree, and picking count."""
    _require_authorized_device_or_user()
    current_user = frappe.session.user or "Guest"
    operators = get_pda_operators()
    active_operator = _get_active_operator_profile(current_user, operators)
    open_picking_count = frappe.db.count(
        "KTA Line Replenishment Order",
        {"status": ["in", ["Draft", "In Progress"]]},
    )
    return {
        "is_locked": current_user == "Guest",
        "current_user": current_user,
        "active_operator": active_operator,
        "device_authorized": bool(
            has_valid_pda_device_cookie() or _is_authorized_pda_user(current_user)
        ),
        "inactivity_timeout_sec": PDA_INACTIVITY_TIMEOUT_SEC,
        "operators": operators,
        "open_picking_count": cint(open_picking_count),
        "menu_categories": get_authorized_menu_categories(current_user),
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
def verify_pda_pin(employee: str, pin: str) -> dict:
    """Verify operator 4-digit PIN and switch the real Frappe session via login_as."""
    _require_authorized_device_or_user()

    clean_employee = str(employee or "").strip()
    clean_pin = str(pin or "").strip()
    if not clean_employee:
        frappe.throw(_("Personel seçimi zorunludur."), frappe.ValidationError)
    if not _PDA_PIN_RE.fullmatch(clean_pin):
        frappe.throw(
            _("PIN kodu tam olarak 4 sayısal rakamdan oluşmalıdır."),
            frappe.ValidationError,
        )

    emp = _validate_pda_operator_record(clean_employee)
    _verify_pin_with_rate_limit(emp.name, clean_pin)

    login_manager = _ensure_login_manager()
    login_manager.login_as(emp.user_id)
    set_pda_device_cookie()
    csrf_token = frappe.sessions.get_csrf_token()
    open_picking_count = cint(
        frappe.db.count(
            "KTA Line Replenishment Order",
            {"status": ["in", ["Draft", "In Progress"]]},
        )
    )
    trans_payload = _build_pda_translations_payload(emp.user_id)
    frappe.local.lang = trans_payload["lang"]

    return {
        "ok": True,
        "user": emp.user_id,
        "employee": emp.name,
        "employee_name": emp.employee_name,
        "csrf_token": csrf_token,
        "menu_categories": get_authorized_menu_categories(emp.user_id),
        "open_picking_count": open_picking_count,
        **trans_payload,
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
def pda_handover_logout() -> dict:
    """Log out the active operator session while keeping the PDA device authorized."""
    _require_authorized_device_or_user()

    if frappe.session.user != "Guest":
        login_manager = _ensure_login_manager()
        login_manager.logout()
        if frappe.session.user != "Guest":
            frappe.set_user("Guest")

    set_pda_device_cookie()
    csrf_token = frappe.sessions.get_csrf_token()
    trans_payload = _build_pda_translations_payload("Guest")
    frappe.local.lang = trans_payload["lang"]

    return {
        "ok": True,
        "is_locked": True,
        "device_authorized": True,
        "csrf_token": csrf_token,
        **trans_payload,
    }


def _require_pda_operator() -> str:
    """Ensure the active Frappe session belongs to an authorized PDA user."""
    if not _is_authorized_pda_user():
        frappe.throw(
            _("Bu işlem için yetkili PDA kullanıcı oturumu gereklidir."),
            frappe.PermissionError,
        )
    return frappe.session.user


def _require_pda_screen_access(screen_keys: str | tuple[str, ...]) -> str:
    """Ensure the active session user holds access to at least one requested PDA screen."""
    target_user = _require_pda_operator()
    required = (screen_keys,) if isinstance(screen_keys, str) else tuple(screen_keys)
    authorized_screens = {
        item["key"]
        for category in get_authorized_menu_categories(target_user)
        for item in category.get("items") or ()
    }
    if not authorized_screens.intersection(required):
        frappe.throw(
            _("Bu PDA ekranına erişim yetkiniz bulunmamaktadır."),
            frappe.PermissionError,
        )
    return target_user


def _ancestor_matches_depot_code(warehouse_name: str | None, depot_code: str) -> bool:
    """Return True when a group warehouse name begins with the exact depot code."""
    normalized = (warehouse_name or "").strip().upper()
    code = (depot_code or "").strip().upper()
    if not (normalized and code):
        return False
    return normalized == code or normalized.startswith((f"{code} ", f"{code}-"))


def _warehouse_has_prefix_ancestor(wh: dict, depot_code: str) -> bool:
    """Verify via NestedSet (or parent chain fallback) that wh belongs to depot_code."""
    lft = cint(wh.get("lft"))
    rgt = cint(wh.get("rgt"))
    if lft > 0 and rgt >= lft:
        filters: dict[str, object] = {
            "lft": ["<=", lft],
            "rgt": [">=", rgt],
            "is_group": 1,
        }
        if wh.get("company"):
            filters["company"] = wh.get("company")
        ancestors = frappe.get_all(
            "Warehouse",
            filters=filters,
            fields=["warehouse_name"],
            limit_page_length=50,
        )
        return any(
            _ancestor_matches_depot_code(a.get("warehouse_name"), depot_code)
            for a in ancestors
        )

    parent = wh.get("parent_warehouse")
    visited: set[str] = set()
    while parent and parent not in visited:
        visited.add(parent)
        parent_meta = frappe.db.get_value(
            "Warehouse",
            parent,
            ["warehouse_name", "parent_warehouse"],
            as_dict=True,
        )
        if not parent_meta:
            break
        if _ancestor_matches_depot_code(parent_meta.get("warehouse_name"), depot_code):
            return True
        parent = parent_meta.get("parent_warehouse")
    return False


def _select_warehouse_match(matches: list[dict], code: str) -> dict | None:
    """Select a single Warehouse match, preferring active leaves and guarding ambiguity."""
    if not matches:
        return None

    active_leaf = [m for m in matches if not cint(m.is_group) and not cint(m.disabled)]
    if len(active_leaf) == 1:
        return active_leaf[0]
    if len(active_leaf) > 1:
        default_company = frappe.defaults.get_user_default(
            "Company"
        ) or frappe.db.get_single_value("Global Defaults", "default_company")
        if default_company:
            company_leaf = [m for m in active_leaf if m.company == default_company]
            if len(company_leaf) == 1:
                return company_leaf[0]
        frappe.throw(
            _("Birden fazla depo eşleşti, lütfen şirket ekiyle tarayın: {0}").format(
                code
            ),
            frappe.ValidationError,
        )

    return matches[0]


def _lookup_warehouse_record(barcode: str, company: str | None = None) -> dict | None:
    """Find a Warehouse by exact name, warehouse_name, or SAP depot-prefixed code."""
    code = (barcode or "").strip()
    if not code:
        return None

    fields = [
        "name",
        "warehouse_name",
        "company",
        "is_group",
        "disabled",
        "lft",
        "rgt",
        "parent_warehouse",
    ]
    exact = frappe.db.get_value("Warehouse", {"name": code}, fields, as_dict=True)
    if exact and (not company or exact.company == company):
        return exact

    base_filters: dict[str, object] = {}
    if company:
        base_filters["company"] = company

    matches = frappe.get_all(
        "Warehouse",
        filters={**base_filters, "warehouse_name": code},
        fields=fields,
        order_by="is_group asc, disabled asc, name asc",
        limit_page_length=10,
    )
    if matches:
        return _select_warehouse_match(matches, code)

    sap_match = _SAP_PREFIXED_WAREHOUSE_RE.match(code)
    if not sap_match:
        return None

    depot_code, shelf_code = sap_match.group(1), sap_match.group(2).strip()
    if not shelf_code:
        return None

    candidates = frappe.get_all(
        "Warehouse",
        filters={**base_filters, "warehouse_name": shelf_code},
        fields=fields,
        order_by="is_group asc, disabled asc, name asc",
        limit_page_length=20,
    )
    scoped = [
        candidate
        for candidate in candidates
        if _warehouse_has_prefix_ancestor(candidate, depot_code)
    ]
    return _select_warehouse_match(scoped, code)


def resolve_warehouse_barcode(barcode: str, company: str | None = None) -> dict:
    """Resolve a scanned warehouse barcode to an active non-group Warehouse record."""
    code = (barcode or "").strip()
    wh = _lookup_warehouse_record(code, company=company)
    if not wh:
        frappe.throw(
            _("Depo barkodu bulunamadı: {0}").format(code), frappe.ValidationError
        )
    if cint(wh.disabled):
        frappe.throw(
            _("Depo pasif durumda: {0}").format(wh.name), frappe.ValidationError
        )
    if cint(wh.is_group):
        frappe.throw(
            _("Grup depo seçilemez: {0}").format(wh.name), frappe.ValidationError
        )
    return {
        "name": wh.name,
        "warehouse_name": wh.warehouse_name,
        "company": wh.company,
        "is_group": cint(wh.is_group),
    }


def _resolve_box_label_and_batch(
    barcode: str,
    fallback_label_name: bool = False,
) -> tuple[dict | None, str | None, str | None]:
    """Resolve a box label or batch barcode into (label_doc, batch_no, item_code)."""
    code = (barcode or "").strip()
    if not code:
        return None, None, None

    label_fields = [
        "name",
        "item_code",
        "batch",
        "label_type",
        "sut_barcode",
        "qty",
        "target_warehouse",
    ]
    label = frappe.db.get_value(
        "KTA Stock Label",
        {"sut_barcode": code, "label_type": ["in", list(_LABEL_TYPES)]},
        label_fields,
        as_dict=True,
        order_by="modified desc",
    )
    if label and label.batch:
        item_code = label.item_code or frappe.db.get_value("Batch", label.batch, "item")
        return label, label.batch, item_code

    batch_doc = frappe.db.get_value(
        "Batch",
        code,
        ["name", "item", "expiry_date", "stock_uom"],
        as_dict=True,
    )
    if batch_doc:
        linked_label = frappe.db.get_value(
            "KTA Stock Label",
            {
                "batch": batch_doc.name,
                "item_code": batch_doc.item,
                "label_type": ["in", list(_LABEL_TYPES)],
            },
            label_fields,
            as_dict=True,
            order_by="modified desc",
        )
        return linked_label, batch_doc.name, batch_doc.item

    if (
        fallback_label_name
        and code.isascii()
        and code.isdigit()
        and frappe.db.exists("KTA Stock Label", code)
    ):
        by_name = frappe.db.get_value(
            "KTA Stock Label",
            {"name": code, "label_type": ["in", list(_LABEL_TYPES)]},
            label_fields,
            as_dict=True,
        )
        if by_name and str(by_name.name) == code and by_name.batch:
            item_code = by_name.item_code or frappe.db.get_value(
                "Batch", by_name.batch, "item"
            )
            return by_name, by_name.batch, item_code

    return None, None, None


def _build_batch_scan_payload(
    label: dict | None,
    batch_no: str,
    item_code: str,
    balances: list[dict],
    kind: str | None = None,
) -> dict:
    """Build normalized batch scan response dictionary from label, metadata, and balances."""
    item_meta = (
        frappe.db.get_value("Item", item_code, ["item_name", "stock_uom"], as_dict=True)
        or {}
    )
    batch_meta = (
        frappe.db.get_value(
            "Batch", batch_no, ["expiry_date", "stock_uom"], as_dict=True
        )
        or {}
    )
    expiry_raw = batch_meta.get("expiry_date")
    clean_balances = [
        {"warehouse": b["warehouse"], "qty": flt(b.get("qty"))} for b in balances
    ]
    total_qty = flt(sum(b["qty"] for b in clean_balances))

    payload = {
        "item_code": item_code,
        "item_name": item_meta.get("item_name"),
        "stock_uom": item_meta.get("stock_uom") or batch_meta.get("stock_uom"),
        "batch_no": batch_no,
        "base_lot": extract_base_lot(batch_no)
        if is_standard_kta_box_batch(batch_no)
        else batch_no,
        "is_standard_batch": is_standard_kta_box_batch(batch_no),
        "label_name": str(label.name) if label else None,
        "label_type": label.get("label_type") if label else None,
        "sut_barcode": label.get("sut_barcode") if label else None,
        "expiry_date": str(expiry_raw) if expiry_raw else None,
        "total_qty": total_qty,
        "balances": clean_balances,
    }
    if kind:
        payload["kind"] = kind
    return payload


@frappe.whitelist()
def pda_scan_box(barcode: str) -> dict:
    """Resolve a box barcode (sut_barcode or Batch) and return non-empty warehouse balances."""
    _require_pda_screen_access(("split", "merge", "transfer", "lookup"))
    code = (barcode or "").strip()
    label, batch_no, item_code = _resolve_box_label_and_batch(
        code, fallback_label_name=True
    )
    if not batch_no or not item_code:
        frappe.throw(
            _("Koli veya parti barkodu bulunamadı: {0}").format(code),
            frappe.ValidationError,
        )

    balances = get_batch_ledger_balances(item_code, batch_no)
    total_qty = flt(sum(flt(b.get("qty")) for b in balances))
    if not balances or total_qty <= _EPSILON:
        frappe.throw(
            _("Bu partide kullanılabilir stok bakiyesi bulunmamaktadır: {0}").format(
                batch_no
            ),
            frappe.ValidationError,
        )

    return _build_batch_scan_payload(label, batch_no, item_code, balances)


def _parse_split_qtys(split_qtys: list[float] | tuple[float, ...] | str) -> list[float]:
    """Parse and validate positive split quantities from list or JSON string."""
    raw = split_qtys
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            frappe.throw(_("Geçersiz bölme miktarları biçimi."), frappe.ValidationError)

    if not isinstance(raw, (list, tuple)) or not raw:
        frappe.throw(_("En az bir bölme miktarı girilmelidir."), frappe.ValidationError)

    qtys: list[float] = []
    for entry in raw:
        val = flt(entry)
        if val <= _EPSILON:
            frappe.throw(
                _("Bölme miktarları sıfırdan büyük olmalıdır."), frappe.ValidationError
            )
        qtys.append(val)
    return qtys


@frappe.whitelist(methods=["POST"])
def pda_package_split(
    item_code: str,
    source_warehouse: str,
    source_batch: str,
    split_qtys: list[float] | str,
    reprint_source_label: int = 1,
) -> dict:
    """Split quantities out of a box batch into new KTA boxes and optionally reprint source label."""
    _require_pda_screen_access("split")
    clean_item = (item_code or "").strip()
    clean_warehouse = (source_warehouse or "").strip()
    clean_batch = (source_batch or "").strip()
    if not (clean_item and clean_warehouse and clean_batch):
        frappe.throw(
            _("Ürün, kaynak depo ve kaynak parti bilgileri zorunludur."),
            frappe.ValidationError,
        )

    parsed_qtys = _parse_split_qtys(split_qtys)
    balances = get_batch_ledger_balances(clean_item, clean_batch)
    available_qty = flt(
        next(
            (b.get("qty") for b in balances if b.get("warehouse") == clean_warehouse),
            0.0,
        )
    )
    if available_qty <= _EPSILON:
        frappe.throw(
            _("Kaynak depoda bu parti için kullanılabilir stok bulunmamaktadır."),
            frappe.ValidationError,
        )

    total_split_qty = flt(sum(parsed_qtys))
    if total_split_qty - available_qty > _EPSILON:
        frappe.throw(
            _(
                "Bölünecek toplam miktar ({0}) mevcut stoktan ({1}) fazla olamaz."
            ).format(total_split_qty, available_qty),
            frappe.ValidationError,
        )

    if (
        is_standard_kta_box_batch(clean_batch)
        and len(parsed_qtys) == 1
        and abs(total_split_qty - available_qty) <= _EPSILON
    ):
        frappe.throw(
            _("Standart KTA kolisinin tamamı tek bir yeni koliye bölünemez."),
            frappe.ValidationError,
        )

    repack_result = create_package_split_repack(
        item_code=clean_item,
        source_warehouse=clean_warehouse,
        target_warehouse=clean_warehouse,
        source_batch=clean_batch,
        split_qtys=parsed_qtys,
        remarks=_("PDA Koli Bölme: {0} ({1})").format(clean_batch, clean_warehouse),
        ignore_reco_lock=False,
    )

    remaining_qty = flt(max(0.0, available_qty - total_split_qty), 6)
    if remaining_qty <= _EPSILON:
        remaining_qty = 0.0

    source_label_name = None
    source_label_reprinted = False
    queued_reprint_count = 0

    if remaining_qty > _EPSILON and cint(reprint_source_label) == 1:
        src_label = frappe.db.get_value(
            "KTA Stock Label",
            {
                "item_code": clean_item,
                "batch": clean_batch,
                "label_type": ["in", list(_LABEL_TYPES)],
            },
            "name",
            order_by="modified desc",
        )
        if src_label:
            source_label_name = str(src_label)
            print_res = enqueue_print_labels_by_names(
                [source_label_name], user=frappe.session.user
            )
            queued_reprint_count = cint(print_res.get("queued"))
            source_label_reprinted = queued_reprint_count > 0

    return {
        "ok": True,
        "stock_entry": repack_result["stock_entry"],
        "base_lot": repack_result["base_lot"],
        "source_batch": clean_batch,
        "source_warehouse": clean_warehouse,
        "remaining_qty": remaining_qty,
        "created_batches": repack_result["created_batches"],
        "source_label_name": source_label_name,
        "source_label_reprinted": source_label_reprinted,
        "queued_reprint_count": queued_reprint_count,
    }


def _parse_merge_source_boxes(source_boxes: list[dict] | str) -> list[dict]:
    """Parse and validate >= 2 source box dicts from JSON string or Python sequence."""
    raw = source_boxes
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            frappe.throw(
                _("Geçersiz kaynak koli listesi biçimi."), frappe.ValidationError
            )

    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        frappe.throw(
            _("Birleştirme için en az 2 kaynak koli seçilmelidir."),
            frappe.ValidationError,
        )

    parsed: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            frappe.throw(_("Geçersiz kaynak koli girdisi."), frappe.ValidationError)
        batch_no = str(entry.get("batch_no") or "").strip()
        warehouse = str(entry.get("warehouse") or "").strip()
        if not batch_no or not warehouse:
            frappe.throw(
                _("Her kaynak koli için parti ve depo bilgisi zorunludur."),
                frappe.ValidationError,
            )
        parsed_entry: dict[str, object] = {
            "batch_no": batch_no,
            "warehouse": warehouse,
        }
        if "qty" in entry and entry.get("qty") is not None and entry.get("qty") != "":
            parsed_entry["qty"] = entry.get("qty")
        parsed.append(parsed_entry)
    return parsed


@frappe.whitelist(methods=["POST"])
def pda_package_merge(
    source_boxes: list[dict] | str,
    target_warehouse_barcode: str | None = None,
    allow_mixed_lots: int = 0,
) -> dict:
    """Merge 2+ same-item source boxes into one KTA box and print its label once."""
    _require_pda_screen_access("merge")
    parsed_boxes = _parse_merge_source_boxes(source_boxes)

    item_codes: list[str] = []
    for box in parsed_boxes:
        batch_item = frappe.db.get_value("Batch", box["batch_no"], "item")
        if not batch_item:
            frappe.throw(
                _("Parti bulunamadı: {0}").format(box["batch_no"]),
                frappe.ValidationError,
            )
        item_codes.append(batch_item)

    if len(set(item_codes)) != 1:
        frappe.throw(
            _("Farklı ürün kodlarına ait koliler birleştirilemez."),
            frappe.ValidationError,
        )
    item_code = item_codes[0]

    first_wh_meta = resolve_warehouse_barcode(parsed_boxes[0]["warehouse"])
    company = first_wh_meta["company"]
    clean_target_code = (target_warehouse_barcode or "").strip()
    if clean_target_code:
        target_warehouse = resolve_warehouse_barcode(
            clean_target_code, company=company
        )["name"]
    else:
        target_warehouse = first_wh_meta["name"]

    res = create_package_merge_repack(
        item_code=item_code,
        source_boxes=parsed_boxes,
        target_warehouse=target_warehouse,
        allow_mixed_lots=bool(cint(allow_mixed_lots)),
    )

    label_info = frappe.db.get_value(
        "KTA Stock Label",
        {
            "item_code": item_code,
            "batch": res["target_batch"],
            "label_type": ["in", list(_LABEL_TYPES)],
        },
        ["name", "quality_ref"],
        as_dict=True,
        order_by="modified desc",
    )

    return {
        "ok": True,
        **res,
        "target_label_name": str(label_info.name) if label_info else None,
        "quality_ref": label_info.quality_ref
        if label_info
        else ("KARMA LOT" if res["is_mixed_lot"] else None),
        "owner": frappe.session.user,
    }


def _resolve_transfer_rate(
    item_code: str,
    warehouse: str,
    posting_date: str,
    posting_time: str,
    company: str,
    qty: float,
    batch_no: str | None = None,
) -> float:
    """Return incoming valuation rate for transfer, falling back to Bin valuation rate."""
    rate = flt(
        get_incoming_rate(
            {
                "item_code": item_code,
                "warehouse": warehouse,
                "posting_date": posting_date,
                "posting_time": posting_time,
                "company": company,
                "qty": -abs(flt(qty)),
                "batch_no": batch_no,
            },
            raise_error_if_no_rate=False,
        )
    )
    if rate <= 0:
        rate = flt(
            frappe.db.get_value(
                "Bin",
                {"item_code": item_code, "warehouse": warehouse},
                "valuation_rate",
            )
        )
    return rate


@frappe.whitelist(methods=["POST"])
def pda_material_transfer(
    item_code: str,
    batch_no: str,
    source_warehouse: str,
    target_warehouse_barcode: str,
    qty: float | None = None,
) -> dict:
    """Transfer an entire box batch between warehouses and synchronize its stock label."""
    _require_pda_screen_access("transfer")
    clean_item = (item_code or "").strip()
    clean_batch = (batch_no or "").strip()
    clean_source_wh = (source_warehouse or "").strip()
    clean_target_code = (target_warehouse_barcode or "").strip()
    if not (clean_item and clean_batch and clean_source_wh and clean_target_code):
        frappe.throw(
            _("Ürün, parti, kaynak depo ve hedef depo bilgileri zorunludur."),
            frappe.ValidationError,
        )

    source_wh_meta = frappe.db.get_value(
        "Warehouse",
        clean_source_wh,
        ["name", "company", "is_group", "disabled"],
        as_dict=True,
    )
    if not source_wh_meta:
        frappe.throw(
            _("Kaynak depo bulunamadı: {0}").format(clean_source_wh),
            frappe.ValidationError,
        )
    if cint(source_wh_meta.is_group) or cint(source_wh_meta.disabled):
        frappe.throw(
            _("Kaynak depo işlem için uygun değil: {0}").format(clean_source_wh),
            frappe.ValidationError,
        )

    target_wh = resolve_warehouse_barcode(
        clean_target_code, company=source_wh_meta.company
    )
    target_warehouse = target_wh["name"]
    if target_warehouse == clean_source_wh:
        frappe.throw(
            _("Hedef depo kaynak depo ile aynı olamaz."), frappe.ValidationError
        )

    balances = get_batch_ledger_balances(clean_item, clean_batch)
    available_qty = flt(
        next(
            (b.get("qty") for b in balances if b.get("warehouse") == clean_source_wh),
            0.0,
        )
    )
    if available_qty <= _EPSILON:
        frappe.throw(
            _("Kaynak depoda bu parti için kullanılabilir stok bulunmamaktadır."),
            frappe.ValidationError,
        )

    if qty is None or qty == "":
        transfer_qty = available_qty
    else:
        transfer_qty = flt(qty)
        if transfer_qty <= _EPSILON:
            frappe.throw(
                _("Transfer miktarı sıfırdan büyük olmalıdır."), frappe.ValidationError
            )
        if abs(transfer_qty - available_qty) > _EPSILON:
            frappe.throw(
                _(
                    "PDA depolar arası transfer işleminde kolinin tamamı ({0}) transfer edilmelidir."
                ).format(available_qty),
                frappe.ValidationError,
            )

    posting_date = nowdate()
    posting_time = nowtime()
    rate = _resolve_transfer_rate(
        item_code=clean_item,
        warehouse=clean_source_wh,
        posting_date=posting_date,
        posting_time=posting_time,
        company=source_wh_meta.company,
        qty=transfer_qty,
        batch_no=clean_batch,
    )

    se = frappe.get_doc(
        {
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Transfer",
            "company": source_wh_meta.company,
            "posting_date": posting_date,
            "posting_time": posting_time,
            "from_warehouse": clean_source_wh,
            "to_warehouse": target_warehouse,
            "remarks": _("PDA Depo Transferi: {0} ({1} -> {2})").format(
                clean_batch, clean_source_wh, target_warehouse
            ),
            "items": [
                {
                    "item_code": clean_item,
                    "s_warehouse": clean_source_wh,
                    "t_warehouse": target_warehouse,
                    "qty": transfer_qty,
                    "batch_no": clean_batch,
                    "use_serial_batch_fields": 1,
                    "basic_rate": rate,
                    "allow_zero_valuation_rate": 1 if rate <= 0 else 0,
                }
            ],
        }
    )
    se.insert(ignore_permissions=True)
    se.submit()

    sync_batch_label_to_ledger_balance(clean_item, clean_batch)
    label_names = frappe.get_all(
        "KTA Stock Label",
        filters={
            "item_code": clean_item,
            "batch": clean_batch,
            "label_type": ["in", list(_LABEL_TYPES)],
        },
        pluck="name",
    )
    for label_name in label_names:
        frappe.db.set_value(
            "KTA Stock Label",
            label_name,
            {"source_warehouse": clean_source_wh, "target_warehouse": target_warehouse},
            update_modified=False,
        )

    return {
        "ok": True,
        "stock_entry": se.name,
        "item_code": clean_item,
        "batch_no": clean_batch,
        "qty": flt(transfer_qty),
        "source_warehouse": clean_source_wh,
        "target_warehouse": target_warehouse,
        "owner": se.owner,
    }


def _lookup_warehouse_stock(wh: dict) -> dict:
    """Return positive Bin item balances for a non-group Warehouse."""
    if cint(wh.is_group):
        frappe.throw(
            _("Grup depo sorgulanamaz: {0}").format(wh.name), frappe.ValidationError
        )

    bins = frappe.get_all(
        "Bin",
        filters={"warehouse": wh.name, "actual_qty": [">", 0]},
        fields=["item_code", "actual_qty", "reserved_qty", "stock_uom"],
        order_by="actual_qty desc, item_code asc",
        limit_page_length=200,
    )
    item_codes = [b.item_code for b in bins]
    item_names = {}
    if item_codes:
        item_names = dict(
            frappe.get_all(
                "Item",
                filters={"name": ["in", item_codes]},
                fields=["name", "item_name"],
                as_list=True,
            )
        )
    items = [
        {
            "item_code": b.item_code,
            "item_name": item_names.get(b.item_code),
            "stock_uom": b.stock_uom,
            "actual_qty": flt(b.actual_qty),
            "reserved_qty": flt(b.reserved_qty),
        }
        for b in bins
    ]
    return {
        "kind": "warehouse",
        "warehouse": wh.name,
        "warehouse_name": wh.warehouse_name,
        "company": wh.company,
        "items": items,
    }


def _get_item_batch_balances(item_code: str) -> list[dict]:
    """Return positive batch balances across warehouses for an item from SLE and SABB."""
    legacy_rows = frappe.db.sql(
        """
        SELECT warehouse, batch_no, SUM(actual_qty) AS qty
        FROM `tabStock Ledger Entry`
        WHERE item_code = %(item_code)s
          AND is_cancelled = 0
          AND IFNULL(serial_and_batch_bundle, '') = ''
          AND IFNULL(batch_no, '') != ''
        GROUP BY warehouse, batch_no
        """,
        {"item_code": item_code},
        as_dict=True,
    )
    bundle_rows = frappe.db.sql(
        """
        SELECT sle.warehouse AS warehouse, sbe.batch_no AS batch_no, SUM(sbe.qty) AS qty
        FROM `tabSerial and Batch Entry` sbe
        INNER JOIN `tabStock Ledger Entry` sle
          ON sle.serial_and_batch_bundle = sbe.parent
        WHERE sle.item_code = %(item_code)s
          AND sle.is_cancelled = 0
          AND sbe.docstatus = 1
          AND IFNULL(sbe.batch_no, '') != ''
        GROUP BY sle.warehouse, sbe.batch_no
        """,
        {"item_code": item_code},
        as_dict=True,
    )

    combined: dict[tuple[str, str], float] = {}
    for row in legacy_rows + bundle_rows:
        key = (row.warehouse, row.batch_no)
        combined[key] = flt(combined.get(key, 0.0) + flt(row.qty))

    result = [
        {
            "warehouse": wh,
            "batch_no": batch_no,
            "qty": flt(qty),
            "is_standard_batch": is_standard_kta_box_batch(batch_no),
        }
        for (wh, batch_no), qty in combined.items()
        if flt(qty) > _EPSILON
    ]
    result.sort(key=lambda r: (-r["qty"], r["batch_no"], r["warehouse"]))
    return result


def _lookup_item_stock(item_code: str) -> dict:
    """Return warehouse and batch balances for an Item."""
    item_meta = (
        frappe.db.get_value(
            "Item",
            item_code,
            ["item_name", "stock_uom", "has_batch_no"],
            as_dict=True,
        )
        or {}
    )
    bins = frappe.get_all(
        "Bin",
        filters={"item_code": item_code, "actual_qty": [">", 0]},
        fields=["warehouse", "actual_qty", "reserved_qty"],
        order_by="actual_qty desc, warehouse asc",
    )
    warehouses = [
        {
            "warehouse": b.warehouse,
            "qty": flt(b.actual_qty),
            "reserved_qty": flt(b.reserved_qty),
        }
        for b in bins
    ]
    batches = _get_item_batch_balances(item_code)
    total_qty = flt(sum(w["qty"] for w in warehouses))
    return {
        "kind": "item",
        "item_code": item_code,
        "item_name": item_meta.get("item_name"),
        "stock_uom": item_meta.get("stock_uom"),
        "has_batch_no": cint(item_meta.get("has_batch_no")),
        "total_qty": total_qty,
        "warehouses": warehouses,
        "batches": batches,
    }


@frappe.whitelist()
def pda_stock_lookup(barcode: str) -> dict:
    """Resolve any scanned barcode (box/batch, warehouse, or item) into stock balances."""
    _require_pda_screen_access("lookup")
    code = (barcode or "").strip()
    if not code:
        frappe.throw(_("Barkod boş olamaz."), frappe.ValidationError)

    label, batch_no, item_code = _resolve_box_label_and_batch(
        code, fallback_label_name=False
    )
    if batch_no and item_code:
        balances = get_batch_ledger_balances(item_code, batch_no)
        return _build_batch_scan_payload(
            label, batch_no, item_code, balances, kind="batch"
        )

    wh = _lookup_warehouse_record(code)
    if wh:
        return _lookup_warehouse_stock(wh)

    barcode_item = frappe.db.get_value("Item Barcode", {"barcode": code}, "parent")
    resolved_item = barcode_item or (code if frappe.db.exists("Item", code) else None)
    if resolved_item:
        return _lookup_item_stock(resolved_item)

    label, batch_no, item_code = _resolve_box_label_and_batch(
        code, fallback_label_name=True
    )
    if batch_no and item_code:
        balances = get_batch_ledger_balances(item_code, batch_no)
        return _build_batch_scan_payload(
            label, batch_no, item_code, balances, kind="batch"
        )

    frappe.throw(
        _("Barkod sistemde bulunamadı: {0}").format(code), frappe.ValidationError
    )


def _normalize_pda_lang(raw_lang: str | None) -> str:
    """Normalize a user/locale language string into tr, en, or de (default tr)."""
    cleaned = str(raw_lang or "").strip().lower().replace("_", "-")
    prefix = cleaned.split("-", 1)[0] if cleaned else ""
    if prefix in _PDA_SUPPORTED_LANGS:
        return prefix
    return "tr"


def _build_pda_translations_payload(user_or_lang: str | None = None) -> dict:
    """Build live translation payload (lang + message dict) for a user or language code."""
    if user_or_lang in _PDA_SUPPORTED_LANGS:
        resolved_lang = str(user_or_lang)
    elif (
        user_or_lang
        and user_or_lang != "Guest"
        and frappe.db.exists("User", user_or_lang)
    ):
        resolved_lang = _normalize_pda_lang(
            frappe.db.get_value("User", user_or_lang, "language")
        )
    else:
        resolved_lang = "tr"

    messages = dict(get_all_translations(resolved_lang) or {})
    return {"lang": resolved_lang, "messages": messages}


def _get_manageable_pda_operators(caller_user: str) -> list[dict]:
    """Return active PDA operators whose PIN the caller is authorized to reset."""
    caller_roles = set(frappe.get_roles(caller_user))
    if not caller_roles.intersection(_PDA_PIN_ADMIN_ROLES):
        return []

    is_sys_mgr = "System Manager" in caller_roles
    manageable: list[dict] = []
    for op in get_pda_operators():
        target_user = op.get("user_id")
        if not target_user or target_user == caller_user:
            continue
        if not is_sys_mgr and set(frappe.get_roles(target_user)).intersection(
            _PDA_PIN_ADMIN_ROLES
        ):
            continue
        manageable.append(op)
    return manageable


def _get_authorized_zebra_printers(user: str) -> list[dict]:
    """Return all KTA Zebra Printers that the given user is permitted to print to."""
    if not frappe.db.exists("DocType", "KTA Zebra Printers"):
        return []

    from kta_system_utils.kta_zebra_utils.printer_manager import ZebraPrinterManager

    rows = frappe.get_all(
        "KTA Zebra Printers",
        fields=["name", "printer_name", "ip", "port"],
        order_by="name asc",
    )
    return [
        {
            "name": row.name,
            "printer_name": row.printer_name or row.name,
            "ip": row.ip,
            "port": cint(row.port or 9100),
        }
        for row in rows
        if ZebraPrinterManager._user_can_print(user, row.name)
    ]


def _verify_account_password_with_rate_limit(
    user: str, account_password: str | None
) -> None:
    """Verify Frappe account password with 5-attempt / 300s lockout via cache."""
    pwd_fail_key = f"{_PDA_PWD_LOCKOUT_PREFIX}{user}"
    fail_count = cint(frappe.cache().get_value(pwd_fail_key, expires=True) or 0)
    if fail_count >= _PDA_PIN_MAX_FAILURES:
        frappe.throw(
            _(
                "Çok fazla hatalı hesap şifresi denemesi. Lütfen 5 dakika sonra tekrar deneyin."
            ),
            frappe.ValidationError,
        )

    raw_pwd = str(account_password or "")
    if not raw_pwd:
        frappe.throw(_("Hesap şifresi zorunludur."), frappe.ValidationError)

    try:
        check_password(user, raw_pwd)
    except frappe.AuthenticationError:
        new_count = fail_count + 1
        frappe.cache().set_value(
            pwd_fail_key, new_count, expires_in_sec=_PDA_PIN_LOCKOUT_SECONDS
        )
        if new_count >= _PDA_PIN_MAX_FAILURES:
            frappe.throw(
                _(
                    "Çok fazla hatalı hesap şifresi denemesi. Hesap 5 dakika süreyle kilitlendi."
                ),
                frappe.ValidationError,
            )
        remaining = _PDA_PIN_MAX_FAILURES - new_count
        frappe.throw(
            _("Hesap şifresi hatalı. Kalan deneme hakkı: {0}.").format(remaining),
            frappe.ValidationError,
        )

    frappe.cache().delete_value(pwd_fail_key)


@frappe.whitelist()
def pda_get_settings_data() -> dict:
    """Return self-service settings payload, Zebra printers, and RBAC-filtered operators."""
    user = _require_pda_operator()
    emp = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name", "department"],
        as_dict=True,
    )

    prefs = None
    if frappe.db.exists("DocType", "KTA User Zebra Printers"):
        prefs = frappe.db.get_value(
            "KTA User Zebra Printers",
            user,
            ["printer", "fallback_printer", "disabled"],
            as_dict=True,
        )
    if not prefs or cint(prefs.disabled) == 1:
        printer_preferences = {
            "printer": None,
            "fallback_printer": None,
            "disabled": 1,
        }
    else:
        printer_preferences = {
            "printer": prefs.printer or None,
            "fallback_printer": prefs.fallback_printer or None,
            "disabled": 0,
        }

    return {
        "has_employee": bool(emp),
        "employee": emp.name if emp else None,
        "employee_name": emp.employee_name if emp else None,
        "department": emp.department if emp else None,
        "has_pin": _employee_has_pda_pin(emp.name) if emp else False,
        "can_manage_operator_pins": bool(
            set(frappe.get_roles(user)) & _PDA_PIN_ADMIN_ROLES
        ),
        "authorized_printers": _get_authorized_zebra_printers(user),
        "printer_preferences": printer_preferences,
        "user_language": _normalize_pda_lang(
            frappe.db.get_value("User", user, "language")
        ),
        "manageable_operators": _get_manageable_pda_operators(user),
    }


@frappe.whitelist(methods=["POST"])
def pda_update_own_pin(
    new_pin: str,
    confirm_pin: str,
    mode: str = "initial",
    current_pin: str | None = None,
    account_password: str | None = None,
) -> dict:
    """Allow an authorized operator to set or update their own 4-digit PIN without Employee.save()."""
    user = _require_pda_operator()
    emp = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name"],
        as_dict=True,
    )
    if not emp:
        frappe.throw(
            _("Bu kullanıcıya bağlı aktif personel kaydı bulunamadı."),
            frappe.ValidationError,
        )

    clean_new = str(new_pin or "").strip()
    clean_confirm = str(confirm_pin or "").strip()
    if not _PDA_PIN_RE.fullmatch(clean_new):
        frappe.throw(
            _("PIN kodu tam olarak 4 sayısal rakamdan oluşmalıdır."),
            frappe.ValidationError,
        )
    if clean_new != clean_confirm:
        frappe.throw(
            _("Yeni PIN kodları birbiriyle eşleşmiyor."),
            frappe.ValidationError,
        )

    if _employee_has_pda_pin(emp.name):
        clean_mode = str(mode or "").strip()
        if clean_mode == "current_pin":
            clean_current = str(current_pin or "").strip()
            if not _PDA_PIN_RE.fullmatch(clean_current):
                frappe.throw(
                    _("PIN kodu tam olarak 4 sayısal rakamdan oluşmalıdır."),
                    frappe.ValidationError,
                )
            _verify_pin_with_rate_limit(emp.name, clean_current)
        elif clean_mode == "account_password":
            _verify_account_password_with_rate_limit(user, account_password)
        else:
            frappe.throw(
                _("Mevcut PIN veya hesap şifresi doğrulaması zorunludur."),
                frappe.ValidationError,
            )

    set_encrypted_password("Employee", emp.name, clean_new, fieldname="custom_pda_pin")
    frappe.cache().delete_value(f"pda_pin_fail:{emp.name}")
    return {"ok": True, "employee": emp.name, "has_pin": True}


@frappe.whitelist(methods=["POST"])
def pda_admin_reset_operator_pin(
    target_employee: str,
    new_pin: str,
    confirm_pin: str,
) -> dict:
    """Allow Stock/System Managers to reset subordinate operators' PINs under strict RBAC."""
    caller = _require_pda_operator()
    caller_roles = set(frappe.get_roles(caller))
    if not caller_roles.intersection(_PDA_PIN_ADMIN_ROLES):
        frappe.throw(
            _("Operatör PIN sıfırlama yetkiniz bulunmamaktadır."),
            frappe.PermissionError,
        )

    clean_target = str(target_employee or "").strip()
    if not clean_target:
        frappe.throw(_("Personel seçimi zorunludur."), frappe.ValidationError)

    emp = _validate_pda_operator_record(clean_target)
    if emp.user_id == caller:
        frappe.throw(
            _("Kendi PIN kodunuzu yönetici sıfırlamasıyla değiştiremezsiniz."),
            frappe.PermissionError,
        )
    if "System Manager" not in caller_roles and set(
        frappe.get_roles(emp.user_id)
    ).intersection(_PDA_PIN_ADMIN_ROLES):
        frappe.throw(
            _("Bu operatörün PIN kodunu sıfırlama yetkiniz bulunmamaktadır."),
            frappe.PermissionError,
        )

    clean_new = str(new_pin or "").strip()
    clean_confirm = str(confirm_pin or "").strip()
    if not _PDA_PIN_RE.fullmatch(clean_new):
        frappe.throw(
            _("PIN kodu tam olarak 4 sayısal rakamdan oluşmalıdır."),
            frappe.ValidationError,
        )
    if clean_new != clean_confirm:
        frappe.throw(
            _("Yeni PIN kodları birbiriyle eşleşmiyor."),
            frappe.ValidationError,
        )

    set_encrypted_password("Employee", emp.name, clean_new, fieldname="custom_pda_pin")
    frappe.cache().delete_value(f"pda_pin_fail:{emp.name}")
    frappe.cache().delete_value(f"{_PDA_PWD_LOCKOUT_PREFIX}{emp.user_id}")
    return {
        "ok": True,
        "employee": emp.name,
        "employee_name": emp.employee_name,
        "has_pin": True,
    }


@frappe.whitelist(methods=["POST"])
def pda_save_printer_preferences(
    printer: str | None = None,
    fallback_printer: str | None = None,
) -> dict:
    """Save or clear the current user's default and fallback Zebra printer preferences."""
    user = _require_pda_operator()
    p1 = (printer or "").strip() or None
    p2 = (fallback_printer or "").strip() or None
    if p1 and p2 and p1 == p2:
        frappe.throw(
            _("Varsayılan ve yedek yazıcı aynı olamaz."),
            frappe.ValidationError,
        )

    from kta_system_utils.kta_zebra_utils.printer_manager import ZebraPrinterManager

    for p_name in (p for p in (p1, p2) if p):
        if not frappe.db.exists("KTA Zebra Printers", p_name):
            frappe.throw(
                _("Zebra yazıcı bulunamadı: {0}").format(p_name),
                frappe.ValidationError,
            )
        if not ZebraPrinterManager._user_can_print(user, p_name):
            frappe.throw(
                _("Seçilen yazıcı için yazdırma yetkiniz yok: {0}").format(p_name),
                frappe.PermissionError,
            )

    disabled = 0 if (p1 or p2) else 1
    if frappe.db.exists("KTA User Zebra Printers", user):
        pref_doc = frappe.get_doc("KTA User Zebra Printers", user)
        pref_doc.printer = p1
        pref_doc.fallback_printer = p2
        pref_doc.disabled = disabled
        pref_doc.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "KTA User Zebra Printers",
                "user": user,
                "printer": p1,
                "fallback_printer": p2,
                "disabled": disabled,
            }
        ).insert(ignore_permissions=True)

    return {
        "ok": True,
        "printer": p1,
        "fallback_printer": p2,
        "disabled": disabled,
    }


@frappe.whitelist(methods=["POST"])
def pda_test_printer_connection(printer_name: str) -> dict:
    """Check Zebra printer connection status without dispatching any print job or log."""
    user = _require_pda_operator()
    clean_name = (printer_name or "").strip()
    if not clean_name or not frappe.db.exists("KTA Zebra Printers", clean_name):
        frappe.throw(
            _("Zebra yazıcı bulunamadı: {0}").format(clean_name),
            frappe.ValidationError,
        )

    from kta_system_utils.kta_zebra_utils.printer_manager import ZebraPrinterManager

    if not ZebraPrinterManager._user_can_print(user, clean_name):
        frappe.throw(
            _("Seçilen yazıcı için yazdırma yetkiniz yok: {0}").format(clean_name),
            frappe.PermissionError,
        )

    status_info = ZebraPrinterManager().check_printer_status(clean_name) or {}
    status_text = str(status_info.get("status") or "")
    online = bool(
        status_info.get("color") == "green"
        or status_text.lower() in ("ready", "online", "ok", "connected")
    )
    return {
        "ok": True,
        "printer": clean_name,
        "online": online,
        "status": status_text or "Error",
        "message": str(status_info.get("message") or ""),
    }


@frappe.whitelist(methods=["POST"])
def pda_update_user_language(language: str) -> dict:
    """Update the active user's User.language and return fresh translation dict for 0ms UI swap."""
    user = _require_pda_operator()
    clean_lang = str(language or "").strip().lower()
    if clean_lang not in _PDA_SUPPORTED_LANGS:
        frappe.throw(
            _("Desteklenmeyen dil seçimi: {0}").format(clean_lang),
            frappe.ValidationError,
        )

    frappe.db.set_value("User", user, "language", clean_lang)
    frappe.clear_cache(user=user)
    trans_payload = _build_pda_translations_payload(clean_lang)
    frappe.local.lang = trans_payload["lang"]
    return {"ok": True, **trans_payload}
