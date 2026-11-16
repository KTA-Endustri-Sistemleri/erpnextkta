import frappe
from frappe import _
from frappe.utils import today, getdate, cint, add_days
from collections import defaultdict
from erpnextkta.kta_mrp.report_utils import get_period_dates


def execute(filters=None):
	if not filters:
		filters = {}

	# Periyot filtresine göre tarihleri belirle
	from_date, to_date = get_period_dates(filters.get("periyot", "Yıllık"), filters)
	if filters.get("periyot") == "Süresiz":
		to_date = get_open_demand_end_date(from_date)

	# Filtre değerlerini al
	filter_ara_malzeme_grubu = filters.get("ara_malzeme_grubu", "")
	filter_musteri_grubu = filters.get("musteri_grubu") or []
	filter_item_group = filters.get("item_group", "")
	filter_sifir_tuketimi_goster = cint(filters.get("sifir_tuketimi_goster", 0))

	# Hammadde brüt ihtiyacını bitmiş ürün (müşteri grubu) kırılımıyla servis katmanından al
	from erpnextkta.kta_mrp.mrp_engine.service import get_gross_requirements

	gross_requirements = get_gross_requirements({"from_date": from_date, "to_date": to_date})

	# KTA Customer Group listesini al
	customer_groups = frappe.db.get_all(
		"KTA Customer Group", fields=["name"], order_by="name"
	)
	cg_names = [cg.name for cg in customer_groups]

	# Hammadde bazında müşteri grubu kırılımını hesapla
	material_cg_totals = defaultdict(lambda: defaultdict(float))
	material_all_totals = defaultdict(float)

	for pegging in gross_requirements.pegging:
		material_cg_totals[pegging.material][pegging.customer_group] += pegging.total
		material_all_totals[pegging.material] += pegging.total

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
			fields=["name", "item_name", "item_group", "stock_uom", "custom_ara_malzeme_grubu", "custom_musteri_grubu"],
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
		{"label": _("Birim"), "fieldname": "birim", "fieldtype": "Data", "width": 80},
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
	uom_totals = defaultdict(lambda: defaultdict(float))
	total_bakiye_degeri = 0.0
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
		uom = item_info.stock_uom if item_info and item_info.stock_uom else _("Adet")

		row = {
			"hammadde_kodu": hammadde,
			"grup": item_group,
			"hammadde_adi": item_info.item_name if item_info else "",
			"birim": uom,
			"varsayilan_tedarikci": supplier,
			"fiyat": price_map.get(hammadde, 0),
			"para_birimi": currency_map.get(hammadde, ""),
			"depo_stok": depo_stok,
			"rezerve_stok": rezerve_stok,
			"serbest_stok": serbest_stok,
			"bakiye_degeri": bakiye_degeri,
			"ara_malzeme_grubu": ara_malzeme,
		}

		uom_totals[uom]["depo_stok"] += depo_stok
		uom_totals[uom]["rezerve_stok"] += rezerve_stok
		uom_totals[uom]["serbest_stok"] += serbest_stok
		total_bakiye_degeri += bakiye_degeri

		for cg in cg_names:
			fieldname = cg_fieldnames[cg]
			row[fieldname] = cg_values[fieldname]
			uom_totals[uom][fieldname] += cg_values[fieldname]

		row["genel_toplam"] = round(genel_toplam, 2)
		uom_totals[uom]["genel_toplam"] += genel_toplam

		if genel_toplam > 0:
			dist_parts = [f"{cg}%{(cg_data.get(cg,0)/genel_toplam)*100:,.1f}" for cg in cg_names if cg_data.get(cg,0) > 0]
			row["musteri_grubu_dagilimi"] = "-".join(dist_parts)
		else:
			row["musteri_grubu_dagilimi"] = ""

		row["musteri_grubu"] = item_info.custom_musteri_grubu if item_info and item_info.custom_musteri_grubu else "-"
		row["toplam_tuketim"] = toplam_tuketim
		uom_totals[uom]["toplam_tuketim"] += toplam_tuketim
		row["fark_oran"] = round(((toplam_tuketim - genel_toplam) / genel_toplam * 100), 6) if genel_toplam > 0 else 0

		data.append(row)
		
		# Özet bilgileri için
		if row["depo_stok"] < row["genel_toplam"]:
			summary_shortage_count += 1
		summary_total_value += row["bakiye_degeri"]

	data.sort(key=lambda x: x.get("bakiye_degeri", 0), reverse=True)

	# Birim Bazlı Alt Toplam Satırları
	sorted_uoms = sorted(
		uom_totals.keys(),
		key=lambda u: (0 if u == "Metre" else 1 if u == "Adet" else 2, str(u)),
	)

	for u in sorted_uoms:
		t_depo = round(uom_totals[u]["depo_stok"], 2)
		t_rezerve = round(uom_totals[u]["rezerve_stok"], 2)
		t_serbest = round(t_depo - t_rezerve, 2)
		t_genel = round(uom_totals[u]["genel_toplam"], 2)
		t_tuketim = round(uom_totals[u]["toplam_tuketim"], 2)

		uom_row = {
			"hammadde_kodu": f"{_('TOPLAM')} ({u})",
			"birim": u,
			"is_total_row": 1,
			"depo_stok": t_depo,
			"rezerve_stok": t_rezerve,
			"serbest_stok": t_serbest,
			"genel_toplam": t_genel,
			"toplam_tuketim": t_tuketim,
			"fark_oran": round(((t_tuketim - t_genel) / t_genel * 100), 6) if t_genel > 0 else 0,
		}
		for cg in cg_names:
			fn = cg_fieldnames[cg]
			uom_row[fn] = round(uom_totals[u][fn], 2)
		data.append(uom_row)

	# Genel Bakiye Değeri Satırı
	data.append({
		"hammadde_kodu": _("GENEL BAKİYE DEĞERİ"),
		"is_total_row": 1,
		"bakiye_degeri": round(total_bakiye_degeri, 2),
	})

	total_rows_count = len(sorted_uoms) + 1

	# Summary Cards
	report_summary = [
		{"value": len(data) - total_rows_count, "label": _("Toplam Kalem"), "indicator": "Blue"},
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


def get_open_demand_end_date(from_date, min_days=90):
	"""Süresiz periyot için: açık SO teslim, MR ve İş Emri tarihlerinin en geç olanı.

	2099'a kadar haftalık kolon üretmek yerine raporu son açık talebe kadar çalıştırır.
	"""
	last_dates = frappe.db.sql(
		"""
		SELECT MAX(so.delivery_date) FROM `tabSales Order` so
		WHERE so.docstatus = 1 AND so.status NOT IN ('Closed', 'Completed')
		UNION ALL
		SELECT MAX(mr.schedule_date) FROM `tabMaterial Request` mr
		WHERE mr.docstatus = 1 AND mr.material_request_type = 'Manufacture'
		AND mr.status NOT IN ('Completed', 'Stopped', 'Cancelled')
		UNION ALL
		SELECT MAX(DATE(wo.planned_start_date)) FROM `tabWork Order` wo
		WHERE wo.docstatus = 1 AND wo.status IN ('Not Started', 'In Process')
		"""
	)
	end_date = add_days(getdate(from_date), min_days)
	for (d,) in last_dates:
		if d and getdate(d) > end_date:
			end_date = getdate(d)
	return str(end_date)
