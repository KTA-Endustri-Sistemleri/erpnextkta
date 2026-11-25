# Copyright (c) 2026, KTA Endustri Sistemleri and contributors
# For license information, please see license.txt

import frappe

from erpnextkta.kta_stock.setup import (
    PDA_ROLE_STOCK_USER,
    setup_pda_roles_and_permissions,
)

_TARGET_DEPARTMENT_NAMES = ("AMBAR", "AMBAR - KTA", "Sevk")
_BACKFILL_SOURCE_ROLES = {"Stock User", "Stock Manager"}


def backfill_existing_pda_stock_operators() -> int:
    """Grant KTA PDA Stock User role non-destructively to active warehouse/dispatch operators."""
    target_departments = set(
        frappe.get_all(
            "Department",
            filters={"department_name": ["in", list(_TARGET_DEPARTMENT_NAMES)]},
            pluck="name",
        )
    ) | {"AMBAR - KTA", "Sevk"}

    employee_user_ids = [
        uid
        for uid in frappe.get_all(
            "Employee",
            filters={
                "status": "Active",
                "department": ["in", list(target_departments)],
                "user_id": ["is", "set"],
            },
            distinct=True,
            pluck="user_id",
        )
        if uid
    ]
    if not employee_user_ids:
        return 0

    enabled_users = frappe.get_all(
        "User",
        filters={"name": ["in", employee_user_ids], "enabled": 1},
        pluck="name",
    )
    if not enabled_users:
        return 0

    role_rows = frappe.get_all(
        "Has Role",
        filters={"parent": ["in", enabled_users], "parenttype": "User"},
        fields=["parent", "role"],
    )
    roles_by_user: dict[str, set[str]] = {}
    for row in role_rows:
        roles_by_user.setdefault(row.parent, set()).add(row.role)

    added_count = 0
    for user_id in enabled_users:
        current_roles = roles_by_user.get(user_id, set())
        if PDA_ROLE_STOCK_USER in current_roles:
            continue
        if not (current_roles & _BACKFILL_SOURCE_ROLES):
            continue

        user_doc = frappe.get_doc("User", user_id)
        user_doc.append("roles", {"role": PDA_ROLE_STOCK_USER})
        user_doc.save(ignore_permissions=True)
        added_count += 1

    return added_count


def execute() -> None:
    """Create PDA stock role/permissions and backfill existing warehouse operators."""
    setup_pda_roles_and_permissions()
    backfill_existing_pda_stock_operators()

    if not frappe.flags.in_test:
        frappe.db.commit()
