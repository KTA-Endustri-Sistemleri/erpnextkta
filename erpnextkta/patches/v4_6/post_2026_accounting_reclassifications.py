import frappe
from erpnext.accounts.utils import get_fiscal_year, get_fiscal_years
from erpnext.stock.utils import get_stock_value_on
from frappe.utils import flt, getdate, nowdate

from erpnextkta.patches.v4_6.backfill_shopfloor_wip_account import (
    get_min_editable_posting_date,
)

ACCOUNT_NUMBERS = (
    "150.01.001",
    "150.01.004",
    "197.01.001",
    "620.01",
    "621.01",
    "710.20",
)

STEP_SPECS = {
    "step_1_1501_wh": {
        "tag": "[KTA-RECLASS-2026-1501-WH]",
        "legacy_prefix": "1501 KESMELER - KTA depo muhasebe hesabı değişikliği devir virmanı",
        "remark": "[KTA-RECLASS-2026-1501-WH] Child stock warehouse account migration transfer (150.01.001 -> 150.01.004)",
    },
    "step_2_mfg_mirror": {
        "tag": "[KTA-RECLASS-2026-MFG-MIRROR]",
        "legacy_prefix": "2026 eski klasik Manufacture fişleri 710.20 <-> 197.01.001",
        "remark": "[KTA-RECLASS-2026-MFG-MIRROR] 2026 classic Manufacture 710.20 <-> 197.01.001 mirror offset",
    },
    "step_3_mt_janfeb": {
        "tag": "[KTA-RECLASS-2026-MT-JANFEB]",
        "legacy_prefix": "2026 Ocak-Şubat hesapsız raf (W1x) Material Transfer düzeltme virmanı",
        "remark": "[KTA-RECLASS-2026-MT-JANFEB] 2026 Jan-Feb unmapped shelf Material Transfer correction (710.20 -> 150.01.001)",
    },
    "step_4_dn_710": {
        "tag": "[KTA-RECLASS-2026-DN-710]",
        "legacy_prefix": "2026 Delivery Note hammadde satış maliyeti SMM sınıflandırma mahsubu",
        "remark": "[KTA-RECLASS-2026-DN-710] 2026 Delivery Note raw material COGS reclassification (710.20 -> 621.01)",
    },
    "step_5_dn_income": {
        "tag": "[KTA-RECLASS-2026-DN-INCOME]",
        "legacy_prefix": "2026 Delivery Note 600/601 gelir hesaplarına yazılan mamul SMM",
        "remark": "[KTA-RECLASS-2026-DN-INCOME] 2026 Delivery Note income-posted finished goods COGS reclassification (-> 620.01)",
    },
}


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


def _resolve_company_context(company: str) -> dict:
    """Resolve leaf accounts, default cost center, and default currency for company."""
    rows = frappe.get_all(
        "Account",
        filters={
            "company": company,
            "is_group": 0,
            "account_number": ["in", list(ACCOUNT_NUMBERS)],
        },
        fields=["name", "account_number"],
    )
    accounts = {num: None for num in ACCOUNT_NUMBERS}
    for row in rows:
        accounts[row.account_number] = row.name

    comp_info = (
        frappe.db.get_value(
            "Company", company, ["cost_center", "default_currency"], as_dict=True
        )
        or frappe._dict()
    )
    cost_center = comp_info.get("cost_center")
    if not cost_center or frappe.db.get_value("Cost Center", cost_center, "is_group"):
        cost_center = frappe.db.get_value(
            "Cost Center", {"company": company, "is_group": 0}, "name"
        )

    return {
        "accounts": accounts,
        "cost_center": cost_center,
        "company_currency": comp_info.get("default_currency") or "TRY",
    }


