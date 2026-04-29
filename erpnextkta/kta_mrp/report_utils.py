import frappe
from frappe.utils import getdate, add_months, today
from datetime import date

@frappe.whitelist()
def get_report_filters(report_name):
    """Rapor adına göre modüler filtre listesini döner."""
    common_filters = {
        "dates": [
            {
                "fieldname": "from_date",
                "label": "Başlangıç Tarihi",
                "fieldtype": "Date",
                "default": today(),
                "reqd": 1
            },
            {
                "fieldname": "to_date",
                "label": "Bitiş Tarihi",
                "fieldtype": "Date",
                "default": add_months(today(), 3),
                "reqd": 1
            }
        ],
        "mrp_common": [
            {
                "fieldname": "item_group",
                "label": "Ürün Grubu",
                "fieldtype": "Link",
                "options": "Item Group"
            },
            {
                "fieldname": "ara_malzeme_grubu",
                "label": "Ara Malzeme Grubu",
                "fieldtype": "Select",
                "options": get_ara_malzeme_gruplari()
            }
        ]
    }
    
    if report_name == "MRP Analysis":
        return [
            {
                "fieldname": "periyot",
                "label": "Periyot",
                "fieldtype": "Select",
                "options": ["Yıllık", "3 Aylık", "6 Aylık", "Süresiz"],
                "default": "Yıllık",
            }
        ] + common_filters["mrp_common"] + [
            {
                "fieldname": "musteri_grubu",
                "label": "Müşteri Grubu",
                "fieldtype": "MultiSelectList",
                "get_data": "frappe.db.get_link_options('KTA Customer Group')"
            },
            {
                "fieldname": "varsayilan_tedarikci",
                "label": "Varsayılan Tedarikçi",
                "fieldtype": "Link",
                "options": "Supplier",
            },
            {
                "fieldname": "sifir_tuketimi_goster",
                "label": "Sıfır Tüketimi Göster",
                "fieldtype": "Check",
                "default": 0,
            }
        ]
    
    if report_name == "Material Requirement":
        return common_filters["dates"] + [
            {
                "fieldname": "stage",
                "label": "Aşama",
                "fieldtype": "Select",
                "options": [
                    "1 - Temel Hammadde İhtiyacı",
                    "2 - Stokları Düş",
                    "3 - PO Teslimatlarını Düş"
                ],
                "default": "1 - Temel Hammadde İhtiyacı"
            },
            {
                "fieldname": "group_by",
                "label": "Gruplama Şekli",
                "fieldtype": "Select",
                "options": ["Bitmiş Ürün + Hammadde", "Sadece Hammadde"],
                "default": "Bitmiş Ürün + Hammadde"
            }
        ]

    if report_name == "Periodic Sales Orders":
        return [
            {
                "fieldname": "from_date",
                "label": "Başlangıç Tarihi",
                "fieldtype": "Date",
                "reqd": 1,
                "default": frappe.utils.add_months(frappe.utils.today(), -1)
            },
            {
                "fieldname": "to_date",
                "label": "Bitiş Tarihi",
                "fieldtype": "Date",
                "reqd": 1,
                "default": frappe.utils.today()
            },
            {
                "fieldname": "range",
                "label": "Dönem Aralığı",
                "fieldtype": "Select",
                "options": ["Weekly", "Monthly", "Quarterly", "Yearly"],
                "default": "Weekly"
            },
            {
                "fieldname": "value_quantity",
                "label": "Değer Türü",
                "fieldtype": "Select",
                "options": [
                    { "label": "Tutar", "value": "Value" },
                    { "label": "Miktar", "value": "Quantity" }
                ],
                "default": "Quantity"
            },
            {
                "fieldname": "target_currency",
                "label": "Hedef Döviz",
                "fieldtype": "Link",
                "options": "Currency"
            },
            {
                "fieldname": "tree_type",
                "label": "Sınıflandırma",
                "fieldtype": "Select",
                "options": [
                    { "label": "Müşteri", "value": "Müşteri" },
                    { "label": "Müşteri Grubu", "value": "Müşteri Grubu" }
                ],
                "default": "Müşteri"
            },
            {
                "fieldname": "tree_key",
                "label": "Müşteri",
                "fieldtype": "Link",
                "options": "Customer"
            },
            {
                "fieldname": "show_pending_only",
                "label": "Sadece Teslim Edilmemişler",
                "fieldtype": "Check",
                "default": 1
            }
        ]

    if report_name == "Production Start Week":
        return common_filters["dates"] + [
            {
                "fieldname": "item_group",
                "label": "Ürün Grubu",
                "fieldtype": "Select",
                "options": [] # Will be populated dynamically in JS if needed, but we can set it here too
            },
            {
                "fieldname": "group_by_item_only",
                "label": "Yalnızca Ürün Bazlı Grupla",
                "fieldtype": "Check",
                "default": 0
            }
        ]

    if report_name == "Shipment Week":
        return [
            {
                "fieldname": "from_date",
                "label": "Başlangıç Tarihi",
                "fieldtype": "Date",
                "default": frappe.utils.add_months(frappe.utils.today(), -1),
                "reqd": 1
            },
            {
                "fieldname": "to_date",
                "label": "Bitiş Tarihi",
                "fieldtype": "Date",
                "default": frappe.utils.add_months(frappe.utils.today(), 2),
                "reqd": 1
            },
            {
                "fieldname": "tree_key",
                "label": "Müşteri",
                "fieldtype": "Link",
                "options": "Customer"
            }
        ]

        return common_filters["dates"] + [
            {
                "fieldname": "dengeleme_yapilsin",
                "label": "Kapasite Dengeleme Yapılsın mı?",
                "fieldtype": "Check",
                "default": 1
            },
            {
                "fieldname": "ramp_up_aktif",
                "label": "Ramp-up (Önden Üretim) Yapılsın mı?",
                "fieldtype": "Check",
                "default": 0
            },
            {
                "fieldname": "ramp_up_weeks",
                "label": "Ramp-up Süresi (Hafta)",
                "fieldtype": "Int",
                "default": 3
            },
            {
                "fieldname": "custom_musteri_grubu",
                "label": "Müşteri Grubu",
                "fieldtype": "Link",
                "options": "KTA Customer Group"
            },
            {
                "fieldname": "item_group",
                "label": "Ürün Grubu",
                "fieldtype": "Link",
                "options": "Item Group"
            }
        ]

    return common_filters["dates"]

