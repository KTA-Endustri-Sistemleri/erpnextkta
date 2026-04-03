import frappe
from frappe.utils import today, getdate
from collections import defaultdict
from datetime import date


def execute(filters=None):
	if not filters:
		filters = {}

	current_date = getdate(today())
	from_date = str(current_date)
	to_date = str(date(current_date.year, 12, 31))

	# Filtre değerlerini al
	filter_ara_malzeme_grubu = filters.get("ara_malzeme_grubu", "")
	filter_musteri_grubu = filters.get("musteri_grubu") or []
	filter_item_group = filters.get("item_group", "")
	filter_varsayilan_tedarikci = filters.get("varsayilan_tedarikci", "")
	filter_sifir_tuketimi_goster = filters.get("sifir_tuketimi_goster", 0)

	# Material Requirement raporunu "Bitmiş Ürün + Hammadde" modunda çalıştır
	from erpnextkta.kta_mrp.report.material_requirement.material_requirement import (
		execute as mr_execute,
	)

	mr_filters = {
		"from_date": from_date,
		"to_date": to_date,
		"stage": "1 - Temel Hammadde İhtiyacı",
		"group_by": "Bitmiş Ürün + Hammadde",
	}

	mr_columns, mr_data = mr_execute(mr_filters)

	# KTA Customer Group listesini al
	customer_groups = frappe.db.get_all(
		"KTA Customer Group", fields=["name"], order_by="name"
	)
	cg_names = [cg.name for cg in customer_groups]

	# Hammadde bazında müşteri grubu kırılımını hesapla
	material_cg_totals = defaultdict(lambda: defaultdict(float))
	material_all_totals = defaultdict(float)

	for row in mr_data:
		hammadde = row.get("hammadde")
		bitmis_urun = row.get("bitmis_urun", "")
		if not hammadde or "<b>" in str(bitmis_urun):
			continue

		musteri_grubu = row.get("musteri_grubu", "") or ""
		satir_toplami = row.get("satir_toplami", 0) or 0

		material_cg_totals[hammadde][musteri_grubu] += satir_toplami
		material_all_totals[hammadde] += satir_toplami

	raw_materials = list(material_cg_totals.keys())

	# Hammadde item bilgilerini toplu al
	item_info_map = {}
	if raw_materials:
		items = frappe.db.get_all(
			"Item",
			filters={"name": ["in", raw_materials]},
			fields=[
				"name",
				"item_name",
				"item_group",
				"custom_ara_malzeme_grubu",
				"custom_musteri_grubu",
			],
		)
		item_info_map = {i.name: i for i in items}

	# Varsayılan tedarikçi bilgilerini toplu al
	default_supplier_map = {}
	if raw_materials:
		supplier_data = frappe.db.get_all(
			"Item Default",
			filters={"parent": ["in", raw_materials]},
			fields=["parent", "default_supplier"],
		)
		for s in supplier_data:
			if s.default_supplier:
				default_supplier_map[s.parent] = s.default_supplier

	# Son alış fiyatı ve para birimini al
	price_map = {}
	currency_map = {}
	if raw_materials:
		price_data = frappe.db.sql(
			"""
			SELECT ip.item_code, ip.price_list_rate, ip.currency
			FROM `tabItem Price` ip
			INNER JOIN (
				SELECT item_code, MAX(creation) as max_creation
				FROM `tabItem Price`
				WHERE item_code IN %s AND buying = 1
				GROUP BY item_code
			) latest ON ip.item_code = latest.item_code AND ip.creation = latest.max_creation
			WHERE ip.buying = 1
		""",
			[tuple(raw_materials)],
			as_dict=True,
		)
		for p in price_data:
			price_map[p.item_code] = p.price_list_rate
			currency_map[p.item_code] = p.currency

	# Stok ve stok değeri bilgilerini al (Kullanılabilir Stok depolarından)
	stock_map = {}
	stock_value_map = {}
	if raw_materials:
		stock_data = frappe.db.sql(
			"""
			SELECT bin.item_code, SUM(bin.actual_qty) as total_qty, SUM(bin.stock_value) as total_value
			FROM `tabBin` bin
			INNER JOIN `tabWarehouse` wh ON bin.warehouse = wh.name
			WHERE bin.item_code IN %s
			AND wh.warehouse_type = 'Kullanılabilir Stok'
			GROUP BY bin.item_code
		""",
			[tuple(raw_materials)],
			as_dict=True,
		)
		for d in stock_data:
			stock_map[d.item_code] = d.total_qty or 0
			stock_value_map[d.item_code] = d.total_value or 0

	# Kolon tanımlamaları
	columns = [
		{
			"label": "Hammadde Kodu",
			"fieldname": "hammadde_kodu",
			"fieldtype": "Link",
			"options": "Item",
			"width": 130,
		},
		{
			"label": "Grup",
			"fieldname": "grup",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": "Hammadde Adı",
			"fieldname": "hammadde_adi",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": "Varsayılan Tedarikçi",
			"fieldname": "varsayilan_tedarikci",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 180,
		},
		{
			"label": "Fiyat",
			"fieldname": "fiyat",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": "Para Birimi",
			"fieldname": "para_birimi",
			"fieldtype": "Data",
			"width": 80,
		},
		{
			"label": "Depo Stok",
			"fieldname": "depo_stok",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": "Bakiye Değeri",
			"fieldname": "bakiye_degeri",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": "Müşteri Grubu Dağılımı",
			"fieldname": "musteri_grubu_dagilimi",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": "Ara Malzeme Grubu",
			"fieldname": "ara_malzeme_grubu",
			"fieldtype": "Data",
			"width": 140,
		},
	]

	# Dinamik müşteri grubu sütunları
	cg_fieldnames = {}
	for cg in cg_names:
		fieldname = frappe.scrub(cg)
		cg_fieldnames[cg] = fieldname
		columns.append(
			{
				"label": cg,
				"fieldname": fieldname,
				"fieldtype": "Float",
				"width": 100,
			}
		)

	columns += [
		{
			"label": "Genel Toplam",
			"fieldname": "genel_toplam",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": "Müşteri Grubu",
			"fieldname": "musteri_grubu",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": "Toplam Tüketim (Kapasite)",
			"fieldname": "toplam_tuketim",
			"fieldtype": "Float",
			"width": 160,
		},
		{
			"label": "Fark Oran",
			"fieldname": "fark_oran",
			"fieldtype": "Percent",
			"width": 100,
		},
	]

	# Veri satırlarını oluştur
	data = []
	column_totals = defaultdict(float)

	for hammadde in sorted(raw_materials):
		item_info = item_info_map.get(hammadde)
		cg_data = material_cg_totals[hammadde]

		# --- Filtre kontrolleri ---
		# Ara Malzeme Grubu filtresi
		ara_malzeme = item_info.custom_ara_malzeme_grubu if item_info else ""
		if filter_ara_malzeme_grubu and ara_malzeme != filter_ara_malzeme_grubu:
			continue

		# Hammadde Grubu (Item Group) filtresi
		item_group = item_info.item_group if item_info else ""
		if filter_item_group and item_group != filter_item_group:
			continue

		# Varsayılan Tedarikçi filtresi
		supplier = default_supplier_map.get(hammadde, "")
		if filter_varsayilan_tedarikci and supplier != filter_varsayilan_tedarikci:
			continue

		# Müşteri grubu sütun değerleri hesapla
		genel_toplam = 0
		cg_values = {}
		for cg in cg_names:
			fieldname = cg_fieldnames[cg]
			val = round(cg_data.get(cg, 0), 2)
			cg_values[fieldname] = val
			genel_toplam += val

		toplam_tuketim = round(material_all_totals.get(hammadde, 0), 2)

		# Müşteri Grubu filtresi (seçilen gruplarda tüketimi olan hammaddeler)
		if filter_musteri_grubu:
			has_consumption = any(cg_data.get(cg, 0) > 0 for cg in filter_musteri_grubu)
			if not has_consumption:
				continue

		# Sıfır tüketimi göster filtresi
		if not filter_sifir_tuketimi_goster and genel_toplam == 0:
			continue

		row = {
			"hammadde_kodu": hammadde,
			"grup": item_group,
			"hammadde_adi": item_info.item_name if item_info else "",
			"varsayilan_tedarikci": supplier,
			"fiyat": price_map.get(hammadde, 0),
			"para_birimi": currency_map.get(hammadde, ""),
			"depo_stok": stock_map.get(hammadde, 0),
			"bakiye_degeri": stock_value_map.get(hammadde, 0),
			"ara_malzeme_grubu": ara_malzeme,
		}

		# Müşteri grubu sütun değerlerini row'a ekle
		for cg in cg_names:
			fieldname = cg_fieldnames[cg]
			row[fieldname] = cg_values[fieldname]
			column_totals[fieldname] += cg_values[fieldname]

		row["genel_toplam"] = round(genel_toplam, 2)
		column_totals["genel_toplam"] += genel_toplam

		# Müşteri grubu yoğunluk dağılımı string'i
		if genel_toplam > 0:
			dist_parts = []
			for cg in cg_names:
				val = cg_data.get(cg, 0)
				if val > 0:
					pct = (val / genel_toplam) * 100
					dist_parts.append(f"{cg}%{pct:,.2f}")
			row["musteri_grubu_dagilimi"] = "-".join(dist_parts) if dist_parts else ""
		else:
			row["musteri_grubu_dagilimi"] = ""

		# Müşteri grubu (Item master'dan)
		musteri_grubu = item_info.custom_musteri_grubu if item_info else ""
		row["musteri_grubu"] = musteri_grubu if musteri_grubu else "-"

		# Toplam tüketim
		row["toplam_tuketim"] = toplam_tuketim
		column_totals["toplam_tuketim"] += toplam_tuketim

		# Fark oranı: (Toplam Tüketim - Genel Toplam) / Genel Toplam
		if genel_toplam > 0:
			row["fark_oran"] = round(
				((toplam_tuketim - genel_toplam) / genel_toplam) * 100, 6
			)
		else:
			row["fark_oran"] = 0

		data.append(row)

	# Bakiye değerine göre azalan sırala
	data.sort(key=lambda x: x.get("bakiye_degeri", 0), reverse=True)

	# Toplam satırı
	total_row = {
		"hammadde_kodu": "<b>TOPLAM</b>",
		"grup": "",
		"hammadde_adi": "",
		"varsayilan_tedarikci": "",
		"fiyat": "",
		"para_birimi": "",
		"depo_stok": "",
		"bakiye_degeri": "",
		"musteri_grubu_dagilimi": "",
		"ara_malzeme_grubu": "",
		"musteri_grubu": "",
	}

	for cg in cg_names:
		fieldname = cg_fieldnames[cg]
		total_row[fieldname] = round(column_totals[fieldname], 2)

	total_row["genel_toplam"] = round(column_totals["genel_toplam"], 2)
	total_row["toplam_tuketim"] = round(column_totals["toplam_tuketim"], 2)

	if column_totals["genel_toplam"] > 0:
		total_row["fark_oran"] = round(
			(
				(column_totals["toplam_tuketim"] - column_totals["genel_toplam"])
				/ column_totals["genel_toplam"]
			)
			* 100,
			6,
		)
	else:
		total_row["fark_oran"] = 0

	data.append(total_row)

	return columns, data


@frappe.whitelist()
def get_ara_malzeme_gruplari():
	"""Ara Malzeme Grubu filtresi için mevcut değerleri döndür."""
	result = frappe.db.sql(
		"""
		SELECT DISTINCT custom_ara_malzeme_grubu
		FROM `tabItem`
		WHERE custom_ara_malzeme_grubu IS NOT NULL
		AND custom_ara_malzeme_grubu != ''
		ORDER BY custom_ara_malzeme_grubu
	""",
		as_list=True,
	)
	return [r[0] for r in result]


@frappe.whitelist()
def get_item_groups():
	"""Hammadde Grubu filtresi için mevcut item group değerlerini döndür."""
	result = frappe.db.sql(
		"""
		SELECT DISTINCT item_group
		FROM `tabItem`
		WHERE item_group IS NOT NULL
		AND item_group != ''
		ORDER BY item_group
	""",
		as_list=True,
	)
	return [r[0] for r in result]
