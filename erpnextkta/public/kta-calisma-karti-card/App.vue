<script setup>
import { computed, onMounted, ref } from "vue";

/**
 * State machine:
 * - ready   : baslangic_saati yok, bitis_saati yok  -> only Start
 * - running : baslangic_saati var, open stop yok    -> Stop + Finish
 * - paused  : open stop var                         -> Resume + Finish
 * - finished: bitis_saati var                       -> no actions
 */

const loading = ref(false);
const doc = ref(null);
const tab = ref("info"); // info | hurda | durus

const HURDA_PARENT_COST_CENTER = "Malzeme Sarfları - KTA";

const docname = computed(() => {
  const r = frappe.get_route(); // ["kta-calisma-karti-card", "<name>"]
  return r && r.length > 1 ? r[1] : null;
});

// --------------------
// Load / API helpers
// --------------------

async function load() {
  if (!docname.value) return;
  loading.value = true;
  try {
    const r = await frappe.call(
      "erpnextkta.kta_calisma_karti.api.get_calisma_karti_detail",
      { name: docname.value }
    );
    doc.value = r.message || null;
    qcFormValue.value = ((doc.value?.kalite_kontrol || "Onay Bekliyor").trim());
  } finally {
    loading.value = false;
  }
}

async function callIslem(islem_tipi, durus_nedeni=null, aciklama=null, tamamlanan_miktar=null) {
  await frappe.call({
    method: "erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.islem_yap",
    args: { docname: docname.value, islem_tipi, durus_nedeni, aciklama, tamamlanan_miktar },
    freeze: true,
    freeze_message: "İşlem yapılıyor..."
  });
  await load();
}

function backToList() {
  frappe.set_route("kta-calisma-karti-cards");
}

function openForm() {
  frappe.set_route("Form", "Calisma Karti", docname.value);
}

// --------------------
// State / UI logic
// --------------------

function computeState(d) {
  const duruslar = d?.duruslar || [];
  const hasOpenStop = duruslar.some((x) => x?.durus_baslangic && !x?.durus_bitis);

  if (d?.bitis_saati) return "finished";
  if (!d?.baslangic_saati) return "ready";
  if (hasOpenStop) return "paused";
  return "running";
}

const state = computed(() => computeState(doc.value));

const durumLabel = computed(() => ({
  ready: "Hazır",
  running: "Çalışıyor",
  paused: "Duruşta",
  finished: "Bitmiş",
}[state.value] || "-"));

const tamamlanan = computed(() => Number(doc.value?.tamamlanan_miktar || 0));

// Buttons visibility
const showStart  = computed(() => state.value === "ready");
const showResume = computed(() => state.value === "paused");
const showStop   = computed(() => state.value === "running");
const showFinish = computed(() =>
  (state.value === "running" || state.value === "paused") &&
  qcApproved.value
);

const statusClass = computed(() => ({
  ready: "ck-status--ready",
  running: "ck-status--running",
  paused: "ck-status--paused",
  finished: "ck-status--finished",
  rejected: "ck-status--rejected", // ⬅️ SADECE BU EK
}[state.value] || "ck-status--ready"));

// QC onaylı mı?

const qcValue = computed(() => (doc.value?.kalite_kontrol || "Onay Bekliyor").trim());

const qcLabel = computed(() => qcValue.value);

const qcApproved = computed(() => qcValue.value === "Onaylandı");

const qcClass = computed(() => {
  if (qcValue.value === "Onaylandı") return "ck-status--running";   // yeşil
  if (qcValue.value === "Onay Bekliyor") return "ck-status--pending"; // mavi
  if (qcValue.value === "Reddedildi") return "ck-status--rejected";  // 🔴 kırmızı
  return "ck-status--paused";
});

// QC tab permissions (UI-only; backend enforces)
const qcOptions = ["Onay Bekliyor", "Onaylandı", "Reddedildi"];

