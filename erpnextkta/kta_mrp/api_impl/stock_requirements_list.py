import frappe
from frappe import _
from frappe.utils import flt, cint, formatdate, getdate, today, add_months, add_days
from collections import defaultdict
from datetime import date
import math

# Tarih filtresinden muaf, sıralamada en üstte tutulan elementler (değer = sıra)
FIXED_ELEMENT_TYPES = {"Stock": 0, "SafeSt": 1}


@frappe.whitelist()
def get_stock_requirements(item_code, from_date=None, to_date=None, show_bom_explosion=0, weekly_view=0):
    """Tek bir malzeme kodu için SAP MD04 benzeri stok/ihtiyaç listesi döner.
    Tarih belirtilmediğinde tüm açık hareketler (tüm zamanlar) incelenir.
    """
    if not item_code:
        frappe.throw(_("Malzeme kodu belirtilmedi"))

    from_date = getdate(from_date) if from_date else None
    to_date = getdate(to_date) if to_date else None
    show_bom_explosion = int(show_bom_explosion)
    weekly_view = int(weekly_view)

    item_info = _get_item_info(item_code)
    if not item_info:
        frappe.throw(_("Malzeme bulunamadı: {0}").format(item_code))

    elements = []

    today_d = getdate(today())
    stock_date = from_date or today_d

    # 1. Mevcut Stok
    stock_qty = _get_current_stock(item_code)
    elements.append(_make_element(
        element_date=stock_date,
        mrp_type="Stock",
        label=_("Mevcut Stok"),
        receipt_qty=stock_qty,
    ))

    # 1b. Emniyet Stoku / Yeniden Sipariş Seviyesi (Talep)
    safety_stock = flt(item_info.get("safety_stock", 0))
    safety_element = _get_safety_stock_element(item_info, stock_date)
    if safety_element:
        elements.append(safety_element)

    # 2. Satış Siparişleri (Talep)
    elements.extend(_get_sales_order_elements(item_code))

    # 3. Satın Alma Siparişleri (Arz)
    elements.extend(_get_purchase_order_elements(item_code))

    # 4. İş Emri elementleri (PrdOrd: Kesinleşmiş Üretim Emri)
    elements.extend(_get_work_order_elements(item_code, item_info))

    # 4b. Planlı Sipariş elementleri (PldOrd: Bitmiş ürün için henüz iş emri açılmamış simülasyon arzı)
    if not item_info.get("is_procured"):
        elements.extend(_get_planned_order_elements(item_code, item_info))

    # 5. Material Request elementleri
    elements.extend(_get_material_request_elements(item_code))

    # 5b. Simüle bağımlı ihtiyaç (hammadde için: iş emri açılmamış satış siparişleri × BOM)
    elements.extend(_get_simulated_requirement_elements(item_code))

    # 5c. Satın Alma Önerisi (PurRqs: Hammadde için haftalık açık kaldığında PO önerisi)
    if item_info.get("is_procured"):
        elements.extend(_get_purchase_proposal_elements(item_code, item_info, elements))

    # 6. BOM Patlatma (opsiyonel — bitmiş ürün seçildiğinde alt malzemeler)
    bom_children = []
    if show_bom_explosion:
        bom_children = _get_bom_explosion_children(item_code)

    # Tarih filtresi (yalnızca tarih sınırı açıkça belirtilmişse)
    if to_date or from_date:
        elements = _filter_by_date(elements, from_date, to_date)

    # Kronolojik sırala ve kümülatif bakiye hesapla
    elements = _sort_and_calculate_running_balance(elements)

    # İstisna tespiti
    elements = _detect_exceptions(elements, safety_stock)

    # Özet hesapla
    summary = _build_summary(elements, item_info, safety_stock)

    # Grafik verisi
    chart_data = _build_chart_data(elements, safety_stock)

    # Haftalık agregasyon
    weekly_elements = []
    if weekly_view:
        weekly_elements = _aggregate_weekly(elements)

    stock_el = next((e for e in elements if e["mrp_element_type"] == "Stock"), None)
    safest_el = next((e for e in elements if e["mrp_element_type"] == "SafeSt"), None)

    return {
        "item_info": item_info,
        "stock_element": stock_el,
        "safety_element": safest_el,
        "mrp_elements": weekly_elements if weekly_view else elements,
        "summary": summary,
        "chart_data": chart_data,
        "bom_children": bom_children,
    }


def _get_item_info(item_code):
    """Malzeme master bilgilerini topla."""
    item = frappe.db.get_value(
        "Item", item_code,
        [
            "name", "item_name", "item_group", "stock_uom",
            "safety_stock", "custom_ara_malzeme_grubu",
            "custom_musteri_grubu", "custom_weekly_production",
            "is_purchase_item", "include_item_in_manufacturing",
            "default_material_request_type", "is_sales_item",
        ],
        as_dict=True,
    )
    if not item:
        return None

    reorder_level, reorder_qty = _get_reorder_settings(item_code)

    item_default = frappe.db.get_value(
        "Item Default", {"parent": item_code}, ["default_supplier", "default_warehouse"], as_dict=True
    ) or {}
    default_supplier = item_default.get("default_supplier") or ""
    default_warehouse = item_default.get("default_warehouse") or ""

    today_d = getdate(today())
    price_records = frappe.db.sql(
        """
        SELECT
            supplier, price_list_rate, currency,
            lead_time_days, custom_minimum_order_quantity, custom_minimum_paketleme_miktari,
            valid_from, valid_upto
        FROM `tabItem Price`
        WHERE item_code = %s
          AND buying = 1
          AND (valid_from IS NULL OR valid_from <= %s)
          AND (valid_upto IS NULL OR valid_upto = '' OR valid_upto >= %s)
        ORDER BY valid_from DESC, creation DESC
        """,
        (item_code, today_d, today_d),
        as_dict=True,
    )

    suppliers_dict = {}
    for p in price_records:
        supp = p.supplier or ""
        if not supp or supp in suppliers_dict:
            continue
        suppliers_dict[supp] = {
            "supplier": supp,
            "rate": flt(p.price_list_rate),
            "currency": p.currency or "EUR",
            "lead_time_days": cint(p.lead_time_days),
            "moq": flt(p.custom_minimum_order_quantity) or 1.0,
            "paket": flt(p.custom_minimum_paketleme_miktari) or 1.0,
            "is_default": (supp == default_supplier),
        }

    if default_supplier and default_supplier not in suppliers_dict:
        suppliers_dict[default_supplier] = {
            "supplier": default_supplier,
            "rate": 0.0,
            "currency": "EUR",
            "lead_time_days": 0,
            "moq": 1.0,
            "paket": 1.0,
            "is_default": True,
        }

    suppliers_list = list(suppliers_dict.values())
    suppliers_list.sort(key=lambda s: (not s["is_default"], s["rate"]))

    primary_supplier = suppliers_list[0] if suppliers_list else {
        "supplier": default_supplier or "",
        "rate": 0.0,
        "currency": "EUR",
        "lead_time_days": 0,
        "moq": 1.0,
        "paket": 1.0,
        "is_default": True,
    }

    stock_qty = _get_current_stock(item_code)
    reserved_qty = _get_reserved_qty(item_code)
    ordered_qty = _get_ordered_qty(item_code)

    is_procured = bool(
        cint(item.is_purchase_item)
        or item.default_material_request_type == "Purchase"
    )

    return {
        "item_code": item.name,
        "item_name": item.item_name,
        "item_group": item.item_group or "",
        "uom": item.stock_uom or "",
        "default_supplier": default_supplier or "",
        "default_warehouse": default_warehouse or "",
        "lead_time_days": primary_supplier.get("lead_time_days", 0),
        "moq": primary_supplier.get("moq", 1.0),
        "paket": primary_supplier.get("paket", 1.0),
        "suppliers": suppliers_list,
        "primary_supplier": primary_supplier,
        "is_purchase_item": cint(item.is_purchase_item),
        "include_item_in_manufacturing": cint(item.include_item_in_manufacturing),
        "default_material_request_type": item.default_material_request_type or "",
        "is_sales_item": cint(item.is_sales_item),
        "is_procured": is_procured,
        # Yeniden sipariş seviyesi girili ise emniyet stoku olarak o kullanılır
        "safety_stock": reorder_level or flt(item.safety_stock),
        "reorder_level": reorder_level,
        "reorder_qty": reorder_qty,
        "current_stock": stock_qty,
        "reserved_qty": reserved_qty,
        "ordered_qty": ordered_qty,
        "available_qty": stock_qty - reserved_qty,
        "weekly_production": flt(item.custom_weekly_production),
        "ara_malzeme_grubu": item.custom_ara_malzeme_grubu or "",
        "musteri_grubu": item.custom_musteri_grubu or "",
    }


