const __ = (...args: any[]) => (window as any).__(...args);
const frappe = (window as any).frappe;

export function getBaseStyle() {
  return `
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial, sans-serif; font-size: 11px; color: #111; padding: 20px; }
    h1 { font-size: 16px; margin-bottom: 4px; }
    h2 { font-size: 13px; font-weight: normal; margin-bottom: 16px; color: #555; }
    .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; border-bottom: 2px solid #111; padding-bottom: 12px; }
    .header-left h1 { font-size: 18px; }
    .header-right { text-align: right; font-size: 11px; color: #444; }
    .header-right b { display: block; font-size: 13px; color: #111; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 24px; }
    th { background: #222; color: #fff; padding: 5px 4px; text-align: center; font-size: 9px; white-space: nowrap; }
    td { padding: 4px; text-align: center; border: 1px solid #ddd; font-size: 9px; }
    .row-even { background: #f9f9f9; }
    .ok { color: #166534; font-weight: bold; }
    .low { color: #991b1b; font-weight: bold; }
    .high { color: #1e40af; font-weight: bold; }
    .signatures { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 40px; margin-top: 40px; }
    .sig-box { border-top: 1px solid #333; padding-top: 8px; }
    .sig-box .title { font-size: 10px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }
    .sig-box .space { height: 50px; }
    .sig-box .name-line { border-bottom: 1px solid #aaa; margin-top: 4px; height: 20px; }
    .footer { margin-top: 20px; font-size: 9px; color: #888; text-align: center; }
    @media print {
      body { padding: 10px; }
      button { display: none; }
    }
  `;
}

export function getHeaderHtml(doc: any, title: string, today: string, is_sub_op_based: boolean = false) {
  return `
    <div class="header">
      <div class="header-left">
        <h1>KTA Endüstri Sistemleri</h1>
        <h2>${title}</h2>
      </div>
      <div class="header-right">
        <b>${doc.name}</b><br>
        İş Emri: ${doc.custom_work_order || "-"}<br>
        Ürün: ${doc.urun_kodu || "-"}<br>
        ${!is_sub_op_based ? `Kalite Belgesi: ${doc.quality_inspection || "-"}<br>` : ''}
        Tarih: ${today}
      </div>
    </div>
  `;
}

export function getSignaturesHtml(doc: any, today: string, qisList: string[] = [], approversList: string[] = []) {
  let qisHtml = "-";
  if (qisList && qisList.length > 0) {
    qisHtml = qisList.join("<br>");
  }

  let approversHtml = "-";
  if (approversList && approversList.length > 0) {
    approversHtml = approversList.join("<br>");
  }

  return `
    <div class="signatures">
      <div class="sig-box">
        <div class="title">${__("Hazırlayan Operatör")}</div>
        <div class="space"></div>
        <div class="name-line" style="border-bottom:none; font-weight:bold; font-size:10px; height:auto;">
          ${doc.operator_name || doc.operator || "-"}
        </div>
        <div class="name-line"></div>
        <div style="margin-top:4px;font-size:9px;color:#555;">İmza / Tarih</div>
      </div>
      <div class="sig-box">
        <div class="title">${__("Kalite Belgeleri")}</div>
        <div class="space"></div>
        <div class="name-line" style="border-bottom:none; font-weight:bold; font-size:10px; height:auto; line-height:1.4;">
          ${qisHtml}
        </div>
        <div class="name-line"></div>
        <div style="margin-top:4px;font-size:9px;color:#555;">İmza / Tarih</div>
      </div>
      <div class="sig-box">
        <div class="title">${__("Onaylayanlar")}</div>
        <div class="space"></div>
        <div class="name-line" style="border-bottom:none; font-weight:bold; font-size:10px; height:auto; line-height:1.4;">
          ${approversHtml}
        </div>
        <div class="name-line"></div>
        <div style="margin-top:4px;font-size:9px;color:#555;">${__("Ad Soyad / İmza / Tarih")}</div>
      </div>
    </div>
    <div class="footer">
      Bu belge KTA Endüstri Sistemleri kalite takip sistemi tarafından otomatik oluşturulmuştur. • ${today}
    </div>
  `;
}

