<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import type { MaterialShortageItem, MaterialTransferItem, OtherWarehouseStock } from '../types';

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  show: boolean;
  workOrder: string;
  shortages: MaterialShortageItem[];
  submitting: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'confirm-stage', transfers: MaterialTransferItem[], allowReservedOverride: boolean): void;
}>();

const transferQtys = ref<Record<string, number>>({});
const selectedSources = ref<Record<string, string>>({});
const allowReservedOverride = ref<boolean>(false);

watch(
  () => [props.show, props.shortages],
  () => {
    if (props.show && props.shortages && props.shortages.length > 0) {
      const newQtys: Record<string, number> = {};
      const newSources: Record<string, string> = {};
      for (const s of props.shortages) {
        newQtys[s.item_code] = Number(s.shortage_qty) || 0;
        const matched = (s.available_sources || []).find((src) => src.warehouse === s.source_warehouse);
        newSources[s.item_code] = matched ? matched.warehouse : (s.available_sources?.[0]?.warehouse || '');
      }
      transferQtys.value = newQtys;
      selectedSources.value = newSources;
      allowReservedOverride.value = false;
    }
  },
  { immediate: true }
);

function getActiveSource(item: MaterialShortageItem): OtherWarehouseStock | undefined {
  const srcWh = selectedSources.value[item.item_code];
  return (item.available_sources || []).find((s) => s.warehouse === srcWh);
}

function getSourceFreeQty(src?: OtherWarehouseStock): number {
  if (!src) return 0;
  return Number(src.free_qty ?? src.available_qty ?? 0);
}

function isRowExceedingActual(item: MaterialShortageItem): boolean {
  const src = getActiveSource(item);
  if (!src) return true;
  const qty = Number(transferQtys.value[item.item_code]) || 0;
  return qty <= 0 || qty > Number(src.actual_qty || 0);
}

function isRowUsingReserved(item: MaterialShortageItem): boolean {
  const src = getActiveSource(item);
  if (!src) return false;
  const qty = Number(transferQtys.value[item.item_code]) || 0;
  return qty > getSourceFreeQty(src) && qty <= Number(src.actual_qty || 0);
}

const hasUnfulfillableItems = computed(() => {
  return (props.shortages || []).some((s) => !s.available_sources || s.available_sources.length === 0);
});

const reservedOverageItems = computed(() => {
  return (props.shortages || []).filter((s) => isRowUsingReserved(s));
});

const hasReservedOverrideRequired = computed(() => reservedOverageItems.value.length > 0);

watch(selectedSources, () => {
  allowReservedOverride.value = false;
}, { deep: true });

const canConfirm = computed(() => {
  if (props.submitting) return false;
  if (!props.shortages || props.shortages.length === 0) return false;
  const allValid = props.shortages.every((s) => {
    const src = selectedSources.value[s.item_code];
    const hasSources = s.available_sources && s.available_sources.length > 0;
    return hasSources && Boolean(src) && !isRowExceedingActual(s);
  });
  if (!allValid) return false;
  if (hasReservedOverrideRequired.value && !allowReservedOverride.value) return false;
  return true;
});

function handleClose() {
  if (!props.submitting) emit('close');
}

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.show) handleClose();
}

function handleConfirm() {
  if (!canConfirm.value) return;
  const transfers: MaterialTransferItem[] = props.shortages.map((s) => ({
    item_code: s.item_code,
    qty: Number(transferQtys.value[s.item_code]) || s.shortage_qty,
    source_warehouse: selectedSources.value[s.item_code],
    target_warehouse: s.target_warehouse,
  }));
  emit('confirm-stage', transfers, hasReservedOverrideRequired.value && allowReservedOverride.value);
}