def _get_reorder_settings(item_code):
    """Item Reorder tablosundaki tüm depoların seviye ve miktar toplamını döner."""
    rows = frappe.get_all(
        "Item Reorder",
        filters={"parent": item_code, "parenttype": "Item"},
        fields=["warehouse_reorder_level", "warehouse_reorder_qty"],
    )
    reorder_level = sum(flt(d.warehouse_reorder_level) for d in rows)
    reorder_qty = sum(flt(d.warehouse_reorder_qty) for d in rows)
    return reorder_level, reorder_qty


def _get_safety_stock_element(item_info, from_date):
    """Emniyet stoku / yeniden sipariş seviyesini stok üzerinde talep olarak döner."""
    safety_stock = flt(item_info.get("safety_stock"))
    if safety_stock <= 0:
        return None
    label = _("Emniyet Stoku")
    if flt(item_info.get("reorder_level")) > 0:
        label = _("Yeniden Sipariş Seviyesi")
    return _make_element(
        element_date=from_date,
        mrp_type="SafeSt",
        label=label,
        requirement_qty=safety_stock,
        doctype="Item",
        element_data=item_info.get("item_code"),
        is_firmed=True,
    )


def _get_current_stock(item_code):
    """Tüm depolardaki toplam stok miktarı."""
    result = frappe.db.sql(
        """
        SELECT SUM(actual_qty)
        FROM `tabBin`
        WHERE item_code = %s
        """,
        (item_code,),
    )
    return flt(result[0][0]) if result and result[0][0] else 0


def _get_reserved_qty(item_code):
    """Bin tablosundaki toplam rezerve miktar."""
    result = frappe.db.sql(
        """
        SELECT SUM(reserved_qty)
        FROM `tabBin`
        WHERE item_code = %s
        """,
        (item_code,),
    )
    return flt(result[0][0]) if result and result[0][0] else 0


def _get_ordered_qty(item_code):
    """Bin tablosundaki toplam sipariş edilmiş miktar."""
    result = frappe.db.sql(
        """
        SELECT SUM(ordered_qty)
        FROM `tabBin`
        WHERE item_code = %s
        """,
        (item_code,),
    )
    return flt(result[0][0]) if result and result[0][0] else 0


def _get_sales_order_elements(item_code):
    """Açık satış siparişlerini talep olarak döner.

    Tarih = müşteri teslim tarihi − sevk (yol) süresi → fabrikadan çıkış tarihi.
    """
    rows = frappe.db.sql(
        """
        SELECT
            soi.delivery_date,
            soi.parent AS voucher_no,
            (soi.qty - soi.delivered_qty) AS pending_qty,
            so.customer, so.shipping_address_name, so.customer_address
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON soi.parent = so.name
        WHERE soi.item_code = %s
          AND so.docstatus = 1
          AND so.status NOT IN ('Closed', 'Cancelled', 'Completed')
          AND soi.qty > soi.delivered_qty
        ORDER BY soi.delivery_date
        """,
        (item_code,),
        as_dict=True,
    )
    return [_make_customer_order_element(d) for d in rows]


def _make_customer_order_element(d):
    """Sipariş satırını fabrika çıkış tarihli CustOrd elementine çevirir."""
    times = _get_sevk_times(d)
    ship_date = add_days(d.delivery_date, -times.delivery_time) if d.delivery_date else None
    return _make_element(
        element_date=ship_date,
        mrp_type="CustOrd",
        label=_("Müşteri Siparişi ({0}) - Müşteri Teslim: {1}").format(
            d.customer or "", formatdate(d.delivery_date)
        ),
        requirement_qty=flt(d.pending_qty),
        element_data=d.voucher_no,
        doctype="Sales Order",
        is_firmed=True,
    )


def _get_sevk_times(d):
    """Siparişin sevk/üretim sürelerini döner.

    Önce müşteri + sevk adresi, sonra müşteri + fatura adresi, yoksa müşteri
    bazında en uzun süreler kullanılır.
    """
    by_address, by_customer = _get_sevk_lookup()
    for address in (d.get("shipping_address_name"), d.get("customer_address")):
        if (d.get("customer"), address) in by_address:
            return by_address[(d.customer, address)]
    return by_customer.get(d.get("customer")) or frappe._dict(production_time=0, delivery_time=0)


def _get_sevk_lookup():
    """KTA Sevk Parametreleri'ni istek boyunca önbelleğe alır."""
    if frappe.flags.kta_sevk_lookup is None:
        by_address, by_customer = {}, {}
        for p in frappe.get_all(
            "KTA Sevk Parametreleri",
            fields=["customer_name", "customer_address", "production_time", "delivery_time"],
        ):
            times = frappe._dict(production_time=int(flt(p.production_time)), delivery_time=int(flt(p.delivery_time)))
            by_address[(p.customer_name, p.customer_address)] = times
            prev = by_customer.get(p.customer_name)
            by_customer[p.customer_name] = frappe._dict(
                production_time=max(times.production_time, prev.production_time if prev else 0),
                delivery_time=max(times.delivery_time, prev.delivery_time if prev else 0),
            )
        frappe.flags.kta_sevk_lookup = (by_address, by_customer)
    return frappe.flags.kta_sevk_lookup


