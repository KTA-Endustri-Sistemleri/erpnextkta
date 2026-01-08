# erpnextkta/patches.py

import frappe

def apply_serial_batch_patch():
    """
    ERPNext'in serial_batch_bundle modülündeki kritik fonksiyonları patch'ler.
    Amacı: Parçalanmış (split) batch'lerin KeyError ve AttributeError fırlatmasını engellemek.
    """
    try:
        import erpnext.stock.serial_batch_bundle as sbb_module
        
        # ---------------------------------------------------------
        # 1. PATCH: set_batch_details_from_package
        # ---------------------------------------------------------
        if hasattr(sbb_module, "set_batch_details_from_package") and not hasattr(sbb_module.set_batch_details_from_package, "_kta_patched"):
            
            def patched_set_batch_details_from_package(ids, batches):
                """KTA Patch: Eksik batch'leri görmezden gel ve veri tipini kontrol et"""
                if frappe.flags.in_patch: return # Re-entry korumas
                
                for d in ids:
                    # 'ids' içindeki 'd' bir obje mi (d.batch_no) yoksa string mi?
                    batch_id = d.batch_no if not isinstance(d, str) else d
                    
                    if batch_id in batches:
                        # Eğer 'd' string ise qty bilgisi yoktur, varsayılan 0 düşülür 
                        # veya 'd' obje ise d.qty kullanılır
                        qty = getattr(d, 'qty', 0) if not isinstance(d, str) else 0
                        batches[batch_id] -= qty
                    else:
                        # Eğer batch sözlükte yoksa hata verme, logla geç
                        frappe.logger().debug(f"KTA: Batch {batch_id} not expected in WO dict, skipping.")

            sbb_module.set_batch_details_from_package = patched_set_batch_details_from_package
            sbb_module.set_batch_details_from_package._kta_patched = True
            frappe.logger().info("✓ KTA: set_batch_details_from_package successfully patched with type check")

        # ---------------------------------------------------------
        # 2. PATCH: get_empty_batches_based_work_order
        # ---------------------------------------------------------
        if hasattr(sbb_module, "get_empty_batches_based_work_order") and not hasattr(sbb_module.get_empty_batches_based_work_order, "_kta_patched"):
            original_get_batches = sbb_module.get_empty_batches_based_work_order

            def patched_get_empty_batches(work_order, item_code):
                """KTA Patch: Split edilmiş batch hatalarını yakala ve boş dön"""
                try:
                    return original_get_batches(work_order, item_code)
                except KeyError as e:
                    batch_no_str = str(e).strip("'\"")
                    
                    # Split edilmiş batch kontrolü (son 4 karakter rakam mı?)
                    if len(batch_no_str) > 4 and batch_no_str[-4:].isdigit():
                        frappe.logger().info(f"KTA: Split batch {batch_no_str} handled.")
                        return {}
                    raise e

            sbb_module.get_empty_batches_based_work_order = patched_get_empty_batches
            sbb_module.get_empty_batches_based_work_order._kta_patched = True
            frappe.logger().info("✓ KTA: get_empty_batches_based_work_order successfully patched")

    except Exception as e:
        frappe.logger().error(f"✗ KTA: Failed to apply serial batch patch: {str(e)}")


def apply_all_patches(bootinfo=None):
    """
    Tüm KTA patch'lerini uygula.
    """
    apply_serial_batch_patch()