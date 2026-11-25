<template>
  <div
    :id="`card-row-${item.name}`"
    :class="[
      'item-card',
      { 'picked-card': isPickedBool },
      { 'highlight-scan': highlighted },
      { 'has-over-tolerance': overTolerance },
    ]"
  >
    <div class="item-card-header">
      <div class="item-code-wrapper">
        <span class="item-code-title">{{ item.item_code }}</span>
      </div>
      <label class="pda-check-label">
        <input
          type="checkbox"
          class="pda-picked-check"
          :checked="isPickedBool"
          @change="onToggleCheck"
        />
        <span class="check-text">{{ __("Toplandı") }}</span>
      </label>
    </div>

    <div v-if="item.item_name" class="item-name-desc">{{ item.item_name }}</div>

    <div class="item-card-badges">
      <span class="pda-badge shelf-badge">📍 {{ __("Raf") }}: {{ shelfLocation }}</span>
      <span class="pda-badge batch-badge">🏷️ {{ __("Parti") }}: {{ batchNumber }}</span>
      <span class="pda-badge qty-badge">📦 {{ item.deficit_qty }} {{ item.uom || "" }}</span>
    </div>

    <div class="progress-section">
      <div class="progress-labels">
        <span class="progress-info">
          {{ __("İlerleme") }}: {{ item.picked_qty }} / {{ item.deficit_qty }} {{ item.uom || "" }}
        </span>
        <span class="progress-percent">{{ progressPercent }}%</span>
      </div>
      <div class="progress-track">
        <div
          class="progress-fill"
          :class="{ 'fill-complete': progressPercent >= 100, 'fill-over': overTolerance }"
          :style="{ width: `${Math.min(100, progressPercent)}%` }"
        ></div>
      </div>
    </div>

    <div class="item-card-grid">
      <div class="grid-cell">
        <span class="cell-label">{{ __("İhtiyaç") }}</span>
        <span class="cell-val bold">{{ item.deficit_qty }} {{ item.uom || "" }}</span>
      </div>
      <div class="grid-cell">
        <span class="cell-label">{{ __("Kaynak Depo") }}</span>
        <span class="cell-val small">{{ shelfLocation }}</span>
      </div>
      <div class="grid-cell cell-batch">
        <span class="cell-label">{{ __("Parti (Batch)") }}</span>
        <span class="cell-val small batch-tag">{{ batchNumber }}</span>
      </div>
      <div class="grid-cell cell-tolerance">
        <span class="cell-label">{{ __("Tolerans") }}</span>
        <span class="cell-val small text-muted">{{ __("Maks") }} {{ maxAllowed.toFixed(2) }} (+%15)</span>
      </div>
    </div>

    <div class="item-card-actions">
      <div class="qty-control-wrapper">
        <label class="qty-label">{{ __("Toplanan Miktar") }}:</label>
        <div class="qty-input-group">
          <button type="button" class="btn btn-qty-step btn-step-dec" :title="__('Azalt (-1)')" @click="decrementQty">-</button>
          <input
            type="number"
            step="any"
            class="pda-picked-qty-input"
            :class="{ 'input-over-tolerance': overTolerance }"
            :value="item.picked_qty"
            @input="onInputQty"
          />
          <button type="button" class="btn btn-qty-step btn-step-inc" :title="__('Artır (+1)')" @click="incrementQty">+</button>
        </div>
      </div>

      <button type="button" class="btn-pick-all" :title="__('Tümünü Al')" @click="emit('pick-all')">
        ⚡ {{ __("Tümünü Al") }}
      </button>
    </div>

    <div v-if="overTolerance" class="tolerance-warning">
      ⚠️ {{ __("Tolerans Aşıldı! (+%15 Üzeri)") }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { type PickingItem, calculateMaxAllowed, isOverTolerance } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

interface Props {
  item: PickingItem;
  highlighted?: boolean;
}

const props = withDefaults(defineProps<Props>(), { highlighted: false });

const emit = defineEmits<{
  (e: "update-qty", qty: number): void;
  (e: "toggle-picked", isPicked: boolean): void;
  (e: "pick-all"): void;
}>();

const isPickedBool = computed(() => Boolean(props.item.is_picked));

const shelfLocation = computed(
  () => props.item.picked_source_warehouse || props.item.suggested_source_warehouse || "-",
);

const batchNumber = computed(
  () => props.item.picked_batch_no || props.item.suggested_batch_no || __("Belirtilmedi"),
);

const maxAllowed = computed(() => calculateMaxAllowed(props.item.deficit_qty));
const overTolerance = computed(() => isOverTolerance(props.item.picked_qty, props.item.deficit_qty));

const progressPercent = computed(() => {
  const deficit = Number(props.item.deficit_qty) || 0;
  if (deficit <= 0) return 100;
  const picked = Number(props.item.picked_qty) || 0;
  return Math.round((picked / deficit) * 100);
});

function onInputQty(event: Event) {
  const target = event.target as HTMLInputElement | null;
  const val = target ? parseFloat(target.value) || 0 : 0;
  emit("update-qty", Math.max(0, val));
}

function decrementQty() {
  const current = Number(props.item.picked_qty) || 0;
  emit("update-qty", Math.max(0, current - 1));
}

function incrementQty() {
  const current = Number(props.item.picked_qty) || 0;
  emit("update-qty", current + 1);
}

function onToggleCheck(event: Event) {
  const target = event.target as HTMLInputElement | null;
  emit("toggle-picked", target ? target.checked : false);
}
</script>

<style scoped>
.item-card {
  background: var(--card-bg, #ffffff);
  border: 2px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  transition: all 0.25s ease;
  position: relative;
}
.item-card.picked-card { border-color: #22c55e; background-color: #f0fdf4; }
[data-theme="dark"] .item-card.picked-card { background-color: rgba(34, 197, 94, 0.14); border-color: #22c55e; }
.item-card.has-over-tolerance { border-color: #ef4444; }
.item-card.highlight-scan { animation: scanHighlight 1.5s ease-out; }
@keyframes scanHighlight {
  0% { box-shadow: 0 0 0 4px #3b82f6; transform: scale(1.02); }
  100% { box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05); transform: scale(1); }
}
.item-card-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.item-code-wrapper { display: flex; align-items: center; gap: 6px; }
.item-code-title { font-family: monospace; font-size: 1.15rem; font-weight: 700; color: var(--text-color, #0f172a); }
.pda-check-label {
  display: flex; align-items: center; gap: 6px; cursor: pointer; padding: 4px 8px;
  border-radius: 6px; background-color: #f1f5f9; user-select: none; min-height: 36px;
}
[data-theme="dark"] .pda-check-label { background-color: rgba(148, 163, 184, 0.16); }
.pda-picked-check { width: 20px; height: 20px; accent-color: #22c55e; cursor: pointer; }
.check-text { font-size: 0.85rem; font-weight: 600; color: #334155; }
[data-theme="dark"] .check-text { color: var(--text-color, #f8fafc); }
.item-name-desc { font-size: 0.9rem; color: #475569; margin-bottom: 8px; line-height: 1.3; }
[data-theme="dark"] .item-name-desc { color: var(--text-muted, #cbd5e1); }
.item-card-badges { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.pda-badge { display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; }
.shelf-badge { background-color: #0f172a; color: #fef08a; border: 1px solid #334155; font-weight: 700; letter-spacing: 0.02em; }
.batch-badge { background-color: #e0e7ff; color: #3730a3; }
[data-theme="dark"] .batch-badge { background-color: rgba(99, 102, 241, 0.24); color: #c7d2fe; }
.qty-badge { background-color: #f1f5f9; color: #334155; }
[data-theme="dark"] .qty-badge { background-color: rgba(148, 163, 184, 0.18); color: var(--text-color, #f8fafc); }
.progress-section { margin-bottom: 10px; }
.progress-labels { display: flex; justify-content: space-between; font-size: 0.8rem; font-weight: 600; color: #475569; margin-bottom: 4px; }
[data-theme="dark"] .progress-labels { color: var(--text-muted, #cbd5e1); }
.progress-track { width: 100%; height: 8px; background-color: #e2e8f0; border-radius: 4px; overflow: hidden; }
[data-theme="dark"] .progress-track { background-color: rgba(255, 255, 255, 0.14); }
.progress-fill { height: 100%; background-color: #3b82f6; border-radius: 4px; transition: width 0.3s ease; }
.progress-fill.fill-complete { background-color: #22c55e; }
.progress-fill.fill-over { background-color: #ef4444; }
.item-card-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 12px; padding: 8px; background-color: #f8fafc; border-radius: 6px; margin-bottom: 10px; font-size: 0.8rem; }
[data-theme="dark"] .item-card-grid { background-color: rgba(15, 23, 42, 0.55); border: 1px solid var(--border-color, rgba(255, 255, 255, 0.12)); }
.grid-cell { display: flex; flex-direction: column; }
.cell-label { color: #64748b; font-size: 0.72rem; text-transform: uppercase; font-weight: 600; }
[data-theme="dark"] .cell-label { color: var(--text-muted, #94a3b8); }
.cell-val { color: #0f172a; }
[data-theme="dark"] .cell-val { color: var(--text-color, #f8fafc); }
.cell-val.bold { font-weight: 700; }
.cell-val.small { font-size: 0.78rem; }
.batch-tag { font-family: monospace; }
.item-card-actions { display: flex; align-items: flex-end; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.qty-control-wrapper { display: flex; flex-direction: column; gap: 4px; }
.qty-label { font-size: 0.78rem; font-weight: 600; color: #475569; }
[data-theme="dark"] .qty-label { color: var(--text-muted, #cbd5e1); }
.qty-input-group { display: flex; align-items: center; }
.btn-qty-step {
  min-width: 44px; min-height: 44px; display: flex; align-items: center; justify-content: center;
  font-size: 1.3rem; font-weight: 700; background-color: #e2e8f0; border: 1px solid #cbd5e1; color: #0f172a; cursor: pointer; user-select: none;
}
[data-theme="dark"] .btn-qty-step { background-color: rgba(148, 163, 184, 0.2); border-color: var(--border-color, rgba(255, 255, 255, 0.16)); color: var(--text-color, #f8fafc); }
.btn-step-dec { border-radius: 6px 0 0 6px; }
.btn-step-inc { border-radius: 0 6px 6px 0; }
.btn-qty-step:active { background-color: #cbd5e1; }
[data-theme="dark"] .btn-qty-step:active { background-color: rgba(148, 163, 184, 0.35); }
.pda-picked-qty-input {
  width: 76px; min-height: 44px; text-align: center; font-size: 1.1rem; font-weight: 700;
  border-top: 1px solid #cbd5e1; border-bottom: 1px solid #cbd5e1; border-left: none; border-right: none;
  background-color: #ffffff; color: #0f172a;
}
[data-theme="dark"] .pda-picked-qty-input { border-color: var(--border-color, rgba(255, 255, 255, 0.16)); background-color: var(--bg-color, #0f172a); color: var(--text-color, #f8fafc); }
.pda-picked-qty-input:focus { outline: none; }
.input-over-tolerance { color: #dc2626 !important; background-color: #fef2f2 !important; }
[data-theme="dark"] .input-over-tolerance { color: #fca5a5 !important; background-color: rgba(239, 68, 68, 0.2) !important; }
.btn-pick-all {
  min-height: 44px; padding: 8px 14px; display: flex; align-items: center; gap: 4px;
  background-color: #2563eb; color: #ffffff; border: none; border-radius: 6px;
  font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: background-color 0.15s ease;
}
.btn-pick-all:active { background-color: #1d4ed8; }
.tolerance-warning {
  margin-top: 8px; padding: 6px 10px; border-radius: 6px; background-color: #fee2e2;
  border: 1px solid #fca5a5; color: #991b1b; font-size: 0.8rem; font-weight: 700;
}
[data-theme="dark"] .tolerance-warning { background-color: rgba(239, 68, 68, 0.18); border-color: rgba(248, 113, 113, 0.45); color: #fecaca; }
</style>