def _get_item_supplier_lead_times(item_code):
    """Tedarikçiye özel Item Price tablosundaki aktif lead_time_days değerlerini döner."""
    today_d = getdate(today())
    rows = frappe.db.sql(
        """
        SELECT supplier, lead_time_days
        FROM `tabItem Price`
        WHERE item_code = %s AND buying = 1
          AND (valid_from IS NULL OR valid_from <= %s)
          AND (valid_upto IS NULL OR valid_upto = '' OR valid_upto >= %s)
        ORDER BY valid_from DESC
        """,
        (item_code, today_d, today_d),
        as_dict=True,
    )
    res = {}
    for r in rows:
        if r.supplier and r.supplier not in res:
            res[r.supplier] = cint(r.lead_time_days)
    return res


def _get_purchase_order_elements(item_code):
    """Açık satın alma siparişlerini ve yolda/antrepoda olan irsaliyeleri arz olarak döner."""
    elements = []
    covered_by_pr_item = defaultdict(float)
    covered_by_po_doc = defaultdict(float)
    supplier_lead_times = None
    item_default_lead_time = None

    # 1. Taslak Satın Alma İrsaliyeleri (Yolda / Antrepoda)
    pr_rows = frappe.db.sql(
        """
        SELECT
            pri.name AS pr_item_name,
            pri.parent AS voucher_no,
            pri.purchase_order,
            pri.purchase_order_item,
            pri.qty,
            pr.supplier,
            pr.workflow_state,
            pr.posting_date,
            pr.yukleme_tarihi,
            pr.gumruge_gelis_tarihi,
            pr.tahmini_varis_tarihi,
            (SELECT poi.schedule_date FROM `tabPurchase Order Item` poi WHERE poi.name = pri.purchase_order_item LIMIT 1) AS po_schedule_date
        FROM `tabPurchase Receipt Item` pri
        INNER JOIN `tabPurchase Receipt` pr ON pri.parent = pr.name
        WHERE pri.item_code = %s
          AND pr.docstatus = 0
          AND pr.status NOT IN ('Cancelled', 'Closed')
          AND pr.workflow_state IN ('Yolda', 'Antrepoda', 'Mal Girişe Hazır', 'Mal Giriş')
        ORDER BY pr.posting_date, pri.parent
        """,
        (item_code,),
        as_dict=True,
    )
    for d in pr_rows:
        if d.workflow_state in ("Antrepoda", "Mal Girişe Hazır", "Mal Giriş"):
            mrp_type = "Bonded"
            label = _("Antrepoda ({0})").format(d.supplier or "")
            edate = d.gumruge_gelis_tarihi or d.posting_date or today()
        else:
            mrp_type = "InTrnst"
            label = _("Yolda ({0})").format(d.supplier or "")
            if d.tahmini_varis_tarihi:
                edate = d.tahmini_varis_tarihi
            else:
                if supplier_lead_times is None:
                    supplier_lead_times = _get_item_supplier_lead_times(item_code)
                lead_time = supplier_lead_times.get(d.supplier, 0)
                if not lead_time:
                    if item_default_lead_time is None:
                        item_default_lead_time = cint(frappe.db.get_value("Item", item_code, "lead_time_days") or 0)
                    lead_time = item_default_lead_time
                base_date = d.yukleme_tarihi or d.posting_date or today()
                if lead_time > 0:
                    edate = add_days(base_date, lead_time)
                elif d.get("po_schedule_date"):
                    edate = d.po_schedule_date
                else:
                    edate = base_date

        elements.append(_make_element(
            element_date=edate,
            mrp_type=mrp_type,
            label=label,
            receipt_qty=flt(d.qty),
            element_data=d.voucher_no,
            doctype="Purchase Receipt",
            is_firmed=True,
        ))

        if d.purchase_order_item:
            covered_by_pr_item[d.purchase_order_item] += flt(d.qty)
        elif d.purchase_order:
            covered_by_po_doc[d.purchase_order] += flt(d.qty)

    # 2. Açık Satın Alma Siparişleri (PO)
    po_rows = frappe.db.sql(
        """
        SELECT
            poi.name AS po_item_name,
            poi.schedule_date,
            poi.parent AS voucher_no,
            (poi.qty - poi.received_qty) AS pending_qty,
            po.supplier,
            poi.idx
        FROM `tabPurchase Order Item` poi
        INNER JOIN `tabPurchase Order` po ON poi.parent = po.name
        WHERE poi.item_code = %s
          AND po.docstatus = 1
          AND po.status NOT IN ('Closed', 'Cancelled', 'Completed')
          AND poi.qty > poi.received_qty
        ORDER BY poi.schedule_date
        """,
        (item_code,),
        as_dict=True,
    )
    for d in po_rows:
        pr_cov = covered_by_pr_item.get(d.po_item_name, 0.0)
        if pr_cov == 0 and d.voucher_no in covered_by_po_doc:
            pr_cov = min(covered_by_po_doc[d.voucher_no], flt(d.pending_qty))
            covered_by_po_doc[d.voucher_no] -= pr_cov

        rem_qty = flt(d.pending_qty) - pr_cov
        if rem_qty > 0:
            label = (
                _("Satın Alma Siparişi ({0}) [Kalem {1}]").format(d.supplier or "", d.idx)
                if d.idx
                else _("Satın Alma Siparişi ({0})").format(d.supplier or "")
            )
            elements.append(_make_element(
                element_date=d.schedule_date,
                mrp_type="PO",
                label=label,
                receipt_qty=rem_qty,
                element_data=d.voucher_no,
                doctype="Purchase Order",
                is_firmed=True,
            ))

    return elements


