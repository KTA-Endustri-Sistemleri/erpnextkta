from __future__ import annotations

import frappe
from frappe.utils import cint, flt, getdate, nowdate

from erpnextkta.kta_shopfloor.report.kta_wip_valuation_report.kta_wip_valuation_report import (
    _build_level_0_rows,
    _fetch_wip_gl_rows,
)
from erpnextkta.overrides.company_wip_validation import (
    ensure_journal_entry_work_order_field,
    get_validated_wip_consumption_account,
)
from erpnextkta.patches.v4_6.backfill_shopfloor_wip_account import (
    get_min_editable_posting_date,
)

DRIFT_TAG = "[KTA-WIP-DRIFT-RECON]"
SCRAP_TAG = "[KTA-WIP-SCRAP-RECON]"
SCRAP_ACCOUNT_NUMBER = "710.001"


def _get_target_companies(company: str | None) -> list[dict]:
    """Return eligible perpetual-inventory companies with validated WIP and adjustment accounts."""
    if company:
        candidates = [company]
    else:
        candidates = frappe.get_all(
            "Company",
            filters=[
                ["name", "not like", "_Test%"],
                ["enable_perpetual_inventory", "=", 1],
            ],
            pluck="name",
        )

    targets: list[dict] = []
    for comp in candidates:
        perpetual = cint(
            frappe.db.get_value("Company", comp, "enable_perpetual_inventory")
        )
        if not perpetual:
            continue
        wip_account = get_validated_wip_consumption_account(comp)
        adj_account = frappe.db.get_value("Company", comp, "stock_adjustment_account")
        if not wip_account or not adj_account or wip_account == adj_account:
            continue
        default_cc = frappe.db.get_value(
            "Company", comp, "cost_center"
        ) or frappe.db.get_value(
            "Cost Center",
            {"company": comp, "is_group": 0, "disabled": 0},
            "name",
        )
        targets.append(
            {
                "company": comp,
                "wip_account": wip_account,
                "adj_account": adj_account,
                "cost_center": default_cc,
                "currency": (
                    frappe.get_cached_value("Company", comp, "default_currency")
                    or "TRY"
                ),
            }
        )
    return targets


def _resolve_scrap_expense_account(company: str, fallback_account: str) -> str:
    """Return leaf 710.001 scrap expense account for company, or fallback_account."""
    scrap_acc = frappe.db.get_value(
        "Account",
        {
            "company": company,
            "is_group": 0,
            "account_number": SCRAP_ACCOUNT_NUMBER,
        },
        "name",
    )
    return scrap_acc or fallback_account


def _get_wo_consumption_sed_vs_sle(
    work_order: str, as_of_date: str
) -> tuple[float, float]:
    """Return (sed_total, sle_total) for submitted Material Consumption entries of a Work Order."""
    res = frappe.db.sql(
        """
        SELECT
            COALESCE(
                SUM(COALESCE(sed.valuation_rate, 0) * COALESCE(sed.transfer_qty, 0)),
                0
            ) AS sed_total,
            COALESCE(
                SUM(
                    COALESCE(
                        sle_agg.sle_val,
                        COALESCE(sed.valuation_rate, 0) * COALESCE(sed.transfer_qty, 0)
                    )
                ),
                0
            ) AS sle_total
        FROM `tabStock Entry` entry
        INNER JOIN `tabStock Entry Detail` sed ON sed.parent = entry.name
        LEFT JOIN (
            SELECT
                sle.voucher_detail_no,
                SUM(-COALESCE(sle.stock_value_difference, 0)) AS sle_val
            FROM `tabStock Ledger Entry` sle
            INNER JOIN `tabStock Entry` se_sle ON se_sle.name = sle.voucher_no
            WHERE sle.voucher_type = 'Stock Entry'
              AND sle.is_cancelled = 0
              AND se_sle.work_order = %s
              AND se_sle.purpose = 'Material Consumption for Manufacture'
              AND se_sle.docstatus = 1
              AND se_sle.posting_date <= %s
            GROUP BY sle.voucher_detail_no
        ) sle_agg ON sle_agg.voucher_detail_no = sed.name
        WHERE entry.work_order = %s
          AND entry.purpose = 'Material Consumption for Manufacture'
          AND entry.docstatus = 1
          AND entry.posting_date <= %s
          AND IFNULL(sed.s_warehouse, '') != ''
        """,
        (work_order, as_of_date, work_order, as_of_date),
    )
    if not res or not res[0]:
        return (0.0, 0.0)
    return (flt(res[0][0]), flt(res[0][1]))


