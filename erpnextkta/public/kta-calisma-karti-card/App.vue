<script setup>
import { computed, onMounted, ref } from "vue";

const loading = ref(false);
const doc = ref(null);
const tab = ref("info"); // info | hurda | durus

const docname = computed(() => {
  const r = frappe.get_route(); // ["kta-calisma-karti-card", "<name>"]
  return r && r.length > 1 ? r[1] : null;
});

function getDurumFromDoc(d) {
  const duruslar = d?.duruslar || [];
  const aktifDurusVarMi = duruslar.some((x) => x?.durus_baslangic && !x?.durus_bitis);
  if (d?.bitis_saati) return "bitmis";
  if (!d?.baslangic_saati) return "hazir";
  if (aktifDurusVarMi) return "durusta";
  return "calisiyor";
}

const durum = computed(() => getDurumFromDoc(doc.value));
const durumLabel = computed(() => ({
  hazir: "Hazır",
  calisiyor: "Çalışıyor",
  durusta: "Duruşta",
  bitmis: "Bitmiş",
}[durum.value] || "-"));

async function load() {
  if (!docname.value) return;
  loading.value = true;
  try {
    const r = await frappe.call("erpnextkta.kta_calisma_karti.api.get_calisma_karti_detail", { name: docname.value });
    doc.value = r.message || null;
  } finally {
    loading.value = false;
  }
}

async function callIslem(islem_tipi, durus_nedeni = null, aciklama = null) {
  await frappe.call({
    method: "erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.islem_yap",
    args: { docname: docname.value, islem_tipi, durus_nedeni, aciklama },
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

function onBaslatDevam() {
  const confirmText = (durum.value === "durusta")
    ? "Duruş sonlandırılıp işleme devam edilecek."
    : "İşlem başlatılacak.";
  frappe.confirm(confirmText, async () => callIslem("Baslat"));
}

function onDurus() {
  frappe.prompt(
    [
      { fieldtype: "Select", label: "Duruş Nedeni", fieldname: "durus_nedeni", reqd: 1,
        options: "Ariza\nMalzeme Bekleme\nKalite Kontrol\nMola\nBakim\nDiger" },
      { fieldtype: "Small Text", label: "Açıklama", fieldname: "aciklama" }
    ],
    async (v) => callIslem("Durus", v.durus_nedeni, v.aciklama),
    "Duruş Bilgisi",
    "Duruş Başlat"
  );
}

function onBitir() {
  frappe.confirm("İşlem bitirilecek. Devam etmek istediğinizden emin misiniz?", async () => callIslem("Bitis"));
}

onMounted(load);
</script>

<template>
  <div class="ck-page">
    <div class="ck-topbar">
      <button class="ck-btn ck-btn--ghost" @click="backToList">← Geri</button>
      <div class="ck-title">Çalışma Kartı</div>
      <button class="ck-btn ck-btn--ghost" @click="openForm">Form</button>
    </div>

    <div v-if="loading" class="ck-muted">Yükleniyor...</div>
    <div v-else-if="!doc" class="ck-empty">Kayıt bulunamadı.</div>

    <template v-else>
      <div class="ck-actionbar">
        <button v-if="durum !== 'bitmis'" class="ck-btn ck-btn--primary ck-btn--wide" @click="onBaslatDevam">
          {{ durum === "durusta" ? "Devam Et" : "Başlat" }}
        </button>
        <button v-if="durum === 'calisiyor'" class="ck-btn ck-btn--warning ck-btn--wide" @click="onDurus">Duruş</button>
        <button v-if="durum !== 'bitmis' && durum !== 'hazir'" class="ck-btn ck-btn--danger ck-btn--wide" @click="onBitir">Bitir</button>
      </div>

      <div class="ck-status">
        <div class="ck-badge">{{ durumLabel }}</div>
        <div class="ck-sub">{{ doc.name }}</div>
      </div>

      <div class="ck-tabs">
        <button :class="['ck-tab', tab==='info' && 'is-active']" @click="tab='info'">Bilgiler</button>
        <button :class="['ck-tab', tab==='hurda' && 'is-active']" @click="tab='hurda'">Hurda</button>
        <button :class="['ck-tab', tab==='durus' && 'is-active']" @click="tab='durus'">Duruş</button>
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
        <div v-if="(doc.hurdalar||[]).length===0" class="ck-muted">Hurda kaydı yok.</div>
        <div v-else class="ck-mini-list">
          <div v-for="(h, i) in doc.hurdalar" :key="i" class="ck-mini-item">
            <b>{{ h.parca_no || ('Hurda #' + (i+1)) }}</b>
            <div class="ck-muted">{{ h.hurda_nedeni || "-" }}</div>
            <div class="ck-muted">{{ h.miktar ?? "-" }} {{ h.birim || "" }}</div>
          </div>
        </div>
      </div>

      <div v-else class="ck-card">
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
    </template>
  </div>
</template>