def _resolve_effective_posting_date(
    company: str, posting_date: str | None
) -> tuple[str, bool, str | None]:
    """Resolve an editable posting_date clamped for locks and residing in an active Fiscal Year."""
    base_date = posting_date or nowdate()
    eff_date, clamped_by_lock = get_min_editable_posting_date(
        company, from_date=base_date
    )
    if get_fiscal_year(eff_date, company=company, verbose=0, boolean=True):
        return (eff_date, clamped_by_lock, None)

    fiscal_years = get_fiscal_years(company=company) or []
    if not fiscal_years:
        return (eff_date, clamped_by_lock, "No active Fiscal Year found")

    eff_dt = getdate(eff_date)
    future_fys = [fy for fy in fiscal_years if getdate(fy.year_end_date) >= eff_dt]
    if future_fys:
        target_fy = min(future_fys, key=lambda fy: getdate(fy.year_start_date))
        candidate = str(target_fy.year_start_date)
    else:
        latest_fy = max(fiscal_years, key=lambda fy: getdate(fy.year_end_date))
        candidate = str(latest_fy.year_end_date)

    checked_date, lock_hit = get_min_editable_posting_date(company, from_date=candidate)
    if lock_hit or not get_fiscal_year(
        checked_date, company=company, verbose=0, boolean=True
    ):
        return (
            eff_date,
            clamped_by_lock,
            f"No editable Fiscal Year covers posting date {eff_date}",
        )

    return (checked_date, clamped_by_lock or checked_date != base_date, None)


def _find_existing_step_je(company: str, tag: str, legacy_prefix: str) -> str | None:
    """Return existing submitted Journal Entry matching step tag or legacy prefix."""
    rows = frappe.db.sql(
        """
        SELECT name
        FROM `tabJournal Entry`
        WHERE docstatus = 1
          AND company = %s
          AND (
            user_remark LIKE %s
            OR user_remark LIKE %s
          )
        ORDER BY creation ASC
        LIMIT 1
        """,
        (company, f"%{tag}%", f"{legacy_prefix}%"),
        pluck=True,
    )
    return rows[0] if rows else None


def _submit_simple_je(
    company: str,
    posting_date: str,
    cost_center: str | None,
    debit_account: str,
    credit_account: str,
    amount: float,
    user_remark: str,
) -> str:
    """Create and submit a balanced 2-line Journal Entry in company currency."""
    amt = flt(amount, 2)
    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.company = company
    je.posting_date = posting_date
    je.user_remark = user_remark
    je.append(
        "accounts",
        {
            "account": debit_account,
            "debit_in_account_currency": amt,
            "credit_in_account_currency": 0.0,
            "cost_center": cost_center,
        },
    )
    je.append(
        "accounts",
        {
            "account": credit_account,
            "debit_in_account_currency": 0.0,
            "credit_in_account_currency": amt,
            "cost_center": cost_center,
        },
    )
    je.insert(ignore_permissions=True)
    je.submit()
    return je.name


