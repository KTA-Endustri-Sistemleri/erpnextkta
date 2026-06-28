import socket
import frappe
import json
from erpnext.controllers.accounts_controller import update_child_qty_rate
from frappe import _
from frappe.utils import nowdate, getdate, flt, today, add_days, cint
from collections import defaultdict
from babel.numbers import format_decimal
from erpnextkta.kta_sales.doctype.kta_so_sync_log.kta_so_sync_log import (
    sync_sales_orders_from_comparison as _sync_sales_orders_from_comparison,
    sync_sales_orders_from_sales_order_update as _sync_sales_orders_from_sales_order_update,
)
from erpnextkta.kta_sales.doctype.kta_sales_order_update_comparison.kta_sales_order_update_comparison import (
    compare_sales_order_update_documents as _compare_sales_order_update_documents,
)


# Refactored Imports
from erpnextkta.kta_stock.label_manager import (
    LabelPrinter,
    print_kta_pr_labels,
    print_split_kta_pr_labels,
    print_kta_wo_labels,
    print_kta_wo_labels_of_stock_entry,
    resplit_and_print_kta_wo_labels
)
from erpnextkta.kta_stock.batch_manager import (
    BatchSplitManager,
    check_packaging_quantity_mismatch
)

# Global doctype constants
DOCTYPE_PARTY_ACCOUNT = "Party Account"
DOCTYPE_CUSTOMER = "Customer"
DOCTYPE_ADDRESS = "Address"
DOCTYPE_KTA_DEPO_ETIKETLERI = "KTA Stock Label"
DOCTYPE_BOM = "BOM"
DOCTYPE_ITEM = "Item"
DOCTYPE_ITEM_CUSTOMER_DETAIL = "Item Customer Detail"
DOCTYPE_SERIAL_AND_BATCH_BUNDLE = "Serial and Batch Bundle"
DOCTYPE_SERIAL_AND_BATCH_ENTRY = "Serial and Batch Entry"
DOCTYPE_BIN = "Bin"
DOCTYPE_STOCK_LEDGER_ENTRY = "Stock Ledger Entry"
DOCTYPE_KTA_MOBIL_DEPO = "KTA Mobil Depo"
DOCTYPE_KTA_MOBIL_DEPO_KALEMI = "KTA Mobil Depo Kalemi"
DOCTYPE_CALISMA_KARTI = "Calisma Karti"
DOCTYPE_CALISMA_KARTI_HURDA = "Calisma Karti Hurda"
DOCTYPE_UOM_CONVERSION_DETAIL = "UOM Conversion Detail"

# Global field constants
FIELD_CUSTOMER_INCOME_ACCOUNT = "customer_income_account"
FIELD_PARENT = "parent"
FIELD_PARENTTYPE = "parenttype"
FIELD_COMPANY = "company"
FIELD_DO_NOT_SPLIT = "do_not_split"
FIELD_NAME = "name"
FIELD_ITEM_CODE = "item_code"
FIELD_ITEM_NAME = "item_name"
FIELD_QTY = "qty"
FIELD_UOM = "uom"
FIELD_SUT_BARCODE = "sut_barcode"
FIELD_BATCH = "batch"
FIELD_DESCRIPTION = "description"
FIELD_STOCK_UOM = "stock_uom"
FIELD_PARENTFIELD = "parentfield"
FIELD_DOCSTATUS = "docstatus"
FIELD_WAREHOUSE = "warehouse"
FIELD_BATCH_NO = "batch_no"
FIELD_ACTUAL_QTY = "actual_qty"
FIELD_BALANCE_QTY = "balance_qty"
FIELD_PLANT_NO_CUSTOMER = "plant_no_customer"
FIELD_PART_NO_CUSTOMER = "part_no_customer"
FIELD_REF_CODE = "ref_code"
FIELD_CUSTOMER_NAME = "customer_name"
FIELD_S_WAREHOUSE = "s_warehouse"
FIELD_DEPO = "depo"
FIELD_HURDA_NEDENI = "hurda_nedeni"

# Global value constants
VALUE_ENTRIES = "entries"
VALUE_TABLE_EVALUATION = "table_evaluation"


