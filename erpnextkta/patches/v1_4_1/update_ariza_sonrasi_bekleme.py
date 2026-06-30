import frappe

def execute():
    # Eski test kayıtlarında veya yeni oluşan kayıtlarda "Diğer" olarak atanan ama aslında "Arıza Sonrası Bekleme" olan duruşları güncelle
    frappe.db.sql("""
        UPDATE `tabOperasyon Duruslari`
        SET durus_nedeni = 'Arıza Sonrası Bekleme'
        WHERE durus_nedeni = 'Diğer' 
        AND (
            aciklama LIKE 'Bakım ekibi işlemi bitirdi, operatörün üretime devam etmesi bekleniyor.%' OR
            aciklama LIKE 'Arıza giderildi, operatör onayı bekleniyor.%' OR
            aciklama LIKE 'Arıza iptal edildi, operatör bekleniyor.%'
        )
    """)
    frappe.db.commit()
