<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

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

const docname = computed(() => {
  const r = frappe.get_route(); // ["kta-calisma-karti-card", "<name>"]
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

onMounted(load);
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
.ck-page {
    padding: 12px;
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
    background: #111;
    color: #fff;
}

.ck-btn--warning {
    background: #f59e0b;
    color: #111;
}

.ck-btn--danger {
    background: #ef4444;
    color: #fff;
}

.ck-btn--ghost {
    background: rgba(0, 0, 0, .06);
    color: #111;
}

.ck-actionbar {
    position: sticky;
    top: 0;
    z-index: 5;
    display: flex;
    gap: 8px;
    padding: 8px 0;
    background: #fff;
}

.ck-muted {
    opacity: .75;
    font-size: 12px;
}

.ck-empty {
    opacity: .8;
    padding: 16px 0;
    text-align: center;
}

.ck-card {
    border: 1px solid rgba(0, 0, 0, .08);
    border-radius: 14px;
    padding: 10px 12px;
    background: #fff;
}

.ck-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 6px 0;
    border-bottom: 1px dashed rgba(0, 0, 0, .06);
}

.ck-row:last-child {
    border-bottom: 0;
}

.ck-row span {
    opacity: .75;
    font-size: 12px;
}

.ck-row b {
    font-weight: 800;
    font-size: 13px;
    text-align: right;
}

.ck-tabs {
    display: flex;
    gap: 8px;
    margin: 10px 0;
}

.ck-tab {
    flex: 1;
    border: 1px solid rgba(0, 0, 0, .08);
    border-radius: 12px;
    padding: 10px 8px;
    font-weight: 800;
    background: #fff;
}

.ck-tab.is-active {
    background: #111;
    color: #fff;
    border-color: #111;
}

.ck-mini-list {
    display: grid;
    gap: 10px;
}

.ck-mini-item {
    padding: 10px 0;
    border-bottom: 1px dashed rgba(0, 0, 0, .06);
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

/* States */
.ck-status--ready {
    background: #e2e3e5;
    color: #383d41;
}

.ck-status--running {
    background: #d4edda;
    color: #155724;
}

.ck-status--paused {
    background: #fff3cd;
    color: #856404;
}

.ck-status--finished {
    background: #d1ecf1;
    color: #0c5460;
}

.ck-status--rejected {
    background: #f8d7da;
    color: #721c24;
}

.ck-status--pending {
    background: #dbeafe;
    color: #1e3a8a;
}

/* QC segmented toggle */
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
    border: 1px solid rgba(0, 0, 0, .14);
    background: #fff;
    font-weight: 800;
    font-size: 13px;
    line-height: 1.1;
    cursor: pointer;
    transition: transform .05s ease, background .15s ease, border-color .15s ease;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.ck-qc-toggle__btn:active {
    transform: scale(0.99);
}

.ck-qc-toggle__btn:disabled {
    opacity: .6;
    cursor: not-allowed;
}

.ck-qc-toggle__btn.is-pending {
    color: #1e3a8a;
}

.ck-qc-toggle__btn.is-ok {
    color: #155724;
}

.ck-qc-toggle__btn.is-reject {
    color: #721c24;
}

.ck-qc-toggle__btn.is-active.is-pending {
    background: #dbeafe;
    border-color: #3b82f6;
}

.ck-qc-toggle__btn.is-active.is-ok {
    background: #d4edda;
    border-color: #22c55e;
}

.ck-qc-toggle__btn.is-active.is-reject {
    background: #f8d7da;
    border-color: #ef4444;
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