import frappe

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
]


def setup():
    """Run idempotent setup routines for the kta_stock module."""
    setup_stock_entry_types()


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
