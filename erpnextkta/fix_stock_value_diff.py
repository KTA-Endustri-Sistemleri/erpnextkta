"""
Fix Stock Value Difference Discrepancies in Stock Ledger Entry
==============================================================

Sorun:
    Yabancı para cinsinden (EUR, USD vb.) düzenlenen Purchase Receipt'lerde
    SLE.stock_value_difference, TRY yerine belge para biriminde (ör. EUR) saklanmış.
    Bu durum Stock Balance raporunda qty=0 olan kalemlerin value≠0 göstermesine yol açar.

Kök neden:
    - SLE.stock_value (kümülatif bakiye)      → TRY cinsinden DOĞRU
    - SLE.stock_value_difference (delta)       → bazı PR kayıtlarında YANLIŞ (belge pari)

Düzeltme formülü:
    correct_svd[i] = stock_value[i] - stock_value[i-1]
    (Her item+warehouse+batch için kronolojik sırada)
    stock_value her zaman TRY bazlı olduğundan delta da TRY olur.

Kullanım:
    # 1. Teşhis / Özet (güvenli, hiçbir şeyi değiştirmez):
    bench --site <site> execute erpnextkta.fix_stock_value_diff.run

    # 2. Detaylı kuru çalıştırma (her değişikliği yazdırır):
    bench --site <site> execute erpnextkta.fix_stock_value_diff.run \\
        --kwargs '{"dry_run": true, "verbose": true}'

    # 3. Canlı uygulama:
    bench --site <site> execute erpnextkta.fix_stock_value_diff.run \\
        --kwargs '{"dry_run": false}'
"""

import frappe
from frappe.utils import flt, now_datetime


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run(dry_run=True, threshold=1.0, verbose=False):
    """
    Yanlış stock_value_difference değerlerini tespit et ve düzelt.

    Args:
        dry_run  : True  → sadece raporla, değiştirme (varsayılan).
                   False → SLE'leri gerçekten güncelle.
        threshold: Düzeltme tetiklemek için minimum fark (TRY). Varsayılan 1.0.
        verbose  : True  → her yanlış SLE'yi tek tek yaz. Varsayılan False.
    """
    _print_header(dry_run)

    combos = _get_affected_combos(threshold)
    if not combos:
        print("Sorun bulunamadı. Tüm stock_value_difference değerleri tutarlı.\n")
        return

    print(f"Etkilenen item+warehouse+batch kombinasyonu: {len(combos)}\n")

    total_sle_fixed      = 0
    total_abs_correction = 0.0

    for idx, combo in enumerate(combos, start=1):
        fixed, correction = _process_combo(
            item_code=combo["item_code"],
            warehouse=combo["warehouse"],
            batch_no=combo["batch_no"] or None,
            dry_run=dry_run,
            threshold=threshold,
            verbose=verbose,
        )
        total_sle_fixed      += fixed
        total_abs_correction += correction

        if not dry_run and idx % 100 == 0:
            frappe.db.commit()
            print(f"  [{idx}/{len(combos)}] {total_sle_fixed} SLE düzeltildi (commit).")

    if not dry_run:
        frappe.db.commit()

    _print_footer(dry_run, total_sle_fixed, total_abs_correction)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _get_affected_combos(threshold):
    """
    Kümülatif qty≈0 ama |sum(SVD)| > threshold olan tüm
    item+warehouse+batch kombinasyonlarını döndür.
    """
    return frappe.db.sql(
        """
        SELECT
            item_code,
            warehouse,
            COALESCE(batch_no, '')       AS batch_no,
            SUM(actual_qty)              AS balance_qty,
            SUM(stock_value_difference)  AS balance_value
        FROM `tabStock Ledger Entry`
        WHERE is_cancelled = 0
          AND docstatus    = 1
        GROUP BY item_code, warehouse, COALESCE(batch_no, '')
        HAVING ABS(SUM(actual_qty)) < 0.001
           AND ABS(SUM(stock_value_difference)) > %(threshold)s
        ORDER BY ABS(SUM(stock_value_difference)) DESC
        """,
        {"threshold": threshold},
        as_dict=True,
    )


def _process_combo(item_code, warehouse, batch_no, dry_run, threshold, verbose):
    """
    Tek bir item+warehouse+batch kombinasyonu için SLE'leri kronolojik sırada gez.
    Her SLE için doğru SVD = stock_value[i] - stock_value[i-1] hesapla.
    Fark threshold'u aşıyorsa güncelle (veya raporla).

    Returns:
        (count_fixed, total_abs_correction)
    """
    sles = frappe.db.sql(
        """
        SELECT
            name,
            actual_qty,
            stock_value,
            stock_value_difference,
            voucher_type,
            voucher_no,
            posting_date
        FROM `tabStock Ledger Entry`
        WHERE item_code              = %(item_code)s
          AND warehouse              = %(warehouse)s
          AND COALESCE(batch_no, '') = %(batch_no)s
          AND is_cancelled           = 0
          AND docstatus              = 1
        ORDER BY timestamp(posting_date, posting_time), creation
        """,
        {"item_code": item_code, "warehouse": warehouse, "batch_no": batch_no or ""},
        as_dict=True,
    )

    count_fixed      = 0
    total_correction = 0.0
    prev_sv          = 0.0

    for sle in sles:
        current_sv  = flt(sle["stock_value"])
        current_svd = flt(sle["stock_value_difference"])
        correct_svd = flt(current_sv - prev_sv)
        diff        = abs(current_svd - correct_svd)

        if diff > threshold:
            if verbose:
                print(
                    f"  {'[DRY]' if dry_run else '[FIX]'} "
                    f"{sle['voucher_type']}:{sle['voucher_no']}  "
                    f"item={item_code}  wh={warehouse}\n"
                    f"        SVD: {current_svd:>15,.4f}  →  {correct_svd:>15,.4f}  "
                    f"(fark: {correct_svd - current_svd:+,.2f} TRY)"
                )

            if not dry_run:
                frappe.db.sql(
                    """
                    UPDATE `tabStock Ledger Entry`
                    SET stock_value_difference = %(svd)s,
                        modified               = %(now)s
                    WHERE name = %(name)s
                    """,
                    {
                        "svd":  correct_svd,
                        "now":  now_datetime(),
                        "name": sle["name"],
                    },
                )

            count_fixed      += 1
            total_correction += diff

        prev_sv = current_sv

    return count_fixed, total_correction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_header(dry_run):
    mode = "KUR ÇALIŞMA (DRY RUN)" if dry_run else "CANLI UYGULAMA"
    print(f"\n{'='*65}")
    print(f" Stock Value Difference Düzeltici  [{mode}]")
    print(f"{'='*65}\n")


def _print_footer(dry_run, total_sle_fixed, total_abs_correction):
    print(f"\n{'='*65}")
    print(f" ÖZET")
    print(f"{'='*65}")
    action = "düzeltilecek" if dry_run else "düzeltilen"
    print(f"  Toplam {action} SLE         : {total_sle_fixed:>8,}")
    print(f"  Toplam düzeltme miktarı    : {total_abs_correction:>18,.2f} TRY")

    if dry_run:
        print(f"\n  Canlı uygulamak için:")
        print(
            f"  bench --site <site> execute erpnextkta.fix_stock_value_diff.run "
            f"--kwargs '{{\"dry_run\": false}}'"
        )
    else:
        print(f"\n  Stock Balance raporu artık doğru değerleri göstermelidir.")
        print(f"  'Repost Item Valuation' gerekmez.")

    print(f"{'='*65}\n")
