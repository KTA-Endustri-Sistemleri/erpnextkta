import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import add_days, cint, flt, getdate

from erpnextkta.overrides.company_wip_validation import (
    ensure_journal_entry_work_order_field,
    get_validated_wip_consumption_account,
)

DEFAULT_FROM_DATE = "2026-11-23"
DEFAULT_WIP_PARENT_NUMBER = "151.01"
DEFAULT_WIP_ACCOUNT_NUMBER = "151.01.002"
DEFAULT_WIP_ACCOUNT_NAME = "ÜRETİM SÜRECİNDEKİ TÜKETİMLER (WIP)"


def ensure_company_wip_field() -> None:
    """Idempotently create Company.custom_wip_consumption_account custom field."""
    custom_fields = {
        "Company": [
            {
                "fieldname": "custom_wip_consumption_account",
                "label": "WIP Consumption Account",
                "fieldtype": "Link",
                "options": "Account",
                "insert_after": "stock_adjustment_account",
                "module": "erpnextkta",
                "description": (
                    "Non-Stock balance sheet account used as Difference Account for "
                    "Work Order Material Consumption and FG-only Manufacture entries."
                ),
            }
        ]
    }
    create_custom_fields(custom_fields, ignore_validate=True)
    frappe.clear_cache(doctype="Company")


def ensure_default_wip_account(company: str) -> str | None:
    """Create and link default 151.01.002 WIP account for company if 151.01 group exists."""
    if not frappe.db.has_column("Company", "custom_wip_consumption_account"):
        ensure_company_wip_field()

    existing_valid = get_validated_wip_consumption_account(company)
    if existing_valid:
        return existing_valid

    parent_151_01 = frappe.db.get_value(
        "Account",
        {
            "company": company,
            "account_number": DEFAULT_WIP_PARENT_NUMBER,
            "is_group": 1,
        },
        "name",
    )
    if not parent_151_01:
        return None

    wip_acc = frappe.db.get_value(
        "Account",
        {"company": company, "account_number": DEFAULT_WIP_ACCOUNT_NUMBER},
        ["name", "is_group", "account_type", "company"],
        as_dict=True,
    )
    if not wip_acc:
        wip_acc = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "parent_account": parent_151_01,
                "account_name": DEFAULT_WIP_ACCOUNT_NAME,
            },
            ["name", "is_group", "account_type", "company"],
            as_dict=True,
        )

    if not wip_acc:
        acc_doc = frappe.get_doc(
            {
                "doctype": "Account",
                "company": company,
                "account_name": DEFAULT_WIP_ACCOUNT_NAME,
                "account_number": DEFAULT_WIP_ACCOUNT_NUMBER,
                "parent_account": parent_151_01,
                "root_type": "Asset",
                "account_type": "",
                "is_group": 0,
            }
        )
        acc_doc.insert(ignore_permissions=True)
        wip_acc = frappe._dict(
            {
                "name": acc_doc.name,
                "is_group": acc_doc.is_group,
                "account_type": acc_doc.account_type,
                "company": acc_doc.company,
            }
        )

    if cint(wip_acc.is_group) or (wip_acc.account_type or "") == "Stock":
        frappe.throw(
            _(
                "Default WIP account {0} for Company {1} cannot be a Group or Stock-type account."
            ).format(frappe.bold(wip_acc.name), frappe.bold(company)),
            frappe.ValidationError,
        )

    frappe.db.set_value(
        "Company", company, "custom_wip_consumption_account", wip_acc.name
    )
    return wip_acc.name


def get_min_editable_posting_date(
    company: str, from_date: str = DEFAULT_FROM_DATE
) -> tuple[str, bool]:
    """Return (effective_from_date, was_clamped) respecting period closing and freeze date."""
    closed_res = frappe.db.sql(
        """
        SELECT MAX(period_end_date)
        FROM `tabPeriod Closing Voucher`
        WHERE docstatus = 1
          AND company = %s
        """,
        (company,),
    )
    closed_date = closed_res[0][0] if closed_res and closed_res[0] else None
    frozen_date = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")

    lock_dates = []
    for raw_date in (closed_date, frozen_date):
        if raw_date and str(raw_date).strip() not in ("", "None", "0000-00-00"):
            parsed = getdate(raw_date)
            if parsed:
                lock_dates.append(parsed)
    locked_upto = max(lock_dates) if lock_dates else None

    target_from = getdate(from_date)
    if locked_upto and locked_upto >= target_from:
        return (str(add_days(locked_upto, 1)), True)

    return (str(target_from), False)