const canEditQC = computed(() => {
  const roles = (frappe?.boot?.user?.roles || []);
  return roles.includes("System Manager")
    || roles.includes("Quality Manager")
    || roles.includes("KTA Kalite Kullanıcısı");
});

const qcFormValue = ref("Onay Bekliyor");
const qcSaving = ref(false);

async function onUpdateQC() {
  if (!canEditQC.value) {
    frappe.msgprint("QC güncelleme yetkiniz yok.");
    return;
  }

  qcSaving.value = true;
  try {
    await frappe.call("erpnextkta.kta_calisma_karti.api.update_kalite_kontrol", {
      name: docname.value,
      kalite_kontrol: (qcFormValue.value || "").trim(),
    });
    frappe.show_alert({ message: "Kalite durumu güncellendi", indicator: "green" });
    await load();
    tab.value = "kalite";
  } finally {
    qcSaving.value = false;
  }
}


// --------------------
// Actions
// --------------------

function onBaslatDevam() {
  const confirmText =
    state.value === "paused"
      ? "Duruş sonlandırılıp işleme devam edilecek."
      : "İşlem başlatılacak.";

  frappe.confirm(confirmText, async () => callIslem("Baslat"));
}

function onDurus() {
  // Only meaningful when running, but you can keep this as-is.
  frappe.prompt(
    [
      {
        fieldtype: "Select",
        label: "Duruş Nedeni",
        fieldname: "durus_nedeni",
        reqd: 1,
        options: "Ariza\nMalzeme Bekleme\nKalite Kontrol\nMola\nBakim\nDiger",
      },
      { fieldtype: "Small Text", label: "Açıklama", fieldname: "aciklama" },
      { fieldtype: "Float", label: "Tamamlanan Miktar (opsiyonel)", fieldname: "tamamlanan_miktar" },
    ],
    async (v) => callIslem("Durus", v.durus_nedeni, v.aciklama, v.tamamlanan_miktar),
    "Duruş Bilgisi",
    "Duruş Başlat"
  );
}

function onBitir() {
  frappe.prompt(
    [
      {
        fieldtype: "Float",
        label: "Tamamlanan Miktar",
        fieldname: "tamamlanan_miktar",
        reqd: 1,
        default: 0,
        description: "İşlemi bitirmek için tamamlanan miktar 0'dan büyük olmalı."
      }
    ],
    async (v) => {
      frappe.confirm(
        "İşlem bitirilecek. Devam etmek istediğinizden emin misiniz?",
        async () => callIslem("Bitis", null, null, v.tamamlanan_miktar)
      );
    },
    "Bitir",
    "Devam"
  );
}

// --------------------
// Hurda CRUD
// IMPORTANT: hurda_nedeni is treated as Link to Cost Center (filtered by parent)
// --------------------

function hurdaNedeniLinkField(defaultValue = "") {
  return {
    fieldtype: "Link",
    label: "Hurda Nedeni",
    fieldname: "hurda_nedeni",
    options: "Cost Center",
    reqd: 1,
    default: defaultValue,
    // Filter only cost centers under the parent
    get_query: () => ({
      filters: {
        parent_cost_center: HURDA_PARENT_COST_CENTER,
        is_group: 0,
      },
    }),
  };
}

async function onHurdaEkle() {
  frappe.prompt(
    [
      { fieldtype: "Link", label: "Parça Numarası", fieldname: "parca_no", options: "Item", reqd: 1 },
      hurdaNedeniLinkField(""),
      { fieldtype: "Float", label: "Miktar", fieldname: "miktar", reqd: 1 },
      { fieldtype: "Link", label: "Birim", fieldname: "birim", options: "UOM", reqd: 1 },
      { fieldtype: "Link", label: "Depo", fieldname: "depo", options: "Warehouse" },
    ],
    async (v) => {
      await frappe.call("erpnextkta.kta_calisma_karti.api.add_hurda", {
        name: docname.value,
        parca_no: v.parca_no,
        hurda_nedeni: v.hurda_nedeni, // Cost Center name
        miktar: v.miktar,
        birim: v.birim,
        depo: v.depo || null,
      });

      frappe.show_alert({ message: "Hurda eklendi", indicator: "green" });
      await load();
      tab.value = "hurda";
    },
    "Hurda Ekle",
    "Kaydet"
  );
}