def _has_existing_reconcile_je(
    company: str, work_order: str, wip_account: str, tag: str
) -> bool:
    """Return True if a submitted reconciliation JE with tag already exists for Work Order."""
    res = frappe.db.sql(
        """
        SELECT 1
        FROM `tabJournal Entry Account` jea
        INNER JOIN `tabJournal Entry` je ON je.name = jea.parent
        WHERE je.docstatus = 1
          AND je.company = %s
          AND jea.custom_work_order = %s
          AND jea.account = %s
          AND COALESCE(je.user_remark, '') LIKE %s
        LIMIT 1
        """,
        (company, work_order, wip_account, f"%{tag}%"),
    )
    return bool(res)


def _reconcile_step1_drift(
    comp_ctx: dict,
    as_of_date: str,
    posting_date: str,
    dry_run: bool,
) -> tuple[dict, set[str]]:
    """Step 1: Reconcile SLE-vs-SED valuation drift on eligible Work Orders via one Journal Entry."""
    company = comp_ctx["company"]
    wip_account = comp_ctx["wip_account"]
    adj_account = comp_ctx["adj_account"]
    cost_center = comp_ctx["cost_center"]
    currency = comp_ctx["currency"]

    raw_rows = _fetch_wip_gl_rows(
        company=company,
        as_of_date=as_of_date,
        wip_account=wip_account,
        adjustment_account=adj_account,
    )
    open_rows = _build_level_0_rows(
        raw_rows=raw_rows,
        company_currency=currency,
        only_open_wip=1,
    )

    wo_accounts: list[dict] = []
    step1_wo_names: set[str] = set()

    for row in open_rows:
        wo_name = row["work_order"]
        wip_balance = flt(row.get("wip_balance"), 2)
        wo_status = row.get("wo_status") or ""

        if abs(wip_balance) <= 0.01:
            continue
        if not (
            wo_status in ("Completed", "Closed")
            or (wo_status == "In Process" and wip_balance < -0.01)
        ):
            continue

        sed_total, sle_total = _get_wo_consumption_sed_vs_sle(wo_name, as_of_date)
        sle_sed_drift = flt(sle_total - sed_total, 2)
        if abs(sle_sed_drift) <= 0.01:
            continue
        if abs(wip_balance - sle_sed_drift) > 0.10:
            continue
        if _has_existing_reconcile_je(company, wo_name, wip_account, DRIFT_TAG):
            continue

        step1_wo_names.add(wo_name)
        amt = abs(wip_balance)
        wo_accounts.append(
            {
                "account": wip_account,
                "custom_work_order": wo_name,
                "cost_center": cost_center,
                "debit_in_account_currency": amt if wip_balance < 0 else 0.0,
                "credit_in_account_currency": amt if wip_balance > 0 else 0.0,
                "wip_balance": wip_balance,
                "sle_sed_drift": sle_sed_drift,
            }
        )

    if not wo_accounts:
        return (
            {
                "would_create": False,
                "journal_entry": None,
                "work_orders": [],
                "rows": [],
                "net_amount": 0.0,
            },
            step1_wo_names,
        )

    total_debit = sum(flt(r["debit_in_account_currency"]) for r in wo_accounts)
    total_credit = sum(flt(r["credit_in_account_currency"]) for r in wo_accounts)
    net_diff = flt(total_debit - total_credit, 2)

    je_rows = [
        {
            "account": r["account"],
            "custom_work_order": r["custom_work_order"],
            "cost_center": r["cost_center"],
            "debit_in_account_currency": r["debit_in_account_currency"],
            "credit_in_account_currency": r["credit_in_account_currency"],
        }
        for r in wo_accounts
    ]
    if abs(net_diff) > 0:
        je_rows.append(
            {
                "account": adj_account,
                "custom_work_order": None,
                "cost_center": cost_center,
                "debit_in_account_currency": abs(net_diff) if net_diff < 0 else 0.0,
                "credit_in_account_currency": net_diff if net_diff > 0 else 0.0,
            }
        )

    step1_result = {
        "would_create": bool(dry_run),
        "journal_entry": None,
        "posting_date": posting_date,
        "work_orders": [r["custom_work_order"] for r in wo_accounts],
        "rows": wo_accounts,
        "net_amount": net_diff,
    }

    if not dry_run:
        je = frappe.get_doc(
            {
                "doctype": "Journal Entry",
                "company": company,
                "posting_date": posting_date,
                "voucher_type": "Journal Entry",
                "user_remark": (
                    f"{DRIFT_TAG} Shopfloor WIP SLE-vs-SED valuation drift clearance"
                ),
                "accounts": je_rows,
            }
        )
        je.insert(ignore_permissions=True)
        je.submit()
        step1_result["journal_entry"] = je.name

    return step1_result, step1_wo_names