def _resolve_candidate_wip_account(company: str, dry_run: bool) -> str | None:
    """Resolve configured WIP account, or preview candidate 151.01.002 during dry-run."""
    wip_account = get_validated_wip_consumption_account(company)
    if wip_account:
        return wip_account

    if not dry_run:
        return None

    existing = frappe.db.get_value(
        "Account",
        {"company": company, "account_number": DEFAULT_WIP_ACCOUNT_NUMBER},
        ["name", "is_group", "account_type"],
        as_dict=True,
    )
    if (
        existing
        and not cint(existing.is_group)
        and (existing.account_type or "") != "Stock"
    ):
        return existing.name

    has_parent = frappe.db.exists(
        "Account",
        {
            "company": company,
            "account_number": DEFAULT_WIP_PARENT_NUMBER,
            "is_group": 1,
        },
    )
    if not has_parent:
        return None

    abbr = frappe.db.get_value("Company", company, "abbr")
    if abbr:
        return f"{DEFAULT_WIP_ACCOUNT_NUMBER} - {DEFAULT_WIP_ACCOUNT_NAME} - {abbr}"
    return f"{DEFAULT_WIP_ACCOUNT_NUMBER} - {DEFAULT_WIP_ACCOUNT_NAME}"


def _find_candidate_stock_entries(
    company: str, effective_from_date: str, stock_adjustment_account: str
) -> list[str]:
    """Return submitted Work Order consumption and FG-only Manufacture entries using stock_adjustment_account."""
    rows = frappe.db.sql(
        """
        SELECT se.name
        FROM `tabStock Entry` se
        WHERE se.docstatus = 1
          AND se.company = %s
          AND se.posting_date >= %s
          AND se.work_order IS NOT NULL
          AND se.work_order != ''
          AND (
            se.purpose = 'Material Consumption for Manufacture'
            OR (
              se.purpose = 'Manufacture'
              AND COALESCE(se.total_outgoing_value, 0) = 0
              AND NOT EXISTS (
                SELECT 1
                FROM `tabStock Entry Detail` sed
                WHERE sed.parent = se.name
                  AND IFNULL(sed.s_warehouse, '') != ''
              )
              AND EXISTS (
                SELECT 1
                FROM `tabStock Entry` mc
                WHERE mc.docstatus = 1
                  AND mc.work_order = se.work_order
                  AND mc.purpose = 'Material Consumption for Manufacture'
              )
            )
          )
          AND EXISTS (
            SELECT 1
            FROM `tabGL Entry` gl
            WHERE gl.voucher_type = 'Stock Entry'
              AND gl.voucher_no = se.name
              AND gl.is_cancelled = 0
              AND gl.account = %s
          )
        ORDER BY se.posting_date ASC, se.creation ASC
        """,
        (company, effective_from_date, stock_adjustment_account),
        pluck=True,
    )
    return list(rows or [])


def _get_voucher_account_totals(
    voucher_names: list[str], account: str
) -> tuple[float, float]:
    """Return (total_debit, total_credit) on account across given Stock Entry vouchers."""
    if not voucher_names:
        return (0.0, 0.0)

    placeholders = ", ".join(["%s"] * len(voucher_names))
    res = frappe.db.sql(
        f"""
        SELECT
            COALESCE(SUM(COALESCE(debit, 0)), 0),
            COALESCE(SUM(COALESCE(credit, 0)), 0)
        FROM `tabGL Entry`
        WHERE voucher_type = 'Stock Entry'
          AND is_cancelled = 0
          AND account = %s
          AND voucher_no IN ({placeholders})
        """,
        (account, *voucher_names),
    )
    if not res or not res[0]:
        return (0.0, 0.0)
    return (flt(res[0][0]), flt(res[0][1]))


def _replace_against_account(against: str, old_account: str, new_account: str) -> str:
    """Replace old_account token inside comma-separated GL Entry.against string."""
    tokens = [token.strip() for token in against.split(",")]
    if old_account not in tokens:
        return against
    replaced = [new_account if token == old_account else token for token in tokens]
    return ", ".join(replaced)


def _reclassify_single_voucher(
    se_name: str, stock_adjustment_account: str, wip_account: str
) -> tuple[float, float]:
    """Move a single Stock Entry's Stock Entry Detail and GL Entry rows inside a savepoint."""
    debit_amt, credit_amt = _get_voucher_account_totals(
        [se_name], stock_adjustment_account
    )

    sp = f"wip_bf_{frappe.generate_hash(length=8)}"
    frappe.db.savepoint(sp)
    try:
        frappe.db.sql(
            """
            UPDATE `tabStock Entry Detail`
            SET expense_account = %s
            WHERE parent = %s
              AND expense_account = %s
            """,
            (wip_account, se_name, stock_adjustment_account),
        )

        frappe.db.sql(
            """
            UPDATE `tabGL Entry`
            SET account = %s
            WHERE voucher_type = 'Stock Entry'
              AND voucher_no = %s
              AND is_cancelled = 0
              AND account = %s
            """,
            (wip_account, se_name, stock_adjustment_account),
        )

        gl_rows = frappe.db.sql(
            """
            SELECT name, against
            FROM `tabGL Entry`
            WHERE voucher_type = 'Stock Entry'
              AND voucher_no = %s
              AND is_cancelled = 0
              AND COALESCE(against, '') != ''
            """,
            (se_name,),
            as_dict=True,
        )
        for row in gl_rows:
            new_against = _replace_against_account(
                row.against, stock_adjustment_account, wip_account
            )
            if new_against != row.against:
                frappe.db.sql(
                    """
                    UPDATE `tabGL Entry`
                    SET against = %s
                    WHERE name = %s
                    """,
                    (new_against, row.name),
                )

        bal_res = frappe.db.sql(
            """
            SELECT ABS(COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0))
            FROM `tabGL Entry`
            WHERE voucher_type = 'Stock Entry'
              AND voucher_no = %s
              AND is_cancelled = 0
            """,
            (se_name,),
        )
        diff = flt(bal_res[0][0]) if bal_res and bal_res[0] else 0.0
        if diff >= 0.01:
            raise frappe.ValidationError(
                f"GL balance mismatch ({diff}) after backfilling Stock Entry {se_name}"
            )

        frappe.db.release_savepoint(sp)
        return (debit_amt, credit_amt)
    except Exception:
        frappe.db.rollback(save_point=sp)
        raise