def _get_work_order_elements(item_code, item_info):
    """İş emri arz/talep elementlerini döner.

    Bitmiş ürün ise → İş emri arz (PldOrd)
    Hammadde ise → İş emri bağımlı ihtiyaç (DepReq)
    """
    elements = []

    # A. Bitmiş ürün olarak iş emirleri (Arz)
    wo_as_product = frappe.db.sql(
        """
        SELECT
            wo.name,
            wo.status,
            wo.planned_start_date,
            wo.planned_end_date,
            (wo.qty - wo.produced_qty) AS pending_qty,
            so.customer, so.shipping_address_name, so.customer_address,
            (SELECT MIN(delivery_date) FROM `tabSales Order Item` WHERE parent = wo.sales_order AND item_code = wo.production_item) AS so_delivery_date
        FROM `tabWork Order` wo
        LEFT JOIN `tabSales Order` so ON wo.sales_order = so.name
        WHERE wo.production_item = %s
          AND wo.docstatus = 1
          AND wo.status NOT IN ('Completed', 'Stopped', 'Cancelled', 'Closed')
          AND wo.qty > wo.produced_qty
        """,
        (item_code,),
        as_dict=True,
    )
    weekly_prod = flt(item_info.get("weekly_production"))
    for d in wo_as_product:
        times = _get_sevk_times(d)
        # 1. Satış Siparişi bağlantısı varsa JIT (Tersine Çizelgeleme)
        if d.so_delivery_date and (times.production_time or times.delivery_time):
            expected_end_date = add_days(d.so_delivery_date, -times.delivery_time)
        elif weekly_prod > 0:
            # 2. Satış siparişi yoksa ama haftalık kapasite girilmişse kapasite bazlı hesap
            expected_end_date = _calc_wo_capacity_end_date(d, weekly_prod)
        else:
            # 3. Fallback standart tarih
            expected_end_date = d.planned_end_date or d.planned_start_date

        elements.append(_make_element(
            element_date=expected_end_date,
            mrp_type="PrdOrd",
            label=_("Üretim Emri (İş Emri)"),
            receipt_qty=flt(d.pending_qty),
            element_data=d.name,
            doctype="Work Order",
            is_firmed=True,
        ))

    # B. Hammadde olarak bağımlı ihtiyaç (BOM üzerinden)
    wo_as_material = frappe.db.sql(
        """
        SELECT
            wo.name,
            wo.planned_start_date,
            wo.production_item,
            (wo.qty - wo.produced_qty) AS pending_qty,
            wo.bom_no,
            so.customer, so.shipping_address_name, so.customer_address,
            (SELECT MIN(delivery_date) FROM `tabSales Order Item` WHERE parent = wo.sales_order AND item_code = wo.production_item) AS so_delivery_date
        FROM `tabWork Order` wo
        LEFT JOIN `tabSales Order` so ON wo.sales_order = so.name
        WHERE wo.docstatus = 1
          AND wo.status NOT IN ('Completed', 'Stopped', 'Cancelled', 'Closed')
          AND wo.qty > wo.produced_qty
        """,
        as_dict=True,
    )
    # BOM patlama ile hammadde ihtiyacını hesapla
    bom_cache = {}
    for d in wo_as_material:
        bom_no = d.bom_no
        if not bom_no:
            continue
        if bom_no not in bom_cache:
            bom_cache[bom_no] = _get_bom_materials(bom_no)
        bom_materials = bom_cache[bom_no]
        
        # SAP Backwards Scheduling Logic for start date
        times = _get_sevk_times(d)
        if d.so_delivery_date and (times.production_time or times.delivery_time):
            expected_end_date = add_days(d.so_delivery_date, -times.delivery_time)
            expected_start_date = add_days(expected_end_date, -times.production_time)
        else:
            expected_start_date = d.planned_start_date

        for mat in bom_materials:
            if mat.item_code == item_code:
                req_qty = flt(mat.stock_qty) * flt(d.pending_qty)
                elements.append(_make_element(
                    element_date=expected_start_date,
                    mrp_type="DepReq",
                    label=_("Bağımlı İhtiyaç ({0})").format(
                        d.production_item
                    ),
                    requirement_qty=req_qty,
                    element_data=d.name,
                    doctype="Work Order",
                    is_firmed=True,
                ))

    return elements


def _calc_wo_capacity_end_date(wo, weekly_capacity):
    """Haftalık üretim kapasitesine göre iş günleri (Pazar hariç) ekleyerek bitiş tarihini hesaplar."""
    pending_qty = flt(wo.get("pending_qty"))
    if pending_qty <= 0 or flt(weekly_capacity) <= 0:
        return wo.get("planned_end_date") or wo.get("planned_start_date") or today()

    # Haftada 6 iş günü varsayımı
    daily_cap = flt(weekly_capacity) / 6.0
    work_days_needed = int(math.ceil(pending_qty / daily_cap))

    # In Process ise bugünden, değilse planned_start_date'den itibaren say
    if wo.get("status") == "In Process":
        curr = getdate(today())
    else:
        curr = getdate(wo.get("planned_start_date") or today())

    added_days = 0
    while added_days < work_days_needed:
        curr = add_days(curr, 1)
        # Pazar gününü atla (isoweekday: 7 = Pazar)
        if getdate(curr).isoweekday() != 7:
            added_days += 1

    return str(curr)


