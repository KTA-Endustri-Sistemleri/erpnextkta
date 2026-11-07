<script setup lang="ts">
import { computed } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);
const frappe = (window as any).frappe;

const props = defineProps<{
  doc: any;
  canEditQC: boolean;
  onSubmitQC: (rowname: string, item_code: string, intent?: "approve" | "reject") => void;
}>();

const rows = computed(() => {
  return props.doc?.alt_operasyon_kayitlari || [];
});

function getThemeClass(status: string) {
  const val = (status || '').toLowerCase();
  if (val === 'accepted' || val === 'onaylandı') return 'is-accepted';
  if (val === 'rejected' || val === 'reddedildi' || val === 'red') return 'is-rejected';
  if (val === 'partially accepted' || val === 'kısmi kabul edildi') return 'is-partial';
  return 'is-default';
}

function openQualityInspection(name: string) {
  if (name && frappe?.set_route) {
    frappe.set_route("Form", "Quality Inspection", name);
  }
}

async function onKaliteOnayiVer(row: any) {
  props.onSubmitQC(row.name, row.hammadde || "", "approve");
}

async function onKaliteReddet(row: any) {
  props.onSubmitQC(row.name, row.hammadde || "", "reject");
}
</script>

<template>
  <div class="ck-section">
    <div class="ck-section-header">
      <div class="ck-section-title">
        <span class="ck-section-icon">✔️</span>
        {{ __("Alt Operasyon Kalite Onayları") }}
      </div>
    </div>
    <div class="ck-section-body">
      <div v-if="rows.length === 0" class="ck-empty-state">{{ __("Alt operasyon kaydı bulunamadı.") }}</div>
      <div v-else class="ck-mini-list">
        <div v-for="(h, i) in rows" :key="h.name || i" class="ck-mini-item">
          <div class="ck-mini-content">
            <b class="ck-mini-title">{{ __(h.title || h.alt_operasyon_title || h.alt_operasyon) }}</b>
            <div class="ck-muted ck-mini-sub" v-if="h.kalip_no"><b>{{ __("Kalıp No") }}:</b> {{ h.kalip_no }}</div>
            <div class="ck-muted ck-mini-sub" v-if="h.satir_no"><b>{{ __("Satır No") }}:</b> {{ h.satir_no }}</div>
            <div class="ck-muted ck-mini-sub" v-if="h.hammadde"><b>{{ __("Hammadde") }}:</b> {{ h.hammadde }}</div>
          </div>
          <div class="ck-mini-actions">
            <span :class="['ck-badge', getThemeClass(h.quality_inspection_status)]">
              {{ h.quality_inspection_status ? __(h.quality_inspection_status) : __("Onay Bekliyor") }}
            </span>
            <template v-if="props.canEditQC && (!h.quality_inspection_status || h.quality_inspection_status === 'Onay Bekliyor')">
              <button 
                class="ck-btn ck-btn--success ck-btn-small" 
                @click="onKaliteOnayiVer(h)"
              >
                {{ __("Kalite Onayı Ver") }}
              </button>
              <button 
                class="ck-btn ck-btn--danger ck-btn-small" 
                @click="onKaliteReddet(h)"
              >
                {{ __("Reddet") }}
              </button>
            </template>
            <button
              v-if="h.quality_inspection"
              class="ck-btn ck-btn-small ck-btn--secondary"
              style="padding: 6px 10px; font-size: 11px;"
              @click="openQualityInspection(h.quality_inspection)"
            >
              {{ __("Görüntüle ↗") }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ck-section {
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: var(--ck-glass-shadow);
}
.ck-section-header {
  padding: 14px 16px;
  background: rgba(0, 0, 0, 0.02);
  border-bottom: 1px solid var(--ck-glass-border-soft);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ck-section-title {
  font-size: 14px;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 8px;
}
.ck-section-body {
  padding: 10px;
}
.ck-empty-state {
  text-align: center;
  color: var(--ck-text-muted);
  font-size: 13px;
  padding: 10px;
}
.ck-mini-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ck-mini-item {
  background: var(--ck-bg);
  border: 1px solid var(--ck-glass-border-soft);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ck-mini-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ck-mini-title {
  font-size: 15px;
  font-weight: 800;
}
.ck-mini-sub {
  font-size: 12px;
  opacity: 0.8;
}
.ck-mini-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}
.ck-badge {
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}
.ck-badge.is-default { background: var(--ck-info-bg); color: var(--info, #3b82f6); }
.ck-badge.is-accepted { background: var(--ck-success-bg); color: var(--success, #22c55e); }
.ck-badge.is-rejected { background: var(--ck-danger-bg); color: var(--danger, #ef4444); }
.ck-badge.is-partial { background: rgba(124, 58, 237, 0.15); color: #7c3aed; }

.ck-btn-small {
  padding: 8px 14px;
  font-size: 12px;
  border-radius: 8px;
  font-weight: 700;
}
</style>