async function onHurdaDuzenle(h) {
  if (!h?.name) {
    frappe.msgprint("Hurda satır kimliği (row name) bulunamadı.");
    return;
  }

  frappe.prompt(
    [
      { fieldtype: "Link", label: "Parça Numarası", fieldname: "parca_no", options: "Item", reqd: 1, default: h.parca_no || "" },
      hurdaNedeniLinkField(h.hurda_nedeni || ""),
      { fieldtype: "Float", label: "Miktar", fieldname: "miktar", reqd: 1, default: h.miktar ?? 0 },
      { fieldtype: "Link", label: "Birim", fieldname: "birim", options: "UOM", reqd: 1, default: h.birim || "" },
      { fieldtype: "Link", label: "Depo", fieldname: "depo", options: "Warehouse", default: h.depo || "" },
    ],
    async (v) => {
      await frappe.call("erpnextkta.kta_calisma_karti.api.update_hurda", {
        name: docname.value,
        rowname: h.name,
        parca_no: v.parca_no,
        hurda_nedeni: v.hurda_nedeni,
        miktar: v.miktar,
        birim: v.birim,
        depo: v.depo || null,
      });

      frappe.show_alert({ message: "Hurda güncellendi", indicator: "green" });
      await load();
      tab.value = "hurda";
    },
    "Hurda Düzenle",
    "Kaydet"
  );
}

function onHurdaSil(h) {
  if (!h?.name) {
    frappe.msgprint("Hurda satır kimliği (row name) bulunamadı.");
    return;
  }

  frappe.confirm("Bu hurda satırı silinecek. Emin misiniz?", async () => {
    await frappe.call("erpnextkta.kta_calisma_karti.api.delete_hurda", {
      name: docname.value,
      rowname: h.name,
    });

    frappe.show_alert({ message: "Hurda silindi", indicator: "green" });
    await load();
    tab.value = "hurda";
  });
}

async function setQC(nextValue) {
  if (!canEditQC.value) {
    frappe.msgprint("QC güncelleme yetkiniz yok.");
    return;
  }

  const next = (nextValue || "").trim();
  const prev = (qcFormValue.value || "").trim();
  const current = (qcValue.value || "").trim(); // doc'taki gerçek değer

  // Aynı değerse: hiçbir şey yapma
  if (!next || next === current) {
    qcFormValue.value = current; // UI senkron
    return;
  }

  // UI'ı hemen güncelle (optimistic)
  qcFormValue.value = next;

  qcSaving.value = true;
  try {
    await frappe.call("erpnextkta.kta_calisma_karti.api.update_kalite_kontrol", {
      name: docname.value,
      kalite_kontrol: next,
    });

    frappe.show_alert({ message: "Kalite durumu güncellendi", indicator: "green" });
    await load();
    tab.value = "kalite";
  } catch (e) {
    // Hata olursa geri al
    qcFormValue.value = current || prev || "Onay Bekliyor";
    throw e;
  } finally {
    qcSaving.value = false;
  }
}

onMounted(load);

// Expose what template needs (Vue <script setup> exposes automatically)
// state, durumLabel, showStart/showResume/showStop/showFinish
// actions: onBaslatDevam, onDurus, onBitir, onHurdaEkle, onHurdaDuzenle, onHurdaSil, backToList, openForm
</script>

