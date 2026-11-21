# Copyright (c) 2026, KTA and Contributors
# See license.txt

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate, today

from erpnextkta.kta_stock.label_manager import enqueue_print_labels_by_names
from erpnextkta.kta_stock.services.relabeling_service import (
    create_package_split_repack,
    get_batch_ledger_balances,
    is_standard_kta_box_batch,
    upsert_box_label,
)

FORBIDDEN_WAREHOUSE_KEYWORDS = (
    "hammadde",
    "raw material",
    "tesellum",
    "tesellüm",
    "giriş",
    "giris",
    "ana depo",
    "central",
    "stores",
)

ALLOWED_PRODUCTION_KEYWORDS = (
    "üretim",
    "uretim",
    "production",
    "wip",
    "work in progress",
)


def _normalize_warehouse_text(value: str | None) -> str:
    """Normalize Turkish and ASCII strings to lowercase without combining dot artifacts."""
    if not value:
        return ""
    return str(value).replace("İ", "i").lower().replace("\u0307", "")


def _contains_any_keyword(
    texts: tuple[str | None, ...], keywords: tuple[str, ...]
) -> bool:
    """Return True if any normalized text contains any keyword."""
    normalized = [_normalize_warehouse_text(t) for t in texts if t]
    return any(kw in text for text in normalized for kw in keywords)


def _dt_sort_str(value) -> str:
    """Format date/datetime consistently for deterministic descending LIFO comparisons."""
    if not value:
        return ""
    dt = get_datetime(value)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f") if dt else str(value)


def _has_forbidden_ancestor(wh_data: dict) -> bool:
    """Return True if any NestedSet ancestor group warehouse carries a forbidden keyword."""
    lft = cint(wh_data.get("lft") or 0)
    rgt = cint(wh_data.get("rgt") or 0)
    if lft <= 0 or rgt <= 0:
        return False

    ancestors = frappe.get_all(
        "Warehouse",
        filters={
            "is_group": 1,
            "lft": ["<", lft],
            "rgt": [">", rgt],
        },
        fields=["name", "warehouse_name"],
    )
    for anc in ancestors:
        if _contains_any_keyword(
            (anc.get("name"), anc.get("warehouse_name")),
            FORBIDDEN_WAREHOUSE_KEYWORDS,
        ):
            return True
    return False


def _is_under_150_production_tree(wh_data: dict) -> bool:
    """Return True if warehouse sits inside a 150 ÜRETİM / 150 URETIM NestedSet subtree."""
    lft = cint(wh_data.get("lft") or 0)
    rgt = cint(wh_data.get("rgt") or 0)
    if lft <= 0 or rgt <= 0:
        return False

    groups = frappe.get_all(
        "Warehouse",
        filters={"is_group": 1, "disabled": 0},
        fields=["name", "warehouse_name", "lft", "rgt"],
    )
    for grp in groups:
        if not _contains_any_keyword(
            (grp.get("name"), grp.get("warehouse_name")),
            ("150 üretim", "150 uretim"),
        ):
            continue
        g_lft = cint(grp.get("lft") or 0)
        g_rgt = cint(grp.get("rgt") or 0)
        if g_lft > 0 and g_rgt >= rgt and g_lft <= lft:
            return True
    return False


def is_valid_production_warehouse(
    warehouse: str | None,
    peer_warehouse: str | None = None,
) -> bool:
    """Validate whether a warehouse is an active leaf production/line warehouse."""
    if not warehouse or not str(warehouse).strip():
        return False

    wh_name = str(warehouse).strip()
    wh_data = frappe.db.get_value(
        "Warehouse",
        wh_name,
        [
            "name",
            "warehouse_name",
            "parent_warehouse",
            "is_group",
            "disabled",
            "lft",
            "rgt",
        ],
        as_dict=True,
    )
    if not wh_data or cint(wh_data.is_group) == 1 or cint(wh_data.disabled) == 1:
        return False

    if _contains_any_keyword(
        (wh_data.name, wh_data.warehouse_name, wh_data.parent_warehouse),
        FORBIDDEN_WAREHOUSE_KEYWORDS,
    ):
        return False

    if _has_forbidden_ancestor(wh_data):
        return False

    if _is_under_150_production_tree(wh_data):
        return True

    if _contains_any_keyword(
        (wh_data.name, wh_data.warehouse_name, wh_data.parent_warehouse),
        ALLOWED_PRODUCTION_KEYWORDS,
    ):
        return True

    if peer_warehouse and str(peer_warehouse).strip():
        peer_parent = frappe.db.get_value(
            "Warehouse", str(peer_warehouse).strip(), "parent_warehouse"
        )
        parent_wh = wh_data.parent_warehouse
        if (
            parent_wh
            and peer_parent
            and parent_wh == peer_parent
            and not _normalize_warehouse_text(parent_wh).startswith("all warehouses")
        ):
            return True

    return False