def _get_planned_order_elements(item_code, item_info, prefetched=None):
    """Bitmiş ürün için açıkta kalan satış siparişlerini karşılamak üzere Planlı Sipariş (PldOrd) arzı oluşturur."""
    # BOM'u olan bir mamul mü kontrol et
    bom_name = frappe.db.get_value("BOM", {"item": item_code, "is_default": 1, "is_active": 1, "docstatus": 1})
    if not bom_name:
        return []

    if prefetched:
        so_lines = prefetched.get("so_lines", {}).get(item_code, [])
        stock_map = prefetched.get("stock_map", {})
        wo_map = prefetched.get("wo_map", {})
        reorder_map = prefetched.get("reorder_map", {})
    else:
        so_lines = _get_open_so_lines([item_code]).get(item_code, [])
        stock_map = _get_fg_stock_map([item_code])
        wo_map = _get_fg_open_wo_map([item_code])
        reorder_map = _get_fg_reorder_map([item_code])

    supply = stock_map.get(item_code, 0) + wo_map.get(item_code, 0) - reorder_map.get(item_code, 0)
    allocations = _allocate_fg_demand(so_lines, supply)

    weekly_prod = flt(item_info.get("weekly_production"))
    elements = []

    today_d = getdate(today())

    # 1. Emniyet stoku tamamlama arzı (varsa)
    for line, uncovered in allocations:
        if line is None:
            elements.append(_make_element(
                element_date=today_d,
                mrp_type="PldOrd",
                label=_("Planlı Sipariş (Emniyet Tamamlama)"),
                receipt_qty=uncovered,
                element_data=item_code,
                doctype="Item",
                is_firmed=False,
                start_date=today_d,
            ))

    # 2. Satış siparişi açık talepleri
    so_demands = []
    for line, uncovered in allocations:
        if line is not None and uncovered > 0:
            times = _get_sevk_times(line)
            ship_d = add_days(line.delivery_date, -times.delivery_time) if line.delivery_date else today_d
            so_demands.append({
                "line": line,
                "qty": uncovered,
                "ship_date": getdate(ship_d),
            })

    if not so_demands:
        return elements

    # Eğer haftalık kapasite girilmemişse doğrudan ship_date ile ekle
    if weekly_prod <= 0:
        for dem in so_demands:
            times = _get_sevk_times(dem["line"])
            prod_time = times.production_time or 0
            start_d = add_days(dem["ship_date"], -prod_time) if prod_time else dem["ship_date"]
            if getdate(start_d) < today_d:
                # Forward Scheduling: üretime geçmişte başlanamaz, en erken bugün başlar
                start_d = today_d
                end_d = add_days(today_d, prod_time) if prod_time else today_d
                is_overdue = True
            else:
                end_d = dem["ship_date"]
                is_overdue = False

            el = _make_element(
                element_date=end_d,
                mrp_type="PldOrd",
                label=_("Planlı Sipariş ({0})").format(dem["line"].sales_order),
                receipt_qty=dem["qty"],
                element_data=dem["line"].sales_order,
                doctype="Sales Order",
                is_firmed=False,
                start_date=start_d,
            )
            if is_overdue:
                el["exception_code"] = "OVERDUE"
                el["exception_message"] = _("Gecikmiş Üretim Planı")
            elements.append(el)
        return elements

    # Haftalık Kapasite Dengeleme (Backward & Forward Capacity Leveling)
    # Siparişleri teslimat tarihine göre sırala
    so_demands.sort(key=lambda x: x["ship_date"])

    # Hafta anahtarı -> o haftaya atanmış toplam PldOrd miktarı
    week_assigned = defaultdict(float)

    def get_week_info(target_date):
        # target_date'in ait olduğu haftanın (Pazartesi, Cuma/Pazar) tarihleri
        iso_y, iso_w, iso_d = target_date.isocalendar()
        monday = add_days(target_date, -(iso_d - 1))
        friday = add_days(monday, 4)
        return f"{iso_y}-W{iso_w:02d}", monday, friday

    iso_ty, iso_tw, iso_td = today_d.isocalendar()
    curr_monday = add_days(today_d, -(iso_td - 1))

    for dem in so_demands:
        rem_qty = dem["qty"]
        target_d = dem["ship_date"]

        # 1. Geriye Doğru Çizelgeleme: ship_date haftasından başlayarak en fazla içinde bulunduğumuz haftaya kadar ara
        while rem_qty > 0 and target_d >= curr_monday:
            w_label, monday, friday = get_week_info(target_d)
            curr_assigned = week_assigned[w_label]
            avail_cap = max(weekly_prod - curr_assigned, 0.0)

            if avail_cap > 0:
                take_qty = min(rem_qty, avail_cap)
                week_assigned[w_label] += take_qty
                rem_qty -= take_qty

                # Bitiş tarihi: Eğer hedef hafta siparişin teslim haftasıysa ship_date, geriye kaymış haftaysa Cuma
                if target_d >= dem["ship_date"]:
                    slot_end_date = dem["ship_date"]
                else:
                    slot_end_date = friday

                slot_start_date = max(getdate(monday), today_d)
                slot_end_date = max(getdate(slot_end_date), today_d)

                elements.append(_make_element(
                    element_date=slot_end_date,
                    mrp_type="PldOrd",
                    label=_("Planlı Sipariş ({0}) [{1}]").format(dem["line"].sales_order, w_label),
                    receipt_qty=take_qty,
                    element_data=dem["line"].sales_order,
                    doctype="Sales Order",
                    is_firmed=False,
                    start_date=slot_start_date,
                ))

            # Bu hafta dolduysa, bir önceki haftanın Cuma gününe kay
            target_d = add_days(monday, -3)

        # 2. İleriye Doğru Çizelgeleme (Forward Scheduling): Geriye doğru sığmayan veya gecikmiş miktar varsa
        # En erken bugünden (veya ship_date'den sonraki haftadan) ileriye doğru boş kapasite ara
        if rem_qty > 0:
            fwd_d = max(dem["ship_date"], today_d)
            while rem_qty > 0:
                w_label, monday, friday = get_week_info(fwd_d)
                curr_assigned = week_assigned[w_label]
                avail_cap = max(weekly_prod - curr_assigned, 0.0)

                if avail_cap > 0:
                    take_qty = min(rem_qty, avail_cap)
                    week_assigned[w_label] += take_qty
                    rem_qty -= take_qty

                    slot_start_date = max(getdate(monday), today_d)
                    slot_end_date = max(getdate(friday), today_d)

                    el = _make_element(
                        element_date=slot_end_date,
                        mrp_type="PldOrd",
                        label=_("Planlı Sipariş ({0}) [{1}]").format(dem["line"].sales_order, w_label),
                        receipt_qty=take_qty,
                        element_data=dem["line"].sales_order,
                        doctype="Sales Order",
                        is_firmed=False,
                        start_date=slot_start_date,
                    )
                    el["exception_code"] = "OVERDUE"
                    el["exception_message"] = _("Gecikmiş Üretim Planı")
                    elements.append(el)

                fwd_d = add_days(friday, 3)

    return elements