export function printHtml(title: string, docName: string, bodyHtml: string) {
  const html = `
  <!DOCTYPE html>
  <html lang="tr">
  <head>
    <meta charset="UTF-8">
    <title>${title} - ${docName}</title>
    <style>${getBaseStyle()}</style>
  </head>
  <body>
    ${bodyHtml}
    <script>
      window.onload = () => window.print();
    </script>
  </body>
  </html>
  `;

  const w = window.open("", "_blank", "width=1100,height=700");
  if (w) {
    w.document.write(html);
    w.document.close();
  }
}

export function printIdcProtocol(doc: any) {
  const rows: any[] = doc.idc_olcumleri || [];
  if (rows.length === 0) return frappe.msgprint(__("Yazdırılacak IDC ölçümü yok."));

  const today = frappe.datetime.get_today();

  const fmt = (val: string) => {
    if (!val) return "-";
    try { const d = new Date(val); return isNaN(d.getTime()) ? val : d.toLocaleString("tr-TR"); } catch { return val; }
  };

  const rows_html = rows.map((r: any, i: number) => `
    <tr class="row-${i % 2 === 0 ? 'even' : 'odd'}">
      <td>${i + 1}</td>
      <td>${r.item_code || "-"}</td>
      <td>${r.yukseklik_mm ?? "-"} mm</td>
      <td>${r.cekme_n ?? "-"} N</td>
      <td>${fmt(r.olcum_tarihi)}</td>
      <td>${r.olcumu_giren || "-"}</td>
    </tr>
  `).join("");

  const bodyHtml = `
    ${getHeaderHtml(doc, "IDC Ölçüm Protokol Belgesi", today)}
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>${__('Item Code')}</th>
          <th>${__('Yükseklik')}</th>
          <th>${__('Çekme')}</th>
          <th>${__('Ölçüm Tarihi')}</th>
          <th>${__('Giren')}</th>
        </tr>
      </thead>
      <tbody>${rows_html}</tbody>
    </table>
    ${getSignaturesHtml(doc, today)}
  `;

  printHtml("IDC Protokol Belgesi", doc.name, bodyHtml);
}

