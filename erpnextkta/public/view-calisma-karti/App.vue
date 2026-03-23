<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import { useCalismaKarti } from "./composables/useCalismaKarti";
import { useCalismaKartiUi } from "./composables/useCalismaKartiUi";
import { durusFields, bitirFields } from "./composables/prompts";

import CkTopbar from "./components/CkTopbar.vue";
import CkChips from "./components/CkChips.vue";
import CkActionbar from "./components/CkActionbar.vue";
import CkTabs, { type TabKey } from "./components/CkTabs.vue";

import InfoView from "./views/InfoView.vue";
import AltOperasyonView from "./views/AltOperasyonView.vue";
import HurdaView from "./views/HurdaView.vue";
import DurusView from "./views/DurusView.vue";
import KaliteView from "./views/KaliteView.vue";
import BakimView from "./views/BakimView.vue";

import QualityInspectionModal from "./components/QualityInspectionModal.vue";

const tab = ref<TabKey>("info");

// ✅ ROUTE'U REACTIVE YAP
const routeRef = ref<string[]>(frappe.get_route() || []);

function syncRoute() {
  if (!alive) return;
  routeRef.value = frappe.get_route() || [];
}

// Keep router listener cleanup safe across Frappe builds
let unsubscribe: any = null;
let alive = true;

const PAGE = "view-calisma-karti";

const docname = computed(() => {
  const r = routeRef.value || [];

  // Only treat route as "doc route" when we're on this page.
  // Prevent breadcrumb/Home routes from being misread as a docname.
  if (r[0] !== PAGE) return null;

  return r.length > 1 ? r[1] : null;
});

const {
  loading, doc, load, checkActiveCardData, callIslem,
  updateQC, addHurda, updateHurda, deleteHurda,
  addIdcOlcumu, updateIdcOlcumu, deleteIdcOlcumu,
  addBarkodKaydi, updateBarkodKaydi, deleteBarkodKaydi,
  addAltOperasyon, updateAltOperasyon, deleteAltOperasyon,
  getQcTemplates, getTemplateDetails, submitStandardQC
} = useCalismaKarti(docname);

// Reactive now timer for timeout warning (updates every minute)
const nowTime = ref(Date.now());
let timerInterval: any = null;

onMounted(() => {
  alive = true;
  syncRoute();
  unsubscribe = frappe.router?.on?.("change", syncRoute);
  
  // Update time every minute to keep warning reactive
  timerInterval = setInterval(() => {
    nowTime.value = Date.now();
  }, 60000);
});

onUnmounted(() => {
  alive = false;
  if (typeof unsubscribe === "function") unsubscribe();
  if (timerInterval) clearInterval(timerInterval);
});

const {
  state,
  durumLabel,
  statusClass,
  qcLabel,
  qcApproved,
  qcClass,
  qcOptions,
  canEditQC,
  qcFormValue,
  showStart,
  showResume,
  showStop,
  showFinish,
} = useCalismaKartiUi(doc);

const showTimeoutWarning = computed(() => {
  // Yalnızca çalışıyor veya duruşta (henüz bitmemiş, başlatılmış) kartlar için
  if (!doc.value?.baslangic_saati || doc.value?.bitis_saati) return false;
  
  // Süre hesaplama (şimdiki zaman - başlangıç zamanı)
  const startMs = frappe.datetime.str_to_obj(doc.value.baslangic_saati).getTime();
  const diffMinutes = (nowTime.value - startMs) / (1000 * 60);
  
  const warnLimit = doc.value.kart_uyari_suresi_dk || 400;
  return diffMinutes > warnLimit;
});

const qcSaving = ref(false);

const showQcModal = ref(false);
const qcTemplates = ref<any[]>([]);
const qcDefaultTemplate = ref("");
const qcItemCode = ref("");
/** "approve" veya "reject" — modal hangi amaçla açıldığını bilir */
const qcIntent = ref<"approve" | "reject">("approve");

function backToList() {
  frappe.set_route("list-calisma-cards");
}

function openForm() {
  if (!docname.value) return;
  frappe.set_route("Form", "Calisma Karti", docname.value);
}