def _get_purchase_proposal_elements(item_code, item_info, current_elements):
    """Satın alınan hammadde için haftalık net açıkları (bakiye < 0) karşılayan Planlı Satın Alma Siparişi (PurRqs) önerilerini üretir."""
    suppliers = item_info.get("suppliers", [])
    primary = item_info.get("primary_supplier", {})
    if not primary and not suppliers:
        return []

    moq = flt(primary.get("moq", 1.0)) or 1.0
    paket = flt(primary.get("paket", 1.0)) or 1.0
    lead_time = cint(primary.get("lead_time_days", 0))
    supplier_name = primary.get("supplier") or item_info.get("default_supplier") or ""

    stock_qty = flt(item_info.get("current_stock", 0))

    # Hafta bazında arz ve talepleri topla
    week_demands = defaultdict(float)
    week_receipts = defaultdict(float)
    week_dates = {}

    for el in current_elements:
        if el["mrp_element_type"] in ["Stock", "SafeSt"]:
            continue
        w = el.get("week_label")
        if not w:
            continue
        d = getdate(el["date"])
        if w not in week_dates or d < week_dates[w]:
            week_dates[w] = d
        week_receipts[w] += flt(el.get("receipt_qty", 0))
        week_demands[w] += flt(el.get("requirement_qty", 0))

    today_d = getdate(today())
    earliest_deliv = add_days(today_d, lead_time)
    iso_y, iso_w, iso_d = getdate(earliest_deliv).isocalendar()
    earliest_w = f"{iso_y}-W{iso_w:02d}"

    all_weeks = set(week_receipts.keys()) | set(week_demands.keys())
    if earliest_w not in all_weeks:
        all_weeks.add(earliest_w)
        week_dates[earliest_w] = earliest_deliv

    sorted_weeks = sorted(all_weeks)
    balance = stock_qty
    proposals = []

    for w in sorted_weeks:
        r = week_receipts[w]
        dem = week_demands[w]
        net_bal = balance + r - dem
        req_date = week_dates.get(w, today_d)

        if w < earliest_w:
            # Tedarik süresi nedeniyle bugünden önceye sipariş verilemez; açıklar fiziksel gecikme olarak kalır
            balance = net_bal
        elif w == earliest_w:
            # En erken teslim haftası: bu tarihe kadar birikmiş net açık karşılanır
            if net_bal < 0:
                deficit = -net_bal
                order_qty = max(moq, math.ceil(deficit / paket) * paket)
                label = _("Planlı Satın Alma Siparişi ({0}) [{1}]").format(
                    supplier_name or _("Tedarikçi"), earliest_w
                )
                p = _make_element(
                    element_date=earliest_deliv,
                    mrp_type="PurRqs",
                    label=label,
                    receipt_qty=order_qty,
                    element_data=supplier_name,
                    doctype="Purchase Order",
                    is_firmed=False,
                    start_date=today_d,
                )
                p["deficit_qty"] = deficit
                p["suppliers_data"] = suppliers
                p["default_warehouse"] = item_info.get("default_warehouse") or ""
                p["exception_code"] = "OVERDUE"
                p["exception_message"] = _("Gecikmiş Sipariş Verme")
                proposals.append(p)
                balance = net_bal + order_qty
            else:
                balance = net_bal
        else:
            # Normal gelecek haftalar (On-time sipariş ufku):
            order_date = add_days(req_date, -lead_time)
            if net_bal < 0:
                deficit = -net_bal
                order_qty = max(moq, math.ceil(deficit / paket) * paket)
                label = _("Planlı Satın Alma Siparişi ({0}) [{1}]").format(
                    supplier_name or _("Tedarikçi"), w
                )
                p = _make_element(
                    element_date=req_date,
                    mrp_type="PurRqs",
                    label=label,
                    receipt_qty=order_qty,
                    element_data=supplier_name,
                    doctype="Purchase Order",
                    is_firmed=False,
                    start_date=order_date,
                )
                p["deficit_qty"] = deficit
                p["suppliers_data"] = suppliers
                p["default_warehouse"] = item_info.get("default_warehouse") or ""
                proposals.append(p)
                balance = net_bal + order_qty
            else:
                balance = net_bal

    return proposals


def _get_bom_materials(bom_no):
    """BOM Explosion Item tablosundan birim başına tüketim listesi."""
    return frappe.db.get_all(
        "BOM Explosion Item",
        filters={"parent": bom_no},
        fields=["item_code", "qty_consumed_per_unit as stock_qty"],
    )


def _get_material_request_elements(item_code):
    """Material Request elementleri.

    MR-Manufacture → Talep (üretim ihtiyacı)
    MR-Purchase → Arz (planlanan tedarik)
    """
    rows = frappe.db.sql(
        """
        SELECT
            mri.schedule_date,
            mri.parent AS voucher_no,
            (mri.qty - mri.ordered_qty) AS pending_qty,
            mr.material_request_type
        FROM `tabMaterial Request Item` mri
        INNER JOIN `tabMaterial Request` mr ON mri.parent = mr.name
        WHERE mri.item_code = %s
          AND mr.docstatus = 1
          AND mr.status NOT IN ('Stopped', 'Cancelled', 'Closed', 'Completed')
          AND mri.qty > mri.ordered_qty
        ORDER BY mri.schedule_date
        """,
        (item_code,),
        as_dict=True,
    )
    elements = []
    for d in rows:
        pending = flt(d.pending_qty)
        if pending <= 0:
            continue
        mr_type = d.material_request_type
        if mr_type == "Manufacture":
            elements.append(_make_element(
                element_date=d.schedule_date,
                mrp_type="MR-Mfg",
                label=_("Üretim Talebi (MR)"),
                requirement_qty=pending,
                element_data=d.voucher_no,
                doctype="Material Request",
                is_firmed=True,
            ))
        elif mr_type == "Purchase":
            elements.append(_make_element(
                element_date=d.schedule_date,
                mrp_type="MR-Pur",
                label=_("Satın Alma Talebi (MR)"),
                receipt_qty=pending,
                element_data=d.voucher_no,
                doctype="Material Request",
                is_firmed=False,
            ))
    return elements


def _get_simulated_requirement_elements(item_code):
    """Üst seviye mamullerin planlı siparişlerini (PldOrd) hammaddeye SimReq olarak yansıtır.

    Her mamulün haftalık kapasitesine göre dengelenmiş PldOrd slotları alınır,
    BOM tüketim katsayısı ile çarpılarak hammadde talebine çevrilir.
    Talep tarihi = Planlı siparişin başlama tarihi (üretim haftası başlangıcı).
    """
    usage = _get_where_used(item_code)
    if not usage:
        return []

    fg_items = list(usage)
    so_lines = _get_open_so_lines(fg_items)
    stock_map = _get_fg_stock_map(fg_items)
    wo_map = _get_fg_open_wo_map(fg_items)
    reorder_map = _get_fg_reorder_map(fg_items)

    weekly_rows = frappe.get_all(
        "Item",
        filters={"name": ("in", fg_items)},
        fields=["name", "custom_weekly_production"],
    )
    weekly_map = {r.name: flt(r.custom_weekly_production) for r in weekly_rows}

    prefetched = {
        "so_lines": so_lines,
        "stock_map": stock_map,
        "wo_map": wo_map,
        "reorder_map": reorder_map,
    }

    elements = []
    for fg, per_unit in usage.items():
        fg_info = {"weekly_production": weekly_map.get(fg, 0.0)}
        pld_orders = _get_planned_order_elements(fg, fg_info, prefetched=prefetched)
        for pld in pld_orders:
            req_qty = flt(pld.get("receipt_qty")) * per_unit
            if req_qty <= 0:
                continue

            req_date = pld.get("start_date") or pld.get("date")

            if pld.get("doctype") == "Item":
                label = _("Emniyet Stoku Tamamlama ({0})").format(fg)
            else:
                label = _("Planlı Bağımlı İhtiyaç ({0})").format(fg)

            elements.append(_make_element(
                element_date=req_date,
                mrp_type="SimReq",
                label=label,
                requirement_qty=req_qty,
                element_data=pld.get("element_data"),
                doctype=pld.get("doctype"),
                is_firmed=False,
            ))

    return elements


def _get_where_used(item_code):
    """Hammaddeyi içeren aktif/varsayılan BOM mamulleri → birim tüketim."""
    rows = frappe.db.sql(
        """
        SELECT b.item AS fg, SUM(be.qty_consumed_per_unit) AS per_unit
        FROM `tabBOM Explosion Item` be
        INNER JOIN `tabBOM` b ON b.name = be.parent
        WHERE be.item_code = %s
          AND b.is_default = 1 AND b.is_active = 1 AND b.docstatus = 1
          AND b.item != %s
        GROUP BY b.item
        """,
        (item_code, item_code),
        as_dict=True,
    )
    return {d.fg: flt(d.per_unit) for d in rows if flt(d.per_unit) > 0}