@frappe.whitelist()
def get_customer_income_account(customer, company):
    """
    Fetch the customer income account from the Party Account child table.
    """
    try:
        frappe.logger().info(f"Fetching customer income account for Customer: {customer}, Company: {company}")

        # Fetch the value from the Party Account child table
        customer_income_account = frappe.get_value(
            DOCTYPE_PARTY_ACCOUNT,
            {FIELD_PARENT: customer, FIELD_PARENTTYPE: DOCTYPE_CUSTOMER, FIELD_COMPANY: company},
            FIELD_CUSTOMER_INCOME_ACCOUNT
        )

        frappe.logger().info(f"Fetched customer income account: {customer_income_account}")
        return customer_income_account
    except Exception as e:
        frappe.log_error(f"Error fetching customer income account: {e}")
        return None





@frappe.whitelist()
def process_supply_on(supply_on):
    supply_on_doc = frappe.get_doc(DOCTYPE_KTA_SUPPLY_ON_HEAD, supply_on)
    supply_on_doc.set(VALUE_TABLE_EVALUATION, [])
    supply_on_doc.save()

    supply_on_balances = get_balances_from_supply_on(supply_on)

    if not supply_on_balances:
        frappe.throw(_("Tedarik için bakiye bulunamadı: {0}").format(supply_on))
        return None

    for balance in supply_on_balances:
        errors = {"plant_no": None, "part_no": None, "bom": None}

        # Process customer
        customer = None
        if balance.plant_no_customer:
            # find the address
            address = frappe.get_value(DOCTYPE_ADDRESS, {"custom_eski_kod": balance.plant_no_customer}, "name")
            if address:
                # Find the customer through the child table
                address_doc = frappe.get_doc(DOCTYPE_ADDRESS, address)
                customer = None
                links = address_doc.get("links") or []
                for link in links:
                     if link.link_doctype == DOCTYPE_CUSTOMER:
                         customer = link.link_name
                         break
                
                if not customer:
                    errors["plant_no"] = f"Address {address} için Customer linki bulunamadı"
            else:
                # No address found with custom_eski_kod
                errors["plant_no"] = f"{balance.plant_no_customer} ile Address bulunamadı"
                customer = None

        # Process item
        item = None
        if balance.part_no_customer and customer:
            item = frappe.get_value(DOCTYPE_ITEM, balance.part_no_customer, FIELD_NAME)
            if not item:
                ref_item = frappe.get_value(
                    DOCTYPE_ITEM_CUSTOMER_DETAIL,
                    {FIELD_REF_CODE: balance.part_no_customer, FIELD_CUSTOMER_NAME: customer},
                    FIELD_PARENT
                )
                if ref_item:
                    item = ref_item
                else:
                    errors["part_no"] = f"Item {balance.part_no_customer} bulunamadı"

        # Get last delivery note if item exists
        last_delivery = [{'max_custom_irsaliye_no': None, 'lr_date': None}]
        if item and customer:
            last_delivery = get_last_delivery_note(customer, item)

        if item:
            if not frappe.get_all(DOCTYPE_BOM, filters={"item": item, "is_default": 1}, limit=1):
                errors["bom"] = "Varsayılan BOM bulunamadı"

        # Append evaluation data
        supply_on_doc.append(
            VALUE_TABLE_EVALUATION,
            {
                FIELD_PLANT_NO_CUSTOMER: balance.plant_no_customer,
                "plant_no_error_message": errors["plant_no"],
                FIELD_PART_NO_CUSTOMER: balance.part_no_customer,
                "part_no_error_message": errors["part_no"],
                "part_no_bom_error_message": errors["bom"],
                "total_qty": balance.total_qty,
                "closed_qty": balance.closed_qty,
                "balance_qty": balance.balance_qty,
                "customer": customer,
                "item": item,
                "last_delivery_note": balance.delivery_note_no,
                "last_delivery_date": balance.delivery_note_date,
                "kta_last_delivery_note": last_delivery[0]['max_custom_irsaliye_no'] if last_delivery else None,
                "kta_last_delivery_date": last_delivery[0]['lr_date'] if last_delivery else None
            }
        )

    supply_on_doc.save()
    evaluate_supply_on_sales_orders(supply_on_doc.name)


