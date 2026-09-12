import frappe
from frappe import _
from frappe.utils import flt, getdate, today, add_months, add_days
from collections import defaultdict
from datetime import date


@frappe.whitelist()
def get_stock_requirements(item_code, from_date=None, to_date=None, show_bom_explosion=0, weekly_view=0):
    """Tek bir malzeme kodu için SAP MD04 benzeri stok/ihtiyaç listesi döner."""
    if not item_code:
        frappe.throw(_("Malzeme kodu belirtilmedi"))

    from_date = getdate(from_date or today())
    to_date = getdate(to_date or add_months(today(), 6))
    show_bom_explosion = int(show_bom_explosion)
    weekly_view = int(weekly_view)

    item_info = _get_item_info(item_code)
    if not item_info:
        frappe.throw(_("Malzeme bulunamadı: {0}").format(item_code))

    elements = []

    # 1. Mevcut Stok
    stock_qty = _get_current_stock(item_code)
    elements.append(_make_element(
        element_date=from_date,
        mrp_type="Stock",
        label=_("Mevcut Stok"),
        receipt_qty=stock_qty,
    ))

    # 2. Satış Siparişleri (Talep)
    elements.extend(_get_sales_order_elements(item_code))

    # 3. Satın Alma Siparişleri (Arz)
    elements.extend(_get_purchase_order_elements(item_code))

    # 4. İş Emri elementleri
    elements.extend(_get_work_order_elements(item_code, item_info))

    # 5. Material Request elementleri
    elements.extend(_get_material_request_elements(item_code))

    # 6. BOM Patlatma (opsiyonel — bitmiş ürün seçildiğinde alt malzemeler)
    bom_children = []
    if show_bom_explosion:
        bom_children = _get_bom_explosion_children(item_code)

    # Tarih filtresi
    elements = _filter_by_date(elements, from_date, to_date)

    # Kronolojik sırala ve kümülatif bakiye hesapla
    elements = _sort_and_calculate_running_balance(elements)

    # İstisna tespiti
    safety_stock = flt(item_info.get("safety_stock", 0))
    elements = _detect_exceptions(elements, safety_stock)

    # Özet hesapla
    summary = _build_summary(elements, item_info, safety_stock)

    # Grafik verisi
    chart_data = _build_chart_data(elements, safety_stock)

    # Haftalık agregasyon
    weekly_elements = []
    if weekly_view:
        weekly_elements = _aggregate_weekly(elements)

    return {
        "item_info": item_info,
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
            "custom_musteri_grubu",
        ],
        as_dict=True,
    )
    if not item:
        return None

    default_supplier = frappe.db.get_value(
        "Item Default", {"parent": item_code}, "default_supplier"
    )

    lead_time = 0
    moq = 0
    if default_supplier:
        price_info = frappe.db.get_value(
            "Item Price",
            {"item_code": item_code, "supplier": default_supplier, "buying": 1},
            ["lead_time_days", "custom_minimum_order_quantity"],
            as_dict=True,
        )
        if price_info:
            lead_time = price_info.lead_time_days or 0
            moq = flt(price_info.custom_minimum_order_quantity)

    stock_qty = _get_current_stock(item_code)
    reserved_qty = _get_reserved_qty(item_code)
    ordered_qty = _get_ordered_qty(item_code)

    return {
        "item_code": item.name,
        "item_name": item.item_name,
        "item_group": item.item_group or "",
        "uom": item.stock_uom or "",
        "default_supplier": default_supplier or "",
        "lead_time_days": lead_time,
        "moq": moq,
        "safety_stock": flt(item.safety_stock),
        "current_stock": stock_qty,
        "reserved_qty": reserved_qty,
        "ordered_qty": ordered_qty,
        "available_qty": stock_qty - reserved_qty,
        "ara_malzeme_grubu": item.custom_ara_malzeme_grubu or "",
        "musteri_grubu": item.custom_musteri_grubu or "",
    }


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
    """Açık satış siparişlerini talep olarak döner."""
    rows = frappe.db.sql(
        """
        SELECT
            soi.delivery_date,
            soi.parent AS voucher_no,
            (soi.qty - soi.delivered_qty) AS pending_qty,
            so.customer
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
    elements = []
    for d in rows:
        elements.append(_make_element(
            element_date=d.delivery_date,
            mrp_type="CustOrd",
            label=_("Müşteri Siparişi ({0})").format(d.customer or ""),
            requirement_qty=flt(d.pending_qty),
            element_data=d.voucher_no,
            doctype="Sales Order",
            is_firmed=True,
        ))
    return elements


def _get_purchase_order_elements(item_code):
    """Açık satın alma siparişlerini arz olarak döner."""
    rows = frappe.db.sql(
        """
        SELECT
            poi.schedule_date,
            poi.parent AS voucher_no,
            (poi.qty - poi.received_qty) AS pending_qty,
            po.supplier
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
    elements = []
    for d in rows:
        elements.append(_make_element(
            element_date=d.schedule_date,
            mrp_type="PO",
            label=_("Satın Alma Siparişi ({0})").format(d.supplier or ""),
            receipt_qty=flt(d.pending_qty),
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
            wo.planned_start_date,
            wo.planned_end_date,
            (wo.qty - wo.produced_qty) AS pending_qty,
            so.customer,
            (SELECT MIN(delivery_date) FROM `tabSales Order Item` WHERE parent = wo.sales_order AND item_code = wo.production_item) AS so_delivery_date,
            IFNULL(sp.production_time, 0) AS param_prod_time,
            IFNULL(sp.delivery_time, 0) AS param_del_time
        FROM `tabWork Order` wo
        LEFT JOIN `tabSales Order` so ON wo.sales_order = so.name
        LEFT JOIN `tabKTA Sevk Parametreleri` sp ON so.customer = sp.customer_name
        WHERE wo.production_item = %s
          AND wo.docstatus = 1
          AND wo.status NOT IN ('Completed', 'Stopped', 'Cancelled', 'Closed')
          AND wo.qty > wo.produced_qty
        """,
        (item_code,),
        as_dict=True,
    )
    for d in wo_as_product:
        # SAP Backwards Scheduling Logic
        if d.so_delivery_date and (d.param_prod_time or d.param_del_time):
            # Planned Order End Date = SO Delivery Date - Delivery Time
            expected_end_date = add_days(d.so_delivery_date, -int(d.param_del_time))
        else:
            expected_end_date = d.planned_end_date or d.planned_start_date

        elements.append(_make_element(
            element_date=expected_end_date,
            mrp_type="PldOrd",
            label=_("İş Emri (Üretim)"),
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
            (SELECT MIN(delivery_date) FROM `tabSales Order Item` WHERE parent = wo.sales_order AND item_code = wo.production_item) AS so_delivery_date,
            IFNULL(sp.production_time, 0) AS param_prod_time,
            IFNULL(sp.delivery_time, 0) AS param_del_time
        FROM `tabWork Order` wo
        LEFT JOIN `tabSales Order` so ON wo.sales_order = so.name
        LEFT JOIN `tabKTA Sevk Parametreleri` sp ON so.customer = sp.customer_name
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
        if d.so_delivery_date and (d.param_prod_time or d.param_del_time):
            expected_end_date = add_days(d.so_delivery_date, -int(d.param_del_time))
            expected_start_date = add_days(expected_end_date, -int(d.param_prod_time))
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


def _get_bom_materials(bom_no):
    """BOM Explosion Item tablosundan malzeme listesi."""
    return frappe.db.get_all(
        "BOM Explosion Item",
        filters={"parent": bom_no},
        fields=["item_code", "stock_qty"],
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
    is_firmed=False
):
    """Tek bir MRP element satırı oluşturur."""
    d = getdate(element_date) if element_date else getdate(today())
    iso_year, iso_week, _ = d.isocalendar()
    return {
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


def _filter_by_date(elements, from_date, to_date):
    """Tarih aralığına göre filtrele. Stok satırı her zaman kalır."""
    filtered = []
    for el in elements:
        if el["mrp_element_type"] == "Stock":
            filtered.append(el)
            continue
        el_date = getdate(el["date"])
        if el_date > to_date:
            continue
        filtered.append(el)
    return filtered


def _sort_and_calculate_running_balance(elements):
    """Kronolojik sırala ve kümülatif bakiye hesapla."""
    # Stok satırı her zaman en başta
    def sort_key(el):
        priority = 0 if el["mrp_element_type"] == "Stock" else 1
        return (priority, el["date"], el["mrp_element_type"])

    elements.sort(key=sort_key)

    running = 0
    for el in elements:
        running += flt(el["receipt_qty"]) - flt(el["requirement_qty"])
        el["available_qty"] = flt(running, 2)

    return elements


def _detect_exceptions(elements, safety_stock):
    """İstisna kodlarını belirle."""
    today_date = getdate(today())
    for el in elements:
        el_date = getdate(el["date"])

        # Stok satırı için istisna yok
        if el["mrp_element_type"] == "Stock":
            continue

        # Stok Açığı
        if el["available_qty"] < 0:
            el["exception_code"] = "SHORTAGE"
            el["exception_message"] = _("Stok Açığı")
            continue

        # Emniyet Stoku Altı
        if safety_stock > 0 and el["available_qty"] < safety_stock:
            el["exception_code"] = "BELOW_SAFETY"
            el["exception_message"] = _("Emniyet Stoku Altı")
            continue

        # Gecikmiş
        if el_date < today_date and (
            el["receipt_qty"] > 0 or el["requirement_qty"] > 0
        ):
            el["exception_code"] = "OVERDUE"
            el["exception_message"] = _("Gecikmiş")

    return elements


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

    # Karşılanma günü tahmini
    coverage_days = 0
    if total_requirements > 0 and current_stock > 0:
        daily_demand = total_requirements / max(
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
        w = el["week_label"]
        week_data[w]["receipt"] += flt(el["receipt_qty"])
        week_data[w]["requirement"] += flt(el["requirement_qty"])
        week_data[w]["balance"] = flt(el["available_qty"])

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
    """Elementleri haftalık bazda grupla."""
    week_groups = defaultdict(lambda: {
        "receipt_qty": 0,
        "requirement_qty": 0,
        "elements": [],
    })

    for el in elements:
        w = el["week_label"]
        week_groups[w]["receipt_qty"] += flt(el["receipt_qty"])
        week_groups[w]["requirement_qty"] += flt(el["requirement_qty"])
        week_groups[w]["elements"].append(el)

    result = []
    running = 0
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
