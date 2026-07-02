<script setup lang="ts">
import { onMounted, computed, ref, watch } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);
import QcToggle from "../components/QcToggle.vue";
import IdcSection from "../components/IdcSection.vue";
import KrimpSection from "../components/KrimpSection.vue";
import EnjeksiyonSection from "../components/EnjeksiyonSection.vue";
import BarkodSection from "../components/BarkodSection.vue";
import { idcOlcumFields, krimpOlcumFields, barkodKayitFields, enjeksiyonOlcumFields } from "../composables/prompts";

function openQualityInspection(name: string) {
  frappe.set_route("Form", "Quality Inspection", name);
}

const props = defineProps<{
  doc: any;

  qcLabel: string;
  qcOptions: string[];
  qcFormValue: string;
  canEditQC: boolean;
  canEditData: boolean;
  qcSaving: boolean;
  onSetQC: (next: string) => void;

  // IDC CRUD
  onAddIdc: (payload: any) => Promise<void>;
  onUpdateIdc: (payload: any) => Promise<void>;
  onDeleteIdc: (rowname: string) => Promise<void>;

  // Krimp CRUD
  onAddKrimp: (payload: any) => Promise<void>;
  onUpdateKrimp: (payload: any) => Promise<void>;
  onDeleteKrimp: (rowname: string) => Promise<void>;

  // Enjeksiyon CRUD
  onAddEnjeksiyon: (payload: any) => Promise<void>;
  onUpdateEnjeksiyon: (payload: any) => Promise<void>;
  onDeleteEnjeksiyon: (rowname: string) => Promise<void>;

  // Barkod CRUD
  onAddBarkod: (payload: any) => Promise<void>;
  onUpdateBarkod: (payload: any) => Promise<void>;
  onDeleteBarkod: (rowname: string) => Promise<void>;
}>();

const qiThemeClass = computed(() => {
  const val = (props.qcFormValue || '').toLowerCase();
  if (val === 'accepted' || val === 'onaylandı') return 'is-accepted';
  if (val === 'rejected' || val === 'reddedildi' || val === 'red') return 'is-rejected';
  return 'is-default';
});

function addIdc() {
  frappe.prompt(
    idcOlcumFields(props.doc.name),
    async (v: any) => {
      await props.onAddIdc({
        item_code: v.item_code,
        yukseklik_mm: v.yukseklik_mm,
        cekme_n: v.cekme_n,
      });
      frappe.show_alert({ message: __("IDC ölçümü eklendi"), indicator: "green" });
    },
    __("IDC Ölçümü Ekle"),
    __("Kaydet")
  );
}

function editIdc(row: any) {
  if (!row?.name) return frappe.msgprint(__("IDC satır kimliği (row name) bulunamadı."));
  frappe.prompt(
    idcOlcumFields(props.doc.name, row),
    async (v: any) => {
      await props.onUpdateIdc({
        rowname: row.name,
        item_code: v.item_code,
        yukseklik_mm: v.yukseklik_mm,
        cekme_n: v.cekme_n,
      });
      frappe.show_alert({ message: __("IDC ölçümü güncellendi"), indicator: "green" });
    },
    __("IDC Ölçümü Düzenle"),
    __("Kaydet")
  );
}

function deleteIdc(row: any) {
  if (!row?.name) return frappe.msgprint(__("IDC satır kimliği (row name) bulunamadı."));
  frappe.confirm(__("Bu IDC ölçüm satırı silinecek. Emin misiniz?"), async () => {
    await props.onDeleteIdc(row.name);
    frappe.show_alert({ message: __("IDC ölçümü silindi"), indicator: "green" });
  });
}

function cloneIdc(row: any) {
  // Pre-fill with the existing row's values so the user can copy & adjust
  frappe.prompt(
    idcOlcumFields(props.doc.name, row),
    async (v: any) => {
      await props.onAddIdc({
        item_code: v.item_code,
        yukseklik_mm: v.yukseklik_mm,
        cekme_n: v.cekme_n,
      });
      frappe.show_alert({ message: __("IDC ölçümü kopyalandı ve eklendi"), indicator: "green" });
    },
    __("IDC Ölçümü Kopyala"),
    __("Kaydet")
  );
}