def get_last_delivery_note(customer_name, item_name):
    return frappe.db.sql("""SELECT MAX(tdn.custom_irsaliye_no) AS max_custom_irsaliye_no,
                                   tdn.lr_date
                            FROM `tabDelivery Note` tdn
                                     INNER JOIN `tabDelivery Note Item` tdni
                                                ON tdn.name = tdni.parent
                                                    AND tdni.item_code = %s
                                     INNER JOIN (SELECT MAX(dn.lr_date) as max_date
                                                 FROM `tabDelivery Note` dn
                                                          INNER JOIN `tabDelivery Note Item` dni
                                                                     ON dn.name = dni.parent
                                                                         AND dni.item_code = %s
                                                 WHERE dn.customer = %s
                                                   AND dn.docstatus = 1
                                                   AND dn.is_return = 0) latest ON tdn.lr_date = latest.max_date
                            WHERE tdn.customer = %s
                              AND tdn.is_return = 0
                              AND tdn.docstatus = 1
                            GROUP BY tdn.lr_date;
                         """, (item_name, item_name, customer_name, customer_name), as_dict=True)


def get_balances_from_supply_on(supply_on):
    return frappe.db.sql("""
                         SELECT plant_no_customer,
                                part_no_customer,
                                delivery_note_no,
                                delivery_note_date,
                                MAX(EFZ)                     AS `total_qty`,
                                MAX(EFZ_customer)            AS `closed_qty`,
                                MAX(EFZ) - MAX(EFZ_customer) AS `balance_qty`
                         FROM `tabKTA Supply On`
                         WHERE parent = %s
                           AND parenttype = %s
                         GROUP BY plant_no_customer,
                                  part_no_customer,
                                  delivery_note_no,
                                  delivery_note_date
                         """, (supply_on, DOCTYPE_KTA_SUPPLY_ON_HEAD), as_dict=True)


@frappe.whitelist()
def evaluate_supply_on_sales_orders(supply_on_head_name):
    """
    Evaluate each row of VALUE_TABLE_EVALUATION where balance_qty is not zero
    against DOCTYPE_KTA_SUPPLY_ON_HEAD and query relevant sales orders
    """
    try:
        # Get the supply on head
        supply_on_doc = frappe.get_doc(DOCTYPE_KTA_SUPPLY_ON_HEAD, supply_on_head_name)
        
        if not supply_on_doc.get(VALUE_TABLE_EVALUATION):
            frappe.throw(_("Tedarik başlık belgesinde değerlendirme verisi bulunamadı"))
            return []
        
        results = []
        
        # Process each evaluation row where balance_qty is not zero
        for eval_row in supply_on_doc.get(VALUE_TABLE_EVALUATION):
            # Convert balance_qty to float for proper comparison
            try:
                balance_qty = float(eval_row.balance_qty or 0)
            except (ValueError, TypeError):
                balance_qty = 0
                
            if balance_qty <= 0:
                continue
                
            customer = eval_row.customer
            item = eval_row.item
            
            if not customer or not item:
                continue
            
            matching_supply_ons = frappe.db.sql("""
                SELECT 
                    delivery_date,
                    delivery_quantity,
                    quantity,
                    efz,
                    efz_customer
                FROM `tabKTA Supply On`
                WHERE plant_no_customer = %s 
                AND part_no_customer = %s
                AND parenttype = %s
                AND parent = %s
            """, (eval_row.plant_no_customer, eval_row.part_no_customer, DOCTYPE_KTA_SUPPLY_ON_HEAD, supply_on_head_name), as_dict=True)

            for supply_on in matching_supply_ons:
                sales_orders = frappe.db.sql("""
                                             SELECT soi.name,
                                                    soi.delivery_date,
                                                    soi.qty,
                                                    soi.delivered_qty,
                                                    soi.pending_qty,
                                                    so.name as sales_order,
                                                    so.transaction_date
                                             FROM `tabSales Order Item` soi
                                                      INNER JOIN `tabSales Order` so on so.name = soi.parent
                                             WHERE soi.item_code = %s
                                               AND so.customer = %s
                                               AND so.docstatus = 1
                                               AND so.status not in ('Closed', 'Cancelled')
                                               AND soi.pending_qty > 0
                                             ORDER BY soi.delivery_date
                                             """, (item, customer), as_dict=True)


        return results

    except Exception as e:
        frappe.log_error(f"Error in evaluate_supply_on_sales_orders: {str(e)}")
        frappe.throw(_("Satış siparişlerinde tedarik değerlendirilirken hata oluştu: {0}").format(str(e)))



@frappe.whitelist()
def compare_sales_order_update_documents(current_sales_order_update_name):
    """Wrapper that delegates to the Sales Order Update Comparison module."""
    return _compare_sales_order_update_documents(current_sales_order_update_name)