def _run_step_1_1501_wh(company: str, eff_date: str, ctx: dict, dry_run: bool) -> dict:
    """Step 1: Migrate child 150.01.001 warehouses under 150.01.004 parent and transfer balance."""
    spec = STEP_SPECS["step_1_1501_wh"]
    existing = _find_existing_step_je(company, spec["tag"], spec["legacy_prefix"])
    if existing:
        return {
            "status": "skipped",
            "reason": "already_posted",
            "journal_entry": existing,
        }

    acc_150_1 = ctx["accounts"].get("150.01.001")
    acc_150_4 = ctx["accounts"].get("150.01.004")
    if not acc_150_1 or not acc_150_4:
        return {"status": "skipped", "reason": "missing_accounts"}

    matched_warehouses = list(
        frappe.db.sql(
            """
            SELECT wh.name
            FROM `tabWarehouse` wh
            INNER JOIN `tabWarehouse` pwh ON pwh.name = wh.parent_warehouse
            WHERE wh.company = %s
              AND IFNULL(wh.is_group, 0) = 0
              AND wh.account = %s
              AND pwh.account = %s
            ORDER BY wh.name ASC
            """,
            (company, acc_150_1, acc_150_4),
            pluck=True,
        )
        or []
    )
    if not matched_warehouses:
        return {
            "status": "skipped",
            "reason": "no_matching_warehouses",
            "warehouses": [],
            "amount": 0.0,
        }

    amount = flt(
        sum(
            flt(
                get_stock_value_on(
                    warehouses=wh, posting_date=eff_date, company=company
                )
            )
            for wh in matched_warehouses
        ),
        2,
    )
    if dry_run:
        return {
            "status": "planned",
            "warehouses": matched_warehouses,
            "amount": amount,
        }

    sp = f"kta_1501_{frappe.generate_hash(length=8)}"
    frappe.db.savepoint(sp)
    try:
        for wh_name in matched_warehouses:
            frappe.db.set_value("Warehouse", wh_name, "account", None)
        frappe.clear_cache()

        je_name = None
        if amount > 0.01:
            je_name = _submit_simple_je(
                company=company,
                posting_date=eff_date,
                cost_center=ctx["cost_center"],
                debit_account=acc_150_4,
                credit_account=acc_150_1,
                amount=amount,
                user_remark=spec["remark"],
            )
        frappe.db.release_savepoint(sp)
        return {
            "status": "applied",
            "warehouses": matched_warehouses,
            "amount": amount,
            "journal_entry": je_name,
        }
    except Exception:
        frappe.db.rollback(save_point=sp)
        raise


def _run_step_2_mfg_mirror(
    company: str,
    eff_date: str,
    ctx: dict,
    fiscal_year_start: str,
    fiscal_year_end: str,
    dry_run: bool,
) -> dict:
    """Step 2: Offset classic Manufacture 710.20 <-> 197.01.001 mirror balances."""
    spec = STEP_SPECS["step_2_mfg_mirror"]
    existing = _find_existing_step_je(company, spec["tag"], spec["legacy_prefix"])
    if existing:
        return {
            "status": "skipped",
            "reason": "already_posted",
            "journal_entry": existing,
        }

    acc_197 = ctx["accounts"].get("197.01.001")
    acc_710 = ctx["accounts"].get("710.20")
    if not acc_197 or not acc_710:
        return {"status": "skipped", "reason": "missing_accounts"}

    res = frappe.db.sql(
        """
        SELECT ROUND(COALESCE(SUM(LEAST(t.dr_710, t.cr_197)), 0), 2)
        FROM (
            SELECT
                se.name,
                COALESCE(SUM(CASE WHEN gle.account = %s THEN gle.debit - gle.credit ELSE 0 END), 0) AS dr_710,
                COALESCE(SUM(CASE WHEN gle.account = %s THEN gle.credit - gle.debit ELSE 0 END), 0) AS cr_197
            FROM `tabStock Entry` se
            INNER JOIN `tabGL Entry` gle
                ON gle.voucher_type = 'Stock Entry'
                AND gle.voucher_no = se.name
                AND gle.is_cancelled = 0
                AND gle.company = %s
            WHERE se.docstatus = 1
              AND se.company = %s
              AND se.purpose = 'Manufacture'
              AND se.posting_date BETWEEN %s AND %s
              AND EXISTS (
                  SELECT 1
                  FROM `tabStock Entry Detail` sed
                  WHERE sed.parent = se.name
                    AND IFNULL(sed.s_warehouse, '') != ''
              )
            GROUP BY se.name
            HAVING dr_710 > 0 AND cr_197 > 0
        ) t
        """,
        (acc_710, acc_197, company, company, fiscal_year_start, fiscal_year_end),
    )
    amount = flt(res[0][0], 2) if res and res[0] else 0.0
    if amount <= 0.01:
        return {"status": "skipped", "reason": "zero_amount", "amount": amount}
    if dry_run:
        return {"status": "planned", "amount": amount}

    je_name = _submit_simple_je(
        company=company,
        posting_date=eff_date,
        cost_center=ctx["cost_center"],
        debit_account=acc_197,
        credit_account=acc_710,
        amount=amount,
        user_remark=spec["remark"],
    )
    return {"status": "applied", "amount": amount, "journal_entry": je_name}