function printIdcProtocol() {
  const rows: any[] = props.doc.idc_olcumleri || [];
  if (rows.length === 0) return frappe.msgprint(__("Yazdırılacak IDC ölçümü yok."));

  const doc = props.doc;
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

  const html = `
  <!DOCTYPE html>
  <html lang="tr">
  <head>
    <meta charset="UTF-8">
    <title>IDC Protokol Belgesi - ${doc.name}</title>
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font-family: Arial, sans-serif; font-size: 11px; color: #111; padding: 20px; }
      h1 { font-size: 16px; margin-bottom: 4px; }
      h2 { font-size: 13px; font-weight: normal; margin-bottom: 16px; color: #555; }
      .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; border-bottom: 2px solid #111; padding-bottom: 12px; }
      .header-left h1 { font-size: 18px; }
      .header-right { text-align: right; font-size: 11px; color: #444; }
      .header-right b { display: block; font-size: 13px; color: #111; }
      table { width: 100%; border-collapse: collapse; margin-bottom: 24px; }
      th { background: #222; color: #fff; padding: 5px 4px; text-align: center; font-size: 10px; white-space: nowrap; }
      td { padding: 5px 4px; text-align: center; border: 1px solid #ddd; font-size: 10px; }
      .row-even { background: #f9f9f9; }
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
    </style>
  </head>
  <body>
    <div class="header">
      <div class="header-left">
        <h1>KTA Endüstri Sistemleri</h1>
        <h2>IDC Ölçüm Protokol Belgesi</h2>
      </div>
      <div class="header-right">
        <b>${doc.name}</b>
        İş Emri: ${doc.custom_work_order || "-"}<br>
        Ürün: ${doc.urun_kodu || "-"}<br>
        Kalite Belgesi: ${doc.quality_inspection || "-"}<br>
        Tarih: ${today}
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>{{ __('Item Code') }}</th>
          <th>{{ __('Yükseklik') }}</th>
          <th>{{ __('Çekme') }}</th>
          <th>{{ __('Ölçüm Tarihi') }}</th>
          <th>{{ __('Giren') }}</th>
        </tr>
      </thead>
      <tbody>${rows_html}</tbody>
    </table>

    <div class="signatures">
      <div class="sig-box">
        <div class="title">{{ __("Hazırlayan Operatör") }}</div>
        <div class="space"></div>
        <div class="name-line" style="border-bottom:none; font-weight:bold; font-size:10px; height:auto;">
          ${doc.operator_name || doc.operator || "-"}
        </div>
        <div class="name-line"></div>
        <div style="margin-top:4px;font-size:9px;color:#555;">İmza / Tarih</div>
      </div>
      <div class="sig-box">
        <div class="title">{{ __("Kalite Sorumlusu") }}</div>
        <div class="space"></div>
        <div class="name-line" style="border-bottom:none; font-weight:bold; font-size:10px; height:auto;">
          ${doc.qi_details?.owner_name || "-"}
        </div>
        <div class="name-line"></div>
        <div style="margin-top:4px;font-size:9px;color:#555;">İmza / Tarih</div>
      </div>
      <div class="sig-box">
        <div class="title">{{ __("Onaylayan") }}</div>
        <div class="space"></div>
        <div class="name-line"></div>
        <div style="margin-top:4px;font-size:9px;color:#555;">{{ __("Ad Soyad / İmza / Tarih") }}</div>
      </div>
    </div>

    <div class="footer">
      Bu belge KTA Endüstri Sistemleri kalite takip sistemi tarafından otomatik oluşturulmuştur. • ${today}
    </div>

    <script>
      window.onload = () => window.print();
    <\/script>
  </body>
  </html>
  `;

  const w = window.open("", "_blank", "width=900,height=600");
  if (w) {
    w.document.write(html);
    w.document.close();
  }
}