// --------------------
// Actions (same behavior as your original)
// --------------------
async function onBaslatDevam() {
  // Pre-check: does operator have an incomplete active card?
  try {
    const check = await checkActiveCardData();
    if (check.has_incomplete) {
      const missingLabels = (check.missing || []).map((m: string) => {
        if (m === "tamamlanan_miktar") return "Tamamlanan Miktar";
        if (m === "alt_operasyon") return "Alt Operasyon Kaydı";
        return m;
      });
      const msg =
        `<b>${check.card_name}</b> kartınızda eksik veri var:<br>` +
        `<ul>${missingLabels.map((l: string) => `<li>${l}</li>`).join("")}</ul>` +
        `Lütfen önce o kartı tamamlayın.`;

      if (check.mode === "hard") {
        // Hard mode: block and redirect
        frappe.confirm(
          msg + `<br><br>Eski karta gitmek ister misiniz?`,
          () => frappe.set_route("view-calisma-karti", check.card_name),
          () => {} // do nothing on cancel
        );
        return;
      } else {
        // Soft mode: warn but allow continue
        const proceed = await new Promise<boolean>((resolve) => {
          frappe.confirm(
            msg + `<br><br><b>Yine de devam etmek istiyor musunuz?</b>`,
            () => resolve(true),
            () => resolve(false)
          );
        });
        if (!proceed) return;
      }
    }
  } catch (e) {
    console.error("[onBaslatDevam] pre-check failed:", e);
    // If the check fails, allow the action to proceed
  }

  const confirmText =
    state.value === "paused"
      ? "Duruş sonlandırılıp işleme devam edilecek."
      : "İşlem başlatılacak.";
  frappe.confirm(confirmText, async () => callIslem("Baslat"));
}

function onDurus() {
  frappe.prompt(
    durusFields(),
    async (v: any) => callIslem("Durus", v.durus_nedeni, v.aciklama, v.tamamlanan_miktar),
    "Duruş Bilgisi",
    "Duruş Başlat"
  );
}

function onBitir() {
  const isMiktarZorunlu = doc.value?.miktar_zorunlu_mu !== 0; // default true if null/undefined

  if (isMiktarZorunlu) {
    frappe.prompt(
      bitirFields(),
      async (v: any) => {
        frappe.confirm("İşlem bitirilecek. Devam etmek istediğinizden emin misiniz?", async () =>
          callIslem("Bitis", null, null, v.tamamlanan_miktar)
        );
      },
      "Bitir",
      "Devam"
    );
  } else {
    // Miktar zorunlu değilse direkt bitir
    frappe.confirm("Herhangi bir üretim miktarı bildirmeden işlem bitirilecek. Emin misiniz?", async () =>
      callIslem("Bitis", null, null, 0)
    );
  }
}

async function setQC(nextValue: string) {
  if (!canEditQC.value) {
    frappe.msgprint("QC güncelleme yetkiniz yok.");
    return;
  }

  const next = (nextValue || "").trim();
  const current = (qcLabel.value || "").trim();

  // Same value: no-op
  if (!next || next === current) {
    qcFormValue.value = current || "Onay Bekliyor";
    return;
  }

  // "Onaylandı" veya "Reddedildi" → önce template'leri kontrol et
  if (next === "Onaylandı" || next === "Reddedildi") {
    try {
      qcSaving.value = true;
      const res = await getQcTemplates();
      if (res.message && res.message.templates && res.message.templates.length > 0) {
        // Template varsa → modal aç
        qcTemplates.value = res.message.templates;
        qcDefaultTemplate.value = res.message.default_template;
        qcItemCode.value = res.message.item_code;
        qcIntent.value = next === "Reddedildi" ? "reject" : "approve";
        showQcModal.value = true;
        qcFormValue.value = current || "Onay Bekliyor";
        return;
      }
    } catch (e) {
      console.error("QC templates fetch failed", e);
    } finally {
      qcSaving.value = false;
    }

    // Template yoksa: Reddedildi için confirm iste, Onaylandı direkt geç
    if (next === "Reddedildi") {
      const confirmed = await new Promise<boolean>((resolve) => {
        frappe.confirm(
          "Kalite kontrol belgesi olmadan reddetmek istediğinizden emin misiniz?",
          () => resolve(true),
          () => resolve(false)
        );
      });
      if (!confirmed) {
        qcFormValue.value = current || "Onay Bekliyor";
        return;
      }
    }
  }

  // Template bulunamadı veya "Onay Bekliyor" → direkt kaydet
  qcFormValue.value = next;
  qcSaving.value = true;

  try {
    await updateQC(next);
    const indicator = next === "Reddedildi" ? "red" : "green";
    frappe.show_alert({ message: "Kalite durumu güncellendi", indicator });
    tab.value = "kalite";
  } catch (e) {
    qcFormValue.value = (qcLabel.value || "Onay Bekliyor").trim();
    throw e;
  } finally {
    qcSaving.value = false;
  }
}