def _run_step_3_mt_janfeb(
    company: str, eff_date: str, ctx: dict, dry_run: bool
) -> dict:
    """Step 3: Reclassify Jan-Feb Material Transfer 710.20 debits back to 150.01.001."""
    spec = STEP_SPECS["step_3_mt_janfeb"]
    existing = _find_existing_step_je(company, spec["tag"], spec["legacy_prefix"])
    if existing:
        return {
            "status": "skipped",
            "reason": "already_posted",
            "journal_entry": existing,
        }

    acc_150_1 = ctx["accounts"].get("150.01.001")
    acc_710 = ctx["accounts"].get("710.20")
    if not acc_150_1 or not acc_710:
        return {"status": "skipped", "reason": "missing_accounts"}

    res = frappe.db.sql(
        """
        SELECT ROUND(COALESCE(SUM(gle.debit - gle.credit), 0), 2)
        FROM `tabGL Entry` gle
        INNER JOIN `tabStock Entry` se
            ON se.name = gle.voucher_no
        WHERE gle.is_cancelled = 0
          AND gle.company = %s
          AND gle.voucher_type = 'Stock Entry'
          AND gle.account = %s
          AND se.docstatus = 1
          AND se.company = %s
          AND se.purpose = 'Material Transfer'
          AND se.posting_date BETWEEN '2026-01-01' AND '2026-02-28'
        """,
        (company, acc_710, company),
    )
    amount = flt(res[0][0], 2) if res and res[0] else 0.0
    if amount <= 0.01:
        return {"status": "skipped", "reason": "zero_amount", "amount": amount}
    if dry_run:
        return {"status": "planned", "amount": amount}

    je_name = _submit_simple_je(
        company=company,
        posting_date=eff_date,
        cost_center=ctx["cost_center"],
        debit_account=acc_150_1,
        credit_account=acc_710,
        amount=amount,
        user_remark=spec["remark"],
    )
    return {"status": "applied", "amount": amount, "journal_entry": je_name}


def _run_step_4_dn_710(
    company: str,
    eff_date: str,
    ctx: dict,
    fiscal_year_start: str,
    fiscal_year_end: str,
    dry_run: bool,
) -> dict:
    """Step 4: Reclassify Delivery Note 710.20 raw material COGS to 621.01."""
    spec = STEP_SPECS["step_4_dn_710"]
    existing = _find_existing_step_je(company, spec["tag"], spec["legacy_prefix"])
    if existing:
        return {
            "status": "skipped",
            "reason": "already_posted",
            "journal_entry": existing,
        }

    acc_621 = ctx["accounts"].get("621.01")
    acc_710 = ctx["accounts"].get("710.20")
    if not acc_621 or not acc_710:
        return {"status": "skipped", "reason": "missing_accounts"}

    res = frappe.db.sql(
        """
        SELECT ROUND(COALESCE(SUM(gle.debit - gle.credit), 0), 2)
        FROM `tabGL Entry` gle
        WHERE gle.is_cancelled = 0
          AND gle.company = %s
          AND gle.voucher_type = 'Delivery Note'
          AND gle.account = %s
          AND gle.posting_date BETWEEN %s AND %s
        """,
        (company, acc_710, fiscal_year_start, fiscal_year_end),
    )
    amount = flt(res[0][0], 2) if res and res[0] else 0.0
    if amount <= 0.01:
        return {"status": "skipped", "reason": "zero_amount", "amount": amount}
    if dry_run:
        return {"status": "planned", "amount": amount}

    je_name = _submit_simple_je(
        company=company,
        posting_date=eff_date,
        cost_center=ctx["cost_center"],
        debit_account=acc_621,
        credit_account=acc_710,
        amount=amount,
        user_remark=spec["remark"],
    )
    return {"status": "applied", "amount": amount, "journal_entry": je_name}