function setupKrimpBookLogic(dialog: any) {
  const kesit_fld = dialog.get_field("kablo_kesiti");
  const kablo_fld = dialog.get_field("kablo_no");
  const kontak_fld = dialog.get_field("kontak_no");
  
  dialog.last_kesit = dialog.get_value("kablo_kesiti");
  dialog.last_kablo = dialog.get_value("kablo_no");
  dialog.last_kontak = dialog.get_value("kontak_no");

  const updateDetails = () => {
    const kesit = dialog.get_value("kablo_kesiti");
    const kontak = dialog.get_value("kontak_no");

    if (kesit && kontak) {
      frappe.call({
        method: "erpnextkta.kta_calisma_karti.api.get_krimp_book_details",
        args: { kablo_no: dialog.get_value("kablo_no") || "", kontak_no: kontak, selected_kesit: kesit },
        callback: (r: any) => {
          if (r.message && Object.keys(r.message).length > 0) {
            const data = r.message;
            dialog.set_value("kalip_no", data.kalip_no);
            dialog.set_value("hedef_iletken_krimp_yuksekliği", data.hedef_iletken_krimp_yuksekliği);
            dialog.set_value("hedef_cekme_kuvveti_n", data.hedef_cekme_kuvveti_n);
            dialog.set_value("izokrimp_yuksekligi", data.izokrimp_yuksekligi);

            frappe.show_alert({ message: __("Krimp Book değerleri yüklendi"), indicator: "blue" });
          }
        }
      });
    } else {
      dialog.set_value("kalip_no", "");
      dialog.set_value("hedef_iletken_krimp_yuksekliği", 0);
      dialog.set_value("hedef_cekme_kuvveti_n", 0);
      dialog.set_value("izokrimp_yuksekligi", 0);
    }
  };

  if (kontak_fld) {
    kontak_fld.df.onchange = () => {
      const current_kontak = dialog.get_value("kontak_no");
      if (dialog.last_kontak === current_kontak) return;
      dialog.last_kontak = current_kontak;

      // Clear dependent fields when contact changes manually
      dialog.set_value("kablo_kesiti", "");
      dialog.set_value("kablo_no", "");

      if (current_kontak) {
        frappe.call({
          method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
          args: { kontak_no: current_kontak },
          callback: (r: any) => {
            if (r.message) {
              dialog.set_df_property("kablo_kesiti", "options", ["", ...r.message]);
            }
          }
        });
      } else {
        // Fallback to all kesits if contact is cleared
        frappe.call({
          method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
          callback: (r: any) => {
            if (r.message) {
              dialog.set_df_property("kablo_kesiti", "options", ["", ...r.message]);
            }
          }
        });
      }

      updateDetails();
    };
  }

  if (kesit_fld) {
    kesit_fld.df.onchange = () => {
      const current_kesit = dialog.get_value("kablo_kesiti");
      if (dialog.last_kesit === current_kesit) return;
      dialog.last_kesit = current_kesit;

      // Clear dependent cable field when kesit changes manually
      dialog.set_value("kablo_no", "");
      updateDetails();
    };
  }

  if (kablo_fld) {
    kablo_fld.df.onchange = () => {
      const current = dialog.get_value("kablo_no");
      if (dialog.last_kablo === current) return;
      dialog.last_kablo = current;
      updateDetails();
    };
  }
}

function addKrimp() {
  const dialog = frappe.prompt(
    krimpOlcumFields({ calisma_karti_name: props.doc.name }),
    async (v: any) => {
      await props.onAddKrimp(v);
      frappe.show_alert({ message: __("Krimp ölçümü eklendi"), indicator: "green" });
    },
    __("Krimp Ölçümü Ekle"),
    __("Kaydet")
  );

  // Set dynamic filters
  dialog.fields_dict.kablo_no.get_query = () => ({
    query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
    filters: { 
      calisma_karti: props.doc.name,
      kablo_kesiti: dialog.get_value("kablo_kesiti"),
      type: "kablo" 
    }
  });
  
  dialog.fields_dict.kontak_no.get_query = () => ({
    query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
    filters: { 
      calisma_karti: props.doc.name,
      kablo_kesiti: dialog.get_value("kablo_kesiti"),
      type: "kontak" 
    }
  });

  dialog.is_loading = true;

  const fetchKesits = () => {
    frappe.call({
      method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
      callback: (r: any) => {
        if (r.message) {
          dialog.set_df_property("kablo_kesiti", "options", ["", ...r.message]);
        }
        dialog.is_loading = false;
      }
    });
  };

  fetchKesits();
  setupKrimpBookLogic(dialog);
}

function editKrimp(row: any) {
  if (!row?.name) return frappe.msgprint(__("Krimp satır kimliği bulunamadı."));
  const dialog = frappe.prompt(
    krimpOlcumFields({ ...row, calisma_karti_name: props.doc.name }),
    async (v: any) => {
      await props.onUpdateKrimp({ rowname: row.name, payload: v });
      frappe.show_alert({ message: __("Krimp ölçümü güncellendi"), indicator: "green" });
    },
    __("Krimp Ölçümü Düzenle"),
    __("Kaydet")
  );

  // Set dynamic filters
  dialog.fields_dict.kablo_no.get_query = () => ({
    query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
    filters: { 
      calisma_karti: props.doc.name,
      kablo_kesiti: dialog.get_value("kablo_kesiti"),
      type: "kablo" 
    }
  });
  
  dialog.fields_dict.kontak_no.get_query = () => ({
    query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
    filters: { 
      calisma_karti: props.doc.name,
      kablo_kesiti: dialog.get_value("kablo_kesiti"),
      type: "kontak" 
    }
  });

  dialog.is_loading = true;

  const fetchKesits = () => {
    frappe.call({
      method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
      callback: (r: any) => {
        if (r.message) {
          dialog.set_df_property("kablo_kesiti", "options", ["", ...r.message]);
          // In edit mode, ensure the current value is selected
          const currentVal = row.kablo_kesiti;
          if (currentVal) dialog.set_value("kablo_kesiti", currentVal);
        }
        dialog.is_loading = false;
      }
    });
  };

  fetchKesits();
  setupKrimpBookLogic(dialog);
}

