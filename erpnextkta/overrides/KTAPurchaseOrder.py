import frappe
from frappe import _
from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder as ERPNextPurchaseOrder

class KTAPurchaseOrder(ERPNextPurchaseOrder):
    def validate_minimum_order_qty(self):
        """
        Item'ların MOQ değerlerini tek sorguda çekip cache'ler.
        MOQ altındaki satırları bloklamaz; sadece uyarı verir.
        """
        items = self.get("items") or []
        if not items:
            return

        # 1) Satırlardaki item_code'ları tekilleştir
        item_codes = {getattr(d, "item_code", None) for d in items}
        item_codes.discard(None)
        if not item_codes:
            return

        # 2) Tek sorguda tüm min_order_qty alanlarını çek
        # name -> Item.name (item_code ile aynıdır)
        rows = frappe.get_all(
            "Item",
            filters={"name": ["in", list(item_codes)]},
            fields=["name", "min_order_qty"],
            as_list=False,
        )

        # 3) Cache sözlüğü oluştur (float dönüştürme dahil)
        moq_map = {}
        for r in rows:
            moq_val = r.get("min_order_qty")
            try:
                moq_map[r["name"]] = float(moq_val) if moq_val is not None else None
            except Exception:
                moq_map[r["name"]] = None

        # 4) Satırları kontrol et (cache üzerinden okuma)
        warnings = []
        for d in items:
            item_code = getattr(d, "item_code", None)
            if not item_code:
                continue

            qty = getattr(d, "qty", 0) or 0
            try:
                qty = float(qty)
            except Exception:
                qty = 0.0

            moq = moq_map.get(item_code)
            if moq and qty < moq:
                warnings.append(
                    _("Item {0} için Minimum Sipariş Miktarı {1}. Satır miktarı {2}.")
                    .format(item_code, moq, qty)
                )

        # 5) Uyarıları tek msgprint ile göster (çok satırlı)
        if warnings:
            frappe.msgprint(
                "<br>".join(warnings),
                title=_("MOQ Uyarısı"),
                indicator="orange",
                is_minimizable=True,
            )