def _run_step_5_dn_income(
    company: str,
    eff_date: str,
    ctx: dict,
    fiscal_year_start: str,
    fiscal_year_end: str,
    dry_run: bool,
) -> dict:
    """Step 5: Reclassify Delivery Note Income-account COGS debits to 620.01 (multi-currency safe)."""
    spec = STEP_SPECS["step_5_dn_income"]
    existing = _find_existing_step_je(company, spec["tag"], spec["legacy_prefix"])
    if existing:
        return {
            "status": "skipped",
            "reason": "already_posted",
            "journal_entry": existing,
        }

    acc_620 = ctx["accounts"].get("620.01")
    if not acc_620:
        return {"status": "skipped", "reason": "missing_accounts"}

    rows = frappe.db.sql(
        """
        SELECT
            gle.account AS account,
            acc.account_currency AS account_currency,
            ROUND(SUM(gle.debit - gle.credit), 2) AS net_try,
            ROUND(SUM(gle.debit_in_account_currency - gle.credit_in_account_currency), 2) AS net_acc_cur
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc
            ON acc.name = gle.account
        WHERE gle.is_cancelled = 0
          AND gle.company = %s
          AND gle.voucher_type = 'Delivery Note'
          AND gle.posting_date BETWEEN %s AND %s
          AND acc.root_type = 'Income'
        GROUP BY gle.account, acc.account_currency
        HAVING SUM(gle.debit - gle.credit) > 0.01
        ORDER BY gle.account ASC
        """,
        (company, fiscal_year_start, fiscal_year_end),
        as_dict=True,
    )
    if not rows:
        return {
            "status": "skipped",
            "reason": "zero_amount",
            "amount": 0.0,
            "accounts": [],
        }

    company_currency = ctx["company_currency"]
    credit_lines = []
    total_credit_try = 0.0
    is_multi_currency = False

    for row in rows:
        acc_cur = row.account_currency or company_currency
        net_try = flt(row.net_try, 2)
        net_acc_cur = flt(row.net_acc_cur, 2)
        if acc_cur == company_currency:
            ex_rate = 1.0
            cr_in_cur = net_try
        else:
            is_multi_currency = True
            cr_in_cur = net_acc_cur
            ex_rate = (net_try / cr_in_cur) if cr_in_cur else 1.0

        if flt(cr_in_cur, 2) <= 0:
            continue

        credit_try = flt(cr_in_cur * ex_rate, 2)
        total_credit_try = flt(total_credit_try + credit_try, 2)
        credit_lines.append(
            {
                "account": row.account,
                "account_currency": acc_cur,
                "credit_in_account_currency": flt(cr_in_cur, 2),
                "exchange_rate": ex_rate,
                "credit_try": credit_try,
            }
        )

    if total_credit_try <= 0.01 or not credit_lines:
        return {
            "status": "skipped",
            "reason": "zero_amount",
            "amount": 0.0,
            "accounts": [],
        }

    if dry_run:
        return {
            "status": "planned",
            "amount": total_credit_try,
            "multi_currency": is_multi_currency,
            "accounts": credit_lines,
        }

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.company = company
    je.posting_date = eff_date
    je.multi_currency = 1 if is_multi_currency else 0
    je.user_remark = spec["remark"]
    if is_multi_currency:
        je.flags.ignore_exchange_rate = True

    je.append(
        "accounts",
        {
            "account": acc_620,
            "debit_in_account_currency": total_credit_try,
            "credit_in_account_currency": 0.0,
            "exchange_rate": 1.0,
            "cost_center": ctx["cost_center"],
        },
    )
    for line in credit_lines:
        je.append(
            "accounts",
            {
                "account": line["account"],
                "debit_in_account_currency": 0.0,
                "credit_in_account_currency": line["credit_in_account_currency"],
                "exchange_rate": line["exchange_rate"],
                "cost_center": ctx["cost_center"],
            },
        )

    je.insert(ignore_permissions=True)
    je.submit()
    return {
        "status": "applied",
        "amount": total_credit_try,
        "multi_currency": is_multi_currency,
        "accounts": credit_lines,
        "journal_entry": je.name,
    }