function deleteKrimp(row: any) {
  if (!row?.name) return frappe.msgprint(__("Krimp satır kimliği bulunamadı."));
  frappe.confirm(__("Bu krimp ölçüm satırı silinecek. Emin misiniz?"), async () => {
    await props.onDeleteKrimp(row.name);
    frappe.show_alert({ message: __("Krimp ölçümü silindi"), indicator: "green" });
  });
}

function cloneKrimp(row: any) {
  // Copy structural data, zero out measured values
  const cloneDefaults = {
    calisma_karti_name: props.doc.name,
    kablo_kesiti: row.kablo_kesiti || "",
    kablo_no: row.kablo_no || "",
    kontak_no: row.kontak_no || "",
    kalip_no: row.kalip_no || "",
    makine_pres_no: row.makine_pres_no || "",
    hedef_kablo_boyu: row.hedef_kablo_boyu ?? 0,
    hedef_iletken_krimp_yuksekliği: row.hedef_iletken_krimp_yuksekliği ?? 0,
    hedef_cekme_kuvveti_n: row.hedef_cekme_kuvveti_n ?? 0,
    olculen_cekme_kuvveti_n: row.olculen_cekme_kuvveti_n ?? 0,
    izokrimp_yuksekligi: row.izokrimp_yuksekligi ?? 0,
    radus_mevcut: row.radus_mevcut ?? 0,
    tel_kesme_mevcut: row.tel_kesme_mevcut ?? 0,
    // Measured values are intentionally left at 0
    olculen_kablo_boyu: 0,
    olculen_iletken_krimp_yuksekliği: 0,
    siyirma_boyu: 0,
    capak_boyu: 0,
  };

  const dialog = frappe.prompt(
    krimpOlcumFields(cloneDefaults),
    async (v: any) => {
      await props.onAddKrimp(v);
      frappe.show_alert({ message: __("Krimp ölçümü kopyalandı ve eklendi"), indicator: "green" });
    },
    __("Krimp Ölçümü Kopyala"),
    __("Kaydet")
  );

  dialog.fields_dict.kablo_no.get_query = () => ({
    query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
    filters: { calisma_karti: props.doc.name, kablo_kesiti: dialog.get_value("kablo_kesiti"), type: "kablo" }
  });
  dialog.fields_dict.kontak_no.get_query = () => ({
    query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
    filters: { calisma_karti: props.doc.name, kablo_kesiti: dialog.get_value("kablo_kesiti"), type: "kontak" }
  });

  dialog.is_loading = true;
  frappe.call({
    method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
    callback: (r: any) => {
      if (r.message) {
        dialog.set_df_property("kablo_kesiti", "options", ["", ...r.message]);
        if (cloneDefaults.kablo_kesiti) dialog.set_value("kablo_kesiti", cloneDefaults.kablo_kesiti);
      }
      dialog.is_loading = false;
    }
  });
  setupKrimpBookLogic(dialog);
}