@frappe.whitelist()
def get_ara_malzeme_gruplari():
    """Item tablosundaki benzersiz Ara Malzeme Grupları."""
    result = frappe.get_all("Item", 
        filters={"custom_ara_malzeme_grubu": ["not in", ["", None]]},
        fields=["custom_ara_malzeme_grubu"], 
        distinct=True
    )
    return [""] + sorted([r.custom_ara_malzeme_grubu for r in result])

@frappe.whitelist()
def get_item_groups():
    """Hammadde Grubu filtresi için mevcut item group değerlerini döndür."""
    result = frappe.get_all("Item", 
        filters={"item_group": ["not in", ["", None]]},
        fields=["item_group"], 
        distinct=True
    )
    return [""] + sorted([r.item_group for r in result])

@frappe.whitelist()
def get_item_group_query(doctype, txt, searchfield, start, page_len, filters):
    """Link alanı için sadece "ÜRÜN" olan kullanılan ürün gruplarını döndüren sorgu."""
    item_filters = {
        "item_group": ["like", f"%{txt}%"],
        "custom_ara_malzeme_grubu": "ÜRÜN"
    }
    if filters and filters.get("custom_musteri_grubu"):
        item_filters["custom_musteri_grubu"] = filters["custom_musteri_grubu"]
        
    result = frappe.get_all("Item", 
        filters=item_filters,
        fields=["item_group"], 
        distinct=True,
        limit_start=start,
        limit_page_length=page_len
    )
    return [[r.item_group] for r in result]

def get_period_dates(period_name, filters=None, start_date=None):
    """Periyot ismine göre başlangıç ve bitiş tarihlerini döner."""
    current_date = getdate(start_date or today())
    
    if period_name == "Özel" and filters:
        from_date = str(getdate(filters.get("from_date")) if filters.get("from_date") else current_date)
        to_date = str(getdate(filters.get("to_date")) if filters.get("to_date") else date(current_date.year, 12, 31))
        return from_date, to_date

    from_date = str(current_date)
    if period_name == "3 Aylık":
        to_date = str(add_months(current_date, 3))
    elif period_name == "6 Aylık":
        to_date = str(add_months(current_date, 6))
    elif period_name == "Süresiz":
        to_date = "2099-12-31"
    else:  # Yıllık (varsayılan)
        to_date = str(date(current_date.year, 12, 31))
        
    return from_date, to_date