onMounted(() => window.addEventListener('keydown', handleKeyDown));
onUnmounted(() => window.removeEventListener('keydown', handleKeyDown));
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="staging-overlay" @click.self="handleClose">
      <div class="staging-modal" role="dialog" aria-modal="true">
        <div class="staging-header">
          <div class="staging-header-title-group">
            <span class="staging-header-icon">⚠️</span>
            <div>
              <h3 class="staging-title">{{ __('Hatlar Arası Hızlı Transfer') }}</h3>
              <p class="staging-subtitle">{{ __('İş Emri: {0}', [workOrder]) }}</p>
            </div>
          </div>
          <button type="button" class="staging-close-btn" :title="__('Kapat')" :disabled="submitting" @click="handleClose">✕</button>
        </div>

        <div class="staging-body">
          <div v-if="!hasUnfulfillableItems" class="staging-banner banner-info">
            <span class="banner-icon">ℹ️</span>
            <div>{{ __('Üretim hattında teyit için gereken hammadde yetersiz. Diğer üretim hatlarından hatlar arası transfer yaparak teyidi tamamlayabilirsiniz.') }}</div>
          </div>
          <div v-else class="staging-banner banner-warning">
            <span class="banner-icon">⚠️</span>
            <div>{{ __('Bazı malzemeler için diğer üretim hatlarında stok bulunamadı. Hammadde deposundan doğrudan hatlar arası transfer yapılamaz. Lütfen depo biriminden hatlar arası transfer veya ambar ikmali talep ediniz.') }}</div>
          </div>

          <div class="staging-table-wrap">
            <table class="staging-table">
              <thead>
                <tr>
                  <th>{{ __('Malzeme') }}</th>
                  <th>{{ __('Hat Deposu') }}</th>
                  <th class="text-right">{{ __('Eksik Miktar') }}</th>
                  <th class="text-right">{{ __('Transfer Miktarı') }}</th>
                  <th>{{ __('Kaynak Üretim Deposu') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in shortages" :key="item.item_code">
                  <td class="item-cell">
                    <span class="item-code">{{ item.item_code }}</span>
                    <span v-if="item.item_name && item.item_name !== item.item_code" class="item-name">{{ item.item_name }}</span>
                  </td>
                  <td>
                    <div class="target-wh-box">
                      <span class="wh-name">{{ item.target_warehouse }}</span>
                      <span class="wh-stock">{{ __('Mevcut: {0} {1}', [item.line_actual_qty, item.stock_uom]) }}</span>
                    </div>
                  </td>
                  <td class="text-right">
                    <span class="shortage-badge">{{ item.shortage_qty }} {{ item.stock_uom }}</span>
                  </td>
                  <td class="text-right">
                    <input
                      v-model.number="transferQtys[item.item_code]"
                      type="number"
                      step="any"
                      min="0.0001"
                      :max="getActiveSource(item)?.actual_qty"
                      class="qty-input"
                      :disabled="submitting || !item.available_sources || item.available_sources.length === 0"
                    />
                    <div v-if="isRowUsingReserved(item)" class="row-reserved-note">⚠️ {{ __('Rezerve aşımı') }}</div>
                  </td>
                  <td>
                    <div v-if="item.available_sources && item.available_sources.length > 0">
                      <select v-model="selectedSources[item.item_code]" class="source-select" :disabled="submitting">
                        <option v-for="src in item.available_sources" :key="src.warehouse" :value="src.warehouse">
                          {{ src.warehouse }} ({{ __('Serbest Stok') }}: {{ src.free_qty ?? src.available_qty }} / {{ __('Fiziksel') }}: {{ src.actual_qty }} {{ item.stock_uom }})
                        </option>
                      </select>
                    </div>
                    <div v-else>
                      <span class="no-stock-badge">⚠️ {{ __('Üretim depolarında stok yok') }}</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="hasReservedOverrideRequired" class="staging-banner banner-warning override-box">
            <span class="banner-icon">⚠️</span>
            <div class="override-content">
              <div>{{ __('Seçili kaynak hatlarda serbest stok yetersiz; transfer için başka iş emirlerine rezerve edilmiş stoktan öncelik kaydırılacak.') }}</div>
              <label class="override-check-label">
                <input v-model="allowReservedOverride" type="checkbox" class="override-checkbox" :disabled="submitting" />
                <span>{{ __('Kaynak hattın rezerve stoğundan öncelik kaydırarak kullanmayı onaylıyorum') }}</span>
              </label>
            </div>
          </div>
        </div>

        <div class="staging-footer">
          <button type="button" class="staging-btn staging-btn-cancel" :disabled="submitting" @click="handleClose">
            {{ __('Vazgeç') }}
          </button>
          <button type="button" class="staging-btn staging-btn-primary" :disabled="!canConfirm || submitting" @click="handleConfirm">
            <span v-if="submitting" class="staging-spinner" aria-hidden="true" />
            <span>{{ submitting ? __('Aktarılıyor ve Teyit Ediliyor…') : __('⚡ Hatta Aktar ve Teyit Et') }}</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.staging-overlay { position: fixed; inset: 0; z-index: 1060; background: rgba(15, 23, 42, 0.55); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; padding: 1.25rem; box-sizing: border-box; }
.staging-modal { --modal-bg: var(--card-bg, #ffffff); --modal-border: var(--border-color, #e2e8f0); --modal-text: var(--text-color, #0f172a); --modal-muted: var(--text-muted, #64748b); width: 100%; max-width: 860px; max-height: 90vh; background: var(--modal-bg); color: var(--modal-text); border: 1px solid var(--modal-border); border-radius: 0.85rem; box-shadow: 0 20px 45px rgba(15, 23, 42, 0.25); display: flex; flex-direction: column; overflow: hidden; font-family: inherit; }
[data-theme='dark'] .staging-modal { --modal-bg: var(--ck-glass-bg, #1c2127); --modal-border: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); --modal-text: #f8fafc; --modal-muted: #94a3b8; box-shadow: 0 24px 54px rgba(0, 0, 0, 0.6); }
.staging-header { display: flex; align-items: center; justify-content: space-between; padding: 1.15rem 1.4rem; border-bottom: 1px solid var(--modal-border); background: var(--bg-color, #f8fafc); }
[data-theme='dark'] .staging-header { background: rgba(255, 255, 255, 0.03); }
.staging-header-title-group { display: flex; align-items: center; gap: 0.65rem; }
.staging-header-icon { font-size: 1.4rem; line-height: 1; }
.staging-title { margin: 0; font-size: 1.05rem; font-weight: 800; color: var(--modal-text); }
.staging-subtitle { margin: 0.15rem 0 0; font-size: 0.78rem; color: var(--modal-muted); }
.staging-close-btn { background: transparent; border: none; border-radius: 0.4rem; width: 32px; height: 32px; font-size: 1.25rem; line-height: 1; color: var(--modal-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background-color 0.15s, color 0.15s; }
.staging-close-btn:hover:not(:disabled) { background: rgba(148, 163, 184, 0.18); color: var(--modal-text); }
.staging-body { padding: 1.25rem 1.4rem; overflow-y: auto; display: flex; flex-direction: column; gap: 1rem; }
.staging-banner { display: flex; align-items: flex-start; gap: 0.65rem; padding: 0.75rem 1rem; border-radius: 0.55rem; font-size: 0.82rem; font-weight: 600; line-height: 1.4; }
.banner-info { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; }
[data-theme='dark'] .banner-info { background: rgba(59, 130, 246, 0.15); border-color: rgba(96, 165, 250, 0.35); color: #93c5fd; }
.banner-warning { background: #fffbeb; border: 1px solid #fde68a; color: #b45309; }
[data-theme='dark'] .banner-warning { background: rgba(245, 158, 11, 0.15); border-color: rgba(251, 191, 36, 0.35); color: #fcd34d; }
.banner-icon { font-size: 1.05rem; line-height: 1.2; }
.staging-table-wrap { border: 1px solid var(--modal-border); border-radius: 0.55rem; overflow-x: auto; }
.staging-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; text-align: left; }
.staging-table th { padding: 0.65rem 0.85rem; background: var(--bg-color, #f8fafc); border-bottom: 1px solid var(--modal-border); font-weight: 700; color: var(--modal-muted); white-space: nowrap; }
[data-theme='dark'] .staging-table th { background: rgba(255, 255, 255, 0.04); }
.staging-table td { padding: 0.65rem 0.85rem; border-bottom: 1px solid var(--modal-border); vertical-align: middle; }
.staging-table tr:last-child td { border-bottom: none; }
.text-right { text-align: right; }
.item-cell { display: flex; flex-direction: column; gap: 0.15rem; }
.item-code { font-weight: 800; color: var(--modal-text); }
.item-name { font-size: 0.74rem; color: var(--modal-muted); max-width: 220px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.target-wh-box { display: flex; flex-direction: column; gap: 0.15rem; }
.wh-name { font-weight: 700; color: var(--modal-text); }
.wh-stock { font-size: 0.72rem; color: var(--modal-muted); }
.shortage-badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 0.35rem; font-weight: 800; background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; white-space: nowrap; }
[data-theme='dark'] .shortage-badge { background: rgba(239, 68, 68, 0.18); border-color: rgba(248, 113, 113, 0.35); color: #f87171; }
.qty-input { width: 95px; padding: 0.35rem 0.5rem; text-align: right; border-radius: 0.4rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--modal-text); font-weight: 700; font-size: 0.82rem; outline: none; transition: border-color 0.15s, box-shadow 0.15s; }
[data-theme='dark'] .qty-input { background: #14181d; border-color: rgba(255, 255, 255, 0.18); }
.qty-input:focus { border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2); }
.row-reserved-note { margin-top: 0.2rem; font-size: 0.71rem; font-weight: 700; color: #b45309; }
[data-theme='dark'] .row-reserved-note { color: #fcd34d; }
.source-select { width: 100%; min-width: 240px; padding: 0.35rem 0.5rem; border-radius: 0.4rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--modal-text); font-size: 0.8rem; font-weight: 600; outline: none; transition: border-color 0.15s; }
[data-theme='dark'] .source-select { background: #14181d; border-color: rgba(255, 255, 255, 0.18); }
.source-select:focus { border-color: #2563eb; }
.no-stock-badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 0.35rem; font-size: 0.74rem; font-weight: 700; background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; white-space: nowrap; }
[data-theme='dark'] .no-stock-badge { background: rgba(239, 68, 68, 0.18); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.override-content { display: flex; flex-direction: column; gap: 0.5rem; }
.override-check-label { display: inline-flex; align-items: center; gap: 0.5rem; cursor: pointer; font-weight: 700; margin: 0; }
.override-checkbox { width: 16px; height: 16px; accent-color: #d97706; cursor: pointer; }
.staging-footer { display: flex; justify-content: flex-end; gap: 0.75rem; padding: 1rem 1.4rem; border-top: 1px solid var(--modal-border); background: var(--bg-color, #f8fafc); }
[data-theme='dark'] .staging-footer { background: rgba(255, 255, 255, 0.02); }
.staging-btn { display: inline-flex; align-items: center; justify-content: center; gap: 0.45rem; padding: 0.55rem 1.15rem; border-radius: 0.5rem; font-size: 0.84rem; font-weight: 700; cursor: pointer; transition: all 0.15s ease; border: none; }
.staging-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.staging-btn-cancel { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #cbd5e1); color: var(--modal-muted); }
[data-theme='dark'] .staging-btn-cancel { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: var(--modal-muted); }
.staging-btn-cancel:hover:not(:disabled) { background: rgba(148, 163, 184, 0.18); color: var(--modal-text); }
.staging-btn-primary { background: #2563eb; color: #ffffff; }
.staging-btn-primary:hover:not(:disabled) { background: #1d4ed8; box-shadow: 0 3px 10px rgba(37, 99, 235, 0.28); }
.staging-spinner { width: 14px; height: 14px; border: 2px solid rgba(255, 255, 255, 0.35); border-top-color: #ffffff; border-radius: 50%; animation: staging-spin 0.75s linear infinite; }
@keyframes staging-spin { to { transform: rotate(360deg); } }
</style>