def _get_open_so_lines(fg_items):
    """Mamul bazında teslim tarihine göre sıralı açık sipariş satırları."""
    rows = frappe.db.sql(
        """
        SELECT
            soi.item_code, soi.parent AS sales_order, soi.delivery_date,
            (soi.qty - soi.delivered_qty) * IFNULL(NULLIF(soi.conversion_factor, 0), 1) AS pending_qty,
            so.customer, so.shipping_address_name, so.customer_address
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON soi.parent = so.name
        WHERE soi.item_code IN %s
          AND so.docstatus = 1
          AND so.status NOT IN ('Closed', 'Cancelled', 'Completed')
          AND soi.qty > soi.delivered_qty
        ORDER BY soi.delivery_date, soi.parent, soi.idx
        """,
        (tuple(fg_items),),
        as_dict=True,
    )
    lines = defaultdict(list)
    for d in rows:
        lines[d.item_code].append(d)
    return lines


def _get_fg_stock_map(fg_items):
    """Red depolar hariç fiziksel mamul stoku."""
    rows = frappe.db.sql(
        """
        SELECT bin.item_code, SUM(bin.actual_qty) AS qty
        FROM `tabBin` bin
        INNER JOIN `tabWarehouse` w ON w.name = bin.warehouse
        WHERE bin.item_code IN %s AND w.is_rejected_warehouse = 0
        GROUP BY bin.item_code
        """,
        (tuple(fg_items),),
    )
    return {r[0]: flt(r[1]) for r in rows}


def _get_fg_open_wo_map(fg_items):
    """Onaylı açık iş emirlerinin kalan üretim miktarı."""
    rows = frappe.db.sql(
        """
        SELECT production_item, SUM(qty - produced_qty)
        FROM `tabWork Order`
        WHERE production_item IN %s
          AND docstatus = 1
          AND status NOT IN ('Completed', 'Stopped', 'Cancelled', 'Closed')
          AND qty > produced_qty
        GROUP BY production_item
        """,
        (tuple(fg_items),),
    )
    return {r[0]: flt(r[1]) for r in rows}


def _get_fg_reorder_map(fg_items):
    """Mamul bazında toplam yeniden sipariş seviyesi."""
    rows = frappe.db.sql(
        """
        SELECT parent, SUM(warehouse_reorder_level)
        FROM `tabItem Reorder`
        WHERE parent IN %s AND parenttype = 'Item'
        GROUP BY parent
        """,
        (tuple(fg_items),),
    )
    return {r[0]: flt(r[1]) for r in rows}


def _allocate_fg_demand(so_lines, supply):
    """Arzı en erken teslimli siparişlerden başlayarak dağıtır.

    Negatif arz (stok < emniyet) bugüne tamamlama ihtiyacı olarak döner (line=None).
    Dönüş: [(so_line | None, karşılanmamış_miktar), ...]
    """
    allocations = []
    if supply < 0:
        allocations.append((None, -supply))
        supply = 0
    for line in so_lines:
        covered = min(supply, flt(line.pending_qty))
        supply -= covered
        uncovered = flt(line.pending_qty) - covered
        if uncovered > 0:
            allocations.append((line, uncovered))
    return allocations


def _make_sim_element(fg, line, req_qty):
    """SimReq elementi oluşturur (sipariş satırı yoksa emniyet tamamlama)."""
    if line is None:
        return _make_element(
            element_date=today(),
            mrp_type="SimReq",
            label=_("Emniyet Stoku Tamamlama ({0})").format(fg),
            requirement_qty=req_qty,
            element_data=fg,
            doctype="Item",
        )
    return _make_element(
        element_date=_get_sim_requirement_date(line),
        mrp_type="SimReq",
        label=_("Planlı Bağımlı İhtiyaç ({0})").format(fg),
        requirement_qty=req_qty,
        element_data=line.sales_order,
        doctype="Sales Order",
    )


def _get_sim_requirement_date(line):
    """Geriye doğru çizelgeleme: teslim − sevk süresi − üretim süresi."""
    times = _get_sevk_times(line)
    lead = times.delivery_time + times.production_time
    return add_days(line.delivery_date, -lead) if line.delivery_date else today()


def _get_bom_explosion_children(item_code):
    """Bitmiş ürün için BOM patlatarak alt malzemeleri listeler."""
    bom_name = frappe.db.get_value(
        "BOM",
        {"item": item_code, "is_default": 1, "is_active": 1},
        "name",
    )
    if not bom_name:
        return []

    children = frappe.db.get_all(
        "BOM Explosion Item",
        filters={"parent": bom_name},
        fields=["item_code", "item_name", "stock_qty", "stock_uom"],
    )
    return [
        {
            "item_code": c.item_code,
            "item_name": c.item_name,
            "qty_per_unit": flt(c.stock_qty),
            "uom": c.stock_uom,
        }
        for c in children
    ]


def _make_element(
    element_date, mrp_type, label,
    receipt_qty=0, requirement_qty=0,
    element_data="", doctype="",
    is_firmed=False,
    start_date=None,
):
    """Tek bir MRP element satırı oluşturur."""
    d = getdate(element_date) if element_date else getdate(today())
    iso_year, iso_week, iso_day = d.isocalendar()
    el = {
        "date": str(d),
        "mrp_element_type": mrp_type,
        "mrp_element_label": label,
        "element_data": element_data,
        "doctype": doctype,
        "receipt_qty": flt(receipt_qty, 2),
        "requirement_qty": flt(requirement_qty, 2),
        "available_qty": 0,
        "exception_code": None,
        "exception_message": None,
        "is_firmed": is_firmed,
        "week_label": f"{iso_year}-W{iso_week:02d}",
    }
    if start_date:
        el["start_date"] = str(getdate(start_date))
    return el


def _filter_by_date(elements, from_date=None, to_date=None):
    """Tarih aralığına göre filtrele. Stok ve emniyet stoku satırları her zaman kalır."""
    if not to_date and not from_date:
        return elements
    to_d = getdate(to_date) if to_date else None
    from_d = getdate(from_date) if from_date else None
    filtered = []
    for el in elements:
        if el["mrp_element_type"] in FIXED_ELEMENT_TYPES:
            filtered.append(el)
            continue
        el_date = getdate(el["date"])
        if to_d and el_date > to_d:
            continue
        if from_d and el_date < from_d:
            continue
        filtered.append(el)
    return filtered


