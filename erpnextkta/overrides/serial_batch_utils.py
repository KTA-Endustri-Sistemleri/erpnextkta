# erpnextkta/overrides/serial_batch_utils.py

import frappe
from erpnext.stock.serial_batch_bundle import (
    get_empty_batches_based_work_order as _original_get_empty_batches,
)


def get_empty_batches_based_work_order(work_order, item_code):
    """
    KTA Override: Manufacturing sırasında split edilmiş batch'leri yok say.
    
    ERPNext'in orijinal fonksiyonu, work order package'larındaki batch'leri
    kontrol ederken split edilmiş batch'leri (örn. 35063810007) bulamıyor.
    Bu override, split batch hatalarını yakalayıp yeni batch oluşturulmasına izin veriyor.
    """
    try:
        return _original_get_empty_batches(work_order, item_code)
    except KeyError as e:
        # Hata mesajından batch numarasını al
        batch_no_str = str(e).strip("'\"")
        
        # Split edilmiş batch kontrolü (son 4 karakter rakam mı?)
        if len(batch_no_str) > 4 and batch_no_str[-4:].isdigit():
            frappe.logger().info(
                f"Split batch {batch_no_str} not found in work order packages. "
                f"This is expected for continued manufacturing. Allowing new batch creation."
            )
            # Boş dict döndür, böylece ERPNext yeni batch'ler oluşturur
            return {}
        
        # Split batch değilse, gerçek bir hata var - tekrar fırlat
        frappe.logger().error(
            f"Unexpected batch error for work order {work_order}, item {item_code}: {e}"
        )
        raise