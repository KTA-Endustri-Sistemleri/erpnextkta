import frappe
from frappe.utils import cint

ACCOUNT_NUMBERS = ("620.01", "621.01", "710.20", "731.01")
RAW_MATERIAL_ROOT_GROUP = "HAMMADDELER"
FINISHED_GOODS_ROOT_GROUP = "ÜRÜNLER"


def _get_target_companies(company: str | None = None) -> list[str]:
    """Return explicit company list or all non-test perpetual inventory companies."""
    if company:
        return [company]
    return list(
        frappe.get_all(
            "Company",
            filters={"enable_perpetual_inventory": 1, "name": ["not like", "_Test%"]},
            pluck="name",
        )
        or []
    )


def _resolve_company_accounts(company: str) -> dict[str, str | None]:
    """Resolve leaf Account names for the target company by account_number."""
    rows = frappe.get_all(
        "Account",
        filters={
            "company": company,
            "is_group": 0,
            "account_number": ["in", list(ACCOUNT_NUMBERS)],
        },
        fields=["name", "account_number"],
    )
    by_num = {row.account_number: row.name for row in rows}
    return {num: by_num.get(num) for num in ACCOUNT_NUMBERS}


def _get_descendant_item_groups(root_group_name: str) -> list[str]:
    """Return root_group_name and all nested descendant Item Groups ordered by lft."""
    bounds = frappe.db.get_value(
        "Item Group", root_group_name, ["lft", "rgt"], as_dict=True
    )
    if not bounds:
        return []
    return list(
        frappe.get_all(
            "Item Group",
            filters={"lft": [">=", cint(bounds.lft)], "rgt": ["<=", cint(bounds.rgt)]},
            order_by="lft asc",
            pluck="name",
        )
        or []
    )


def _fix_company_defaults(
    company: str, accounts: dict[str, str | None], dry_run: bool
) -> dict:
    """Fix Company default_expense_account and default_operating_cost_account if needed."""
    acc_621 = accounts.get("621.01")
    acc_710 = accounts.get("710.20")
    acc_731 = accounts.get("731.01")

    current = (
        frappe.db.get_value(
            "Company",
            company,
            ["default_expense_account", "default_operating_cost_account"],
            as_dict=True,
        )
        or frappe._dict()
    )

    updates = {}
    current_exp = current.get("default_expense_account")
    if acc_621 and (not current_exp or (acc_710 and current_exp == acc_710)):
        updates["default_expense_account"] = {"from": current_exp, "to": acc_621}
        if not dry_run:
            frappe.db.set_value("Company", company, "default_expense_account", acc_621)

    current_op = current.get("default_operating_cost_account")
    if acc_731 and current_op:
        is_group = cint(frappe.db.get_value("Account", current_op, "is_group"))
        if is_group == 1:
            updates["default_operating_cost_account"] = {
                "from": current_op,
                "to": acc_731,
            }
            if not dry_run:
                frappe.db.set_value(
                    "Company", company, "default_operating_cost_account", acc_731
                )

    return updates


def _clear_raw_material_item_group_defaults(
    company: str, accounts: dict[str, str | None], dry_run: bool
) -> list[dict]:
    """Clear 710.20/621.01 expense_account on HAMMADDELER hierarchy Item Defaults."""
    rm_groups = _get_descendant_item_groups(RAW_MATERIAL_ROOT_GROUP)
    clear_accounts = [
        acc for acc in (accounts.get("710.20"), accounts.get("621.01")) if acc
    ]
    if not rm_groups or not clear_accounts:
        return []

    rows = frappe.get_all(
        "Item Default",
        filters={
            "parenttype": "Item Group",
            "parent": ["in", rm_groups],
            "company": company,
            "expense_account": ["in", clear_accounts],
        },
        fields=["name", "parent", "expense_account"],
        order_by="parent asc",
    )

    cleared = []
    for row in rows:
        cleared.append(
            {
                "item_group": row.parent,
                "item_default": row.name,
                "from": row.expense_account,
                "to": None,
            }
        )
        if not dry_run:
            frappe.db.set_value("Item Default", row.name, "expense_account", None)
    return cleared