@frappe.whitelist()
def sync_sales_orders_from_sales_order_update(sales_order_update_name=None, sales_order_update_reference=None):
    """Wrapper that delegates to the SO Sync Log module."""
    return _sync_sales_orders_from_sales_order_update(
        sales_order_update_name=sales_order_update_name,
        sales_order_update_reference=sales_order_update_reference,
    )


@frappe.whitelist()
def diagnose_bundle_valuation():
    """Geçici tanı fonksiyonu: bundle/SLE tutarsızlıklarını raporlar."""
    results = {}

    results["entries_zero_rate"] = frappe.db.sql("""
        SELECT COUNT(DISTINCT sabb.name) as cnt
        FROM `tabSerial and Batch Bundle` sabb
        JOIN `tabStock Ledger Entry` sle ON sle.serial_and_batch_bundle = sabb.name
        JOIN `tabSerial and Batch Entry` sabe ON sabe.parent = sabb.name
        WHERE sabb.docstatus=1 AND sabb.is_cancelled=0 AND sabb.type_of_transaction='Inward'
          AND sle.actual_qty>0 AND sle.is_cancelled=0 AND sle.docstatus=1
          AND sle.stock_value_difference>0
          AND (sabe.incoming_rate IS NULL OR sabe.incoming_rate = 0)
    """)[0][0]

    results["total_amount_zero_but_sle_positive"] = frappe.db.sql("""
        SELECT COUNT(*) as cnt
        FROM `tabSerial and Batch Bundle` sabb
        JOIN `tabStock Ledger Entry` sle ON sle.serial_and_batch_bundle = sabb.name
        WHERE sabb.docstatus=1 AND sabb.is_cancelled=0 AND sabb.type_of_transaction='Inward'
          AND sabb.total_amount = 0
          AND sle.actual_qty>0 AND sle.is_cancelled=0 AND sle.docstatus=1
          AND sle.stock_value_difference>0
    """)[0][0]

    results["entries_sum_mismatch"] = frappe.db.sql("""
        SELECT COUNT(*) as cnt
        FROM `tabSerial and Batch Bundle` sabb
        JOIN `tabStock Ledger Entry` sle ON sle.serial_and_batch_bundle = sabb.name
        WHERE sabb.docstatus=1 AND sabb.is_cancelled=0 AND sabb.type_of_transaction='Inward'
          AND sle.actual_qty>0 AND sle.is_cancelled=0 AND sle.docstatus=1
          AND sle.stock_value_difference>0
          AND ABS(COALESCE((
              SELECT SUM(s.stock_value_difference)
              FROM `tabSerial and Batch Entry` s WHERE s.parent=sabb.name
          ), 0) - sabb.total_amount) > 0.01
    """)[0][0]

    samples = frappe.db.sql("""
        SELECT DISTINCT sabb.item_code, sabb.name as bundle,
               sabb.total_amount as bundle_amt, sle.stock_value_difference as sle_svd,
               sle.incoming_rate as sle_rate,
               COALESCE((SELECT SUM(s.stock_value_difference)
                         FROM `tabSerial and Batch Entry` s WHERE s.parent=sabb.name), 0) as entries_sum,
               COALESCE((SELECT MIN(s.incoming_rate)
                         FROM `tabSerial and Batch Entry` s WHERE s.parent=sabb.name), 0) as min_entry_rate
        FROM `tabSerial and Batch Bundle` sabb
        JOIN `tabStock Ledger Entry` sle ON sle.serial_and_batch_bundle = sabb.name
        JOIN `tabSerial and Batch Entry` sabe ON sabe.parent = sabb.name
        WHERE sabb.docstatus=1 AND sabb.is_cancelled=0 AND sabb.type_of_transaction='Inward'
          AND sle.actual_qty>0 AND sle.is_cancelled=0 AND sle.docstatus=1
          AND sle.stock_value_difference>0
          AND (sabe.incoming_rate IS NULL OR sabe.incoming_rate = 0)
        LIMIT 5
    """, as_dict=True)
    results["samples"] = samples

    return results


