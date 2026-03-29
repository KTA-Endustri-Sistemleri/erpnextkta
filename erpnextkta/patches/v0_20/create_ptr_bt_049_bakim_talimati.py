import frappe


def execute():
    """Create PTR.BT.049 Bakim Talimati record if it doesn't exist."""

    if frappe.db.exists("Bakim Talimati", "PTR.BT.049"):
        return

    talimat_metni = """<div style="font-family: Arial, sans-serif;">
<h4>PTR.BT.049 GÜNLÜK KORUYUCU BAKIM TALİMATI</h4>

<p><strong>Operatör işe başlamadan önce</strong> aşağıdaki kontrolleri yapmalı ve
<strong>PTR08.009 Makine Günlük Bakım Takip Formu'nu</strong> imzalamadan
kesinlikle çalışmamalıdır.</p>

<hr/>

<table style="width:100%; border-collapse: collapse; margin: 10px 0;">
<tr style="background-color: #f0f0f0;">
  <th style="border: 1px solid #ccc; padding: 8px; text-align: left; width: 150px;">Sorumlu</th>
  <th style="border: 1px solid #ccc; padding: 8px; text-align: left;">İşlem</th>
</tr>
<tr>
  <td style="border: 1px solid #ccc; padding: 8px; font-weight: bold; color: #c00;">Operatör</td>
  <td style="border: 1px solid #ccc; padding: 8px;">PTR08.009 Makine Günlük Bakım Takip Formunu
  <strong>imzalamadan kesinlikle çalışma!</strong></td>
</tr>
<tr>
  <td style="border: 1px solid #ccc; padding: 8px;">Operatör</td>
  <td style="border: 1px solid #ccc; padding: 8px;">Makine üzerinde <strong>yabancı madde
  bulunmamasına</strong> dikkat et.</td>
</tr>
<tr>
  <td style="border: 1px solid #ccc; padding: 8px;">Operatör</td>
  <td style="border: 1px solid #ccc; padding: 8px;">Makine veya cihaz üzerinde mevcut
  <strong>kumanda butonlarının</strong> çalışıp çalışmadığını kontrol et.</td>
</tr>
<tr>
  <td style="border: 1px solid #ccc; padding: 8px;">Operatör</td>
  <td style="border: 1px solid #ccc; padding: 8px;">Makine üzerindeki <strong>fanların</strong>
  (soğutma fanı bulunan makinelerde) çalışıp çalışmadığını kontrol et.</td>
</tr>
<tr>
  <td style="border: 1px solid #ccc; padding: 8px;">Operatör</td>
  <td style="border: 1px solid #ccc; padding: 8px;">Makine veya cihaz üzerindeki
  <strong>lambaların</strong> yanıp yanmadığını kontrol et.</td>
</tr>
<tr>
  <td style="border: 1px solid #ccc; padding: 8px;">Operatör</td>
  <td style="border: 1px solid #ccc; padding: 8px;">Herhangi bir uygunsuzluk yoksa
  <strong>Günlük Bakım Takip Formunun ilgili bölümünü onayla.</strong></td>
</tr>
<tr>
  <td style="border: 1px solid #ccc; padding: 8px; color: #c00;">Operatör</td>
  <td style="border: 1px solid #ccc; padding: 8px;">Herhangi bir olumsuzluk tespit ettiğinde
  <strong>Vardiya Sorumlusunu haberdar et.</strong> Makineye onarım açısından kesinlikle
  müdahale etme.</td>
</tr>
<tr>
  <td style="border: 1px solid #ccc; padding: 8px;">Vardiya Sorumlusu</td>
  <td style="border: 1px solid #ccc; padding: 8px;">Makine veya cihazdaki problemi
  <strong>Arıza Bildirim ve İş Takip Formu</strong> ile Bakım Onarım Sorumlusuna ilet.</td>
</tr>
<tr>
  <td style="border: 1px solid #ccc; padding: 8px; color: #c00;">Operatör</td>
  <td style="border: 1px solid #ccc; padding: 8px;">Makine veya cihaza ait problem
  giderilmedikçe <strong>Günlük Bakım Takip Formunu onaylama.</strong></td>
</tr>
<tr>
  <td style="border: 1px solid #ccc; padding: 8px;">Operatör / Vardiya Sorumlusu</td>
  <td style="border: 1px solid #ccc; padding: 8px;">Günlük bakımı yapılmamış cihaz ve
  makineleri <strong>kesinlikle kullanma</strong> ve kullanımına müsaade etme.</td>
</tr>
<tr>
  <td style="border: 1px solid #ccc; padding: 8px;">Operatör</td>
  <td style="border: 1px solid #ccc; padding: 8px;">İş bitiminde makine ve çevresinin
  <strong>genel temizliğini</strong> yap.</td>
</tr>
</table>

<p style="font-size: 11px; color: #666; margin-top: 15px;">
Hazırlayan: M. Hayri Mahiroğlu | Onay: Turgut Yıldız | Rev: 01 (01.10.2015)</p>
</div>"""

    doc = frappe.get_doc(
        {
            "doctype": "Bakim Talimati",
            "talimat_kodu": "PTR.BT.049",
            "talimat_adi": "Günlük Koruyucu Bakım Talimatı",
            "aktif": 1,
            "versiyon": "01",
            "amac": (
                "PRETTL bünyesindeki bütün makine, cihaz vb. nin günlük bakımlarının "
                "Makine Operatörleri tarafından nasıl yapılacağının belirlenmesidir."
            ),
            "kapsam": "Prettl bünyesindeki bütün makine ve cihazları kapsar.",
            "talimat_metni": talimat_metni,
        }
    )
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
