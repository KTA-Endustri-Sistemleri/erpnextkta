import frappe


def execute():
    frappe.db.sql(
        """
        UPDATE `tabItem Customer Detail`
        SET custom_musteri_paketleme_miktari = 0
        WHERE custom_musteri_paketleme_miktari >= 5000
    """
    )