export async function printKrimpProtocol(doc: any) {
  const rows: any[] = doc.krimp_olcumleri || [];
  if (rows.length === 0) return frappe.msgprint(__("Yazdırılacak krimp ölçümü yok."));

  const today = frappe.datetime.get_today();

  const sapmaTxt = (olculen: number, hedef: number) => {
    if (!hedef) return "-";
    const d = (olculen - hedef).toFixed(3);
    return d === "0.000" ? "✔ OK" : `${Number(d) > 0 ? "+" : ""}${d} mm`;
  };

  const sapmaClass = (olculen: number, hedef: number) => {
    if (!hedef) return "";
    const d = olculen - hedef;
    if (Math.abs(d) < 0.001) return "ok";
    return d < 0 ? "low" : "high";
  };

  const altOps = doc.alt_operasyon_kayitlari || [];
  const qis = altOps.map((a: any) => a.quality_inspection).filter(Boolean);
  const is_sub_op_based = qis.length > 0;

  let qisList: string[] = [];
  let approversList: string[] = [];

  if (is_sub_op_based) {
    try {
      const res = await frappe.call({
        method: "frappe.client.get_list",
        args: {
          doctype: "Quality Inspection",
          filters: { name: ["in", qis] },
          fields: ["name", "owner"]
        }
      });
      const userEmails = res.message.map((m: any) => m.owner);
      if (userEmails.length > 0) {
        const usersRes = await frappe.call({
          method: "frappe.client.get_list",
          args: {
            doctype: "User",
            filters: { name: ["in", userEmails] },
            fields: ["name", "full_name"]
          }
        });
        const users = usersRes.message || [];
        const userMap = users.reduce((acc: any, u: any) => { acc[u.name] = u.full_name; return acc; }, {});
        
        const ownerMap = res.message.reduce((acc: any, m: any) => { acc[m.name] = userMap[m.owner] || m.owner; return acc; }, {});
        
        rows.forEach((r: any, i: number) => {
          const altOp = altOps.find((a: any) => a.name === r.alt_operasyon_kaydi);
          const qiName = altOp?.quality_inspection;
          if (qiName) {
            const qStr = `${i + 1}. ${qiName}`;
            const aStr = `${i + 1}. ${ownerMap[qiName] || "-"}`;
            if (!qisList.includes(qStr)) {
              qisList.push(qStr);
              approversList.push(aStr);
            }
          }
        });
      }
    } catch (e) {
      console.error("Failed to fetch QI owners", e);
    }
  } else {
    if (doc.quality_inspection) {
      qisList.push(doc.quality_inspection);
      approversList.push(doc.qi_details?.owner_name || doc.qi_owner_name || "-");
    }
  }

  const rows_html = rows.map((r: any, i: number) => {
    const t1_radus = !r.kontak_no && (r.siyirma_boyu || 0) > 0 && r.yon_2_kontak_no ? r.yon_2_radus_mevcut : (!r.kontak_no ? 1 : r.radus_mevcut);
    const t1_tel_kesme = !r.kontak_no && (r.siyirma_boyu || 0) > 0 && r.yon_2_kontak_no ? r.yon_2_tel_kesme_mevcut : (!r.kontak_no ? 0 : r.tel_kesme_mevcut);
    
    const t2_radus = !r.yon_2_kontak_no && (r.yon_2_siyirma_boyu || 0) > 0 && r.kontak_no ? r.radus_mevcut : (!r.yon_2_kontak_no ? 1 : r.yon_2_radus_mevcut);
    const t2_tel_kesme = !r.yon_2_kontak_no && (r.yon_2_siyirma_boyu || 0) > 0 && r.kontak_no ? r.tel_kesme_mevcut : (!r.yon_2_kontak_no ? 0 : r.yon_2_tel_kesme_mevcut);

    const altOp = altOps.find((a: any) => a.name === r.alt_operasyon_kaydi);
    const satir_no = altOp?.satir_no || "-";

    let row1 = `
    <tr class="row-${i % 2 === 0 ? 'even' : 'odd'}">
      <td ${r.is_cift_tarafli ? 'rowspan="2"' : ''}>${i + 1}</td>
      <td ${r.is_cift_tarafli ? 'rowspan="2"' : ''}>${satir_no}</td>
      <td ${r.is_cift_tarafli ? 'rowspan="2"' : ''}>${r.kablo_no || "-"}</td>
      <td>${r.is_cift_tarafli ? '(T1) ' : ''}${r.kontak_no || "-"}</td>
      <td>${r.kablo_kesiti || "-"}</td>
      <td>${r.makine_pres_no || "-"}</td>
      <td>${r.kalip_no || "-"}</td>
      <td ${r.is_cift_tarafli ? 'rowspan="2"' : ''}>${r.hedef_kablo_boyu ?? "-"}</td>
      <td ${r.is_cift_tarafli ? 'rowspan="2"' : ''}>${r.olculen_kablo_boyu ?? "-"}</td>
      <td ${r.is_cift_tarafli ? 'rowspan="2"' : ''} class="${sapmaClass(r.olculen_kablo_boyu, r.hedef_kablo_boyu)}">${sapmaTxt(r.olculen_kablo_boyu, r.hedef_kablo_boyu)}</td>
      <td>${r.hedef_iletken_krimp_yuksekliği ?? "-"}</td>
      <td>${r.olculen_iletken_krimp_yuksekliği ?? "-"}</td>
      <td class="${sapmaClass(r.olculen_iletken_krimp_yuksekliği, r.hedef_iletken_krimp_yuksekliği)}">${sapmaTxt(r.olculen_iletken_krimp_yuksekliği, r.hedef_iletken_krimp_yuksekliği)}</td>
      <td>${r.siyirma_boyu ?? "-"} mm</td>
      <td>${r.capak_boyu ?? "-"} mm</td>
      <td>${r.olculen_cekme_kuvveti_n ?? "-"} N (Hedef: ${r.hedef_cekme_kuvveti_n ?? "-"})</td>
      <td class="${t1_radus ? 'ok' : 'low'}">${t1_radus ? "✔" : "✘"}</td>
      <td class="${!t1_tel_kesme ? 'ok' : 'low'}">${!t1_tel_kesme ? "✔" : "✘"}</td>
      <td ${r.is_cift_tarafli ? 'rowspan="2"' : ''}>${r.operator || "-"}</td>
    </tr>
    `;

    if (r.is_cift_tarafli) {
      let row2 = `
    <tr class="row-${i % 2 === 0 ? 'even' : 'odd'}">
      <td>(T2) ${r.yon_2_kontak_no || "-"}</td>
      <td>${r.yon_2_kablo_kesiti || "-"}</td>
      <td>${r.yon_2_makine_pres_no || "-"}</td>
      <td>${r.yon_2_kalip_no || "-"}</td>
      <td>${r.yon_2_hedef_iletken_krimp_yuksekligi ?? "-"}</td>
      <td>${r.yon_2_olculen_iletken_krimp_yuksekligi ?? "-"}</td>
      <td class="${sapmaClass(r.yon_2_olculen_iletken_krimp_yuksekligi, r.yon_2_hedef_iletken_krimp_yuksekligi)}">${sapmaTxt(r.yon_2_olculen_iletken_krimp_yuksekligi, r.yon_2_hedef_iletken_krimp_yuksekligi)}</td>
      <td>${r.yon_2_siyirma_boyu ?? "-"} mm</td>
      <td>${r.yon_2_capak_boyu ?? "-"} mm</td>
      <td>${r.yon_2_olculen_cekme_kuvveti_n ?? "-"} N (Hedef: ${r.yon_2_hedef_cekme_kuvveti_n ?? "-"})</td>
      <td class="${t2_radus ? 'ok' : 'low'}">${t2_radus ? "✔" : "✘"}</td>
      <td class="${!t2_tel_kesme ? 'ok' : 'low'}">${!t2_tel_kesme ? "✔" : "✘"}</td>
    </tr>
      `;
      return row1 + row2;
    }
    
    return row1;
  }).join("");

  const bodyHtml = `
    ${getHeaderHtml(doc, "Krimp Ölçüm Protokol Belgesi", today, is_sub_op_based)}
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>${__('Satır No')}</th>
          <th>${__('Kablo No')}</th>
          <th>${__('Terminal No')}</th>
          <th>${__('Kesit')}</th>
          <th>${__('Makine')}</th>
          <th>${__('Kalıp')}</th>
          <th>${__('Hdf. Kablo Boyu')}</th>
          <th>${__('Ölc. Kablo Boyu')}</th>
          <th>${__('Sapma')}</th>
          <th>${__('Hdf. Krimp Yük.')}</th>
          <th>${__('Ölc. Krimp Yük.')}</th>
          <th>${__('Sapma')}</th>
          <th>${__('Sıyırma')}</th>
          <th>${__('Çapak')}</th>
          <th>${__('Çekme')}</th>
          <th>${__('Radüs Var')}</th>
          <th>${__('Tel Kesme Yok')}</th>
          <th>${__('Operatör')}</th>
        </tr>
      </thead>
      <tbody>${rows_html}</tbody>
    </table>
    ${getSignaturesHtml(doc, today, qisList, approversList)}
  `;

  printHtml("Krimp Protokol Belgesi", doc.name, bodyHtml);
}

