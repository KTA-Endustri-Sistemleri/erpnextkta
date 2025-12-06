# Copyright (c) 2025, Framras AS and contributors
# For license information, please see license.txt

# import frappe
from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, getdate, today


class KTASupplyOn(Document):
    """Validate incoming Supply On rows."""

    _DATE_FORMATS = ("%d.%m.%Y", "%d-%m-%Y", "%Y.%m.%d", "%m.%d.%Y")
    _INVALID_DATE_TOKENS = {"invalid date", "nan", "none", "null"}

    def validate(self):
        self._normalize_date_fields()

    def _normalize_date_fields(self):
        if not hasattr(self, "_kta_date_fields"):
            meta = frappe.get_meta(self.doctype)
            self._kta_date_fields = [
                df.fieldname for df in meta.fields if df.fieldtype in ("Date", "Datetime")
            ]

        for fieldname in self._kta_date_fields:
            raw_value = self.get(fieldname)
            normalized_value = self._parse_date_value(fieldname, raw_value)
            self.set(fieldname, normalized_value)

    def _parse_date_value(self, fieldname, value):
        if not value:
            return None

        if isinstance(value, str):
            candidate = value.strip()
        else:
            candidate = value

        if not candidate:
            return None

        if isinstance(candidate, str) and candidate.lower() in self._INVALID_DATE_TOKENS:
            return None

        try:
            return getdate(candidate)
        except Exception:
            pass

        if isinstance(candidate, str):
            for fmt in self._DATE_FORMATS:
                try:
                    return datetime.strptime(candidate, fmt).date()
                except Exception:
                    continue

        frappe.logger("erpnextkta").warning(
            f"KTA Supply On -> Unable to parse date field '{fieldname}' with value '{value}'"
        )
        return None


def get_supply_on_doc(supply_on_name: str):
    """Fetch a Supply On document, raising a user-level error if not found."""
    if not supply_on_name:
        frappe.throw(_("Supply On referansı belirtilmedi."))

    if not frappe.db.exists("KTA Supply On", supply_on_name):
        frappe.throw(_("Supply On kaydı bulunamadı: {0}").format(supply_on_name))

    return frappe.get_doc("KTA Supply On", supply_on_name)


def get_customer_and_item(plant_no_customer, part_no_customer):
    """
    Plant no'dan Customer, part_no_customer'dan Item bul.

    Customer:
      - Address.custom_eski_kod == plant_no_customer
      - Address.links (Dynamic Link) içinde link_doctype='Customer' satırının link_name'i

    Item:
      - Item.name == part_no_customer ise doğrudan onu kullan
    """
    customer = None
    item = None

    if plant_no_customer:
        address_name = frappe.db.get_value(
            "Address",
            {"custom_eski_kod": plant_no_customer},
            "name",
        )

        if address_name:
            customer = frappe.db.get_value(
                "Dynamic Link",
                {
                    "parenttype": "Address",
                    "parent": address_name,
                    "link_doctype": "Customer",
                },
                "link_name",
            )

    if part_no_customer:
        item = frappe.db.get_value(
            "Item",
            {"name": part_no_customer},
            "name",
        )

    return customer, item


def get_delivery_time_for_plant(plant_no_customer):
    """
    Plant numarasına göre KTA Sevk Parametreleri'nden delivery_time (gün) döner.
    """
    if not plant_no_customer:
        return 0

    address_name = frappe.db.get_value(
        "Address",
        {"custom_eski_kod": plant_no_customer},
        "name",
    )

    if not address_name:
        return 0

    delivery_time = frappe.db.get_value(
        "KTA Sevk Parametreleri",
        {"customer_address": address_name},
        "delivery_time",
    )

    return cint(delivery_time or 0)


def get_shipped_qty_for_window(customer, plant_no_customer, item_code, delivery_time_days):
    """
    Belirli müşteri + plant + item için (bugün - delivery_time_days, bugün] aralığında sevk edilen
    toplam qty.
    """
    if not (customer and plant_no_customer and item_code and delivery_time_days > 0):
        return 0

    end_date = getdate(today())
    start_date = add_days(end_date, -delivery_time_days)

    rows = frappe.db.sql(
        """
        SELECT SUM(dni.qty) AS total_qty
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        LEFT JOIN `tabAddress` addr ON addr.name = dn.shipping_address_name
        WHERE dn.docstatus = 1
          AND dn.posting_date BETWEEN %s AND %s
          AND dni.item_code = %s
          AND dn.customer = %s
          AND COALESCE(addr.custom_eski_kod, '') = %s
    """,
        (start_date, end_date, item_code, customer, plant_no_customer),
        as_dict=True,
    )

    total = rows[0].total_qty if rows and rows[0].total_qty is not None else 0
    return flt(total)


def adjust_supply_on_with_shipments(rows):
    """
    Verilen Supply On satır listesi üzerinde, sevk parametresi + sevk irsaliyelerini
    dikkate alarak teslimat miktarlarını düşer.
    """
    # İrsaliye düşümü geçici olarak devre dışı
    # Aşağıdaki blok daha önce sevk edilen qty'leri düşüyordu.
    # ileride yeniden aktifleştirilmek üzere korunuyor.
    #
    # groups = defaultdict(list)
    # for r in rows:
    #     key = (r.plant_no_customer, r.part_no_customer)
    #     groups[key].append(r)
    #
    # for (plant_no, part_no), group_rows in groups.items():
    #     customer, item_code = get_customer_and_item(plant_no, part_no)
    #     if not (customer and item_code):
    #         continue
    #
    #     delivery_time_days = get_delivery_time_for_plant(plant_no)
    #     if delivery_time_days <= 0:
    #         continue
    #
    #     shipped_qty = get_shipped_qty_for_window(customer, plant_no, item_code, delivery_time_days)
    #     if shipped_qty <= 0:
    #         continue
    #
    #     group_rows.sort(
    #         key=lambda r: getdate(r.delivery_date) if r.delivery_date else getdate("1900-01-01")
    #     )
    #
    #     for r in group_rows:
    #         if shipped_qty <= 0:
    #             break
    #
    #         row_qty = flt(r.delivery_quantity or 0)
    #         if row_qty <= 0:
    #             continue
    #
    #         consume = min(shipped_qty, row_qty)
    #         r.delivery_quantity = row_qty - consume
    #         shipped_qty -= consume

    return rows
