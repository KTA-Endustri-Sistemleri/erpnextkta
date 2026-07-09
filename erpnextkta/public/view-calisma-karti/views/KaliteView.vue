<script setup lang="ts">
import { onMounted, computed } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);
const frappe = (window as any).frappe;

import QcToggle from "../components/QcToggle.vue";
import IdcSection from "../components/IdcSection.vue";
import KrimpSection from "../components/KrimpSection.vue";
import EnjeksiyonSection from "../components/EnjeksiyonSection.vue";
import BarkodSection from "../components/BarkodSection.vue";

import { useIdcDialogs } from "../composables/dialogs/useIdcDialogs";
import { useKrimpDialogs } from "../composables/dialogs/useKrimpDialogs";
import { useEnjeksiyonDialogs } from "../composables/dialogs/useEnjeksiyonDialogs";
import { useBarkodDialogs } from "../composables/dialogs/useBarkodDialogs";

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
  onSetSubOpQC: (rowname: string, item_code: string) => void;

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

const { addIdc, editIdc, deleteIdc, cloneIdc, printIdcProtocol } = useIdcDialogs(props);
const { addKrimp, editKrimp, deleteKrimp, cloneKrimp, printKrimpProtocol } = useKrimpDialogs(props);
const { addEnjeksiyon, editEnjeksiyon, deleteEnjeksiyon, cloneEnjeksiyon, printEnjeksiyonProtocol } = useEnjeksiyonDialogs(props);
const { addBarkod, editBarkod, deleteBarkod } = useBarkodDialogs(props);

onMounted(() => {});
</script>

<template>
  <div class="ck-card ck-kalite-card">
    <template v-if="!props.doc.alt_operasyon_bazli_kalite">
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
    </template>

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
      :onSubmitQC="(rowname, item_code) => props.onSetSubOpQC(rowname, item_code)"
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