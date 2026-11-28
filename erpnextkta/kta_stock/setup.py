import frappe
from frappe.core.doctype.doctype.doctype import clear_permissions_cache
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property
from frappe.utils import cint

PDA_ROLE_STOCK_USER = "KTA PDA Stock User"
PDA_STOCK_USER_DOCPERMS = {
    "Stock Entry": ("read", "write", "create", "submit"),
    "Serial and Batch Bundle": ("read", "write", "create", "submit"),
    "Batch": ("read", "write", "create"),
    "Stock Ledger Entry": ("read",),
    "Item": ("read",),
    "Warehouse": ("read",),
    "KTA Stock Label": ("read", "write", "create"),
    "KTA Line Replenishment Order": ("read", "write"),
}

STOCK_ENTRY_TYPES = [
    {
        "name": "Return from Production Supply",
        "purpose": "Material Transfer",
        "is_standard": 0,
        "custom_etiket_basilabilir": 1,
        "custom_etiket_sablonu": "Depo Giriş Etiketi",
    },
    {
        "name": "Package Split",
        "purpose": "Repack",
        "is_standard": 0,
        "custom_etiket_basilabilir": 1,
        "custom_etiket_sablonu": "Depo Giriş Etiketi",
    },
    {
        "name": "Package Merge",
        "purpose": "Repack",
        "is_standard": 0,
        "custom_etiket_basilabilir": 1,
        "custom_etiket_sablonu": "Depo Giriş Etiketi",
    },
]


def setup():
    """Run idempotent setup routines for the kta_stock module."""
    setup_stock_entry_types()
    setup_pda_custom_fields()
    setup_pda_roles_and_permissions()


def setup_pda_roles_and_permissions() -> None:
    """Create KTA PDA Stock User role, Custom DocPerms, and restricted printer permissions."""
    _ensure_pda_stock_role()
    _sync_pda_role_docperms(PDA_ROLE_STOCK_USER, PDA_STOCK_USER_DOCPERMS)
    _sync_pda_printer_permissions()


def _ensure_pda_stock_role() -> None:
    if not frappe.db.exists("Role", PDA_ROLE_STOCK_USER):
        frappe.get_doc(
            {
                "doctype": "Role",
                "role_name": PDA_ROLE_STOCK_USER,
                "desk_access": 0,
                "home_page": "/pda",
            }
        ).insert(ignore_permissions=True)
        return

    existing = frappe.db.get_value(
        "Role", PDA_ROLE_STOCK_USER, ["desk_access", "home_page"], as_dict=True
    )
    if existing and (cint(existing.desk_access) != 0 or existing.home_page != "/pda"):
        frappe.db.set_value(
            "Role",
            PDA_ROLE_STOCK_USER,
            {"desk_access": 0, "home_page": "/pda"},
        )


def _sync_pda_role_docperms(role: str, docperms: dict[str, tuple[str, ...]]) -> None:
    rights_order = ("read", "write", "create", "submit")
    for doctype, granted_rights in docperms.items():
        if not frappe.db.exists("DocType", doctype):
            continue

        filters = {
            "parent": doctype,
            "role": role,
            "permlevel": 0,
            "if_owner": 0,
        }
        existing = frappe.db.get_value(
            "Custom DocPerm", filters, list(rights_order), as_dict=True
        )
        changed = False
        if not existing:
            add_permission(doctype, role, permlevel=0)
            existing = (
                frappe.db.get_value(
                    "Custom DocPerm", filters, list(rights_order), as_dict=True
                )
                or {}
            )
            changed = True

        for right in rights_order:
            target_val = 1 if right in granted_rights else 0
            if cint(existing.get(right)) != target_val:
                update_permission_property(
                    doctype, role, 0, right, target_val, validate=False
                )
                changed = True

        if changed:
            clear_permissions_cache(doctype)
            frappe.clear_cache(doctype=doctype)


def _sync_pda_printer_permissions() -> None:
    if not frappe.db.exists("DocType", "KTA Printer Permission"):
        return

    restricted_printers = frappe.get_all(
        "KTA Printer Permission",
        filters={"role": "Stock User", "can_print": 1},
        distinct=True,
        pluck="printer",
    )
    for printer_name in restricted_printers:
        if not printer_name or not frappe.db.exists("KTA Zebra Printers", printer_name):
            continue

        existing = frappe.db.get_value(
            "KTA Printer Permission",
            {"printer": printer_name, "role": PDA_ROLE_STOCK_USER},
            ["name", "can_print"],
            as_dict=True,
        )
        if not existing:
            frappe.get_doc(
                {
                    "doctype": "KTA Printer Permission",
                    "printer": printer_name,
                    "role": PDA_ROLE_STOCK_USER,
                    "can_print": 1,
                }
            ).insert(ignore_permissions=True)
        elif cint(existing.can_print) != 1:
            frappe.db.set_value("KTA Printer Permission", existing.name, "can_print", 1)


def setup_pda_custom_fields() -> None:
    """Create or update PDA-related custom fields idempotently."""
    create_custom_fields(
        {
            "Employee": [
                {
                    "fieldname": "custom_pda_pin",
                    "label": "PDA PIN",
                    "fieldtype": "Password",
                    "insert_after": "attendance_device_id",
                    "description": "4 haneli PDA giriş PIN kodu",
                }
            ]
        }
    )


def setup_stock_entry_types():
    """Create or update KTA Stock Entry Types and normalize standard Repack label flags."""
    for cfg in STOCK_ENTRY_TYPES:
        _ensure_stock_entry_type(cfg)

    _configure_standard_repack_label_settings()


def _ensure_stock_entry_type(cfg: dict):
    name = cfg["name"]
    if not frappe.db.exists("Stock Entry Type", name):
        doc = frappe.get_doc(
            {
                "doctype": "Stock Entry Type",
                "name": name,
                "purpose": cfg["purpose"],
                "is_standard": cfg["is_standard"],
                "custom_etiket_basilabilir": cfg["custom_etiket_basilabilir"],
                "custom_etiket_sablonu": cfg["custom_etiket_sablonu"],
            }
        )
        doc.insert(ignore_permissions=True)
        return

    frappe.db.set_value(
        "Stock Entry Type",
        name,
        {
            "purpose": cfg["purpose"],
            "is_standard": cfg["is_standard"],
            "custom_etiket_basilabilir": cfg["custom_etiket_basilabilir"],
            "custom_etiket_sablonu": cfg["custom_etiket_sablonu"],
        },
    )


def _configure_standard_repack_label_settings():
    if frappe.db.exists("Stock Entry Type", {"name": "Repack", "is_standard": 1}):
        frappe.db.set_value(
            "Stock Entry Type",
            "Repack",
            {
                "custom_etiket_basilabilir": 0,
                "custom_etiket_sablonu": None,
            },
        )