async function handleStandardQcSubmit(payload: any) {
    try {
        await submitStandardQC({ ...payload, intent: qcIntent.value });
        const ok = qcIntent.value === "approve";
        frappe.show_alert({
            message: ok ? "Kalite belgesi oluşturuldu ve onayandı" : "Kalite belgesi oluşturuldu ve reddedildi",
            indicator: ok ? "green" : "red",
        });
    } catch (e) {
        console.error("Standard QC submission failed", e);
        throw e;
    }
}

watch(
  docname,
  async (next, prev) => {
    if (!next) {
      doc.value = null;
      return;
    }

    try {
      // if (next !== prev) tab.value = "info";
      await load();
    } catch (e) {
      // Navigation (breadcrumb/home) sırasında request abort / route değişimi gibi durumlarda
      // watcher'ın "Unhandled error" vermesini engelle.
      console.error("[watch docname] load failed during navigation:", e);
      doc.value = null;
    }
  },
  { immediate: true }
);

</script>

<template>
  <div class="ck-page">
    <CkTopbar :onBack="backToList" :onOpenForm="openForm" />

    <div v-if="loading" class="ck-muted">Yükleniyor...</div>
    <div v-else-if="!doc" class="ck-empty">Kayıt bulunamadı.</div>

    <template v-else>
      <CkChips
        :durumLabel="durumLabel"
        :statusClass="statusClass"
        :qcLabel="qcLabel"
        :qcClass="qcClass"
      />

      <CkActionbar
        :showStart="showStart"
        :showResume="showResume"
        :showStop="showStop"
        :showFinish="showFinish"
        :qcApproved="qcApproved"
        :onBaslatDevam="onBaslatDevam"
        :onDurus="onDurus"
        :onBitir="onBitir"
      />

      <!-- Timeout Banner Uyarısı -->
      <div v-if="showTimeoutWarning" class="ck-timeout-alert text-center margin-bottom mx-2">
        <b>⚠️ Dikkat:</b> Bu kart <b>{{ doc.kart_uyari_suresi_dk || 400 }} dakikayı</b> aştı! Lütfen işlem bittiyse bitirin.
      </div>

      <CkTabs :modelValue="tab" :onChange="(t) => (tab = t)" />

      <InfoView v-if="tab === 'info'" :doc="doc" />

      <AltOperasyonView
        v-else-if="tab === 'alt_operasyon'"
        :doc="doc"
        :onAdd="addAltOperasyon"
        :onUpdate="updateAltOperasyon"
        :onDelete="deleteAltOperasyon"
      />

      <HurdaView
        v-else-if="tab === 'hurda'"
        :doc="doc"
        :onAdd="addHurda"
        :onUpdate="updateHurda"
        :onDelete="deleteHurda"
      />

      <DurusView v-else-if="tab === 'durus'" :doc="doc" />

      <KaliteView
        v-else-if="tab === 'kalite'"
        :doc="doc"
        :qcLabel="qcLabel"
        :qcOptions="qcOptions"
        :qcFormValue="qcFormValue"
        :canEditQC="canEditQC"
        :qcSaving="qcSaving"
        :onSetQC="setQC"
        :onAddIdc="addIdcOlcumu"
        :onUpdateIdc="updateIdcOlcumu"
        :onDeleteIdc="deleteIdcOlcumu"
        :onAddBarkod="addBarkodKaydi"
        :onUpdateBarkod="updateBarkodKaydi"
        :onDeleteBarkod="deleteBarkodKaydi"
        />

      <BakimView
        v-else-if="tab === 'bakim'"
        :doc="doc"
        />
    </template>

    <QualityInspectionModal
        :show="showQcModal"
        :templates="qcTemplates"
        :defaultTemplate="qcDefaultTemplate"
        :itemCode="qcItemCode"
        :intent="qcIntent"
        :onClose="() => showQcModal = false"
        :onFetchDetails="getTemplateDetails"
        :onSubmit="handleStandardQcSubmit"
    />
  </div>