function printKrimpProtocol() {
  const rows: any[] = props.doc.krimp_olcumleri || [];
  if (rows.length === 0) return frappe.msgprint(__("Yazdırılacak krimp ölçümü yok."));

  const doc = props.doc;
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

  const rows_html = rows.map((r: any, i: number) => `
    <tr class="row-${i % 2 === 0 ? 'even' : 'odd'}">
      <td>${i + 1}</td>
      <td>${r.kablo_no || "-"}</td>
      <td>${r.kontak_no || "-"}</td>
      <td>${r.kablo_kesiti || "-"}</td>
      <td>${r.makine_pres_no || "-"}</td>
      <td>${r.kalip_no || "-"}</td>
      <td>${r.hedef_kablo_boyu ?? "-"}</td>
      <td>${r.olculen_kablo_boyu ?? "-"}</td>
      <td class="${sapmaClass(r.olculen_kablo_boyu, r.hedef_kablo_boyu)}">${sapmaTxt(r.olculen_kablo_boyu, r.hedef_kablo_boyu)}</td>
      <td>${r.hedef_iletken_krimp_yuksekliği ?? "-"}</td>
      <td>${r.olculen_iletken_krimp_yuksekliği ?? "-"}</td>
      <td class="${sapmaClass(r.olculen_iletken_krimp_yuksekliği, r.hedef_iletken_krimp_yuksekliği)}">${sapmaTxt(r.olculen_iletken_krimp_yuksekliği, r.hedef_iletken_krimp_yuksekliği)}</td>
      <td>${r.siyirma_boyu ?? "-"} mm</td>
      <td>${r.capak_boyu ?? "-"} mm</td>
      <td>${r.olculen_cekme_kuvveti_n ?? "-"} N (Hedef: ${r.hedef_cekme_kuvveti_n ?? "-"})</td>
      <td class="${r.radus_mevcut ? 'ok' : 'low'}">${r.radus_mevcut ? "✔" : "✘"}</td>
      <td class="${r.tel_kesme_mevcut ? 'ok' : 'low'}">${r.tel_kesme_mevcut ? "✔" : "✘"}</td>
      <td>${r.operator || "-"}</td>
    </tr>
  `).join("");

  const html = `
  <!DOCTYPE html>
  <html lang="tr">
  <head>
    <meta charset="UTF-8">
    <title>Krimp Protokol Belgesi - ${doc.name}</title>
    <style>
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
    </style>
  </head>
  <body>
    <div class="header">
      <div class="header-left">
        <h1>KTA Endüstri Sistemleri</h1>
        <h2>Krimp Ölçüm Protokol Belgesi</h2>
      </div>
      <div class="header-right">
        <b>${doc.name}</b>
        İş Emri: ${doc.custom_work_order || "-"}<br>
        Ürün: ${doc.urun_kodu || "-"}<br>
        Kalite Belgesi: ${doc.quality_inspection || "-"}<br>
        Tarih: ${today}
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>{{ __('Kablo No') }}</th>
          <th>{{ __('Kontak No') }}</th>
          <th>{{ __('Kesit') }}</th>
          <th>{{ __('Makine') }}</th>
          <th>{{ __('Kalıp') }}</th>
          <th>{{ __('Hdf. Kablo Boyu') }}</th>
          <th>{{ __('Ölc. Kablo Boyu') }}</th>
          <th>{{ __('Sapma') }}</th>
          <th>{{ __('Hdf. Krimp Yük.') }}</th>
          <th>{{ __('Ölc. Krimp Yük.') }}</th>
          <th>{{ __('Sapma') }}</th>
          <th>{{ __('Sıyırma') }}</th>
          <th>{{ __('Çapak') }}</th>
          <th>{{ __('Çekme') }}</th>
          <th>{{ __('Radüs') }}</th>
          <th>{{ __('Tel Kesme') }}</th>
          <th>{{ __('Operatör') }}</th>
        </tr>
      </thead>
      <tbody>${rows_html}</tbody>
    </table>

    <div class="signatures">
      <div class="sig-box">
        <div class="title">{{ __("Hazırlayan Operatör") }}</div>
        <div class="space"></div>
        <div class="name-line" style="border-bottom:none; font-weight:bold; font-size:10px; height:auto;">
          ${doc.operator_name || doc.operator || "-"}
        </div>
        <div class="name-line"></div>
        <div style="margin-top:4px;font-size:9px;color:#555;">İmza / Tarih</div>
      </div>
      <div class="sig-box">
        <div class="title">{{ __("Kalite Sorumlusu") }}</div>
        <div class="space"></div>
        <div class="name-line" style="border-bottom:none; font-weight:bold; font-size:10px; height:auto;">
          ${doc.qi_details?.owner_name || "-"}
        </div>
        <div class="name-line"></div>
        <div style="margin-top:4px;font-size:9px;color:#555;">İmza / Tarih</div>
      </div>
      <div class="sig-box">
        <div class="title">{{ __("Onaylayan") }}</div>
        <div class="space"></div>
        <div class="name-line"></div>
        <div style="margin-top:4px;font-size:9px;color:#555;">{{ __("Ad Soyad / İmza / Tarih") }}</div>
      </div>
    </div>

    <div class="footer">
      Bu belge KTA Endüstri Sistemleri kalite takip sistemi tarafından otomatik oluşturulmuştur. • ${today}
    </div>

    <script>
      window.onload = () => window.print();
    <\/script>
  </body>
  </html>
  `;

  const w = window.open("", "_blank", "width=1100,height=700");
  if (w) {
    w.document.write(html);
    w.document.close();
  }
}

