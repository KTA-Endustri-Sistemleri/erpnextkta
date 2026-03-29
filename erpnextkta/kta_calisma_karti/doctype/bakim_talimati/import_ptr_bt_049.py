#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to import PTR.BT.049 maintenance instruction from XLS file into Bakim Talimati doctype.
Run this script once to populate the instruction in the system.

Usage:
    bench execute erpnextkta.kta_calisma_karti.doctype.bakim_talimati.import_ptr_bt_049.import_instruction
"""

import frappe
import xlrd
import os


def import_instruction():
    """Import PTR.BT.049 instruction from XLS file into Bakim Talimati"""

    # Path to the XLS file
    app_path = frappe.get_app_path("erpnextkta")
    xls_file = os.path.join(app_path, "..", "PTR_BT_049_01 GÜNLÜK KORUYUCU BAKIM TALİMATI.xls")

    if not os.path.exists(xls_file):
        frappe.throw(f"XLS file not found at: {xls_file}")

    # Read the XLS file
    wb = xlrd.open_workbook(xls_file, formatting_info=False)
    sheet = wb.sheet_by_index(0)

    # Extract content
    talimat_kodu = "PTR.BT.049"
    talimat_adi = "GÜNLÜK KORUYUCU BAKIM TALİMATI"

    # Extract Amaç (row 3)
    amac = str(sheet.row_values(3)[1]).strip()

    # Extract Kapsam (row 4)
    kapsam = str(sheet.row_values(4)[1]).strip()

    # Build instruction content as HTML list
    instructions = []

    # Row 8: Main warning
    instructions.append("<li><strong>PTR08.009 MAKİNE GÜNLÜK BAKIM TAKİP FORMUNU İMZALAMADAN KESİNLİKLE ÇALIŞMA !!</strong></li>")

    # Row 11: Check for foreign objects
    instructions.append("<li>Makine üzerinde yabancı madde bulunmamasına dikkat et.</li>")

    # Row 13: Check control buttons
    instructions.append("<li>Makine veya cihaz üzerinde mevcut kumanda butonlarının çalışıp çalışmadığını kontrol et.</li>")

    # Row 16: Check fans
    instructions.append("<li>Makine üzerindeki Fanların (Soğutma fanı bulunan mak.) çalışıp çalışmadığını kontrol et.</li>")

    # Row 19: Check lamps
    instructions.append("<li>Makine veya cihaz üzerindeki lambaların yanıp yanmadığını kontrol et.</li>")

    # Row 22: Approve if no issues
    instructions.append("<li>Makine veya Cihaz üzerinde herhangibir uygunsuzluk yoksa Günlük Bakım Takip Formunun ilgili Bölümünü onayla.</li>")

    # Row 25: Report issues - no repair
    instructions.append("<li>Makine ve Cihaz üzerinde Kontrol ettiğin Bölümlerde herhangi bir olumsuzluk tespit ettiğinde Vardiya Sorumlusunu haberdar et. <strong>Makineye Onarım açısından kesinlikle müdahale etme.</strong></li>")

    # Row 30-31: Report to maintenance
    instructions.append("<li>Makine veya cihazdaki problemi Arıza Bildirim ve İştakip Formu (PTR 08 01) ile Bakım Onarım Sorumlusuna ilet.</li>")

    # Row 39: Final warning
    instructions.append("<li><strong>Günlük Bakımı yapılmamış Cihaz ve Makineleri kesinlikle Kullanma ve Kullanımına müsaade etme.</strong></li>")

    talimat_metni = "<ul>\n" + "\n".join(instructions) + "\n</ul>"

    # Check if instruction already exists
    if frappe.db.exists("Bakim Talimati", talimat_kodu):
        # Update existing
        doc = frappe.get_doc("Bakim Talimati", talimat_kodu)
        doc.talimat_adi = talimat_adi
        doc.amac = amac
        doc.kapsam = kapsam
        doc.talimat_metni = talimat_metni
        doc.aktif = 1
        doc.save()
        frappe.db.commit()
        print(f"✓ Updated: {talimat_kodu} - {talimat_adi}")
    else:
        # Create new
        doc = frappe.get_doc({
            "doctype": "Bakim Talimati",
            "talimat_kodu": talimat_kodu,
            "talimat_adi": talimat_adi,
            "amac": amac,
            "kapsam": kapsam,
            "talimat_metni": talimat_metni,
            "aktif": 1,
            "versiyon": "1.0"
        })
        doc.insert()
        frappe.db.commit()
        print(f"✓ Created: {talimat_kodu} - {talimat_adi}")

    return doc.name


if __name__ == "__main__":
    # For standalone execution
    import_instruction()