@frappe.whitelist()
def fix_zero_rate_qi_bundles(dry_run=True, company=None):
    """
    QI (Kalite Kontrol) akışında split edilen ve entry'lerin stock_value_difference=0
    olduğu eski bundle'ları düzeltir. Bu fonksiyon e668cde fix'inden önce oluşturulan ve
    Stock Balance raporunda bal_qty=0 ama bal_val!=0 olarak görünen kalemleri onarır.

    Çalışma Mantığı:
    1. Submitted, Inward tipinde, entry SVD toplamı != bundle total_amount olan bundle'ları bulur
    2. Bu bundle'lara bağlı SLE'den gerçek incoming_rate'i alır
    3. Bundle entry'lerini doğru incoming_rate ve stock_value_difference ile günceller
    4. Repost Item Valuation oluşturur (tüketim SLE'lerini de düzeltmek için)

    Args:
        dry_run: True ise sadece etkilenen kayıtları listeler, değişiklik yapmaz.
        company: Belirli bir şirketle sınırlandırmak için (None = tümü).

    Returns:
        dict: Bulunan ve düzeltilen bundle sayısı ile detaylar.
    """
    dry_run = cint(dry_run)

    # Bozuk bundle tespiti: Bundle header'daki total_amount ile entry'lerin
    # stock_value_difference toplamı arasında anlamlı fark olanlar.
    # e668cde öncesinde QI split edilen bundle'larda entry'ler svd=0 ile oluşturulmuş
    # ama bundle.total_amount SLE işlemi sırasında doğru değeri almış.
    # Dolayısıyla avg_rate=0 veya total_amount=0 kontrolü değil, direkt uyumsuzluk aranır.
    affected = frappe.db.sql("""
        SELECT
            sabb.name          AS bundle_name,
            sabb.item_code,
            sabb.warehouse,
            sabb.voucher_type,
            sabb.voucher_no,
            sabb.posting_date,
            sabb.posting_time,
            sabb.total_qty,
            sabb.total_amount  AS bundle_total_amount,
            ROUND(COALESCE((
                SELECT SUM(sabe.stock_value_difference)
                FROM `tabSerial and Batch Entry` sabe
                WHERE sabe.parent = sabb.name
            ), 0), 4)          AS entries_svd_sum,
            sle.incoming_rate  AS sle_incoming_rate,
            sle.stock_value_difference AS sle_stock_value_diff,
            sle.name           AS sle_name,
            sle.company
        FROM `tabSerial and Batch Bundle` sabb
        JOIN `tabStock Ledger Entry` sle
            ON sle.serial_and_batch_bundle = sabb.name
        WHERE sabb.docstatus = 1
          AND sabb.is_cancelled = 0
          AND sabb.type_of_transaction = 'Inward'
          AND sle.actual_qty > 0
          AND sle.is_cancelled = 0
          AND sle.docstatus = 1
          AND sle.stock_value_difference > 0
          AND ABS(COALESCE((
                SELECT SUM(sabe2.stock_value_difference)
                FROM `tabSerial and Batch Entry` sabe2
                WHERE sabe2.parent = sabb.name
            ), 0) - sabb.total_amount) > 0.01
          {company_filter}
    """.format(
        company_filter=f"AND sle.company = {frappe.db.escape(company)}" if company else ""
    ), as_dict=True)

    if not affected:
        return {"fixed": 0, "total_found": 0, "details": []}

    results = []
    fixed_count = 0
    repost_vouchers = set()  # (voucher_type, voucher_no, posting_date, company)

    for row in affected:
        total_qty = flt(row.total_qty)
        entries_svd_sum = flt(row.entries_svd_sum)
        bundle_total = flt(row.bundle_total_amount)
        sle_rate = flt(row.sle_incoming_rate)
        sle_svd = flt(row.sle_stock_value_diff)

        if not total_qty:
            results.append({"bundle": row.bundle_name, "status": "ATLANDA - total_qty=0"})
            continue

        # Hangi tarafın bozuk olduğunu belirle:
        # A) Entries bozuk (svd≈0), total_amount doğru → entry'leri SLE rate ile düzelt
        # B) total_amount bozuk (≈0), entries doğru → sadece header güncelle
        # C) Her ikisi de büyük ama fark küçük → floating-point yuvarlama, geç
        entries_broken = abs(entries_svd_sum) < 0.01 and bundle_total > 0.01
        header_broken = abs(bundle_total) < abs(entries_svd_sum) * 0.01 and abs(entries_svd_sum) > 0.01

        if not entries_broken and not header_broken:
            # Fark sadece yuvarlama kaynaklı, güvenli şekilde atla
            results.append({
                "bundle": row.bundle_name,
                "status": "ATLANDA - yuvarlama farkı (entries_sum≈total)",
                "bundle_total_amount": bundle_total,
                "entries_svd_sum": entries_svd_sum,
            })
            continue

        # Bundle'ın child entry'lerini bul
        entries = frappe.db.get_all(
            "Serial and Batch Entry",
            filters={"parent": row.bundle_name},
            fields=["name", "batch_no", "qty", "incoming_rate", "stock_value_difference"],
            order_by="idx asc",
        )

        if entries_broken:
            # Durum A: Entry'ler sıfır, SLE rate'i kullan
            if not sle_rate:
                if sle_svd and total_qty:
                    sle_rate = sle_svd / total_qty
                else:
                    results.append({
                        "bundle": row.bundle_name,
                        "status": "ATLANDA - entries bozuk ama SLE rate hesaplanamadı",
                    })
                    continue
            new_total_amount = total_qty * sle_rate
            fix_mode = "ENTRIES_FIXED"
            entry_details = [
                {"batch_no": e.batch_no, "qty": flt(e.qty),
                 "old_svd": flt(e.stock_value_difference),
                 "new_svd": flt(e.qty) * sle_rate}
                for e in entries
            ]
        else:
            # Durum B: Entries doğru, sadece total_amount bozuk
            new_total_amount = entries_svd_sum
            sle_rate = entries_svd_sum / total_qty
            fix_mode = "HEADER_ONLY"
            entry_details = [
                {"batch_no": e.batch_no, "qty": flt(e.qty),
                 "old_svd": flt(e.stock_value_difference),
                 "new_svd": flt(e.stock_value_difference)}  # değişmeyecek
                for e in entries
            ]

        results.append({
            "bundle": row.bundle_name,
            "voucher": f"{row.voucher_type} {row.voucher_no}",
            "item_code": row.item_code,
            "warehouse": row.warehouse,
            "fix_mode": fix_mode,
            "sle_rate": sle_rate,
            "total_qty": total_qty,
            "bundle_total_amount": bundle_total,
            "entries_svd_sum": entries_svd_sum,
            "new_total_amount": new_total_amount,
            "entries": entry_details,
            "status": "DRY_RUN" if dry_run else "DÜZELTILDI",
        })

        if dry_run:
            continue

        if entries_broken:
            # Entry'leri güncelle
            for e in entries:
                new_svd = flt(e.qty) * sle_rate
                frappe.db.set_value(
                    "Serial and Batch Entry",
                    e.name,
                    {
                        "incoming_rate": sle_rate,
                        "stock_value_difference": new_svd,
                    },
                    update_modified=False,
                )

        # Bundle header'ını güncelle (her iki durumda)
        frappe.db.set_value(
            "Serial and Batch Bundle",
            row.bundle_name,
            {
                "total_amount": new_total_amount,
                "avg_rate": sle_rate,
            },
            update_modified=False,
        )
        frappe.clear_document_cache("Serial and Batch Bundle", row.bundle_name)

        fixed_count += 1
        repost_vouchers.add((row.voucher_type, row.voucher_no, row.posting_date, row.company))

    # Repost Item Valuation oluştur (tüketim SLE'lerini de düzeltmek için)
    repost_names = []
    if not dry_run:
        for voucher_type, voucher_no, posting_date, comp in repost_vouchers:
            try:
                repost_doc = frappe.get_doc({
                    "doctype": "Repost Item Valuation",
                    "based_on": "Transaction",
                    "voucher_type": voucher_type,
                    "voucher_no": voucher_no,
                    "posting_date": posting_date,
                    "company": comp,
                    "allow_negative_stock": 1,
                })
                repost_doc.flags.ignore_permissions = True
                repost_doc.insert()
                repost_doc.submit()
                repost_names.append(repost_doc.name)
            except Exception as e:
                frappe.log_error(
                    f"fix_zero_rate_qi_bundles Repost Hatası: {voucher_type} {voucher_no}: {e}",
                    "KTA Bundle Fix Repost Error",
                )

    return {
        "total_found": len(affected),
        "fixed": fixed_count,
        "repost_docs": repost_names,
        "details": results,
    }


@frappe.whitelist()
def sync_sales_orders_from_comparison(comparison_name):
    """Wrapper that delegates to the SO Sync Log module."""
    return _sync_sales_orders_from_comparison(comparison_name)