function setupEnjeksiyonToleransLogic(dialog: any) {
  const hammadde_fld = dialog.get_field("hammadde_no");
  dialog.enjeksiyon_tolerans = {}; // store fetched limits

  const updateDetails = () => {
    const hammadde = dialog.get_value("hammadde_no");
    if (hammadde) {
      frappe.call({
        method: "erpnextkta.kta_calisma_karti.api.get_enjeksiyon_tolerans",
        args: { hammadde_no: hammadde },
        callback: (r: any) => {
          if (r.message && Object.keys(r.message).length > 0) {
            dialog.enjeksiyon_tolerans = r.message;
            const t = r.message;
            
            // Set descriptions to show targets
            const desc = (val: number, tol?: number) => val ? `İstenen: ${val} ${tol ? `±${tol}` : ''}` : '';
            const descRange = (min: number, max: number) => min || max ? `İstenen: ${min} - ${max}` : '';
            const descMin = (min: number) => min ? `Minimum: ${min}` : '';

            dialog.set_df_property("hammadde_kazan_isisi", "description", desc(t.hammadde_kazan_isisi_merkez, t.hammadde_kazan_isisi_tolerans));
            dialog.set_df_property("ara_hortum_isisi", "description", desc(t.ara_hortum_isisi_merkez, t.ara_hortum_isisi_tolerans));
            dialog.set_df_property("kafa_meme_isisi", "description", desc(t.kafa_meme_isisi_merkez, t.kafa_meme_isisi_tolerans));
            dialog.set_df_property("soguk_su_isisi", "description", descRange(t.soguk_su_isisi_min, t.soguk_su_isisi_maks));
            dialog.set_df_property("motor_devir", "description", descRange(t.motor_devir_min, t.motor_devir_maks));
            dialog.set_df_property("hammadde_enjeksiyon_zamani", "description", descRange(t.enjeksiyon_zamani_min, t.enjeksiyon_zamani_maks));
            dialog.set_df_property("sogutma_zamani", "description", descRange(t.sogutma_zamani_min, t.sogutma_zamani_maks));
            dialog.set_df_property("cekme_kuvveti_olculen", "description", descMin(t.cekme_kuvveti_min));

            frappe.show_alert({ message: __("Tolerans değerleri yüklendi"), indicator: "blue" });
          } else {
             dialog.enjeksiyon_tolerans = {};
             // clear descriptions
             ["hammadde_kazan_isisi", "ara_hortum_isisi", "kafa_meme_isisi", "soguk_su_isisi", "motor_devir", "hammadde_enjeksiyon_zamani", "sogutma_zamani", "cekme_kuvveti_olculen"].forEach(f => {
               dialog.set_df_property(f, "description", "");
             });
          }
        }
      });
    }
  };

  if (hammadde_fld) {
    hammadde_fld.df.onchange = updateDetails;
  }
}

function addEnjeksiyon() {
  const dialog = frappe.prompt(
    enjeksiyonOlcumFields({ calisma_karti_name: props.doc.name }),
    async (v: any) => {
      const payload = { ...v };
      if (dialog.enjeksiyon_tolerans) {
         Object.keys(dialog.enjeksiyon_tolerans).forEach(k => {
             payload[`hedef_${k}`] = dialog.enjeksiyon_tolerans[k];
         });
      }
      await props.onAddEnjeksiyon(payload);
      frappe.show_alert({ message: __("Enjeksiyon ölçümü eklendi"), indicator: "green" });
    },
    __("Enjeksiyon Ölçümü Ekle"),
    __("Kaydet")
  );
  setupEnjeksiyonToleransLogic(dialog);
}

function editEnjeksiyon(row: any) {
  if (!row?.name) return frappe.msgprint(__("Enjeksiyon satır kimliği bulunamadı."));
  const dialog = frappe.prompt(
    enjeksiyonOlcumFields({ ...row, calisma_karti_name: props.doc.name }),
    async (v: any) => {
      const payloadObj = { ...v };
      if (dialog.enjeksiyon_tolerans) {
         Object.keys(dialog.enjeksiyon_tolerans).forEach(k => {
             payloadObj[`hedef_${k}`] = dialog.enjeksiyon_tolerans[k];
         });
      }
      await props.onUpdateEnjeksiyon({ rowname: row.name, payload: payloadObj });
      frappe.show_alert({ message: __("Enjeksiyon ölçümü güncellendi"), indicator: "green" });
    },
    __("Enjeksiyon Ölçümü Düzenle"),
    __("Kaydet")
  );
  setupEnjeksiyonToleransLogic(dialog);
  if (row.hammadde_no) {
      setTimeout(() => dialog.get_field("hammadde_no").df.onchange(), 100);
  }
}

function deleteEnjeksiyon(row: any) {
  if (!row?.name) return frappe.msgprint(__("Enjeksiyon satır kimliği bulunamadı."));
  frappe.confirm(__("Bu enjeksiyon ölçüm satırı silinecek. Emin misiniz?"), async () => {
    await props.onDeleteEnjeksiyon(row.name);
    frappe.show_alert({ message: __("Enjeksiyon ölçümü silindi"), indicator: "green" });
  });
}

function cloneEnjeksiyon(row: any) {
  const cloneDefaults = {
    ...row,
    calisma_karti_name: props.doc.name,
  };

  const dialog = frappe.prompt(
    enjeksiyonOlcumFields(cloneDefaults),
    async (v: any) => {
      const payload = { ...v };
      if (dialog.enjeksiyon_tolerans) {
         Object.keys(dialog.enjeksiyon_tolerans).forEach(k => {
             payload[`hedef_${k}`] = dialog.enjeksiyon_tolerans[k];
         });
      }
      await props.onAddEnjeksiyon(payload);
      frappe.show_alert({ message: __("Enjeksiyon ölçümü kopyalandı ve eklendi"), indicator: "green" });
    },
    __("Enjeksiyon Ölçümü Kopyala"),
    __("Kaydet")
  );
  setupEnjeksiyonToleransLogic(dialog);
  if (row.hammadde_no) {
      setTimeout(() => dialog.get_field("hammadde_no").df.onchange(), 100);
  }
}