def backfill_shopfloor_wip_entries(
    company: str | None = None,
    from_date: str = DEFAULT_FROM_DATE,
    dry_run: bool = False,
) -> dict:
    """Backfill open-period shopfloor Stock Entries from stock_adjustment_account to WIP account."""
    target_companies = (
        [company]
        if company
        else frappe.get_all(
            "Company",
            filters=[["name", "not like", "_Test%"]],
            pluck="name",
        )
    )

    summary = {
        "dry_run": bool(dry_run),
        "companies": {},
        "matched_vouchers": 0,
        "updated_vouchers": 0,
        "total_debit_moved": 0.0,
        "total_credit_moved": 0.0,
        "net_wip_moved": 0.0,
        "errors": [],
    }

    for comp in target_companies:
        wip_account = _resolve_candidate_wip_account(comp, dry_run=dry_run)
        stock_adjustment_account = frappe.db.get_value(
            "Company", comp, "stock_adjustment_account"
        )

        if (
            not stock_adjustment_account
            or not wip_account
            or wip_account == stock_adjustment_account
        ):
            summary["companies"][comp] = {
                "wip_account": wip_account,
                "stock_adjustment_account": stock_adjustment_account,
                "matched_vouchers": 0,
                "updated_vouchers": 0,
                "total_debit_moved": 0.0,
                "total_credit_moved": 0.0,
                "net_wip_moved": 0.0,
                "skipped": True,
            }
            continue

        effective_from_date, clamped = get_min_editable_posting_date(comp, from_date)
        matched_names = _find_candidate_stock_entries(
            comp, effective_from_date, stock_adjustment_account
        )
        matched_debit, matched_credit = _get_voucher_account_totals(
            matched_names, stock_adjustment_account
        )

        comp_updated = 0
        comp_debit_moved = matched_debit if dry_run else 0.0
        comp_credit_moved = matched_credit if dry_run else 0.0

        if not dry_run:
            for se_name in matched_names:
                try:
                    d_amt, c_amt = _reclassify_single_voucher(
                        se_name, stock_adjustment_account, wip_account
                    )
                    comp_updated += 1
                    comp_debit_moved += d_amt
                    comp_credit_moved += c_amt
                except (frappe.ValidationError, OSError) as exc:
                    summary["errors"].append(
                        {"company": comp, "voucher_no": se_name, "error": str(exc)}
                    )
                except Exception as exc:  # noqa: BLE001
                    summary["errors"].append(
                        {"company": comp, "voucher_no": se_name, "error": str(exc)}
                    )

        comp_net = flt(comp_debit_moved - comp_credit_moved)
        summary["companies"][comp] = {
            "wip_account": wip_account,
            "stock_adjustment_account": stock_adjustment_account,
            "effective_from_date": effective_from_date,
            "clamped_by_lock": clamped,
            "matched_vouchers": len(matched_names),
            "updated_vouchers": comp_updated,
            "voucher_names": matched_names,
            "total_debit_moved": flt(comp_debit_moved),
            "total_credit_moved": flt(comp_credit_moved),
            "net_wip_moved": comp_net,
            "skipped": False,
        }

        summary["matched_vouchers"] += len(matched_names)
        summary["updated_vouchers"] += comp_updated
        summary["total_debit_moved"] = flt(
            summary["total_debit_moved"] + comp_debit_moved
        )
        summary["total_credit_moved"] = flt(
            summary["total_credit_moved"] + comp_credit_moved
        )

    summary["net_wip_moved"] = flt(
        summary["total_debit_moved"] - summary["total_credit_moved"]
    )
    return summary


def execute() -> None:
    """Patch entrypoint: add WIP field, create default WIP account, and backfill open entries."""
    ensure_company_wip_field()
    ensure_journal_entry_work_order_field()
    companies = frappe.get_all(
        "Company",
        filters=[["name", "not like", "_Test%"]],
        pluck="name",
    )
    for company in companies:
        ensure_default_wip_account(company)

    backfill_shopfloor_wip_entries(dry_run=False)
