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
import HurdaView from "./views/HurdaView.vue";
import DurusView from "./views/DurusView.vue";
import KaliteView from "./views/KaliteView.vue";

const tab = ref<TabKey>("info");

// ✅ ROUTE'U REACTIVE YAP
const routeRef = ref<string[]>(frappe.get_route() || []);

function syncRoute() {
  routeRef.value = frappe.get_route() || [];
}

// frappe.router.on("change") bazı sürümlerde "off" fonksiyonu döndürür, bazılarında döndürmez.
// O yüzden güvenli kapatma yapıyoruz.
let unsubscribe: any = null;

onMounted(() => {
  // ilk sync
  syncRoute();

  // route değişince sync
  // (Frappe build'ine göre router.on var/yok olabilir, optional chaining kullandık)
  unsubscribe = frappe.router?.on?.("change", syncRoute);

  // İlk yükleme: watcher immediate zaten yapacak, ister burada çağırma.
});

onUnmounted(() => {
  // Eğer unsubscribe bir fonksiyon ise çağır
  if (typeof unsubscribe === "function") unsubscribe();
});

// ✅ docname artık reactive routeRef üstünden computed
const docname = computed(() => {
  const r = routeRef.value; // reactive dependency
  // ["kta-calisma-karti-card", "<name>"]
  return r && r.length > 1 ? r[1] : null;
});

const {
  loading, doc, load, callIslem,
  updateQC, addHurda, updateHurda, deleteHurda,
  addIdcOlcumu, updateIdcOlcumu, deleteIdcOlcumu,
  addBarkodKaydi, updateBarkodKaydi, deleteBarkodKaydi
} = useCalismaKarti(docname);

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

const qcSaving = ref(false);

function backToList() {
  frappe.set_route("kta-calisma-karti-cards");
}

function openForm() {
  if (!docname.value) return;
  frappe.set_route("Form", "Calisma Karti", docname.value);
}

// --------------------
// Actions (same behavior as your original)
// --------------------
function onBaslatDevam() {
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

  qcFormValue.value = next;
  qcSaving.value = true;

  try {
    await updateQC(next);
    frappe.show_alert({ message: "Kalite durumu güncellendi", indicator: "green" });
    tab.value = "kalite";
  } catch (e) {
    // Roll back UI to actual doc value (after load, qcLabel already reflects it)
    qcFormValue.value = (qcLabel.value || "Onay Bekliyor").trim();
    throw e;
  } finally {
    qcSaving.value = false;
  }
}

// ✅ Route (docname) değiştikçe yükle + ilk açılışta da yükle
watch(
  docname,
  async (next, prev) => {
    if (!next) {
      doc.value = null;
      return;
    }
    // Doc değiştiyse tab resetlemek istersen aç:
    // if (next !== prev) tab.value = "info";
    await load();
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

      <CkTabs :modelValue="tab" :onChange="(t) => (tab = t)" />

      <InfoView v-if="tab === 'info'" :doc="doc" />

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
    </template>
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
  --ck-primary-contrast: var(--primary-contrast, #fff);

  /* Buttons / misc */
  --ck-ghost-bg: var(--control-bg, rgba(0, 0, 0, .06));
  --ck-focus: var(--primary, #3b82f6);

  /* Semantic colors (Frappe varsa ondan, yoksa fallback) */
  --ck-danger: var(--danger, #ef4444);
  --ck-warning: var(--warning, #f59e0b);
  --ck-success: var(--success, #22c55e);
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
  background: var(--ck-bg);
  color: var(--ck-text);
}

.ck-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
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

.ck-btn {
  border: 0;
  border-radius: 10px;
  padding: 10px 12px;
  font-weight: 800;
}

.ck-btn--wide {
  flex: 1;
}

.ck-btn--primary {
  background: var(--secondary);
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
  color: var(--ck-danger-contrast);
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
  padding: 8px 0;
  background: var(--ck-bg);
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
  padding: 10px 12px;
  background: var(--ck-surface);
}

.ck-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
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
  gap: 8px;
  margin: 10px 0;
}

.ck-tab {
  flex: 1;
  border: 1px solid var(--ck-border);
  border-radius: 12px;
  padding: 10px 8px;
  font-weight: 800;
  background: var(--ck-surface);
  color: var(--ck-text);
}

.ck-tab.is-active {
  background: var(--ck-primary);
  color: var(--ck-primary-contrast);
  border-color: var(--ck-primary);
}

.ck-mini-list {
  display: grid;
  gap: 10px;
}

.ck-mini-item {
  padding: 10px 0;
  border-bottom: 1px dashed var(--ck-border-soft);
}

.ck-mini-item:last-child {
  border-bottom: 0;
}

.ck-status-badge {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
}

.ck-chips {
  display: flex;
  flex-direction: row;
  margin: 6px 0 6px;
  justify-content: space-between;
  align-items: center;
}

.ck-chip {
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  font-weight: 600;
  line-height: 1;
}

/* =========================
   STATES (theme-friendly)
   ========================= */

.ck-status--ready {
  background: var(--ck-ready-bg);
  color: var(--ck-ready-fg);
}

.ck-status--running {
  background: var(--ck-success-bg);
  color: var(--ck-success-fg);
}

.ck-status--paused {
  background: var(--ck-paused-bg);
  color: var(--ck-paused-fg);
}

.ck-status--finished {
  background: var(--ck-finished-bg);
  color: var(--ck-finished-fg);
}

.ck-status--rejected {
  background: var(--ck-danger-bg);
  color: var(--ck-danger-fg);
}

.ck-status--pending {
  background: var(--ck-info-bg);
  color: var(--ck-info-fg);
}

/* =========================
   QC segmented toggle
   ========================= */

.ck-qc-toggle {
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
  background: var(--ck-info-bg);
  border-color: var(--ck-pending-border);
}

.ck-qc-toggle__btn.is-active.is-ok {
  background: var(--ck-success-bg);
  border-color: var(--ck-ok-border);
}

.ck-qc-toggle__btn.is-active.is-reject {
  background: var(--ck-danger-bg);
  border-color: var(--ck-danger-border);
}

@media (max-width: 420px) {
  .ck-qc-toggle {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
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