function printEnjeksiyonProtocol() {
  const rows: any[] = props.doc.enjeksiyon_olcumleri || [];
  if (rows.length === 0) return frappe.msgprint(__("Yazdırılacak enjeksiyon ölçümü yok."));

  const doc = props.doc;
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

  const html = `
  <!DOCTYPE html>
  <html lang="tr">
  <head>
    <meta charset="UTF-8">
    <title>Enjeksiyon Protokol Belgesi - ${doc.name}</title>
    <style>
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
    </style>
  </head>
  <body>
    <div class="header">
      <div class="header-left">
        <h1>KTA Endüstri Sistemleri</h1>
        <h2>Enjeksiyon Ölçüm Protokol Belgesi</h2>
      </div>
      <div class="header-right">
        <b>${doc.name}</b>
        İş Emri: ${doc.custom_work_order || "-"}<br>
        Ürün: ${doc.urun_kodu || "-"}<br>
        Kalite Belgesi: ${doc.quality_inspection || "-"}<br>
        Tarih: ${today}
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>{{ __('Periyot') }}</th>
          <th>{{ __('Hammadde') }}</th>
          <th>{{ __('Kazan Isısı') }}</th>
          <th>{{ __('Hortum Isısı') }}</th>
          <th>{{ __('Meme Isısı') }}</th>
          <th>{{ __('Soğuk Su') }}</th>
          <th>{{ __('Devir') }}</th>
          <th>{{ __('Enj. Zamanı') }}</th>
          <th>{{ __('Soğ. Zamanı') }}</th>
          <th>{{ __('Çekme (N)') }}</th>
          <th>{{ __('Göz Knt.') }}</th>
          <th>{{ __('Operatör') }}</th>
        </tr>
      </thead>
      <tbody>${rows_html}</tbody>
    </table>

    <div class="signatures">
      <div class="sig-box">
        <div class="title">{{ __("Hazırlayan Operatör") }}</div>
        <div class="space"></div>
        <div class="name-line" style="border-bottom:none; font-weight:bold; font-size:10px; height:auto;">
          ${doc.operator_name || doc.operator || "-"}
        </div>
        <div class="name-line"></div>
        <div style="margin-top:4px;font-size:9px;color:#555;">İmza / Tarih</div>
      </div>
      <div class="sig-box">
        <div class="title">{{ __("Kalite Sorumlusu") }}</div>
        <div class="space"></div>
        <div class="name-line" style="border-bottom:none; font-weight:bold; font-size:10px; height:auto;">
          ${doc.qi_details?.owner_name || "-"}
        </div>
        <div class="name-line"></div>
        <div style="margin-top:4px;font-size:9px;color:#555;">İmza / Tarih</div>
      </div>
      <div class="sig-box">
        <div class="title">{{ __("Onaylayan") }}</div>
        <div class="space"></div>
        <div class="name-line"></div>
        <div style="margin-top:4px;font-size:9px;color:#555;">{{ __("Ad Soyad / İmza / Tarih") }}</div>
      </div>
    </div>

    <div class="footer">
      Bu belge KTA Endüstri Sistemleri kalite takip sistemi tarafından otomatik oluşturulmuştur. • ${today}
    </div>

    <script>
      window.onload = () => window.print();
    <\/script>
  </body>
  </html>
  `;

  const w = window.open("", "_blank", "width=1100,height=700");
  if (w) {
    w.document.write(html);
    w.document.close();
  }
}

function addBarkod() {
  frappe.prompt(
    barkodKayitFields(),
    async (v: any) => {
      await props.onAddBarkod({ barcode: v.barcode });
      frappe.show_alert({ message: __("Barkod kaydı eklendi"), indicator: "green" });
    },
    "Barkod Kaydı Ekle",
    __("Kaydet")
  );
}

function editBarkod(row: any) {
  if (!row?.name) return frappe.msgprint(__("Barkod satır kimliği (row name) bulunamadı."));
  frappe.prompt(
    barkodKayitFields(row),
    async (v: any) => {
      await props.onUpdateBarkod({ rowname: row.name, barcode: v.barcode });
      frappe.show_alert({ message: __("Barkod kaydı güncellendi"), indicator: "green" });
    },
    "Barkod Kaydı Düzenle",
    __("Kaydet")
  );
}

function deleteBarkod(row: any) {
  if (!row?.name) return frappe.msgprint(__("Barkod satır kimliği (row name) bulunamadı."));
  frappe.confirm(__("Bu barkod satırı silinecek. Emin misiniz?"), async () => {
    await props.onDeleteBarkod(row.name);
    frappe.show_alert({ message: __("Barkod kaydı silindi"), indicator: "green" });
  });
}