def _sort_and_calculate_running_balance(elements):
    """Kronolojik sırala ve kümülatif bakiye hesapla.

    Aynı tarihte:
    1. Sabit elementler (Stock, SafeSt)
    2. Arzlar (PO, PrdOrd, PldOrd, MR-Pur) -> Önce stok artar
    3. Talepler (CustOrd, DepReq, SimReq, MR-Mfg) -> Sonra stok tüketilir
    """
    def sort_key(el):
        priority = FIXED_ELEMENT_TYPES.get(el["mrp_element_type"])
        if priority is None:
            priority = len(FIXED_ELEMENT_TYPES)
        # Arz (+) ise 0, Talep (-) ise 1 (aynı tarihte önce arz girsin)
        flow_priority = 0 if flt(el.get("receipt_qty")) > 0 else 1
        return (priority, el["date"], flow_priority, el["mrp_element_type"])

    elements.sort(key=sort_key)

    running = 0
    for el in elements:
        running += flt(el["receipt_qty"]) - flt(el["requirement_qty"])
        el["available_qty"] = flt(running, 2)

    return elements


def _detect_exceptions(elements, safety_stock):
    """İstisna kodlarını belirle.

    Bakiye emniyet stoku (SafeSt) düşülmüş net miktardır:
    bakiye < -emniyet → fiziksel stok açığı, bakiye < 0 → emniyet stoku altı.
    """
    today_date = getdate(today())
    for el in elements:
        if el["mrp_element_type"] in FIXED_ELEMENT_TYPES:
            continue
        code, message = _get_exception(el, safety_stock, today_date)
        el["exception_code"] = code
        el["exception_message"] = message

    return elements


def _get_exception(el, safety_stock, today_date):
    """Tek bir element için istisna kodu ve mesajını döner."""
    available = flt(el["available_qty"])
    if available < -flt(safety_stock):
        return "SHORTAGE", _("Stok Açığı")
    if available < 0:
        return "BELOW_SAFETY", _("Emniyet Stoku Altı")
    if el.get("exception_code"):
        return el["exception_code"], el.get("exception_message")
    if el.get("mrp_element_type") in ("PurRqs", "PldOrd"):
        start_d = getdate(el.get("start_date")) if el.get("start_date") else None
        if start_d and start_d < today_date:
            return "OVERDUE", _("Gecikmiş Sipariş Verme")
    if getdate(el["date"]) < today_date and (
        el["receipt_qty"] > 0 or el["requirement_qty"] > 0
    ):
        return "OVERDUE", _("Gecikmiş")
    return None, None


def _build_summary(elements, item_info, safety_stock):
    """Özet bilgileri hesapla."""
    total_requirements = 0
    total_receipts = 0
    first_shortage_date = None
    exception_count = 0

    for el in elements:
        if el["mrp_element_type"] == "Stock":
            continue
        total_requirements += flt(el["requirement_qty"])
        total_receipts += flt(el["receipt_qty"])

        if el.get("exception_code"):
            exception_count += 1

        if el["available_qty"] < 0 and not first_shortage_date:
            first_shortage_date = el["date"]

    net_requirement = total_requirements - total_receipts
    current_stock = flt(item_info.get("current_stock", 0))

    # Karşılanma günü tahmini (emniyet stoku tüketim talebi değildir)
    flow_requirements = total_requirements - flt(safety_stock)
    coverage_days = 0
    if flow_requirements > 0 and current_stock > 0:
        daily_demand = flow_requirements / max(
            (getdate(elements[-1]["date"]) - getdate(elements[0]["date"])).days,
            1,
        )
        if daily_demand > 0:
            coverage_days = int(current_stock / daily_demand)

    return {
        "total_requirements": flt(total_requirements, 2),
        "total_receipts": flt(total_receipts, 2),
        "net_requirement": flt(net_requirement, 2),
        "coverage_days": coverage_days,
        "first_shortage_date": first_shortage_date,
        "exception_count": exception_count,
    }


def _build_chart_data(elements, safety_stock):
    """Haftalık bazda grafik verisi oluştur."""
    week_data = defaultdict(lambda: {
        "receipt": 0, "requirement": 0, "balance": 0,
    })

    for el in elements:
        if el["mrp_element_type"] == "SafeSt":
            continue
        w = el["week_label"]
        # Bakiye net (emniyet düşülmüş); grafikte fiziksel stok projeksiyonu gösterilir
        week_data[w]["balance"] = flt(el["available_qty"]) + flt(safety_stock)
        if el["mrp_element_type"] == "Stock":
            continue
        week_data[w]["receipt"] += flt(el["receipt_qty"])
        week_data[w]["requirement"] += flt(el["requirement_qty"])

    sorted_weeks = sorted(week_data.keys())

    return {
        "labels": sorted_weeks,
        "datasets": [
            {
                "name": _("Kümülatif Stok"),
                "values": [week_data[w]["balance"] for w in sorted_weeks],
                "chartType": "line",
            },
            {
                "name": _("Haftalık Talep"),
                "values": [
                    week_data[w]["requirement"] for w in sorted_weeks
                ],
                "chartType": "bar",
            },
            {
                "name": _("Haftalık Arz"),
                "values": [week_data[w]["receipt"] for w in sorted_weeks],
                "chartType": "bar",
            },
            {
                "name": _("Emniyet Stoku"),
                "values": [safety_stock] * len(sorted_weeks),
                "chartType": "line",
            },
        ],
    }


def _aggregate_weekly(elements):
    """Elementleri haftalık bazda grupla.

    Stock ve SafeSt açılış elementleri haftaların içine hareket olarak eklenmez;
    haftalık bakiye açılış stoğundan başlayarak hesaplanır.
    """
    week_groups = defaultdict(lambda: {
        "receipt_qty": 0,
        "requirement_qty": 0,
        "elements": [],
    })

    stock_qty = 0.0
    safety_qty = 0.0

    for el in elements:
        if el["mrp_element_type"] == "Stock":
            stock_qty += flt(el.get("receipt_qty", 0))
            continue
        if el["mrp_element_type"] == "SafeSt":
            safety_qty += flt(el.get("requirement_qty", 0))
            continue

        w = el["week_label"]
        week_groups[w]["receipt_qty"] += flt(el["receipt_qty"])
        week_groups[w]["requirement_qty"] += flt(el["requirement_qty"])
        week_groups[w]["elements"].append(el)

    result = []
    running = stock_qty - safety_qty

    for week in sorted(week_groups.keys()):
        grp = week_groups[week]
        running += grp["receipt_qty"] - grp["requirement_qty"]

        result.append({
            "week_label": week,
            "receipt_qty": flt(grp["receipt_qty"], 2),
            "requirement_qty": flt(grp["requirement_qty"], 2),
            "available_qty": flt(running, 2),
            "element_count": len(grp["elements"]),
            "elements": grp["elements"],
        })

    return result