def _resolve_target_company(company: str | None = None) -> str | None:
    """Resolve active company, skipping _Test% companies outside test mode."""
    if company and str(company).strip():
        return str(company).strip()

    resolved = (
        frappe.defaults.get_user_default("Company")
        or frappe.defaults.get_user_default("company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )
    if not frappe.flags.in_test and (not resolved or str(resolved).startswith("_Test")):
        real_company = frappe.db.get_value(
            "Company",
            {"name": ["not like", "_Test%"], "is_group": 0},
            "name",
        )
        if real_company:
            return real_company

    if not resolved:
        resolved = frappe.db.get_value("Company", {"is_group": 0}, "name")

    return resolved


def _clean_warehouse_label(wh_row: dict, abbr: str | None) -> str:
    """Strip trailing company abbreviation from warehouse display label."""
    raw_label = wh_row.get("warehouse_name") or wh_row.get("name") or ""
    suffix = f" - {abbr}" if abbr else ""
    if suffix and raw_label.endswith(suffix):
        return raw_label[: -len(suffix)]
    return raw_label


def _is_production_warehouse_row(
    wh_data: dict,
    group_warehouses: list[dict],
) -> bool:
    """Fast production warehouse check using preloaded group warehouses."""
    if (
        not wh_data
        or cint(wh_data.get("is_group")) == 1
        or cint(wh_data.get("disabled")) == 1
    ):
        return False

    if _contains_any_keyword(
        (
            wh_data.get("name"),
            wh_data.get("warehouse_name"),
            wh_data.get("parent_warehouse"),
        ),
        FORBIDDEN_WAREHOUSE_KEYWORDS,
    ):
        return False

    lft = cint(wh_data.get("lft") or 0)
    rgt = cint(wh_data.get("rgt") or 0)
    if lft > 0 and rgt > 0:
        for grp in group_warehouses:
            g_lft = cint(grp.get("lft") or 0)
            g_rgt = cint(grp.get("rgt") or 0)
            if (
                g_lft < lft
                and g_rgt > rgt
                and _contains_any_keyword(
                    (grp.get("name"), grp.get("warehouse_name")),
                    FORBIDDEN_WAREHOUSE_KEYWORDS,
                )
            ):
                return False

        for grp in group_warehouses:
            g_lft = cint(grp.get("lft") or 0)
            g_rgt = cint(grp.get("rgt") or 0)
            if (
                g_lft > 0
                and g_lft <= lft
                and g_rgt >= rgt
                and _contains_any_keyword(
                    (grp.get("name"), grp.get("warehouse_name")),
                    ("150 üretim", "150 uretim"),
                )
            ):
                return True

    return _contains_any_keyword(
        (
            wh_data.get("name"),
            wh_data.get("warehouse_name"),
            wh_data.get("parent_warehouse"),
        ),
        ALLOWED_PRODUCTION_KEYWORDS,
    )


def _get_mrp_settings_return_roots(company: str | None = None) -> list[dict]:
    """Resolve configured central raw material warehouse roots from KTA MRP Settings if present."""
    if not frappe.db.exists("DocType", "KTA MRP Settings"):
        return []

    meta = frappe.get_meta("KTA MRP Settings")
    has_rejected_col = frappe.db.has_column("Warehouse", "is_rejected_warehouse")
    fields = ["name", "warehouse_name", "company", "is_group", "disabled", "lft", "rgt"]
    if has_rejected_col:
        fields.append("is_rejected_warehouse")

    roots: list[dict] = []
    for fieldname in (
        "central_warehouse",
        "raw_material_warehouse",
        "default_raw_material_warehouse",
    ):
        if not meta.has_field(fieldname):
            continue
        wh_name = frappe.db.get_single_value("KTA MRP Settings", fieldname)
        if not wh_name or not frappe.db.exists("Warehouse", wh_name):
            continue
        wh_row = frappe.db.get_value("Warehouse", wh_name, fields, as_dict=True)
        if not wh_row or cint(wh_row.get("disabled")) == 1:
            continue
        if company and wh_row.get("company") and wh_row.get("company") != company:
            continue
        roots.append(wh_row)
    return roots


def _get_raw_material_return_roots(company: str | None = None) -> list[dict]:
    """Find 110 HAMMADDE / 110 Raw Material root nodes for the given company."""
    roots = _get_mrp_settings_return_roots(company)
    wh_filters: dict = {"is_group": 1, "disabled": 0}
    if company:
        wh_filters["company"] = company

    group_candidates = frappe.get_all(
        "Warehouse",
        filters=wh_filters,
        fields=["name", "warehouse_name", "company", "is_group", "lft", "rgt"],
    )
    seen = {r.get("name") for r in roots}
    for grp in group_candidates:
        if grp.name in seen:
            continue
        if _contains_any_keyword(
            (grp.get("name"), grp.get("warehouse_name")),
            ("110 hammadde", "110 raw material"),
        ):
            roots.append(grp)
            seen.add(grp.name)

    if roots:
        return roots

    leaf_filters: dict = {"is_group": 0, "disabled": 0}
    if company:
        leaf_filters["company"] = company
    for leaf in frappe.get_all(
        "Warehouse",
        filters=leaf_filters,
        fields=["name", "warehouse_name", "company", "is_group", "lft", "rgt"],
    ):
        if _contains_any_keyword(
            (leaf.get("name"), leaf.get("warehouse_name")),
            ("110 hammadde", "110 raw material"),
        ):
            roots.append(leaf)

    return roots


def _warehouse_in_roots(wh_data: dict, roots: list[dict]) -> bool:
    """Return True if wh_data is one of roots or sits inside a root NestedSet subtree."""
    wh_lft = cint(wh_data.get("lft") or 0)
    wh_rgt = cint(wh_data.get("rgt") or 0)
    wh_name = wh_data.get("name")
    for root in roots:
        r_lft = cint(root.get("lft") or 0)
        r_rgt = cint(root.get("rgt") or 0)
        if r_lft > 0 and r_rgt > 0 and wh_lft > 0 and wh_rgt > 0:
            if r_lft <= wh_lft and wh_rgt <= r_rgt:
                return True
        elif wh_name and wh_name == root.get("name"):
            return True
    return False


def is_valid_raw_material_return_warehouse(
    warehouse: str | None,
    company: str | None = None,
) -> bool:
    """Validate whether a warehouse is an active non-rejected leaf shelf under 110 HAMMADDE."""
    if not warehouse or not str(warehouse).strip():
        return False

    wh_name = str(warehouse).strip()
    has_rejected_col = frappe.db.has_column("Warehouse", "is_rejected_warehouse")
    fields = [
        "name",
        "warehouse_name",
        "parent_warehouse",
        "company",
        "is_group",
        "disabled",
        "lft",
        "rgt",
    ]
    if has_rejected_col:
        fields.append("is_rejected_warehouse")

    wh_data = frappe.db.get_value("Warehouse", wh_name, fields, as_dict=True)
    if (
        not wh_data
        or cint(wh_data.get("is_group")) == 1
        or cint(wh_data.get("disabled")) == 1
        or cint(wh_data.get("is_rejected_warehouse") or 0) == 1
    ):
        return False

    if company and wh_data.get("company") and wh_data.get("company") != company:
        return False

    if is_valid_production_warehouse(wh_data.name):
        return False

    effective_company = (
        company or wh_data.get("company") or _resolve_target_company(None)
    )
    roots = _get_raw_material_return_roots(effective_company)
    return _warehouse_in_roots(wh_data, roots)


def get_raw_material_return_warehouses(company: str | None = None) -> list[dict]:
    """List active non-rejected leaf shelves under 110 HAMMADDE for production supply return."""
    target_company = _resolve_target_company(company)
    if not target_company:
        return []

    roots = _get_raw_material_return_roots(target_company)
    if not roots:
        return []

    abbr = frappe.db.get_value("Company", target_company, "abbr")
    has_rejected_col = frappe.db.has_column("Warehouse", "is_rejected_warehouse")
    leaf_filters: dict = {
        "company": target_company,
        "is_group": 0,
        "disabled": 0,
    }
    if has_rejected_col:
        leaf_filters["is_rejected_warehouse"] = 0

    fields = [
        "name",
        "warehouse_name",
        "parent_warehouse",
        "is_group",
        "disabled",
        "lft",
        "rgt",
    ]
    if has_rejected_col:
        fields.append("is_rejected_warehouse")

    leaf_warehouses = frappe.get_all(
        "Warehouse",
        filters=leaf_filters,
        fields=fields,
        order_by="name asc",
    )
    group_warehouses = frappe.get_all(
        "Warehouse",
        filters={"is_group": 1, "disabled": 0},
        fields=["name", "warehouse_name", "lft", "rgt"],
    )

    result = []
    for w in leaf_warehouses:
        if cint(w.get("is_rejected_warehouse") or 0) == 1:
            continue
        if not _warehouse_in_roots(w, roots):
            continue
        if _is_production_warehouse_row(w, group_warehouses):
            continue
        result.append(
            {
                "warehouse": w.name,
                "label": _clean_warehouse_label(w, abbr),
            }
        )
    return result


def get_production_warehouses(company: str | None = None) -> list[dict]:
    """List active leaf production warehouses for the resolved company."""
    target_company = _resolve_target_company(company)
    if not target_company:
        return []

    abbr = frappe.db.get_value("Company", target_company, "abbr")
    warehouses = frappe.get_all(
        "Warehouse",
        filters={"company": target_company, "is_group": 0, "disabled": 0},
        fields=["name", "warehouse_name"],
        order_by="name asc",
    )

    result = []
    for w in warehouses:
        if is_valid_production_warehouse(w.name):
            result.append(
                {
                    "warehouse": w.name,
                    "label": _clean_warehouse_label(w, abbr),
                }
            )
    return result


def _query_warehouse_batch_balances(item_code: str, warehouse: str) -> list[dict]:
    """Query positive batch balances and latest inward timestamps from SLE and SBE."""
    return frappe.db.sql(
        """
        SELECT
            batch_no,
            SUM(qty) AS qty,
            MAX(CASE WHEN qty > 0 THEN posting_dt ELSE NULL END) AS last_inward_posting_datetime,
            MAX(CASE WHEN qty > 0 THEN sle_creation ELSE NULL END) AS last_inward_creation
        FROM (
            SELECT
                sle.batch_no AS batch_no,
                sle.actual_qty AS qty,
                COALESCE(
                    sle.posting_datetime,
                    TIMESTAMP(sle.posting_date, COALESCE(sle.posting_time, '00:00:00'))
                ) AS posting_dt,
                sle.creation AS sle_creation
            FROM `tabStock Ledger Entry` sle
            WHERE sle.item_code = %(item_code)s
              AND sle.warehouse = %(warehouse)s
              AND sle.is_cancelled = 0
              AND sle.batch_no IS NOT NULL
              AND sle.batch_no != ''
              AND (sle.serial_and_batch_bundle IS NULL OR sle.serial_and_batch_bundle = '')

            UNION ALL

            SELECT
                sbe.batch_no AS batch_no,
                sbe.qty AS qty,
                COALESCE(
                    sle.posting_datetime,
                    TIMESTAMP(sle.posting_date, COALESCE(sle.posting_time, '00:00:00'))
                ) AS posting_dt,
                sle.creation AS sle_creation
            FROM `tabStock Ledger Entry` sle
            INNER JOIN `tabSerial and Batch Entry` sbe
                ON sbe.parent = sle.serial_and_batch_bundle
            WHERE sle.item_code = %(item_code)s
              AND COALESCE(NULLIF(sbe.warehouse, ''), sle.warehouse) = %(warehouse)s
              AND sle.is_cancelled = 0
              AND sle.serial_and_batch_bundle IS NOT NULL
              AND sle.serial_and_batch_bundle != ''
              AND sbe.batch_no IS NOT NULL
              AND sbe.batch_no != ''
        ) AS combined
        GROUP BY batch_no
        HAVING SUM(qty) > 0
        """,
        {"item_code": item_code, "warehouse": warehouse},
        as_dict=True,
    )


def _fallback_get_batch_qty(item_code: str, warehouse: str) -> list[dict]:
    """Fallback to ERPNext get_batch_qty when direct ledger query yields no rows."""
    try:
        from erpnext.stock.doctype.batch.batch import get_batch_qty

        raw = get_batch_qty(item_code=item_code, warehouse=warehouse) or []
    except Exception:  # noqa: BLE001
        return []

    rows = []
    for entry in raw:
        b_no = entry.get("batch_no")
        qty = flt(entry.get("qty") or 0)
        if b_no and qty > 0:
            rows.append(
                {
                    "batch_no": b_no,
                    "qty": qty,
                    "last_inward_posting_datetime": None,
                    "last_inward_creation": None,
                }
            )
    return rows


def _filter_and_sort_lifo_candidates(
    raw_batches: list[dict],
    prior_consumed: dict[str, float] | None = None,
) -> list[dict]:
    """Filter active, unexpired batches and sort by LIFO (newest inward first)."""
    if not raw_batches:
        return []

    batch_nos = list({r["batch_no"] for r in raw_batches if r.get("batch_no")})
    if not batch_nos:
        return []

    batch_records = frappe.get_all(
        "Batch",
        filters={"name": ["in", batch_nos], "disabled": 0},
        fields=["name", "expiry_date", "creation"],
    )
    batch_meta = {b.name: b for b in batch_records}
    today_date = getdate(today())
    consumed_map = prior_consumed or {}

    candidates = []
    for row in raw_batches:
        b_no = row.get("batch_no")
        meta = batch_meta.get(b_no)
        if not meta:
            continue
        expiry_date = meta.get("expiry_date")
        if expiry_date and getdate(expiry_date) < today_date:
            continue

        avail_qty = flt(flt(row.get("qty") or 0) - flt(consumed_map.get(b_no, 0.0)), 4)
        if avail_qty <= 0:
            continue

        candidates.append(
            {
                "batch_no": b_no,
                "qty": avail_qty,
                "last_inward_posting_datetime": row.get("last_inward_posting_datetime"),
                "last_inward_creation": row.get("last_inward_creation"),
                "batch_creation": meta.get("creation"),
            }
        )

    candidates.sort(
        key=lambda c: (
            _dt_sort_str(c.get("last_inward_posting_datetime")),
            _dt_sort_str(c.get("last_inward_creation")),
            _dt_sort_str(c.get("batch_creation")),
            c.get("batch_no") or "",
        ),
        reverse=True,
    )
    return candidates


def _allocate_lifo_from_candidates(
    item_code: str,
    warehouse: str,
    req_qty: float,
    candidates: list[dict],
) -> list[dict]:
    """Split required_qty across sorted LIFO batch candidates without spool rounding."""
    total_avail = flt(sum(flt(c["qty"]) for c in candidates), 4)
    if total_avail < req_qty:
        frappe.throw(
            _(
                "Kaynak depoda ({0}) {1} için yeterli geçerli parti stoğu bulunamadı. Mevcut: {2}, İstenen: {3}"
            ).format(warehouse, item_code, total_avail, req_qty),
            frappe.ValidationError,
        )

    allocations: list[dict] = []
    remaining = req_qty
    for cand in candidates:
        if remaining <= 0:
            break
        avail_qty = flt(cand["qty"], 4)
        if avail_qty <= 0:
            continue
        take_qty = flt(min(avail_qty, remaining), 4)
        if take_qty <= 0:
            continue
        allocations.append({"batch_no": cand["batch_no"], "qty": take_qty})
        remaining = flt(remaining - take_qty, 4)

    if remaining > 0:
        frappe.throw(
            _(
                "Kaynak depoda ({0}) {1} için yeterli geçerli parti stoğu bulunamadı. Mevcut: {2}, İstenen: {3}"
            ).format(warehouse, item_code, total_avail, req_qty),
            frappe.ValidationError,
        )

    return allocations


def resolve_lifo_batches(
    item_code: str,
    warehouse: str,
    required_qty: float,
    _prior_consumed: dict[str, float] | None = None,
) -> list[dict]:
    """Resolve batch breakdown in LIFO order (latest inward batch first) without spool rounding."""
    req_qty = flt(required_qty, 4)
    if req_qty <= 0:
        frappe.throw(
            _("Transfer miktarı sıfırdan büyük olmalıdır."),
            frappe.ValidationError,
        )

    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(
            _("Geçerli bir malzeme kodu zorunludur: {0}").format(item_code),
            frappe.ValidationError,
        )

    if not warehouse or not frappe.db.exists("Warehouse", warehouse):
        frappe.throw(
            _("Geçerli bir kaynak depo zorunludur: {0}").format(warehouse),
            frappe.ValidationError,
        )

    has_batch_no = cint(frappe.db.get_value("Item", item_code, "has_batch_no") or 0)
    if not has_batch_no:
        return [{"batch_no": None, "qty": req_qty}]

    raw_batches = _query_warehouse_batch_balances(item_code, warehouse)
    if not raw_batches:
        raw_batches = _fallback_get_batch_qty(item_code, warehouse)

    candidates = _filter_and_sort_lifo_candidates(
        raw_batches, prior_consumed=_prior_consumed
    )
    return _allocate_lifo_from_candidates(item_code, warehouse, req_qty, candidates)


def get_sibling_production_sources(
    item_code: str,
    company: str | None,
    exclude_warehouse: str | None,
) -> list[dict]:
    """Return sibling production warehouse stock levels sorted by free_qty desc, actual_qty desc."""
    if not item_code or not company:
        return []

    rows = frappe.db.sql(
        """
        SELECT b.warehouse, b.actual_qty, b.reserved_qty_for_production
        FROM `tabBin` b
        INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
        WHERE b.item_code = %s
          AND w.company = %s
          AND w.name != %s
          AND w.is_group = 0
          AND w.disabled = 0
          AND b.actual_qty > 0
        """,
        (item_code, company, exclude_warehouse or ""),
        as_dict=True,
    )

    sources = []
    for row in rows:
        if not is_valid_production_warehouse(row.warehouse, exclude_warehouse):
            continue
        actual_qty = flt(row.actual_qty or 0, 4)
        reserved_qty = flt(row.reserved_qty_for_production or 0, 4)
        free_qty = flt(max(0.0, actual_qty - reserved_qty), 4)
        sources.append(
            {
                "warehouse": row.warehouse,
                "actual_qty": actual_qty,
                "reserved_qty": reserved_qty,
                "free_qty": free_qty,
                "available_qty": free_qty,
            }
        )

    sources.sort(key=lambda s: (-s["free_qty"], -s["actual_qty"], s["warehouse"]))
    return sources


def _validate_production_warehouse_or_throw(warehouse: str | None) -> str:
    """Validate warehouse is a valid active production warehouse or throw ValidationError."""
    wh = str(warehouse or "").strip()
    if not is_valid_production_warehouse(wh):
        frappe.throw(
            _(
                "Geçerli bir üretim/hat deposu seçilmelidir (hammadde veya grup depoları seçilemez): {0}"
            ).format(warehouse or ""),
            frappe.ValidationError,
        )
    return wh


def _fetch_items_metadata(item_codes: list[str]) -> dict[str, dict]:
    """Fetch item_name and stock_uom for a list of item codes."""
    if not item_codes:
        return {}
    return {
        d.name: d
        for d in frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=["name", "item_name", "stock_uom"],
        )
    }


def _fetch_sibling_bins_by_item(
    item_codes: list[str],
    company: str,
    target_wh: str,
) -> dict[str, list[dict]]:
    """Query positive Bin stock across valid sibling production warehouses for items."""
    if not item_codes or not company:
        return {}

    rows = frappe.db.sql(
        """
        SELECT b.item_code, b.warehouse, b.actual_qty, b.reserved_qty_for_production
        FROM `tabBin` b
        INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
        WHERE b.item_code IN %(item_codes)s
          AND w.company = %(company)s
          AND w.name != %(target_wh)s
          AND w.is_group = 0
          AND w.disabled = 0
          AND b.actual_qty > 0
        """,
        {"item_codes": tuple(item_codes), "company": company, "target_wh": target_wh},
        as_dict=True,
    )

    validity_cache: dict[str, bool] = {}
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        wh = row.warehouse
        if wh not in validity_cache:
            validity_cache[wh] = is_valid_production_warehouse(wh, target_wh)
        if not validity_cache[wh]:
            continue

        actual_qty = flt(row.actual_qty or 0, 4)
        reserved_qty = flt(row.reserved_qty_for_production or 0, 4)
        free_qty = flt(max(0.0, actual_qty - reserved_qty), 4)
        grouped.setdefault(row.item_code, []).append(
            {
                "warehouse": wh,
                "actual_qty": actual_qty,
                "reserved_qty": reserved_qty,
                "free_qty": free_qty,
                "available_qty": free_qty,
            }
        )

    for sources in grouped.values():
        sources.sort(key=lambda s: (-s["free_qty"], -s["actual_qty"], s["warehouse"]))

    return grouped


def get_line_transfer_deficits(target_warehouse: str) -> list[dict]:
    """Mode 1 (Deficit Fulfillment): find line deficits coverable from sibling production lines."""
    target_wh = _validate_production_warehouse_or_throw(target_warehouse)

    deficit_rows = frappe.db.sql(
        """
        SELECT item_code, stock_uom, actual_qty, reserved_qty_for_production
        FROM `tabBin`
        WHERE warehouse = %s
          AND reserved_qty_for_production > actual_qty
        ORDER BY item_code ASC
        """,
        (target_wh,),
        as_dict=True,
    )
    if not deficit_rows:
        return []

    company = frappe.db.get_value("Warehouse", target_wh, "company")
    item_codes = list({r["item_code"] for r in deficit_rows if r.get("item_code")})
    items_meta = _fetch_items_metadata(item_codes)
    sibling_sources_map = _fetch_sibling_bins_by_item(item_codes, company, target_wh)

    results = []
    for row in deficit_rows:
        item_code = row.get("item_code")
        sources = sibling_sources_map.get(item_code) or []
        if not sources:
            continue

        line_actual_qty = flt(row.get("actual_qty") or 0, 4)
        reserved_qty = flt(row.get("reserved_qty_for_production") or 0, 4)
        deficit_qty = flt(reserved_qty - line_actual_qty, 4)
        if deficit_qty <= 0:
            continue

        meta = items_meta.get(item_code)
        item_name = meta.item_name if meta else item_code
        uom = row.get("stock_uom") or (meta.stock_uom if meta else "")

        best = sources[0]
        uses_reserved_stock = best["free_qty"] <= 0
        default_selected = not uses_reserved_stock
        source_cap = best["free_qty"] if not uses_reserved_stock else best["actual_qty"]
        suggested_qty = flt(min(deficit_qty, source_cap), 4)

        results.append(
            {
                "item_code": item_code,
                "item_name": item_name,
                "uom": uom,
                "target_warehouse": target_wh,
                "line_actual_qty": line_actual_qty,
                "reserved_qty": reserved_qty,
                "deficit_qty": deficit_qty,
                "suggested_source_warehouse": best["warehouse"],
                "suggested_qty": suggested_qty,
                "uses_reserved_stock": uses_reserved_stock,
                "default_selected": default_selected,
                "available_sources": sources,
            }
        )

    return results


def _fetch_sibling_deficits_by_item(
    item_codes: list[str],
    company: str,
    source_wh: str,
) -> dict[str, dict]:
    """Find highest-deficit sibling production warehouse for each item_code."""
    if not item_codes or not company:
        return {}

    rows = frappe.db.sql(
        """
        SELECT
            b.item_code,
            b.warehouse,
            (b.reserved_qty_for_production - b.actual_qty) AS deficit_qty
        FROM `tabBin` b
        INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
        WHERE b.item_code IN %(item_codes)s
          AND w.company = %(company)s
          AND w.name != %(source_wh)s
          AND w.is_group = 0
          AND w.disabled = 0
          AND b.reserved_qty_for_production > b.actual_qty
        """,
        {"item_codes": tuple(item_codes), "company": company, "source_wh": source_wh},
        as_dict=True,
    )

    validity_cache: dict[str, bool] = {}
    best_by_item: dict[str, dict] = {}
    for row in rows:
        wh = row.warehouse
        if wh not in validity_cache:
            validity_cache[wh] = is_valid_production_warehouse(wh, source_wh)
        if not validity_cache[wh]:
            continue

        deficit = flt(row.deficit_qty or 0, 4)
        if deficit <= 0:
            continue

        existing = best_by_item.get(row.item_code)
        if (
            not existing
            or deficit > existing["deficit_qty"]
            or (deficit == existing["deficit_qty"] and wh < existing["warehouse"])
        ):
            best_by_item[row.item_code] = {"warehouse": wh, "deficit_qty": deficit}

    return best_by_item


def _fetch_warehouse_batches_by_item(
    item_codes: list[str],
    warehouse: str,
) -> dict[str, list[dict]]:
    """Fetch positive unexpired batch balances per item_code in a single bulk query (LIFO ordered)."""
    if not item_codes or not warehouse:
        return {}

    batch_item_codes = frappe.get_all(
        "Item",
        filters={"name": ["in", item_codes], "has_batch_no": 1},
        pluck="name",
    )
    if not batch_item_codes:
        return {}

    rows = frappe.db.sql(
        """
        SELECT
            item_code,
            batch_no,
            SUM(qty) AS qty,
            MAX(CASE WHEN qty > 0 THEN posting_dt ELSE NULL END) AS last_inward_posting_datetime,
            MAX(CASE WHEN qty > 0 THEN sle_creation ELSE NULL END) AS last_inward_creation
        FROM (
            SELECT
                sle.item_code AS item_code,
                sle.batch_no AS batch_no,
                sle.actual_qty AS qty,
                COALESCE(
                    sle.posting_datetime,
                    TIMESTAMP(sle.posting_date, COALESCE(sle.posting_time, '00:00:00'))
                ) AS posting_dt,
                sle.creation AS sle_creation
            FROM `tabStock Ledger Entry` sle
            WHERE sle.item_code IN %(item_codes)s
              AND sle.warehouse = %(warehouse)s
              AND sle.is_cancelled = 0
              AND sle.batch_no IS NOT NULL
              AND sle.batch_no != ''
              AND (sle.serial_and_batch_bundle IS NULL OR sle.serial_and_batch_bundle = '')

            UNION ALL

            SELECT
                sle.item_code AS item_code,
                sbe.batch_no AS batch_no,
                sbe.qty AS qty,
                COALESCE(
                    sle.posting_datetime,
                    TIMESTAMP(sle.posting_date, COALESCE(sle.posting_time, '00:00:00'))
                ) AS posting_dt,
                sle.creation AS sle_creation
            FROM `tabStock Ledger Entry` sle
            INNER JOIN `tabSerial and Batch Entry` sbe
                ON sbe.parent = sle.serial_and_batch_bundle
            WHERE sle.item_code IN %(item_codes)s
              AND COALESCE(NULLIF(sbe.warehouse, ''), sle.warehouse) = %(warehouse)s
              AND sle.is_cancelled = 0
              AND sle.serial_and_batch_bundle IS NOT NULL
              AND sle.serial_and_batch_bundle != ''
              AND sbe.batch_no IS NOT NULL
              AND sbe.batch_no != ''
        ) AS combined
        GROUP BY item_code, batch_no
        HAVING SUM(qty) > 1e-6
        """,
        {"item_codes": tuple(batch_item_codes), "warehouse": warehouse},
        as_dict=True,
    )
    if not rows:
        return {}

    batch_nos = list({r.batch_no for r in rows if r.get("batch_no")})
    batch_meta = {
        b.name: b
        for b in frappe.get_all(
            "Batch",
            filters={"name": ["in", batch_nos], "disabled": 0},
            fields=["name", "expiry_date", "creation"],
        )
    }
    today_date = getdate(today())

    grouped_raw: dict[str, list[dict]] = {}
    for row in rows:
        meta = batch_meta.get(row.batch_no)
        if not meta:
            continue
        expiry_date = meta.get("expiry_date")
        if expiry_date and getdate(expiry_date) < today_date:
            continue
        grouped_raw.setdefault(row.item_code, []).append(
            {
                "batch_no": row.batch_no,
                "qty": flt(row.qty, 4),
                "last_inward_posting_datetime": row.get("last_inward_posting_datetime"),
                "last_inward_creation": row.get("last_inward_creation"),
                "batch_creation": meta.get("creation"),
            }
        )

    result: dict[str, list[dict]] = {}
    for item_code, candidates in grouped_raw.items():
        candidates.sort(
            key=lambda c: (
                _dt_sort_str(c.get("last_inward_posting_datetime")),
                _dt_sort_str(c.get("last_inward_creation")),
                _dt_sort_str(c.get("batch_creation")),
                c.get("batch_no") or "",
            ),
            reverse=True,
        )
        result[item_code] = [
            {"batch_no": c["batch_no"], "qty": c["qty"]} for c in candidates
        ]
    return result


def get_line_idle_stock(source_warehouse: str) -> list[dict]:
    """Mode 2 (Idle Line Stock): find unreserved free stock on source_warehouse and matching line deficits."""
    source_wh = _validate_production_warehouse_or_throw(source_warehouse)

    idle_rows = frappe.db.sql(
        """
        SELECT item_code, stock_uom, actual_qty, reserved_qty_for_production
        FROM `tabBin`
        WHERE warehouse = %s
          AND actual_qty > 0
          AND (actual_qty - COALESCE(reserved_qty_for_production, 0)) > 0
        ORDER BY item_code ASC
        """,
        (source_wh,),
        as_dict=True,
    )
    if not idle_rows:
        return []

    company = frappe.db.get_value("Warehouse", source_wh, "company")
    item_codes = list({r["item_code"] for r in idle_rows if r.get("item_code")})
    items_meta = _fetch_items_metadata(item_codes)
    sibling_deficits = _fetch_sibling_deficits_by_item(item_codes, company, source_wh)
    batches_by_item = _fetch_warehouse_batches_by_item(item_codes, source_wh)

    results = []
    for row in idle_rows:
        item_code = row.get("item_code")
        actual_qty = flt(row.get("actual_qty") or 0, 4)
        reserved_qty = flt(row.get("reserved_qty_for_production") or 0, 4)
        free_qty = flt(actual_qty - reserved_qty, 4)
        if free_qty <= 0:
            continue

        meta = items_meta.get(item_code)
        item_name = meta.item_name if meta else item_code
        uom = row.get("stock_uom") or (meta.stock_uom if meta else "")

        target_info = sibling_deficits.get(item_code)
        suggested_target_wh = target_info["warehouse"] if target_info else ""
        target_deficit_qty = flt(target_info["deficit_qty"], 4) if target_info else 0.0
        suggested_qty = (
            flt(min(free_qty, target_deficit_qty), 4)
            if target_deficit_qty > 0
            else free_qty
        )

        results.append(
            {
                "item_code": item_code,
                "item_name": item_name,
                "uom": uom,
                "source_warehouse": source_wh,
                "actual_qty": actual_qty,
                "reserved_qty": reserved_qty,
                "free_qty": free_qty,
                "suggested_target_warehouse": suggested_target_wh,
                "target_deficit_qty": target_deficit_qty,
                "suggested_qty": suggested_qty,
                "available_batches": batches_by_item.get(item_code, []),
            }
        )

    return results


def search_line_transfer_items(
    source_warehouse: str,
    search: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """Search stocked items inside a production warehouse for ad-hoc manual line transfer."""
    source_wh = _validate_production_warehouse_or_throw(source_warehouse)
    safe_limit = max(1, min(cint(limit or 30), 200))

    params: dict[str, object] = {"source_wh": source_wh, "limit": safe_limit}
    search_clause = ""
    if search and str(search).strip():
        params["term"] = f"%{str(search).strip()}%"
        search_clause = "AND (b.item_code LIKE %(term)s OR i.item_name LIKE %(term)s)"

    rows = frappe.db.sql(
        f"""
        SELECT
            b.item_code,
            i.item_name,
            COALESCE(NULLIF(b.stock_uom, ''), i.stock_uom) AS uom,
            b.actual_qty,
            b.reserved_qty_for_production
        FROM `tabBin` b
        INNER JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse = %(source_wh)s
          AND b.actual_qty > 0
          {search_clause}
        ORDER BY b.item_code ASC
        LIMIT %(limit)s
        """,
        params,
        as_dict=True,
    )

    return [
        {
            "item_code": r.item_code,
            "item_name": r.item_name or r.item_code,
            "uom": r.uom or "",
            "actual_qty": flt(r.actual_qty or 0, 4),
            "reserved_qty": flt(r.reserved_qty_for_production or 0, 4),
            "free_qty": flt(
                max(
                    0.0,
                    flt(r.actual_qty or 0) - flt(r.reserved_qty_for_production or 0),
                ),
                4,
            ),
        }
        for r in rows
    ]


def _parse_transfers_payload(transfers: list[dict] | str) -> list[dict]:
    """Parse transfers payload from list or JSON string and ensure non-empty."""
    if isinstance(transfers, str):
        try:
            parsed = json.loads(transfers)
        except (json.JSONDecodeError, TypeError, ValueError):
            parsed = frappe.parse_json(transfers)
    else:
        parsed = transfers

    if not parsed or not isinstance(parsed, list):
        frappe.throw(
            _("Transfer edilecek malzeme listesi boş olamaz."),
            frappe.ValidationError,
        )
    return parsed


def _validate_single_transfer_row(row: dict) -> dict:
    """Validate a single transfer payload item and normalize warehouse/uom metadata."""
    item_code = row.get("item_code")
    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(
            _("Geçerli bir malzeme kodu zorunludur: {0}").format(item_code),
            frappe.ValidationError,
        )

    qty = flt(row.get("qty"), 4)
    if qty <= 0:
        frappe.throw(
            _("Transfer miktarı sıfırdan büyük olmalıdır."),
            frappe.ValidationError,
        )

    source_wh = str(row.get("source_warehouse") or "").strip()
    target_wh = str(row.get("target_warehouse") or "").strip()
    if not source_wh or not frappe.db.exists("Warehouse", source_wh):
        frappe.throw(
            _("Geçerli bir kaynak depo zorunludur: {0}").format(source_wh),
            frappe.ValidationError,
        )
    if not target_wh or not frappe.db.exists("Warehouse", target_wh):
        frappe.throw(
            _("Geçerli bir hedef depo zorunludur: {0}").format(target_wh),
            frappe.ValidationError,
        )
    if source_wh == target_wh:
        frappe.throw(
            _("Kaynak depo ve hedef depo aynı olamaz: {0}").format(source_wh),
            frappe.ValidationError,
        )

    if not is_valid_production_warehouse(source_wh, target_wh):
        frappe.throw(
            _(
                "Hammadde veya grup depolarından hat transferi yapılamaz. Kaynak yalnızca geçerli bir üretim deposu olabilir: {0}"
            ).format(source_wh),
            frappe.ValidationError,
        )
    if not is_valid_production_warehouse(target_wh, source_wh):
        frappe.throw(
            _(
                "Hammadde veya grup depolarına hat transferi yapılamaz. Hedef yalnızca geçerli bir üretim deposu olabilir: {0}"
            ).format(target_wh),
            frappe.ValidationError,
        )

    src_company = frappe.db.get_value("Warehouse", source_wh, "company")
    tgt_company = frappe.db.get_value("Warehouse", target_wh, "company")
    if src_company and tgt_company and src_company != tgt_company:
        frappe.throw(
            _(
                "Kaynak depo ({0}) ve hedef depo ({1}) aynı şirkete ait olmalıdır."
            ).format(source_wh, target_wh),
            frappe.ValidationError,
        )

    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
    return {
        "item_code": item_code,
        "qty": qty,
        "source_warehouse": source_wh,
        "target_warehouse": target_wh,
        "stock_uom": stock_uom,
        "company": src_company or tgt_company,
    }


def _validate_transfer_rows(
    transfers_list: list[dict],
) -> tuple[list[dict], dict[tuple[str, str], float]]:
    """Validate individual transfer lines and aggregate demand per (item_code, source_warehouse)."""
    validated_items: list[dict] = []
    agg_demand: dict[tuple[str, str], float] = {}

    for row in transfers_list:
        if not isinstance(row, dict):
            continue
        item_data = _validate_single_transfer_row(row)
        validated_items.append(item_data)
        key = (item_data["item_code"], item_data["source_warehouse"])
        agg_demand[key] = flt(agg_demand.get(key, 0.0) + item_data["qty"], 4)

    if not validated_items:
        frappe.throw(
            _("Transfer edilecek geçerli malzeme bulunamadı."),
            frappe.ValidationError,
        )

    return validated_items, agg_demand


def _validate_bin_and_reservation_limits(
    agg_demand: dict[tuple[str, str], float],
    allow_reserved_override: int | bool,
) -> bool:
    """Ensure requested quantities do not exceed Bin actual stock or unapproved reserved stock."""
    used_reserved_stock = False
    override_allowed = bool(cint(allow_reserved_override))

    for (item_code, source_wh), req_qty in agg_demand.items():
        bin_vals = (
            frappe.db.get_value(
                "Bin",
                {"item_code": item_code, "warehouse": source_wh},
                ["actual_qty", "reserved_qty_for_production"],
                as_dict=True,
            )
            or {}
        )
        actual_qty = flt(bin_vals.get("actual_qty") or 0, 4)
        reserved_qty = flt(bin_vals.get("reserved_qty_for_production") or 0, 4)
        free_qty = flt(max(0.0, actual_qty - reserved_qty), 4)

        if req_qty > actual_qty:
            frappe.throw(
                _(
                    "Kaynak depoda ({0}) {1} için yeterli stok yok. Mevcut: {2}, İstenen: {3}"
                ).format(source_wh, item_code, actual_qty, req_qty),
                frappe.ValidationError,
            )

        if req_qty > free_qty:
            used_reserved_stock = True
            if not override_allowed:
                frappe.throw(
                    _(
                        "Kaynak depoda ({0}) {1} kaleminin serbest stoğu ({2}) yetersiz; {3} miktarında başka iş emirlerine rezerve stok kullanılacak. Devam etmek için rezerve stok kullanımını onaylayın."
                    ).format(source_wh, item_code, free_qty, req_qty),
                    frappe.ValidationError,
                )

    return used_reserved_stock


def _build_stock_entry_items_with_lifo(validated_items: list[dict]) -> list[dict]:
    """Expand each validated transfer line into Stock Entry Detail dicts using LIFO batches."""
    se_items: list[dict] = []
    consumed_by_key: dict[tuple[str, str], dict[str, float]] = {}

    for row in validated_items:
        item_code = row["item_code"]
        source_wh = row["source_warehouse"]
        key = (item_code, source_wh)
        prior = consumed_by_key.setdefault(key, {})

        allocations = resolve_lifo_batches(
            item_code=item_code,
            warehouse=source_wh,
            required_qty=row["qty"],
            _prior_consumed=prior,
        )

        for alloc in allocations:
            batch_no = alloc.get("batch_no")
            alloc_qty = flt(alloc.get("qty"), 4)
            if batch_no:
                prior[batch_no] = flt(prior.get(batch_no, 0.0) + alloc_qty, 4)

            detail = {
                "item_code": item_code,
                "s_warehouse": source_wh,
                "t_warehouse": row["target_warehouse"],
                "qty": alloc_qty,
                "transfer_qty": alloc_qty,
                "stock_uom": row["stock_uom"],
                "uom": row["stock_uom"],
                "conversion_factor": 1.0,
            }
            if batch_no:
                detail["batch_no"] = batch_no
                detail["use_serial_batch_fields"] = 1
            se_items.append(detail)

    return se_items


def _ensure_relabeling_stock_entry_types() -> None:
    """Ensure Return from Production Supply and Package Split Stock Entry Types exist."""
    if not frappe.db.exists(
        "Stock Entry Type", "Return from Production Supply"
    ) or not frappe.db.exists("Stock Entry Type", "Package Split"):
        from erpnextkta.kta_stock.setup import setup_stock_entry_types

        setup_stock_entry_types()


def _is_full_remaining_standard_box(
    item_code: str,
    source_wh: str,
    batch_no: str | None,
    alloc_qty: float,
) -> bool:
    """Return True if batch_no is a 7+4 KTA box with full remaining balance only in source_wh."""
    if not batch_no or not is_standard_kta_box_batch(batch_no):
        return False

    balances = get_batch_ledger_balances(item_code, batch_no)
    source_balance = flt(
        sum(flt(b["qty"]) for b in balances if b["warehouse"] == source_wh), 4
    )
    if abs(source_balance - flt(alloc_qty, 4)) > 1e-6:
        return False

    other_balances = [
        b for b in balances if b["warehouse"] != source_wh and abs(flt(b["qty"])) > 1e-6
    ]
    return len(other_balances) == 0


def _submit_transfer_stock_entry(
    se_items: list[dict],
    company: str | None,
    stock_entry_type: str,
    purpose: str,
    remarks: str,
    work_order: str | None = None,
    call_set_stock_entry_type: bool = True,
) -> str:
    """Create, populate, and submit a Material Transfer / Return Stock Entry."""
    se = frappe.new_doc("Stock Entry")
    se.purpose = purpose
    se.stock_entry_type = stock_entry_type
    if work_order:
        se.work_order = work_order
    se.company = company

    sources = {d["s_warehouse"] for d in se_items if d.get("s_warehouse")}
    targets = {d["t_warehouse"] for d in se_items if d.get("t_warehouse")}
    if len(sources) == 1:
        se.from_warehouse = next(iter(sources))
    if len(targets) == 1:
        se.to_warehouse = next(iter(targets))

    for item_row in se_items:
        se.append("items", item_row)

    se.remarks = remarks
    if call_set_stock_entry_type and hasattr(se, "set_stock_entry_type"):
        se.set_stock_entry_type()
    if hasattr(se, "calculate_rate_and_amount"):
        se.calculate_rate_and_amount(raise_error_if_no_rate=False)
    for row in se.get("items") or []:
        if flt(row.get("basic_rate")) <= 0:
            row.allow_zero_valuation_rate = 1

    se.flags.ignore_permissions = True
    se.insert(ignore_permissions=True)
    se.submit()
    return se.name


def _execute_split_line_transfer(
    validated_items: list[dict],
    transfers_list: list[dict],
    used_reserved_stock: bool,
    company: str | None,
    work_order: str | None = None,
    remarks: str | None = None,
) -> dict:
    """Execute inter-line transfer with Package Split on partial/legacy boxes and label printing."""
    _ensure_relabeling_stock_entry_types()
    consumed_by_key: dict[tuple[str, str], dict[str, float]] = {}
    mt_items: list[dict] = []
    split_stock_entries: list[str] = []
    all_stock_entries: list[str] = []
    printed_labels = 0

    for row in validated_items:
        item_code = row["item_code"]
        source_wh = row["source_warehouse"]
        target_wh = row["target_warehouse"]
        prior = consumed_by_key.setdefault((item_code, source_wh), {})

        allocations = resolve_lifo_batches(
            item_code=item_code,
            warehouse=source_wh,
            required_qty=row["qty"],
            _prior_consumed=prior,
        )

        for alloc in allocations:
            alloc_batch = alloc.get("batch_no")
            alloc_qty = flt(alloc.get("qty"), 4)
            if alloc_batch and not _is_full_remaining_standard_box(
                item_code, source_wh, alloc_batch, alloc_qty
            ):
                split_res = create_package_split_repack(
                    item_code=item_code,
                    source_warehouse=source_wh,
                    target_warehouse=target_wh,
                    source_batch=alloc_batch,
                    split_qtys=[alloc_qty],
                    remarks=remarks
                    or _("Hatlar Arası Koli Bölme Transferi: {0} -> {1}").format(
                        source_wh, target_wh
                    ),
                )
                se_name = split_res["stock_entry"]
                split_stock_entries.append(se_name)
                all_stock_entries.append(se_name)
                printed_labels += len(split_res.get("created_batches") or [])
            else:
                if alloc_batch:
                    prior[alloc_batch] = flt(prior.get(alloc_batch, 0.0) + alloc_qty, 4)
                detail = {
                    "item_code": item_code,
                    "s_warehouse": source_wh,
                    "t_warehouse": target_wh,
                    "qty": alloc_qty,
                    "transfer_qty": alloc_qty,
                    "stock_uom": row["stock_uom"],
                    "uom": row["stock_uom"],
                    "conversion_factor": 1.0,
                }
                if alloc_batch:
                    detail["batch_no"] = alloc_batch
                    detail["use_serial_batch_fields"] = 1
                mt_items.append(detail)

    transfer_se_name = None
    if mt_items:
        purpose = (
            "Material Transfer for Manufacture" if work_order else "Material Transfer"
        )
        eff_remarks = (
            str(remarks).strip()
            if remarks and str(remarks).strip()
            else (
                _("Hat İkmal Transferi (Shopfloor Hub) - İş Emri: {0}").format(
                    work_order
                )
                if work_order
                else _("Hatlar Arası Transfer (Line Transfer)")
            )
        )
        transfer_se_name = _submit_transfer_stock_entry(
            se_items=mt_items,
            company=company,
            stock_entry_type=purpose,
            purpose=purpose,
            remarks=eff_remarks,
            work_order=work_order,
            call_set_stock_entry_type=True,
        )
        all_stock_entries.insert(0, transfer_se_name)

        posting_date = frappe.db.get_value(
            "Stock Entry", transfer_se_name, "posting_date"
        )
        labels_to_print: list[str] = []
        for detail in mt_items:
            if not detail.get("batch_no"):
                continue
            lbl_name = upsert_box_label(
                item_code=detail["item_code"],
                batch_no=detail["batch_no"],
                qty=flt(detail["qty"]),
                target_warehouse=detail["t_warehouse"],
                source_warehouse=detail["s_warehouse"],
                reference_doctype="Stock Entry",
                reference_name=transfer_se_name,
                posting_date=posting_date,
                fallback_ref="TRANSFER",
            )
            if lbl_name and str(lbl_name) not in labels_to_print:
                labels_to_print.append(str(lbl_name))

        if labels_to_print:
            enqueue_print_labels_by_names(labels_to_print)
            printed_labels += len(labels_to_print)

    primary_se = transfer_se_name or (
        split_stock_entries[0] if split_stock_entries else None
    )
    return {
        "success": True,
        "stock_entry": primary_se,
        "stock_entries": all_stock_entries,
        "split_stock_entries": split_stock_entries,
        "printed_labels": printed_labels,
        "transferred_items": transfers_list,
        "used_reserved_stock": used_reserved_stock,
        "message": _("{0} numaralı hat transferi başarıyla tamamlandı.").format(
            ", ".join(all_stock_entries)
        ),
    }


def execute_line_transfer(
    transfers: list[dict] | str,
    allow_reserved_override: int | bool = 0,
    work_order: str | None = None,
    remarks: str | None = None,
    split_packages: int | bool = 0,
) -> dict:
    """Execute inter-line Material Transfer (or Material Transfer for Manufacture) with LIFO batches."""
    transfers_list = _parse_transfers_payload(transfers)
    validated_items, agg_demand = _validate_transfer_rows(transfers_list)
    used_reserved_stock = _validate_bin_and_reservation_limits(
        agg_demand, allow_reserved_override
    )

    company = None
    if work_order:
        if not frappe.db.exists("Work Order", work_order):
            frappe.throw(
                _("Geçerli bir İş Emri zorunludur: {0}").format(work_order),
                frappe.ValidationError,
            )
        company = frappe.db.get_value("Work Order", work_order, "company")
    if not company:
        company = validated_items[0].get("company") or frappe.db.get_value(
            "Warehouse", validated_items[0]["target_warehouse"], "company"
        )

    if cint(split_packages):
        return _execute_split_line_transfer(
            validated_items=validated_items,
            transfers_list=transfers_list,
            used_reserved_stock=used_reserved_stock,
            company=company,
            work_order=work_order,
            remarks=remarks,
        )

    se_items = _build_stock_entry_items_with_lifo(validated_items)
    purpose = "Material Transfer for Manufacture" if work_order else "Material Transfer"
    eff_remarks = (
        str(remarks).strip()
        if remarks and str(remarks).strip()
        else (
            _("Hat İkmal Transferi (Shopfloor Hub) - İş Emri: {0}").format(work_order)
            if work_order
            else _("Hatlar Arası Transfer (Line Transfer)")
        )
    )
    se_name = _submit_transfer_stock_entry(
        se_items=se_items,
        company=company,
        stock_entry_type=purpose,
        purpose=purpose,
        remarks=eff_remarks,
        work_order=work_order,
        call_set_stock_entry_type=True,
    )

    return {
        "success": True,
        "stock_entry": se_name,
        "transferred_items": transfers_list,
        "used_reserved_stock": used_reserved_stock,
        "message": _("{0} numaralı hat transferi başarıyla tamamlandı.").format(
            se_name
        ),
    }


def _validate_single_return_row(row: dict, default_target_wh: str) -> dict:
    """Validate a single production supply return row."""
    item_code = row.get("item_code")
    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(
            _("Geçerli bir malzeme kodu zorunludur: {0}").format(item_code),
            frappe.ValidationError,
        )

    qty = flt(row.get("qty"), 4)
    if qty <= 0:
        frappe.throw(
            _("İade miktarı sıfırdan büyük olmalıdır."),
            frappe.ValidationError,
        )

    source_wh = str(row.get("source_warehouse") or "").strip()
    target_wh = str(row.get("target_warehouse") or default_target_wh or "").strip()

    if not source_wh or not frappe.db.exists("Warehouse", source_wh):
        frappe.throw(
            _("Geçerli bir kaynak üretim deposu zorunludur: {0}").format(source_wh),
            frappe.ValidationError,
        )
    if not is_valid_production_warehouse(source_wh):
        frappe.throw(
            _(
                "Depo iadesi yalnızca geçerli üretim hatlarından yapılabilir: {0}"
            ).format(source_wh),
            frappe.ValidationError,
        )
    if not is_valid_raw_material_return_warehouse(target_wh):
        frappe.throw(
            _("Hedef depo geçerli bir 110 hammadde yaprak rafı olmalıdır: {0}").format(
                target_wh
            ),
            frappe.ValidationError,
        )
    if source_wh == target_wh:
        frappe.throw(
            _("Kaynak depo ve hedef depo aynı olamaz: {0}").format(source_wh),
            frappe.ValidationError,
        )

    src_company = frappe.db.get_value("Warehouse", source_wh, "company")
    tgt_company = frappe.db.get_value("Warehouse", target_wh, "company")
    if src_company and tgt_company and src_company != tgt_company:
        frappe.throw(
            _(
                "Kaynak depo ({0}) ve hedef depo ({1}) aynı şirkete ait olmalıdır."
            ).format(source_wh, target_wh),
            frappe.ValidationError,
        )

    item_meta = (
        frappe.db.get_value(
            "Item", item_code, ["stock_uom", "has_batch_no"], as_dict=True
        )
        or {}
    )
    batch_no = str(row.get("batch_no") or "").strip() or None
    if batch_no and not cint(item_meta.get("has_batch_no") or 0):
        frappe.throw(
            _("Parti takipsiz kalem için parti seçilemez: {0}").format(item_code),
            frappe.ValidationError,
        )

    return {
        "item_code": item_code,
        "qty": qty,
        "source_warehouse": source_wh,
        "target_warehouse": target_wh,
        "batch_no": batch_no,
        "has_batch_no": cint(item_meta.get("has_batch_no") or 0),
        "stock_uom": item_meta.get("stock_uom") or "Nos",
        "company": src_company or tgt_company,
    }


def _validate_return_rows(
    items_list: list[dict],
    target_warehouse: str,
) -> tuple[list[dict], dict[tuple[str, str], float]]:
    """Validate target return shelf and all return item rows."""
    default_target_wh = str(target_warehouse or "").strip()
    if not is_valid_raw_material_return_warehouse(default_target_wh):
        frappe.throw(
            _("Hedef depo geçerli bir 110 hammadde yaprak rafı olmalıdır: {0}").format(
                target_warehouse or ""
            ),
            frappe.ValidationError,
        )

    validated_items: list[dict] = []
    agg_demand: dict[tuple[str, str], float] = {}

    for row in items_list:
        if not isinstance(row, dict):
            continue
        item_data = _validate_single_return_row(row, default_target_wh)
        validated_items.append(item_data)
        key = (item_data["item_code"], item_data["source_warehouse"])
        agg_demand[key] = flt(agg_demand.get(key, 0.0) + item_data["qty"], 4)

    if not validated_items:
        frappe.throw(
            _("İade edilecek geçerli malzeme bulunamadı."),
            frappe.ValidationError,
        )

    return validated_items, agg_demand


def _resolve_explicit_batch_allocation(
    item_code: str,
    source_wh: str,
    qty: float,
    batch_no: str,
    prior_consumed: dict[str, float],
) -> list[dict]:
    """Validate and allocate an explicit user-selected batch from source_wh."""
    batch_meta = frappe.db.get_value(
        "Batch",
        batch_no,
        ["name", "item", "disabled", "expiry_date"],
        as_dict=True,
    )
    if (
        not batch_meta
        or batch_meta.get("item") != item_code
        or cint(batch_meta.get("disabled")) == 1
    ):
        frappe.throw(
            _("Geçerli ve aktif bir parti seçilmelidir: {0}").format(batch_no),
            frappe.ValidationError,
        )

    expiry_date = batch_meta.get("expiry_date")
    if expiry_date and getdate(expiry_date) < getdate(today()):
        frappe.throw(
            _("Seçilen partinin son kullanma tarihi dolmuştur: {0}").format(batch_no),
            frappe.ValidationError,
        )

    balances = get_batch_ledger_balances(item_code, batch_no)
    src_bal = flt(
        sum(flt(b["qty"]) for b in balances if b["warehouse"] == source_wh), 4
    )
    avail = flt(src_bal - flt(prior_consumed.get(batch_no, 0.0)), 4)
    if avail + 1e-6 < flt(qty, 4):
        frappe.throw(
            _(
                "Seçilen parti ({0}) için kaynak depoda ({1}) yeterli bakiye yok. Mevcut: {2}, İstenen: {3}"
            ).format(batch_no, source_wh, avail, flt(qty, 4)),
            frappe.ValidationError,
        )

    return [{"batch_no": batch_no, "qty": flt(qty, 4)}]


def execute_production_supply_return(
    items: list[dict] | str,
    target_warehouse: str,
    allow_reserved_override: int | bool = 0,
    remarks: str | None = None,
) -> dict:
    """Return idle production line stock back to 110 raw material leaf shelves with strict box routing."""
    _ensure_relabeling_stock_entry_types()
    items_list = _parse_transfers_payload(items)
    validated_items, agg_demand = _validate_return_rows(items_list, target_warehouse)
    used_reserved_stock = _validate_bin_and_reservation_limits(
        agg_demand, allow_reserved_override
    )

    company = validated_items[0].get("company") or frappe.db.get_value(
        "Warehouse", validated_items[0]["target_warehouse"], "company"
    )
    consumed_by_key: dict[tuple[str, str], dict[str, float]] = {}
    return_rows: list[dict] = []
    split_stock_entries: list[str] = []
    stock_entries: list[str] = []
    returned_items: list[dict] = []
    printed_labels = 0

    for row in validated_items:
        item_code = row["item_code"]
        source_wh = row["source_warehouse"]
        target_wh = row["target_warehouse"]
        prior = consumed_by_key.setdefault((item_code, source_wh), {})

        if row["has_batch_no"] and row["batch_no"]:
            allocations = _resolve_explicit_batch_allocation(
                item_code=item_code,
                source_wh=source_wh,
                qty=row["qty"],
                batch_no=row["batch_no"],
                prior_consumed=prior,
            )
        else:
            allocations = resolve_lifo_batches(
                item_code=item_code,
                warehouse=source_wh,
                required_qty=row["qty"],
                _prior_consumed=prior,
            )

        for alloc in allocations:
            alloc_batch = alloc.get("batch_no")
            alloc_qty = flt(alloc.get("qty"), 4)
            is_full_std = _is_full_remaining_standard_box(
                item_code, source_wh, alloc_batch, alloc_qty
            )

            if alloc_batch is None or is_full_std:
                if alloc_batch:
                    prior[alloc_batch] = flt(prior.get(alloc_batch, 0.0) + alloc_qty, 4)
                detail = {
                    "item_code": item_code,
                    "s_warehouse": source_wh,
                    "t_warehouse": target_wh,
                    "qty": alloc_qty,
                    "transfer_qty": alloc_qty,
                    "stock_uom": row["stock_uom"],
                    "uom": row["stock_uom"],
                    "conversion_factor": 1.0,
                }
                if alloc_batch:
                    detail["batch_no"] = alloc_batch
                    detail["use_serial_batch_fields"] = 1
                return_rows.append(detail)
            else:
                split_res = create_package_split_repack(
                    item_code=item_code,
                    source_warehouse=source_wh,
                    target_warehouse=target_wh,
                    source_batch=alloc_batch,
                    split_qtys=[alloc_qty],
                    remarks=remarks
                    or _(
                        "Üretim Tedarik Alanından Koli Bölme İadesi: {0} -> {1}"
                    ).format(source_wh, target_wh),
                )
                split_se_name = split_res["stock_entry"]
                split_stock_entries.append(split_se_name)
                stock_entries.append(split_se_name)
                created = split_res.get("created_batches") or []
                printed_labels += len(created)
                returned_items.append(
                    {
                        "item_code": item_code,
                        "qty": alloc_qty,
                        "source_warehouse": source_wh,
                        "target_warehouse": target_wh,
                        "batch_no": alloc_batch,
                        "result_batch_no": created[0]["batch_no"]
                        if created
                        else alloc_batch,
                        "stock_entry": split_se_name,
                        "routing": "split",
                    }
                )

    return_stock_entry = None
    if return_rows:
        eff_remarks = (
            str(remarks).strip()
            if remarks and str(remarks).strip()
            else _("Üretim Tedarik Alanından Depo İadesi (150x -> 110)")
        )
        # Never call set_stock_entry_type() so custom type 'Return from Production Supply' is preserved
        return_stock_entry = _submit_transfer_stock_entry(
            se_items=return_rows,
            company=company,
            stock_entry_type="Return from Production Supply",
            purpose="Material Transfer",
            remarks=eff_remarks,
            call_set_stock_entry_type=False,
        )
        stock_entries.insert(0, return_stock_entry)
        for detail in return_rows:
            if detail.get("batch_no"):
                printed_labels += 1
            returned_items.append(
                {
                    "item_code": detail["item_code"],
                    "qty": flt(detail["qty"]),
                    "source_warehouse": detail["s_warehouse"],
                    "target_warehouse": detail["t_warehouse"],
                    "batch_no": detail.get("batch_no"),
                    "result_batch_no": detail.get("batch_no"),
                    "stock_entry": return_stock_entry,
                    "routing": "return",
                }
            )

    return {
        "success": True,
        "stock_entries": stock_entries,
        "return_stock_entry": return_stock_entry,
        "split_stock_entries": split_stock_entries,
        "printed_labels": printed_labels,
        "returned_items": returned_items,
        "used_reserved_stock": used_reserved_stock,
        "message": _("{0} numaralı depo iadesi başarıyla tamamlandı.").format(
            ", ".join(stock_entries)
        ),
    }