<template>
  <div class="ck-page">
    <div class="ck-topbar">
      <button class="ck-btn ck-btn--ghost" @click="backToList">← Geri</button>
      <div class="ck-topbar-title">
        <div class="ck-title">Çalışma Kartı</div>
      </div>
      <button class="ck-btn ck-btn--ghost" @click="openForm">Form</button>
    </div>

    <div v-if="loading" class="ck-muted">Yükleniyor...</div>
    <div v-else-if="!doc" class="ck-empty">Kayıt bulunamadı.</div>

    <template v-else>
      <div class="ck-chips">
        <span :class="['ck-status-badge', statusClass]">
          {{ durumLabel }}
        </span>
        <span :class="['ck-chip', qcClass]">QC: {{ qcLabel }}</span>
      </div>
      <div class="ck-actionbar">
        <!-- READY: only Start -->
        <button
          v-if="showStart"
          class="ck-btn ck-btn--primary ck-btn--wide"
          @click="onBaslatDevam"
        >
          Başlat
        </button>

        <!-- PAUSED: Resume + Finish -->
        <button
          v-if="showResume"
          class="ck-btn ck-btn--primary ck-btn--wide"
          @click="onBaslatDevam"
        >
          Devam Et
        </button>

        <!-- RUNNING: Stop + Finish -->
        <button
          v-if="showStop"
          class="ck-btn ck-btn--warning ck-btn--wide"
          @click="onDurus"
        >
          Duruş
        </button>

        <button
          v-if="showFinish"
          :disabled="!qcApproved"
          class="ck-btn ck-btn--danger ck-btn--wide"
          @click="onBitir"
        >
          Bitir
        </button>
      </div>

      <div class="ck-tabs">
        <button :class="['ck-tab', tab==='info' && 'is-active']" @click="tab='info'">Bilgiler</button>
        <button :class="['ck-tab', tab==='hurda' && 'is-active']" @click="tab='hurda'">Hurda</button>
        <button :class="['ck-tab', tab==='durus' && 'is-active']" @click="tab='durus'">Duruş</button>
        <button :class="['ck-tab', tab==='kalite' && 'is-active']" @click="tab='kalite'">Kalite</button>
      </div>

      <div v-if="tab==='info'" class="ck-card">
        <div class="ck-row"><span>İş Emri</span><b>{{ doc.custom_work_order || "-" }}</b></div>
        <div class="ck-row"><span>İş Kartı</span><b>{{ doc.is_karti || "-" }}</b></div>
        <div class="ck-row"><span>Ürün</span><b>{{ doc.urun_kodu || "-" }}</b></div>
        <div class="ck-row"><span>Operasyon</span><b>{{ doc.operasyon || "-" }}</b></div>
        <div class="ck-row"><span>İstasyon</span><b>{{ doc.is_istasyonu || "-" }}</b></div>
        <div class="ck-row"><span>Operatör</span><b>{{ doc.operator || "-" }}</b></div>
      </div>

      <div v-else-if="tab==='hurda'" class="ck-card">
        <div style="display:flex; gap:8px; margin-bottom:10px;">
          <button class="ck-btn ck-btn--primary ck-btn--wide" @click="onHurdaEkle">Hurda Ekle</button>
        </div>
        <div v-if="(doc.hurdalar||[]).length===0" class="ck-muted">Hurda kaydı yok.</div>
        <div v-else class="ck-mini-list">
          <div v-for="(h, i) in doc.hurdalar" :key="h.name || i" class="ck-mini-item">
            <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start;">
              <div style="min-width:0;">
                <b style="display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                  {{ h.parca_no || ('Hurda #' + (i+1)) }}
                </b>
                <div class="ck-muted">{{ h.hurda_nedeni || "-" }}</div>
                <div class="ck-muted">{{ h.miktar ?? "-" }} {{ h.birim || "" }}</div>
                <div v-if="h.depo" class="ck-muted">Depo: {{ h.depo }}</div>
              </div>

              <div style="display:flex; gap:6px; flex-shrink:0;">
                <button class="ck-btn ck-btn--ghost" style="padding:8px 10px;" @click="onHurdaDuzenle(h)">Düzenle</button>
                <button class="ck-btn ck-btn--danger" style="padding:8px 10px;" @click="onHurdaSil(h)">Sil</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="tab==='durus'" class="ck-card">
        <div v-if="(doc.duruslar||[]).length===0" class="ck-muted">Duruş kaydı yok.</div>
        <div v-else class="ck-mini-list">
          <div v-for="(d, i) in doc.duruslar" :key="i" class="ck-mini-item">
            <b>{{ d.durus_nedeni || ('Duruş #' + (i+1)) }}</b>
            <div class="ck-muted">{{ d.durus_baslangic || "-" }} → {{ d.durus_bitis || "Devam ediyor" }}</div>
            <div class="ck-muted">Süre: {{ d.durus_suresi ?? "-" }} dk</div>
            <div v-if="d.aciklama" class="ck-muted">{{ d.aciklama }}</div>
          </div>
        </div>
      </div>

      <div v-else-if="tab==='kalite'" class="ck-card">
        <div class="ck-row" style="justify-content:space-between; align-items:center;">
          <span>Kalite Kontrol</span>
          <b>{{ qcLabel }}</b>
        </div>

        <div v-if="!canEditQC" class="ck-muted" style="margin-top:10px;">
          Bu sekmeyi görüntüleyebilirsiniz ancak güncelleme yetkiniz yok.
        </div>

        <div v-else style="margin-top:10px;">
          <div class="ck-qc-toggle" role="group" aria-label="Kalite durumu">
            <button
              v-for="o in qcOptions"
              :key="o"
              type="button"
              class="ck-qc-toggle__btn"
              :class="[
                qcFormValue === o && 'is-active',
                o === 'Onay Bekliyor' && 'is-pending',
                o === 'Onaylandı' && 'is-ok',
                o === 'Reddedildi' && 'is-reject',
              ]"
              :disabled="qcSaving"
              @click="setQC(o)"
            >
              {{ o }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
<style lang="css" scoped>
  .ck-page{ padding:12px; }
.ck-topbar{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:10px; }
.ck-title{ font-weight:800; font-size:16px; }
.ck-btn{ border:0; border-radius:10px; padding:10px 12px; font-weight:800; }
.ck-btn--wide{ flex:1; }
.ck-btn--primary{ background:#111; color:#fff; }
.ck-btn--warning{ background:#f59e0b; color:#111; }
.ck-btn--danger{ background:#ef4444; color:#fff; }
.ck-btn--ghost{ background:rgba(0,0,0,.06); color:#111; }
.ck-actionbar{ position:sticky; top:0; z-index:5; display:flex; gap:8px; padding:8px 0; background:#fff; }
.ck-muted{ opacity:.75; font-size:12px; }
.ck-empty{ opacity:.8; padding:16px 0; text-align:center; }
.ck-card{ border:1px solid rgba(0,0,0,.08); border-radius:14px; padding:10px 12px; background:#fff; }
.ck-row{ display:flex; justify-content:space-between; gap:12px; padding:6px 0; border-bottom:1px dashed rgba(0,0,0,.06); }
.ck-row:last-child{ border-bottom:0; }
.ck-row span{ opacity:.75; font-size:12px; }
.ck-row b{ font-weight:800; font-size:13px; text-align:right; }
.ck-status{ margin:10px 0; }
.ck-badge{ display:inline-block; padding:6px 10px; border-radius:999px; background:rgba(0,0,0,.06); font-weight:800; font-size:12px; }
.ck-sub{ margin-top:6px; opacity:.8; font-size:12px; }
.ck-tabs{ display:flex; gap:8px; margin:10px 0; }
.ck-tab{ flex:1; border:1px solid rgba(0,0,0,.08); border-radius:12px; padding:10px 8px; font-weight:800; background:#fff; }
.ck-tab.is-active{ background:#111; color:#fff; border-color:#111; }
.ck-mini-list{ display:grid; gap:10px; }
.ck-mini-item{ padding:10px 0; border-bottom:1px dashed rgba(0,0,0,.06); }
.ck-mini-item:last-child{ border-bottom:0; }
.ck-topbar{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  margin-bottom:10px;
}

.ck-topbar-title{
  display:flex;
  flex-direction: column;
  align-items:center;
  gap:8px;
  min-width:0;
}

.ck-title{
  font-weight:700;
  font-size:15px;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}

.ck-status-badge{
  font-size:12px;
  padding:4px 8px;
  border-radius:999px;
  font-weight:600;
  line-height:1;
  white-space:nowrap;
}

/* States */
.ck-status--ready{
  background:#e2e3e5;
  color:#383d41;
}
.ck-status--running{
  background:#d4edda;
  color:#155724;
}
.ck-status--paused{
  background:#fff3cd;
  color:#856404;
}
.ck-status--finished{
  background:#d1ecf1;
  color:#0c5460;
}
.ck-status--rejected{
  background:#f8d7da;
  color:#721c24;
}
.ck-chips{
  display: flex;
  flex-direction: row;
  margin: 6px 0 6px;
  justify-content: space-between;
  align-items: center;
}

.ck-chip{
  font-size:12px;
  padding:6px 10px;
  border-radius:999px;
  font-weight:600;
  line-height:1;
}

/* QC */
.ck-qc--ok{
  background:#d4edda;
  color:#155724;
}
.ck-qc--wait{
  background:#f8d7da;
  color:#721c24;
}


.ck-qc-input{
  width:100%;
  padding:10px 12px;
  border:1px solid rgba(0,0,0,.12);
  border-radius:12px;
  font-size:14px;
  background:#fff;
}

/* QC segmented toggle */
.ck-qc-toggle{
  width:100%;
  display:flex;
  gap:8px;
}

.ck-qc-toggle__btn{
  flex:1;
  min-width:0;                 /* taşmayı azaltır */
  padding:10px 10px;
  border-radius:12px;
  border:1px solid rgba(0,0,0,.14);
  background:#fff;
  font-weight:800;
  font-size:13px;
  line-height:1.1;
  cursor:pointer;
  transition: transform .05s ease, background .15s ease, border-color .15s ease;
  white-space:nowrap;          /* tek satır */
  overflow:hidden;
  text-overflow:ellipsis;      /* sığmazsa ... */
}

.ck-qc-toggle__btn:active{ transform: scale(0.99); }
.ck-qc-toggle__btn:disabled{ opacity:.6; cursor:not-allowed; }

/* inactive text colors */
.ck-qc-toggle__btn.is-pending{ color:#1e3a8a; }
.ck-qc-toggle__btn.is-ok{ color:#155724; }
.ck-qc-toggle__btn.is-reject{ color:#721c24; }

/* active (filled) */
.ck-qc-toggle__btn.is-active.is-pending{
  background:#dbeafe;
  border-color:#3b82f6;
}
.ck-qc-toggle__btn.is-active.is-ok{
  background:#d4edda;
  border-color:#22c55e;
}
.ck-qc-toggle__btn.is-active.is-reject{
  background:#f8d7da;
  border-color:#ef4444;
}

.ck-status--pending{
  background:#dbeafe; /* açık mavi */
  color:#1e3a8a;      /* koyu mavi */
}

/* Responsive: dar ekranda 2+1 (grid) */
@media (max-width: 420px){
  .ck-qc-toggle{
    display:grid;
    grid-template-columns: 1fr 1fr;
    gap:8px;
  }
  .ck-qc-toggle__btn{
    width:100%;
    flex:unset;
  }
  /* 3. buton tam satır kaplasın */
  .ck-qc-toggle__btn:nth-child(3){
    grid-column: 1 / -1;
  }
}
</style>