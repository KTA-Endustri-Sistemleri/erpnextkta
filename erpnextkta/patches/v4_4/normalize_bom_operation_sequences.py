# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from frappe.utils import cint


def execute():
    """Normalize BOM Operation and draft Work Order Operation sequence_id values."""
    _normalize_table_sequences("BOM Operation", draft_only=False)
    _normalize_table_sequences("Work Order Operation", draft_only=True)

    if not frappe.flags.in_test:
        frappe.db.commit()


def _normalize_table_sequences(doctype: str, draft_only: bool = False) -> None:
    """Normalize sequence_id values to 1-based sequential steps (preserving parallels)."""
    if not frappe.db.exists("DocType", doctype):
        return

    table = f"`tab{doctype}`"
    draft_filter = "AND docstatus = 0" if draft_only else ""

    # 1. Fast bulk updates for SAP 10x sequences and missing/zero sequences
    frappe.db.sql(
        f"UPDATE {table} SET sequence_id = idx WHERE sequence_id = idx * 10 {draft_filter}"
    )
    frappe.db.sql(
        f"UPDATE {table} SET sequence_id = idx WHERE (sequence_id = 0 OR sequence_id IS NULL) {draft_filter}"
    )

    # 2. Query any remaining distinct parents with invalid sequences
    parents = frappe.db.sql(
        f"""
        SELECT DISTINCT parent, parenttype
        FROM {table}
        WHERE ((idx = 1 AND sequence_id != 1) OR sequence_id > idx OR sequence_id < 1)
        {draft_filter}
        """,
        as_dict=True,
    )

    for row in parents:
        ops = frappe.get_all(
            doctype,
            filters={"parent": row.parent, "parenttype": row.parenttype},
            fields=["name", "idx", "sequence_id"],
            order_by="idx asc",
        )
        if not ops:
            continue

        current_seq = 1
        first_orig_seq = cint(ops[0].get("sequence_id"))
        prev_orig_seq = first_orig_seq
        if first_orig_seq != 1:
            frappe.db.set_value(
                doctype, ops[0]["name"], "sequence_id", 1, update_modified=False
            )

        for op in ops[1:]:
            orig_seq = cint(op.get("sequence_id"))
            if orig_seq == prev_orig_seq and orig_seq not in (0, None):
                new_seq = current_seq
            else:
                current_seq += 1
                new_seq = current_seq
            prev_orig_seq = orig_seq

            if orig_seq != new_seq:
                frappe.db.set_value(
                    doctype, op["name"], "sequence_id", new_seq, update_modified=False
                )
