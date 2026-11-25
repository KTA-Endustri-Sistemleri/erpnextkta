# Copyright (c) 2026, KTA Endustri Sistemleri and contributors
# For license information, please see license.txt

import frappe


def execute():
    """Create or update PDA custom fields (including Employee custom_pda_pin)."""
    from erpnextkta.kta_stock.setup import setup_pda_custom_fields

    setup_pda_custom_fields()

    if not frappe.flags.in_test:
        frappe.db.commit()
