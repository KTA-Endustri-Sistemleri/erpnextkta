# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

COMPANY = "TEST"
WAREHOUSE_RM = "Stores - TEST"  # Hammadde Deposu
WAREHOUSE_FG = "Finished Goods - TEST"  # Ürün Deposu
WAREHOUSE_WIP = "Work In Progress - TEST"  # WIP Deposu
WAREHOUSE = WAREHOUSE_RM  # Geriye dönük uyumluluk
ITEM_GROUP_FG = "KABLO GRUBU"
ITEM_GROUP_RM = "Hammadde"

# Customer codes & delivery parameters
CUSTOMERS = {
	"MUSTERI-AVRUPA": {
		"customer_name": "MUSTERI-AVRUPA",
		"customer_group": "Commercial",
		"custom_shipping_lead_days": 5,
		"production_time": 7,
		"delivery_time": 5,
	},
	"MUSTERI-YERLI": {
		"customer_name": "MUSTERI-YERLI",
		"customer_group": "Commercial",
		"custom_shipping_lead_days": 1,
		"production_time": 3,
		"delivery_time": 1,
	},
}

# Suppliers
SUPPLIERS = {
	"TEDARIKCI-ITHALAT": {
		"supplier_name": "TEDARIKCI-ITHALAT",
		"supplier_group": "Local",
	},
	"TEDARIKCI-YERLI": {
		"supplier_name": "TEDARIKCI-YERLI",
		"supplier_group": "Local",
	},
}

# Workstations & Operations
WORKSTATIONS = ["Kesim Hattı", "Krimp Presi", "Montaj Masası"]
OPERATIONS = ["Kablo Kesim", "Terminal Krimp", "Grup Montaj"]

# Finished Goods
FINISHED_GOODS = {
	"URUN-01": {
		"item_name": "URUN-01 (İhracat Kablo Demeti)",
		"item_group": ITEM_GROUP_FG,
		"stock_uom": "Adet",
		"custom_weekly_production": 500,
		"custom_manufacturing_lead_days": 7,
		"custom_ara_malzeme_grubu": "ÜRÜN",
		"reorder_level": 20,
		"reorder_qty": 100,
	},
	"URUN-02": {
		"item_name": "URUN-02 (Yurtiçi Kablo Grubu)",
		"item_group": ITEM_GROUP_FG,
		"stock_uom": "Adet",
		"custom_weekly_production": 400,
		"custom_manufacturing_lead_days": 3,
		"custom_ara_malzeme_grubu": "ÜRÜN",
	},
}

# Raw Materials
RAW_MATERIALS = {
	"HAMMADDE-01": {
		"item_name": "HAMMADDE-01 (FLRY-B 0.50mm² Kablo)",
		"stock_uom": "Metre",
		"custom_ara_malzeme_grubu": "HAMMADDE",
		"default_supplier": "TEDARIKCI-YERLI",
		"state": "Kısmi Serbest Stok (500 Mtr)",
	},
	"HAMMADDE-02": {
		"item_name": "HAMMADDE-02 (Dişi Terminal 2.8mm)",
		"stock_uom": "Adet",
		"custom_ara_malzeme_grubu": "HAMMADDE",
		"default_supplier": "TEDARIKCI-YERLI",
		"state": "Açık Satınalma Siparişi (1.000 Adet)",
	},
	"HAMMADDE-03": {
		"item_name": "HAMMADDE-03 (6-Way Konnektör Gövdesi)",
		"stock_uom": "Adet",
		"custom_ara_malzeme_grubu": "HAMMADDE",
		"default_supplier": "TEDARIKCI-ITHALAT",
		"state": "Yolda / In-Transit İrsaliye (500 Adet)",
	},
	"HAMMADDE-04": {
		"item_name": "HAMMADDE-04 (Kablo Grommet / Kauçuk)",
		"stock_uom": "Adet",
		"custom_ara_malzeme_grubu": "HAMMADDE",
		"default_supplier": "TEDARIKCI-ITHALAT",
		"state": "Antrepoda İrsaliye (800 Adet)",
	},
	"HAMMADDE-05": {
		"item_name": "HAMMADDE-05 (Mini Sigorta Kutusu)",
		"stock_uom": "Adet",
		"custom_ara_malzeme_grubu": "HAMMADDE",
		"default_supplier": "TEDARIKCI-ITHALAT",
		"state": "Gümrüklemede İrsaliye (400 Adet)",
	},
	"HAMMADDE-06": {
		"item_name": "HAMMADDE-06 (Yalıtım PVC Bant)",
		"stock_uom": "Adet",
		"custom_ara_malzeme_grubu": "HAMMADDE",
		"default_supplier": "TEDARIKCI-YERLI",
		"state": "Tam Yeterli Serbest Stok (2.000 Adet)",
	},
	"HAMMADDE-07": {
		"item_name": "HAMMADDE-07 (Erkek Pin Terminal)",
		"stock_uom": "Adet",
		"custom_ara_malzeme_grubu": "HAMMADDE",
		"default_supplier": "TEDARIKCI-ITHALAT",
		"state": "Kritik Açık (Sıfır Stok/Sipariş -> Önerilen PO)",
		"min_order_qty": 1000,
		"custom_paket_miktari": 250,
		"lead_time_days": 14,
	},
}