export function printEnjeksiyonProtocol(doc: any) {
  const rows: any[] = doc.enjeksiyon_olcumleri || [];
  if (rows.length === 0) return frappe.msgprint(__("Yazdırılacak enjeksiyon ölçümü yok."));

  const today = frappe.datetime.get_today();

  const sapmaClass = (val: number, merkez: number, tolerans: number) => {
      if (!val || !merkez) return "";
      const diff = Math.abs(val - merkez);
      return diff <= tolerans ? "ok" : "low";
  };
  
  const minMaxClass = (val: number, min: number, max: number) => {
      if (!val || (!min && !max)) return "";
      if (min && val < min) return "low";
      if (max && val > max) return "low";
      return "ok";
  };
  
  const formatMerkez = (val: number, merkez: number, tol: number) => {
      if (!val) return "-";
      return merkez ? `${val} <br><span style="font-size:8px;color:#666;">(${merkez}±${tol})</span>` : val;
  };
  
  const formatMinMax = (val: number, min: number, max: number) => {
      if (!val) return "-";
      if (min && max) return `${val} <br><span style="font-size:8px;color:#666;">(${min}-${max})</span>`;
      if (min) return `${val} <br><span style="font-size:8px;color:#666;">(>${min})</span>`;
      if (max) return `${val} <br><span style="font-size:8px;color:#666;">(<${max})</span>`;
      return val;
  };

  const rows_html = rows.map((r: any, i: number) => `
    <tr class="row-${i % 2 === 0 ? 'even' : 'odd'}">
      <td>${i + 1}</td>
      <td>${r.kontrol_periyodu || "-"}</td>
      <td>${r.hammadde_no || "-"}</td>
      <td class="${sapmaClass(r.hammadde_kazan_isisi, r.hedef_hammadde_kazan_isisi_merkez, r.hedef_hammadde_kazan_isisi_tolerans)}">${formatMerkez(r.hammadde_kazan_isisi, r.hedef_hammadde_kazan_isisi_merkez, r.hedef_hammadde_kazan_isisi_tolerans)}</td>
      <td class="${sapmaClass(r.ara_hortum_isisi, r.hedef_ara_hortum_isisi_merkez, r.hedef_ara_hortum_isisi_tolerans)}">${formatMerkez(r.ara_hortum_isisi, r.hedef_ara_hortum_isisi_merkez, r.hedef_ara_hortum_isisi_tolerans)}</td>
      <td class="${sapmaClass(r.kafa_meme_isisi, r.hedef_kafa_meme_isisi_merkez, r.hedef_kafa_meme_isisi_tolerans)}">${formatMerkez(r.kafa_meme_isisi, r.hedef_kafa_meme_isisi_merkez, r.hedef_kafa_meme_isisi_tolerans)}</td>
      <td class="${minMaxClass(r.soguk_su_isisi, r.hedef_soguk_su_isisi_min, r.hedef_soguk_su_isisi_maks)}">${formatMinMax(r.soguk_su_isisi, r.hedef_soguk_su_isisi_min, r.hedef_soguk_su_isisi_maks)}</td>
      <td class="${minMaxClass(r.motor_devir, r.hedef_motor_devir_min, r.hedef_motor_devir_maks)}">${formatMinMax(r.motor_devir, r.hedef_motor_devir_min, r.hedef_motor_devir_maks)}</td>
      <td class="${minMaxClass(r.hammadde_enjeksiyon_zamani, r.hedef_enjeksiyon_zamani_min, r.hedef_enjeksiyon_zamani_maks)}">${formatMinMax(r.hammadde_enjeksiyon_zamani, r.hedef_enjeksiyon_zamani_min, r.hedef_enjeksiyon_zamani_maks)}</td>
      <td class="${minMaxClass(r.sogutma_zamani, r.hedef_sogutma_zamani_min, r.hedef_sogutma_zamani_maks)}">${formatMinMax(r.sogutma_zamani, r.hedef_sogutma_zamani_min, r.hedef_sogutma_zamani_maks)}</td>
      <td class="${minMaxClass(r.cekme_kuvveti_olculen, r.hedef_cekme_kuvveti_min, 0)}">${formatMinMax(r.cekme_kuvveti_olculen, r.hedef_cekme_kuvveti_min, 0)}</td>
      <td class="${r.goz_kontrol ? 'ok' : 'low'}">${r.goz_kontrol ? "✔" : "✘"}</td>
      <td>${r.operator || "-"}</td>
    </tr>
  `).join("");

  const bodyHtml = `
    ${getHeaderHtml(doc, "Enjeksiyon Ölçüm Protokol Belgesi", today)}
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>${__('Periyot')}</th>
          <th>${__('Hammadde')}</th>
          <th>${__('Kazan Isısı')}</th>
          <th>${__('Hortum Isısı')}</th>
          <th>${__('Meme Isısı')}</th>
          <th>${__('Soğuk Su')}</th>
          <th>${__('Devir')}</th>
          <th>${__('Enj. Zamanı')}</th>
          <th>${__('Soğ. Zamanı')}</th>
          <th>${__('Çekme (N)')}</th>
          <th>${__('Göz Knt.')}</th>
          <th>${__('Operatör')}</th>
        </tr>
      </thead>
      <tbody>${rows_html}</tbody>
    </table>
    ${getSignaturesHtml(doc, today)}
  `;

  printHtml("Enjeksiyon Protokol Belgesi", doc.name, bodyHtml);
}