def _process_company_reclassifications(
    company: str,
    posting_date: str | None,
    fiscal_year_start: str,
    fiscal_year_end: str,
    dry_run: bool,
) -> tuple[dict, int, list[dict]]:
    """Run all 5 reclassification steps for a single company and return (report, je_count, errors)."""
    ctx = _resolve_company_context(company)
    eff_date, clamped, date_err = _resolve_effective_posting_date(company, posting_date)
    if date_err:
        return (
            {
                "effective_posting_date": eff_date,
                "clamped_by_lock": clamped,
                "skipped": True,
                "reason": date_err,
                "steps": {},
            },
            0,
            [{"company": company, "step": "date", "error": date_err}],
        )

    step_calls = [
        ("step_1_1501_wh", _run_step_1_1501_wh, (company, eff_date, ctx, dry_run)),
        (
            "step_2_mfg_mirror",
            _run_step_2_mfg_mirror,
            (company, eff_date, ctx, fiscal_year_start, fiscal_year_end, dry_run),
        ),
        ("step_3_mt_janfeb", _run_step_3_mt_janfeb, (company, eff_date, ctx, dry_run)),
        (
            "step_4_dn_710",
            _run_step_4_dn_710,
            (company, eff_date, ctx, fiscal_year_start, fiscal_year_end, dry_run),
        ),
        (
            "step_5_dn_income",
            _run_step_5_dn_income,
            (company, eff_date, ctx, fiscal_year_start, fiscal_year_end, dry_run),
        ),
    ]

    step_results = {}
    je_count = 0
    errors = []
    for step_key, fn, args in step_calls:
        try:
            res = fn(*args)
            step_results[step_key] = res
            if res.get("status") == "applied" and res.get("journal_entry"):
                je_count += 1
        except Exception as exc:  # noqa: BLE001
            step_results[step_key] = {"status": "error", "error": str(exc)}
            errors.append({"company": company, "step": step_key, "error": str(exc)})

    report = {
        "effective_posting_date": eff_date,
        "clamped_by_lock": clamped,
        "accounts": ctx["accounts"],
        "cost_center": ctx["cost_center"],
        "skipped": False,
        "steps": step_results,
    }
    return (report, je_count, errors)


def post_2026_accounting_reclassifications(
    company: str | None = None,
    posting_date: str | None = None,
    fiscal_year_start: str = "2026-01-01",
    fiscal_year_end: str = "2026-12-31",
    dry_run: bool = False,
) -> dict:
    """Post 2026 inventory and COGS reclassification Journal Entries idempotently."""
    target_companies = _get_target_companies(company)
    summary = {
        "dry_run": bool(dry_run),
        "companies": {},
        "total_journal_entries_created": 0,
        "errors": [],
    }

    for comp in target_companies:
        comp_report, je_count, comp_errors = _process_company_reclassifications(
            comp,
            posting_date=posting_date,
            fiscal_year_start=fiscal_year_start,
            fiscal_year_end=fiscal_year_end,
            dry_run=dry_run,
        )
        summary["companies"][comp] = comp_report
        summary["total_journal_entries_created"] += je_count
        summary["errors"].extend(comp_errors)

    return summary


def execute() -> None:
    """Patch entrypoint: post 2026 accounting reclassifications idempotently."""
    result = post_2026_accounting_reclassifications(dry_run=False)
    print(
        "[post_2026_accounting_reclassifications] "
        f"companies={len(result['companies'])} "
        f"journal_entries_created={result['total_journal_entries_created']} "
        f"errors={len(result['errors'])}"
    )
