import frappe
from frappe import _
from frappe.utils import cint
from collections import defaultdict
from erpnextkta.kta_mrp.report_utils import get_period_dates


def execute(filters=None):
	if not filters:
		filters = {}

	# Periyot filtresine göre tarihleri belirle
	from_date, to_date = get_period_dates(filters.get("periyot", "Yıllık"), filters)

	# Filtre değerlerini al
	filter_ara_malzeme_grubu = filters.get("ara_malzeme_grubu", "")
	filter_musteri_grubu = filters.get("musteri_grubu") or []
	filter_item_group = filters.get("item_group", "")
	filter_sifir_tuketimi_goster = cint(filters.get("sifir_tuketimi_goster", 0))

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

	mr_res = mr_execute(mr_filters)
	mr_columns, mr_data = mr_res[0], mr_res[1]

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

	# Sıfır tüketimi göster aktifse stokta bulunan HAMMADDE ve OBS* kalemlerini de dahil et
	if filter_sifir_tuketimi_goster:
		for item_code in get_zero_consumption_items():
			if item_code not in material_cg_totals:
				raw_materials.append(item_code)
				material_all_totals[item_code] = 0

	# Verileri toplu al
	item_info_map = {}
	default_supplier_map = {}
	price_map = {}
	currency_map = {}
	stock_map = {}
	stock_value_map = {}
	reserved_map = {}

	if raw_materials:
		items = frappe.db.get_all(
			"Item",
			filters={"name": ["in", raw_materials]},
			fields=["name", "item_name", "item_group", "custom_ara_malzeme_grubu", "custom_musteri_grubu"],
		)
		item_info_map = {i.name: i for i in items}

		supplier_data = frappe.db.get_all(
			"Item Default",
			filters={"parent": ["in", raw_materials]},
			fields=["parent", "default_supplier"],
		)
		for s in supplier_data:
			if s.default_supplier:
				default_supplier_map[s.parent] = s.default_supplier

		# Fiyatları daimi olarak varsayılan tedarikçi üzerinden çek
		price_data = frappe.db.sql(
			"""
			SELECT ip.item_code, ip.price_list_rate, ip.currency, ip.supplier
			FROM `tabItem Price` ip
			INNER JOIN (
				SELECT item_code, supplier, MAX(creation) as max_creation
				FROM `tabItem Price`
				WHERE item_code IN %s AND buying = 1 AND supplier IS NOT NULL AND supplier != ''
				GROUP BY item_code, supplier
			) latest ON ip.item_code = latest.item_code AND ip.supplier = latest.supplier AND ip.creation = latest.max_creation
			WHERE ip.buying = 1
		""",
			[tuple(raw_materials)],
			as_dict=True,
		)
		for p in price_data:
			def_sup = default_supplier_map.get(p.item_code)
			if def_sup and def_sup == p.supplier:
				price_map[p.item_code] = p.price_list_rate
				currency_map[p.item_code] = p.currency

		stock_data = frappe.db.sql(
			"""
			SELECT 
				bin.item_code, 
				SUM(bin.actual_qty) as total_qty, 
				SUM(bin.stock_value) as total_value,
				SUM(
					COALESCE(bin.reserved_qty_for_production, 0) + 
					COALESCE(bin.reserved_qty, 0) + 
					COALESCE(bin.reserved_qty_for_sub_contract, 0)
				) as total_reserved
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
			reserved_map[d.item_code] = d.total_reserved or 0

	# Kolonlar
	columns = [
		{"label": _("Hammadde Kodu"), "fieldname": "hammadde_kodu", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Grup"), "fieldname": "grup", "fieldtype": "Data", "width": 140},
		{"label": _("Hammadde Adı"), "fieldname": "hammadde_adi", "fieldtype": "Data", "width": 200},
		{"label": _("Varsayılan Tedarikçi"), "fieldname": "varsayilan_tedarikci", "fieldtype": "Link", "options": "Supplier", "width": 180},
		{"label": _("Fiyat"), "fieldname": "fiyat", "fieldtype": "Float", "width": 100},
		{"label": _("Para Birimi"), "fieldname": "para_birimi", "fieldtype": "Data", "width": 80},
		{"label": _("Depo Stok"), "fieldname": "depo_stok", "fieldtype": "Float", "width": 100},
		{"label": _("Rezerve Miktar"), "fieldname": "rezerve_stok", "fieldtype": "Float", "width": 110},
		{"label": _("Serbest Stok"), "fieldname": "serbest_stok", "fieldtype": "Float", "width": 110},
		{"label": _("Bakiye Değeri (TL)"), "fieldname": "bakiye_degeri", "fieldtype": "Float", "width": 130},
		{"label": _("Müşteri Grubu Dağılımı"), "fieldname": "musteri_grubu_dagilimi", "fieldtype": "Data", "width": 220},
		{"label": _("Ara Malzeme Grubu"), "fieldname": "ara_malzeme_grubu", "fieldtype": "Data", "width": 140},
	]

	cg_fieldnames = {}
	for cg in cg_names:
		fieldname = frappe.scrub(cg)
		cg_fieldnames[cg] = fieldname
		columns.append({"label": cg, "fieldname": fieldname, "fieldtype": "Float", "width": 100})

	columns += [
		{"label": _("Genel Toplam"), "fieldname": "genel_toplam", "fieldtype": "Float", "width": 120},
		{"label": _("Müşteri Grubu"), "fieldname": "musteri_grubu", "fieldtype": "Data", "width": 120},
		{"label": _("Toplam Tüketim (Kapasite)"), "fieldname": "toplam_tuketim", "fieldtype": "Float", "width": 160},
		{"label": _("Fark Oran"), "fieldname": "fark_oran", "fieldtype": "Percent", "width": 100},
	]

	# Veriler
	data = []
	column_totals = defaultdict(float)
	summary_shortage_count = 0
	summary_total_value = 0

	for hammadde in sorted(raw_materials):
		item_info = item_info_map.get(hammadde)
		cg_data = material_cg_totals[hammadde]

		ara_malzeme = item_info.custom_ara_malzeme_grubu if item_info else ""
		if filter_ara_malzeme_grubu and ara_malzeme != filter_ara_malzeme_grubu:
			continue

		item_group = item_info.item_group if item_info else ""
		if filter_item_group and item_group != filter_item_group:
			continue

		supplier = default_supplier_map.get(hammadde, "")

		genel_toplam = 0
		cg_values = {}
		for cg in cg_names:
			fieldname = cg_fieldnames[cg]
			val = round(cg_data.get(cg, 0), 2)
			cg_values[fieldname] = val
			genel_toplam += val

		toplam_tuketim = round(material_all_totals.get(hammadde, 0), 2)

		if filter_musteri_grubu:
			has_consumption = any(cg_data.get(cg, 0) > 0 for cg in filter_musteri_grubu)
			matches_item_cg = item_info and item_info.custom_musteri_grubu in filter_musteri_grubu
			if not (has_consumption or (filter_sifir_tuketimi_goster and matches_item_cg)):
				continue

		if not filter_sifir_tuketimi_goster and genel_toplam == 0:
			continue

		depo_stok = stock_map.get(hammadde, 0)
		rezerve_stok = reserved_map.get(hammadde, 0)
		serbest_stok = round(depo_stok - rezerve_stok, 2)
		bakiye_degeri = stock_value_map.get(hammadde, 0)

		row = {
			"hammadde_kodu": hammadde,
			"grup": item_group,
			"hammadde_adi": item_info.item_name if item_info else "",
			"varsayilan_tedarikci": supplier,
			"fiyat": price_map.get(hammadde, 0),
			"para_birimi": currency_map.get(hammadde, ""),
			"depo_stok": depo_stok,
			"rezerve_stok": rezerve_stok,
			"serbest_stok": serbest_stok,
			"bakiye_degeri": bakiye_degeri,
			"ara_malzeme_grubu": ara_malzeme,
		}

		column_totals["depo_stok"] += depo_stok
		column_totals["rezerve_stok"] += rezerve_stok
		column_totals["serbest_stok"] += serbest_stok
		column_totals["bakiye_degeri"] += bakiye_degeri

		for cg in cg_names:
			fieldname = cg_fieldnames[cg]
			row[fieldname] = cg_values[fieldname]
			column_totals[fieldname] += cg_values[fieldname]

		row["genel_toplam"] = round(genel_toplam, 2)
		column_totals["genel_toplam"] += genel_toplam

		if genel_toplam > 0:
			dist_parts = [f"{cg}%{(cg_data.get(cg,0)/genel_toplam)*100:,.1f}" for cg in cg_names if cg_data.get(cg,0) > 0]
			row["musteri_grubu_dagilimi"] = "-".join(dist_parts)
		else:
			row["musteri_grubu_dagilimi"] = ""

		row["musteri_grubu"] = item_info.custom_musteri_grubu if item_info and item_info.custom_musteri_grubu else "-"
		row["toplam_tuketim"] = toplam_tuketim
		column_totals["toplam_tuketim"] += toplam_tuketim
		row["fark_oran"] = round(((toplam_tuketim - genel_toplam) / genel_toplam * 100), 6) if genel_toplam > 0 else 0

		data.append(row)
		
		# Özet bilgileri için
		if row["depo_stok"] < row["genel_toplam"]:
			summary_shortage_count += 1
		summary_total_value += row["bakiye_degeri"]

	data.sort(key=lambda x: x.get("bakiye_degeri", 0), reverse=True)

	# Toplam satırı
	total_depo = round(column_totals["depo_stok"], 2)
	total_rezerve = round(column_totals["rezerve_stok"], 2)

	total_row = {
		"hammadde_kodu": _("TOPLAM"),
		"is_total_row": 1,
		"depo_stok": total_depo,
		"rezerve_stok": total_rezerve,
		"serbest_stok": round(total_depo - total_rezerve, 2),
		"bakiye_degeri": round(column_totals["bakiye_degeri"], 2),
	}
	for cg in cg_names:
		fn = cg_fieldnames[cg]
		total_row[fn] = round(column_totals[fn], 2)
	total_row["genel_toplam"] = round(column_totals["genel_toplam"], 2)
	total_row["toplam_tuketim"] = round(column_totals["toplam_tuketim"], 2)
	total_row["fark_oran"] = round(((column_totals["toplam_tuketim"] - column_totals["genel_toplam"]) / column_totals["genel_toplam"] * 100), 6) if column_totals["genel_toplam"] > 0 else 0
	data.append(total_row)

	# Summary Cards
	report_summary = [
		{"value": len(data) - 1, "label": _("Toplam Kalem"), "indicator": "Blue"},
		{"value": summary_shortage_count, "label": _("Eksik Kalem"), "indicator": "Red"},
		{"value": frappe.format(summary_total_value, "Currency"), "label": _("Toplam Stok Değeri"), "indicator": "Green"}
	]

	return columns, data, None, None, report_summary


def get_zero_consumption_items():
	"""Kullanılabilir stokta olan ve ara malzeme grubu HAMMADDE ya da OBS ile başlayan kalemler."""
	return frappe.db.sql_list(
		"""
		SELECT DISTINCT bin.item_code
		FROM `tabBin` bin
		INNER JOIN `tabWarehouse` wh ON bin.warehouse = wh.name
		INNER JOIN `tabItem` item ON item.name = bin.item_code
		WHERE wh.warehouse_type = 'Kullanılabilir Stok'
		  AND bin.actual_qty > 0
		  AND item.disabled = 0
		  AND (item.custom_ara_malzeme_grubu = 'HAMMADDE' OR item.custom_ara_malzeme_grubu LIKE 'OBS%%')
		"""
	)