onMounted(() => {});
</script>

<template>
  <div class="ck-card ck-kalite-card">
    <QcToggle
      :qcLabel="props.qcLabel"
      :qcOptions="props.qcOptions"
      :qcFormValue="props.qcFormValue"
      :canEditQC="props.canEditQC"
      :qcSaving="props.qcSaving"
      :onSetQC="props.onSetQC"
    />

    <div v-if="props.doc.quality_inspection" :class="['ck-qi-link', qiThemeClass]">
      <div class="ck-mini-content">
        <span class="ck-qi-link__label">{{ __("Kalite Belgesi") }}</span>
        <b class="ck-mini-title">{{ props.doc.quality_inspection }}</b>
      </div>
      <button
        class="ck-btn ck-btn-small"
        @click="openQualityInspection(props.doc.quality_inspection)"
      >
        {{ __("Görüntüle ↗") }}
      </button>
    </div>

    <!-- IdcSection & BarkodSection automatically match since they exist within the flow -->
    <KrimpSection
      v-if="props.doc.has_krimp"
      :doc="props.doc"
      :rows="props.doc.krimp_olcumleri || []"
      :canEditQC="props.canEditQC"
      :canEditData="props.canEditData"
      :onAdd="addKrimp"
      :onEdit="editKrimp"
      :onDelete="deleteKrimp"
      :onClone="cloneKrimp"
      :onPrint="printKrimpProtocol"
    />

    <IdcSection
      v-if="props.doc.has_idc"
      :rows="props.doc.idc_olcumleri || []"
      :canEditQC="props.canEditQC"
      :canEditData="props.canEditData"
      :onAdd="addIdc"
      :onEdit="editIdc"
      :onDelete="deleteIdc"
      :onClone="cloneIdc"
      :onPrint="printIdcProtocol"
    />

    <EnjeksiyonSection
      v-if="props.doc.has_enjeksiyon"
      :doc="props.doc"
      :rows="props.doc.enjeksiyon_olcumleri || []"
      :canEditQC="props.canEditQC"
      :canEditData="props.canEditData"
      :onAdd="addEnjeksiyon"
      :onEdit="editEnjeksiyon"
      :onDelete="deleteEnjeksiyon"
      :onClone="cloneEnjeksiyon"
      :onPrint="printEnjeksiyonProtocol"
    />

    <BarkodSection
      v-if="props.doc.has_barkod"
      :rows="props.doc.barkod_kayitlari || []"
      :canEditQC="props.canEditQC"
      :canEditData="props.canEditData"
      :onAdd="addBarkod"
      :onUpdate="props.onUpdateBarkod"
      :onDelete="props.onDeleteBarkod"
    />

  </div>
</template>

<style scoped>
.ck-kalite-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 14px 10px;
}
.ck-mini-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ck-mini-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--ck-text);
}
.ck-btn-small {
  padding: 8px 12px;
  font-size: 13px;
  border-radius: 8px;
  font-weight: 700;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
  transition: all 0.2s ease;
}

/* Base Link Banner */
.ck-qi-link {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin: 0;
  padding: 14px 16px;
  border-radius: 12px;
  box-shadow: var(--ck-glass-highlight);
  transition: background 0.3s ease, border-color 0.3s ease;
}

.ck-qi-link__label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.9;
}

/* Default (Info/Blue) */
.ck-qi-link.is-default {
  background: var(--ck-info-bg);
  border: 1px solid rgba(59, 130, 246, 0.15);
}
.ck-qi-link.is-default .ck-qi-link__label,
.ck-qi-link.is-default .ck-btn {
  color: var(--info, #3b82f6);
}
.ck-qi-link.is-default .ck-btn {
  background: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.2);
}

/* Accepted (Success/Green) */
.ck-qi-link.is-accepted {
  background: var(--ck-success-bg);
  border: 1px solid rgba(34, 197, 94, 0.15);
}
.ck-qi-link.is-accepted .ck-qi-link__label,
.ck-qi-link.is-accepted .ck-btn {
  color: var(--success, #22c55e);
}
.ck-qi-link.is-accepted .ck-btn {
  background: rgba(34, 197, 94, 0.1);
  border-color: rgba(34, 197, 94, 0.2);
}

/* Rejected (Danger/Red) */
.ck-qi-link.is-rejected {
  background: var(--ck-danger-bg);
  border: 1px solid rgba(239, 68, 68, 0.15);
}
.ck-qi-link.is-rejected .ck-qi-link__label,
.ck-qi-link.is-rejected .ck-btn {
  color: var(--danger, #ef4444);
}
.ck-qi-link.is-rejected .ck-btn {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.2);
}
</style>