def _run_step2_closed_wo_scrap_writeoff(
    comp_ctx: dict,
    as_of_date: str,
    posting_date: str,
    step1_wo_names: set[str],
    dry_run: bool,
) -> dict:
    """Step 2: Write off remaining excess WIP on Closed Work Orders to scrap expense account."""
    company = comp_ctx["company"]
    wip_account = comp_ctx["wip_account"]
    adj_account = comp_ctx["adj_account"]
    cost_center = comp_ctx["cost_center"]
    currency = comp_ctx["currency"]
    scrap_account = _resolve_scrap_expense_account(company, adj_account)

    raw_rows = _fetch_wip_gl_rows(
        company=company,
        as_of_date=as_of_date,
        wip_account=wip_account,
        adjustment_account=adj_account,
        wo_status="Closed",
    )
    closed_open_rows = _build_level_0_rows(
        raw_rows=raw_rows,
        company_currency=currency,
        only_open_wip=1,
    )

    wo_accounts: list[dict] = []
    for row in closed_open_rows:
        wo_name = row["work_order"]
        wip_balance = flt(row.get("wip_balance"), 2)
        if wip_balance <= 0.01 or wo_name in step1_wo_names:
            continue
        if _has_existing_reconcile_je(company, wo_name, wip_account, SCRAP_TAG):
            continue

        wo_accounts.append(
            {
                "account": wip_account,
                "custom_work_order": wo_name,
                "cost_center": cost_center,
                "debit_in_account_currency": 0.0,
                "credit_in_account_currency": wip_balance,
                "user_remark": f"{SCRAP_TAG} Closed WO scrap/fire write-off ({wo_name})",
                "wip_balance": wip_balance,
            }
        )

    if not wo_accounts:
        return {
            "would_create": False,
            "journal_entry": None,
            "scrap_account": scrap_account,
            "work_orders": [],
            "rows": [],
            "net_amount": 0.0,
        }

    total_amount = flt(
        sum(flt(r["credit_in_account_currency"]) for r in wo_accounts), 2
    )
    je_rows = [
        {
            "account": r["account"],
            "custom_work_order": r["custom_work_order"],
            "cost_center": r["cost_center"],
            "debit_in_account_currency": 0.0,
            "credit_in_account_currency": r["credit_in_account_currency"],
            "user_remark": r["user_remark"],
        }
        for r in wo_accounts
    ]
    je_rows.append(
        {
            "account": scrap_account,
            "custom_work_order": None,
            "cost_center": cost_center,
            "debit_in_account_currency": total_amount,
            "credit_in_account_currency": 0.0,
        }
    )

    step2_result = {
        "would_create": bool(dry_run),
        "journal_entry": None,
        "posting_date": posting_date,
        "scrap_account": scrap_account,
        "work_orders": [r["custom_work_order"] for r in wo_accounts],
        "rows": wo_accounts,
        "net_amount": total_amount,
    }

    if not dry_run:
        je = frappe.get_doc(
            {
                "doctype": "Journal Entry",
                "company": company,
                "posting_date": posting_date,
                "voucher_type": "Journal Entry",
                "user_remark": (
                    f"{SCRAP_TAG} Closed Work Order excess WIP scrap/fire write-off"
                ),
                "accounts": je_rows,
            }
        )
        je.insert(ignore_permissions=True)
        je.submit()
        step2_result["journal_entry"] = je.name

    return step2_result


def reconcile_shopfloor_wip_discrepancies(
    company: str | None = None,
    dry_run: bool = False,
    as_of_date: str | None = None,
) -> dict:
    """Reconcile shopfloor WIP SLE-vs-SED drift and Closed WO excess scrap/fire write-off."""
    ensure_journal_entry_work_order_field()
    effective_as_of = str(getdate(as_of_date or nowdate()))

    targets = _get_target_companies(company)
    summary: dict = {
        "dry_run": bool(dry_run),
        "as_of_date": effective_as_of,
        "companies": {},
        "step1_journal_entries": 0,
        "step2_journal_entries": 0,
    }

    for comp_ctx in targets:
        comp = comp_ctx["company"]
        min_editable_date, _ = get_min_editable_posting_date(comp)
        posting_date = str(max(getdate(effective_as_of), getdate(min_editable_date)))

        step1_res, step1_wo_names = _reconcile_step1_drift(
            comp_ctx=comp_ctx,
            as_of_date=effective_as_of,
            posting_date=posting_date,
            dry_run=dry_run,
        )
        step2_res = _run_step2_closed_wo_scrap_writeoff(
            comp_ctx=comp_ctx,
            as_of_date=effective_as_of,
            posting_date=posting_date,
            step1_wo_names=step1_wo_names,
            dry_run=dry_run,
        )

        summary["companies"][comp] = {
            "posting_date": posting_date,
            "step1": step1_res,
            "step2": step2_res,
        }
        if step1_res.get("journal_entry"):
            summary["step1_journal_entries"] += 1
        if step2_res.get("journal_entry"):
            summary["step2_journal_entries"] += 1

    return summary


def execute() -> None:
    """Patch entrypoint: apply dynamic shopfloor WIP drift and Closed WO scrap write-off."""
    reconcile_shopfloor_wip_discrepancies(dry_run=False)