def _clear_cross_company_row_links(row, company: str) -> None:
    """Clear auto-filled link defaults on a new Item Default row if they belong to another company."""
    for doctype, fieldname in (
        ("Warehouse", "default_warehouse"),
        ("Cost Center", "buying_cost_center"),
        ("Cost Center", "selling_cost_center"),
        ("Account", "income_account"),
        ("Account", "default_discount_account"),
        ("Account", "deferred_expense_account"),
        ("Account", "deferred_revenue_account"),
    ):
        if fieldname not in row.dont_update_if_missing:
            row.dont_update_if_missing.append(fieldname)
        linked_val = row.get(fieldname)
        if not linked_val:
            continue
        linked_company = frappe.db.get_value(doctype, linked_val, "company")
        if linked_company and linked_company != company:
            row.set(fieldname, None)


def _set_finished_goods_item_group_defaults(
    company: str, accounts: dict[str, str | None], dry_run: bool
) -> tuple[list[dict], list[dict]]:
    """Ensure ÜRÜNLER hierarchy Item Defaults point expense_account to 620.01."""
    acc_620 = accounts.get("620.01")
    fg_groups = _get_descendant_item_groups(FINISHED_GOODS_ROOT_GROUP)
    if not fg_groups or not acc_620:
        return ([], [])

    existing_rows = frappe.get_all(
        "Item Default",
        filters={
            "parenttype": "Item Group",
            "parent": ["in", fg_groups],
            "company": company,
        },
        fields=["name", "parent", "expense_account"],
    )
    rows_by_group: dict[str, list] = {}
    for row in existing_rows:
        rows_by_group.setdefault(row.parent, []).append(row)

    updated = []
    appended = []
    for group_name in fg_groups:
        group_rows = rows_by_group.get(group_name, [])
        if group_rows:
            for row in group_rows:
                if (row.expense_account or "") != acc_620:
                    updated.append(
                        {
                            "item_group": group_name,
                            "item_default": row.name,
                            "from": row.expense_account,
                            "to": acc_620,
                        }
                    )
                    if not dry_run:
                        frappe.db.set_value(
                            "Item Default", row.name, "expense_account", acc_620
                        )
        else:
            appended.append({"item_group": group_name, "from": None, "to": acc_620})
            if not dry_run:
                ig_doc = frappe.get_doc("Item Group", group_name)
                new_row = ig_doc.append(
                    "item_group_defaults",
                    {"company": company, "expense_account": acc_620},
                )
                _clear_cross_company_row_links(new_row, company)
                ig_doc.save(ignore_permissions=True)

    return (updated, appended)


def fix_accounting_master_defaults(
    company: str | None = None, dry_run: bool = False
) -> dict:
    """Fix Company and Item Group accounting defaults for perpetual inventory companies."""
    target_companies = _get_target_companies(company)
    summary = {
        "dry_run": bool(dry_run),
        "companies": {},
        "total_company_fields_updated": 0,
        "total_rm_defaults_cleared": 0,
        "total_fg_defaults_updated": 0,
        "total_fg_defaults_appended": 0,
    }

    for comp in target_companies:
        accounts = _resolve_company_accounts(comp)
        comp_updates = _fix_company_defaults(comp, accounts, dry_run=dry_run)
        rm_cleared = _clear_raw_material_item_group_defaults(
            comp, accounts, dry_run=dry_run
        )
        fg_updated, fg_appended = _set_finished_goods_item_group_defaults(
            comp, accounts, dry_run=dry_run
        )

        summary["companies"][comp] = {
            "accounts": accounts,
            "company_defaults_updated": comp_updates,
            "rm_defaults_cleared_count": len(rm_cleared),
            "rm_defaults_cleared": rm_cleared,
            "fg_defaults_updated_count": len(fg_updated),
            "fg_defaults_updated": fg_updated,
            "fg_defaults_appended_count": len(fg_appended),
            "fg_defaults_appended": fg_appended,
        }
        summary["total_company_fields_updated"] += len(comp_updates)
        summary["total_rm_defaults_cleared"] += len(rm_cleared)
        summary["total_fg_defaults_updated"] += len(fg_updated)
        summary["total_fg_defaults_appended"] += len(fg_appended)

    if not dry_run:
        frappe.clear_cache()

    return summary


def execute() -> None:
    """Patch entrypoint: apply accounting master default fixes idempotently."""
    result = fix_accounting_master_defaults(dry_run=False)
    print(
        "[fix_accounting_master_defaults] "
        f"companies={len(result['companies'])} "
        f"company_fields={result['total_company_fields_updated']} "
        f"rm_cleared={result['total_rm_defaults_cleared']} "
        f"fg_updated={result['total_fg_defaults_updated']} "
        f"fg_appended={result['total_fg_defaults_appended']}"
    )