</template>
<style>
:root {
  /* Surfaces */
  --ck-bg: var(--bg-color, #fff);
  --ck-surface: var(--card-bg, var(--fg-color, #fff));

  /* Text */
  --ck-text: var(--text-color, #111);
  --ck-text-muted: var(--text-muted, rgba(0, 0, 0, .65));

  /* Borders */
  --ck-border: var(--border-color, rgba(0, 0, 0, .12));
  --ck-border-soft: var(--border-color, rgba(0, 0, 0, .08));
  --ck-border-strong: var(--border-color, rgba(0, 0, 0, .16));

  /* Brand */
  --ck-primary: var(--primary, #111);
  --ck-secondary: var(--secondary);
  --ck-primary-contrast: var(--primary-contrast, #fff);

  /* Buttons / misc */
  --ck-ghost-bg: var(--control-bg, rgba(0, 0, 0, .06));
  --ck-focus: var(--primary, #3b82f6);

  /* Semantic colors (Frappe varsa ondan, yoksa fallback) */
  --ck-danger: var(--danger, #ef4444);
  --ck-warning: var(--warning, #f59e0b);
  --ck-success: var(--success, #22c55e);
  --ck-finished-bg: var(--success, #22c55e);
  --ck-info: var(--info, #3b82f6);

  /* Badge backgrounds: Frappe alert bg'lerine yaslan (yoksa fallback) */
  --ck-danger-bg: var(--alert-danger-bg, rgba(239, 68, 68, .14));
  --ck-warning-bg: var(--alert-warning-bg, rgba(245, 158, 11, .16));
  --ck-success-bg: var(--alert-success-bg, rgba(34, 197, 94, .14));
  --ck-info-bg: var(--alert-info-bg, rgba(59, 130, 246, .14));
}

/* =========================
   BASE STYLES
   ========================= */

.ck-page {
  padding: 12px;
  color: var(--ck-text);
}

.ck-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  border-bottom: solid 2px var(--gray-400);
  padding-bottom: 12px;
}

.ck-topbar-title {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.ck-title {
  font-weight: 700;
  font-size: 15px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ck-timeout-alert {
  background-color: var(--alert-danger-bg, rgba(239, 68, 68, .14));
  color: var(--danger, #ef4444);
  border: 1px solid var(--danger, #ef4444);
  border-radius: 8px;
  padding: 10px;
  font-size: 13px;
  margin-top: -4px;
  margin-bottom: 8px;
}

.ck-btn {
  border: 0;
  border-radius: 10px;
  padding: 10px 12px;
  font-weight: 800;
  border: 0.1px solid var(--gray-300);
}

.ck-btn--wide {
  flex: 1;
}

.ck-btn--secondary {
  background: var(--ck-ghost-bg);
  color: var(--ck-primary-contrast);
}

.ck-btn--success {
  background: var(--ck-success);
  color: var(--ck-primary-contrast);
}

.ck-btn--warning {
  background: var(--ck-warning);
  color: var(--ck-warning-contrast);
}

.ck-btn--danger {
  background: var(--ck-danger);
  color: var(--white);
}

.ck-btn--ghost {
  background: var(--ck-ghost-bg);
  color: var(--ck-text);
}

.ck-actionbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  gap: 8px;
  padding-bottom: 11px;
}

.ck-muted {
  opacity: 1;
  color: var(--ck-text-muted);
  font-size: 12px;
}

.ck-empty {
  opacity: 1;
  color: var(--ck-text-muted);
  padding: 16px 0;
  text-align: center;
}

.ck-card {
  border: 1px solid var(--ck-border);
  border-radius: 14px;
  padding: 10px 0px;
  background: var(--ck-surface);
}

.ck-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 6px;
  border-bottom: 1px dashed var(--ck-border-soft);
}

.ck-row:last-child {
  border-bottom: 0;
}

.ck-row span {
  opacity: 1;
  color: var(--ck-text-muted);
  font-size: 12px;
}

.ck-row b {
  font-weight: 800;
  font-size: 13px;
  text-align: right;
  color: var(--ck-text);
}
.ck-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 0;
  border-top: 1px solid var(--ck-border-soft);
}

.ck-tab {
  /* Mobilde 3 sütun düzeni için: %33'ten biraz az yer kapla ve büyüdüğünde satırı doldur */
  flex: 1 1 calc(33.33% - 8px);
  border: 1px solid var(--ck-border);
  border-radius: 12px;
  padding: 12px 8px;
  font-weight: 800;
  background: var(--control-bg, var(--btn-default-bg));
  color: var(--ck-text);
  font-size: 13px;
  transition: all 0.2s ease;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  text-align: center;
}

.ck-tab:active {
  transform: scale(0.95);
}

.ck-tab.is-active {
  background: var(--ck-warning);
  border-color: var(--ck-warning);
  color: #000; /* Siyah metin, sarı/turuncu üzerinde daha iyi okunur */
  box-shadow: 0 0 8px var(--ck-warning); /* Parlama efekti */
}

/* Masaüstü: Tüm butonlar tek satırda */
@media (min-width: 768px) {
  .ck-tab {
    flex: 1;
  }
}


.ck-mini-list {
  display: grid;
  gap: 10px;
}

.ck-mini-item {
  padding: 10px 10px;
  border-bottom: 1px dashed var(--ck-border-soft);
}

.ck-mini-item:last-child {
  border-bottom: 0;
}

.ck-status-badge {
  font-size: 12px;
  padding: 6px 10px;
  font-weight: 600;
  white-space: nowrap;
  border-radius: 6px 0px 0px 6px;
}

.ck-chips {
  display: flex;
  flex-direction: row;
  margin: 8px 0 8px;
  justify-content: space-between;
  align-items: center;
}

.ck-chip {
  font-size: 12px;
  padding: 6px 10px;
  font-weight: 600;
  text-align: end;
  border-radius: 0px 6px 6px 0px;
}

/* =========================
   STATES (theme-friendly)
   ========================= */

.ck-status--ready {
  background: linear-gradient(90deg, var(--blue), transparent);
  color: var(--white-overlay-900);
}

.ck-status--running {
  background: linear-gradient(90deg, var(--green), transparent);
  color: var(--white-overlay-900);
}

.ck-status-qc--running {
  background: linear-gradient(270deg, var(--green), transparent);
  color: var(--white-overlay-900);
}

.ck-status--paused {
  background: linear-gradient(90deg, var(--ck-warning), transparent);
  color: var(--ck-paused-fg);
}

.ck-status--finished {
  background: linear-gradient(90deg, var(--ck-finished-bg), transparent);
  color: var(--white-overlay-900);
}

.ck-status--rejected {
  background: linear-gradient(90deg, var(--ck-danger), transparent);
  color: var(--white-overlay-900);
}

.ck-status-qc--rejected {
  background: linear-gradient(270deg, var(--ck-danger), transparent);
  color: var(--white-overlay-900);
}

.ck-status--pending {
    background: linear-gradient(90deg, var(--blue), transparent);
    color: var(--white-overlay-900);
}

.ck-status-qc--pending {
    background: linear-gradient(270deg, var(--blue), transparent);
    color: var(--white-overlay-900);
}

/* =========================
   QC segmented toggle
   ========================= */

.ck-qc-toggle {
  padding: 0px 6px;
  width: 100%;
  display: flex;
  gap: 8px;
}

.ck-qc-toggle__btn {
  flex: 1;
  min-width: 0;
  padding: 10px 10px;
  border-radius: 12px;
  border: 1px solid var(--ck-border-strong);
  background: var(--ck-surface);
  font-weight: 800;
  font-size: 13px;
  line-height: 1.1;
  cursor: pointer;
  transition: transform 0.05s ease, background 0.15s ease, border-color 0.15s ease;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--ck-text);
}

.ck-qc-toggle__btn:active {
  transform: scale(0.99);
}

.ck-qc-toggle__btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* text colors */
.ck-qc-toggle__btn.is-pending {
  color: var(--ck-pending-fg);
}
.ck-qc-toggle__btn.is-ok {
  color: var(--ck-running-fg);
}
.ck-qc-toggle__btn.is-reject {
  color: var(--ck-rejected-fg);
}

/* active backgrounds + borders */
.ck-qc-toggle__btn.is-active.is-pending {
  background: var(--blue);
  border-color: var(--blue-800);
  color: var(--white);
}

.ck-qc-toggle__btn.is-active.is-ok {
  background: var(--ck-success);
  border-color: var(--green-700);
  color: var(--white);
}

.ck-qc-toggle__btn.is-active.is-reject {
  background: var(--ck-danger);
  border-color: var(--red-900);
  color: var(--white);
}
.ck-qc-header{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  border-bottom-width: 1px;
  border-bottom-style: solid;
  border-bottom-color: var(--fg-hover-color);
  padding: 14px 6px;
  background: var(--btn-default-bg);
}
@media (max-width: 420px) {
  .ck-qc-toggle {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 0px 6px;
  }

  .ck-qc-toggle__btn {
    width: 100%;
    flex: unset;
  }

  .ck-qc-toggle__btn:nth-child(3) {
    grid-column: 1 / -1;
  }
}
</style>
