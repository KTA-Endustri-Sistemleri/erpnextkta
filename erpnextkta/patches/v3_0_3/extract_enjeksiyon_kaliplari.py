# Copyright (c) 2026, KTA Endustri Sistemleri and contributors
# For license information, please see license.txt

import re

import frappe

# Curated 46 baseline injection molds and their default QI templates
SEED_MOLDS = {
    "8705902432": "8705902432 Enjeksiyon KP Rev.00",
    "8705902433": "8705902433 Enjeksiyon KP Rev.00 - 8705901120",
    "8705902434": "8705902434 Enjeksiyon KP Rev.00 - 8705902372",
    "8710506149": "8710506149 Enjeksiyon KP Rev.00 - 8714402086",
    "8710506150": "8710506150 Enjeksiyon KP Rev.00",
    "8710506191": "8710506191 Enjeksiyon KP Rev.00",
    "8710506248": "8710506248 Enjeksiyon KP Rev.00",
    "8710506250": "8710506250 Enjeksiyon KP Rev.00",
    "8710506285": "8710506285 Enjeksiyon KP Rev.00",
    "8716774095": "8716774095 Enjeksiyon KP Rev.00",
    "8718222729": "8718222729 Enjeksiyon KP Rev.00",
    "8718641274": "8718641274 Enjeksiyon KP Rev.00",
    "8718641275": "8718641275 Enjeksiyon KP Rev.00",
    "8718645633": "8718645633 Enjeksiyon KP Rev.00",
    "8718650317": "8718650317 Enjeksiyon KP Rev.00",
    "8718650719": "8718650719 Enjeksiyon KP Rev.00",
    "8718650720": "8718650720 Enjeksiyon KP Rev.00 - 8718650713",
    "8718650721": "8718650721 Enjeksiyon KP Rev.00 - 8718650710",
    "8718651611": "8718651611 Enjeksiyon KP Rev.00",
    "8718663738": "8718663738 Enjeksiyon KP Rev.00",
    "8718667270": "8718667270 Enjeksiyon KP Rev.00",
    "8718667797": "8718667797 Enjeksiyon KP Rev.00",
    "8718668287": "8718668287 Enjeksiyon KP Rev.00",
    "8718668288": "8718668288 Enjeksiyon KP Rev.00",
    "8718668339": "8718668339 Enjeksiyon KP Rev.00",
    "8718668340": "8718668340 Enjeksiyon KP Rev.00",
    "8718668341": "8718668341 Enjeksiyon KP Rev.00",
    "8718668342": "8718668342 Enjeksiyon KP Rev.00",
    "8718672904": "8718672904 Enjeksiyon KP Rev.00",
    "8718678521": "8718678521 Enjeksiyon KP Rev.00",
    "8718686417": "8718686417 Enjeksiyon KP Rev.00",
    "8718686739": "8718686739 Enjeksiyon KP Rev.00",
    "8718687762": "8718687762 Enjeksiyon KP Rev.00",
    "8718688356": "8718688356 Enjeksiyon KP Rev.00",
    "8718695970": "8718695970 Enjeksiyon",
    "8718695994": "8718695994 Enjeksiyon KP Rev.00",
    "8719905701": "8719905701 Enjeksiyon KP Rev.00 - 8716013585",
    "8733207662": "8733207662 Enjeksiyon KP Rev.00",
    "8733211087": "8733211087 Enjeksiyon KP Rev.00",
    "8740403028": "8740403028 Enjeksiyon KP Rev.00",
    "8750300792": "8750300792 Enjeksiyon KP Rev.00 - 8750777512",
    "8750303956": "8750303956 Enjeksiyon rev 02",
    "8750306384": "8750306384 Enjeksiyon KP Rev.00 - 8750301805",
    "8750741360": "8750741360 Enjeksiyon KP Rev.00",
    "8750768335": "8750768335 Enjeksiyon KP Rev.01",
    "8750795055": "8750795055 Enjeksiyon KP 8750779556",
}


def execute():
    """Extract 10-digit injection mold numbers from Quality Inspection Templates

    and populate KTA Enjeksiyon Kalibi records idempotently.
    Ensures all 46 baseline molds exist even in fresh/test databases.
    """
    if not frappe.db.table_exists("KTA Enjeksiyon Kalibi"):
        return

    molds_to_create = dict(SEED_MOLDS)

    # If database has additional QI templates, discover them dynamically
    if frappe.db.table_exists("Quality Inspection Template"):
        db_templates = frappe.db.sql(
            """
            SELECT name
            FROM `tabQuality Inspection Template`
            WHERE name LIKE '%Enjeksiyon%'
            ORDER BY name ASC
            """,
            as_dict=True,
        )
        for t in db_templates:
            template_name = t.name.strip()
            match = re.match(r"^(\d{10})\b", template_name)
            if match:
                mold_no = match.group(1)
                molds_to_create[mold_no] = template_name

    for mold_no, template_name in molds_to_create.items():
        # Ensure QI template stub exists if needed to satisfy Link validation
        if (
            template_name
            and frappe.db.table_exists("Quality Inspection Template")
            and not frappe.db.exists("Quality Inspection Template", template_name)
        ):
            try:
                frappe.get_doc({
                    "doctype": "Quality Inspection Template",
                    "quality_inspection_template_name": template_name,
                    "item_quality_inspection_parameter": [
                        {"specification": "Görsel Kontrol", "value": "OK"}
                    ],
                }).insert(
                    ignore_permissions=True,
                    ignore_mandatory=True,
                    ignore_links=True,
                    ignore_if_duplicate=True,
                )
            except (frappe.DuplicateEntryError, frappe.ValidationError) as e:
                frappe.logger("patch").debug(f"QI template stub creation skipped: {e}")

        if not frappe.db.exists("KTA Enjeksiyon Kalibi", mold_no):
            frappe.get_doc({
                "doctype": "KTA Enjeksiyon Kalibi",
                "kalip_no": mold_no,
                "kalip_adi": f"{mold_no} Enjeksiyon Kalıbı",
                "varsayilan_kalite_sablonu": template_name,
                "mevcut_adet": 1,
                "disabled": 0,
            }).insert(ignore_permissions=True, ignore_links=True, ignore_if_duplicate=True)
        else:
            # Backfill default template if previously missing or None
            curr_template = frappe.db.get_value("KTA Enjeksiyon Kalibi", mold_no, "varsayilan_kalite_sablonu")
            if not curr_template and template_name:
                frappe.db.set_value("KTA Enjeksiyon Kalibi", mold_no, "varsayilan_kalite_sablonu", template_name)
