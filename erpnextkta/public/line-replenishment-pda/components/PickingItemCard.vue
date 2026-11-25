<template>
  <!-- State C: Picked collapsed 1-line green card -->
  <div
    v-if="isPickedBool && !isSkippedBool"
    :id="`card-row-${item.name}`"
    :data-testid="`picking-card-${item.name}`"
    :class="['collapsed-row', 'picked-row', { 'highlight-scan': highlighted }]"
  >
    <span class="row-icon icon-picked" aria-hidden="true">✓</span>
    <span class="row-shelf">{{ shelfLocation }}</span>
    <span class="row-code mono">{{ item.item_code }}</span>
    <span class="row-qty">{{ item.picked_qty }} {{ item.uom || "" }}</span>
    <span v-if="pickedBatchLabel" class="row-batch mono">{{ pickedBatchLabel }}</span>
    <span v-if="isFifoOverrideBool" data-testid="fifo-override-badge" class="fifo-override-badge">
      ⚠️ {{ __("FIFO Sapması") }}
    </span>
    <button type="button" class="btn-undo" data-testid="card-undo-btn" :title="__('Geri Al')" @click="emit('undo')">
      ↩
    </button>
  </div>

  <!-- State D: Skipped collapsed 1-line muted/amber card -->
  <div
    v-else-if="isSkippedBool"
    :id="`card-row-${item.name}`"
    :data-testid="`picking-card-${item.name}`"
    class="collapsed-row skipped-row"
  >
    <span class="row-icon icon-skipped" aria-hidden="true">⊘</span>
    <span class="row-shelf">{{ shelfLocation }}</span>
    <span class="row-code mono">{{ item.item_code }}</span>
    <span class="skipped-pill">{{ __("Atlandı") }}</span>
    <button v-if="canSkip" type="button" class="btn-undo" data-testid="card-undo-btn" :title="__('Geri Al')" @click="emit('undo')">
      ↩
    </button>
  </div>

  <!-- State A & B: Pending compact walk-order card -->
  <div
    v-else
    :id="`card-row-${item.name}`"
    :data-testid="`picking-card-${item.name}`"
    :class="['pending-card', { 'highlight-scan': highlighted }, { 'has-over-tolerance': !isBatchTracked && overTolerance }]"
  >
    <div class="card-top-row">
      <span class="shelf-badge">📍 {{ shelfLocation }}</span>
      <span class="box-qty-badge">{{ item.deficit_qty }} {{ item.uom || "" }}</span>
    </div>

    <div class="card-mid-row">
      <div class="item-code-title mono">{{ item.item_code }}</div>
      <div v-if="item.item_name" class="item-name-clipped">{{ item.item_name }}</div>
    </div>

    <div v-if="isBatchTracked" class="card-bottom-row">
      <span class="batch-pill mono">🏷️ {{ item.suggested_batch_no || __("Belirtilmedi") }}</span>
      <button v-if="canSkip" type="button" class="btn-skip-subtle" data-testid="card-skip-btn" @click="emit('request-skip')">
        {{ __("Atla") }}
      </button>
    </div>

    <div v-else class="non-batch-row">
      <div class="non-batch-controls">
        <input
          type="number"
          step="any"
          min="0"
          data-testid="non-batch-qty-input"
          class="non-batch-input"
          :class="{ 'input-over-tolerance': overTolerance }"
          :value="item.picked_qty"
          @input="onInputQty"
        />
        <button type="button" class="btn-confirm-non-batch" data-testid="confirm-non-batch-btn" @click="emit('confirm-non-batch')">
          ✓ {{ __("Onayla") }}
        </button>
        <button v-if="canSkip" type="button" class="btn-skip-subtle" data-testid="card-skip-btn" @click="emit('request-skip')">
          {{ __("Atla") }}
        </button>
      </div>
      <div v-if="overTolerance" class="tolerance-warning">⚠️ {{ __("Tolerans Aşıldı! (+%15 Üzeri)") }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { type PickingItem, isOverTolerance } from "../types";
import { isBatchTrackedRow } from "../composables/useLineReplenishmentPicking";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{ item: PickingItem; highlighted?: boolean; canSkip?: boolean }>(),
  { highlighted: false, canSkip: false },
);

const emit = defineEmits<{
  (e: "undo"): void;
  (e: "request-skip"): void;
  (e: "update-qty", qty: number): void;
  (e: "confirm-non-batch"): void;
}>();

const isPickedBool = computed(() => Boolean(props.item.is_picked));
const isSkippedBool = computed(() => Boolean(props.item.is_skipped));
const isFifoOverrideBool = computed(() => Boolean(props.item.is_fifo_override));
const isBatchTracked = computed(() => isBatchTrackedRow(props.item));
const shelfLocation = computed(() => props.item.picked_source_warehouse || props.item.suggested_source_warehouse || "-");
const pickedBatchLabel = computed(() => props.item.picked_batch_no || props.item.suggested_batch_no || "");
const overTolerance = computed(() => isOverTolerance(props.item.picked_qty, props.item.deficit_qty));

function onInputQty(event: Event) {
  const target = event.target as HTMLInputElement | null;
  emit("update-qty", Math.max(0, target ? parseFloat(target.value) || 0 : 0));
}
</script>

<style scoped>
.mono { font-family: monospace; }
.pending-card {
  background: var(--card-bg, #ffffff); border: 1.5px solid var(--border-color, #cbd5e1);
  border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05); transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.pending-card.has-over-tolerance { border-color: var(--pda-danger, #dc2626); }
.highlight-scan { animation: scanHighlight 1.4s ease-out; }
@keyframes scanHighlight {
  0% { box-shadow: 0 0 0 3px var(--pda-primary, #2563eb); }
  100% { box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05); }
}
.card-top-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.shelf-badge {
  display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; border-radius: 6px;
  background-color: #0f172a; color: #fef08a; border: 1px solid #334155;
  font-size: 0.82rem; font-weight: 800; letter-spacing: 0.02em; word-break: break-word;
}
.box-qty-badge {
  display: inline-flex; align-items: center; padding: 4px 9px; border-radius: 6px;
  background: var(--pda-surface-alt, #f1f5f9); color: var(--text-color, #0f172a);
  border: 1px solid var(--border-color, #e2e8f0); font-size: 0.84rem; font-weight: 800; white-space: nowrap;
}
.card-mid-row { display: flex; flex-direction: column; gap: 2px; }
.item-code-title { font-size: 1.05rem; font-weight: 800; color: var(--text-color, #0f172a); word-break: break-word; }
.item-name-clipped {
  font-size: 0.85rem; line-height: 1.3; color: var(--text-muted, #64748b);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.card-bottom-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.batch-pill {
  display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; border-radius: 6px;
  background: #e0e7ff; color: #3730a3; font-size: 0.8rem; font-weight: 700;
}
[data-theme="dark"] .batch-pill { background: rgba(99, 102, 241, 0.24); color: #c7d2fe; }
.btn-skip-subtle {
  min-height: 36px; padding: 4px 12px; border-radius: 6px; border: 1px solid var(--border-color, #cbd5e1);
  background: var(--pda-surface-alt, #f8fafc); color: var(--text-muted, #475569);
  font-size: 0.8rem; font-weight: 700; cursor: pointer; margin-left: auto;
}
.btn-skip-subtle:hover { color: var(--pda-danger, #dc2626); border-color: var(--pda-danger, #dc2626); }
.non-batch-row { display: flex; flex-direction: column; gap: 6px; }
.non-batch-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.non-batch-input {
  width: 90px; min-height: 40px; padding: 4px 8px; border-radius: 6px; border: 1.5px solid var(--border-color, #cbd5e1);
  background: var(--control-bg, #ffffff); color: var(--text-color, #0f172a); font-size: 0.95rem; font-weight: 700; text-align: center;
}
.input-over-tolerance { border-color: var(--pda-danger, #dc2626); color: var(--pda-danger, #dc2626); }
.btn-confirm-non-batch {
  min-height: 40px; padding: 6px 12px; border: none; border-radius: 6px;
  background: var(--pda-primary, #2563eb); color: #ffffff; font-size: 0.85rem; font-weight: 700; cursor: pointer;
}
.tolerance-warning { font-size: 0.78rem; font-weight: 700; color: var(--pda-danger, #dc2626); }
.collapsed-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 10px;
  border-radius: 8px; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); font-size: 0.84rem;
}
.picked-row { border-left: 4px solid var(--pda-success, #16a34a); background: #f0fdf4; }
[data-theme="dark"] .picked-row { background: rgba(34, 197, 94, 0.12); }
.skipped-row { opacity: 0.85; border-left: 4px solid #d97706; background: var(--pda-surface-alt, #f8fafc); }
.row-icon { font-weight: 900; font-size: 0.95rem; }
.icon-picked { color: var(--pda-success, #16a34a); }
.icon-skipped { color: #d97706; }
.row-shelf, .row-code { font-weight: 800; color: var(--text-color, #0f172a); }
.row-qty { font-weight: 700; color: var(--pda-success, #16a34a); }
.row-batch { font-size: 0.78rem; color: var(--text-muted, #64748b); }
.fifo-override-badge, .skipped-pill {
  padding: 2px 7px; border-radius: 999px; background: rgba(245, 158, 11, 0.2);
  color: #b45309; font-size: 0.72rem; font-weight: 800;
}
[data-theme="dark"] .fifo-override-badge, [data-theme="dark"] .skipped-pill { color: #fcd34d; }
.btn-undo {
  margin-left: auto; min-width: 34px; min-height: 34px; border-radius: 6px; border: 1px solid var(--border-color, #cbd5e1);
  background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-size: 0.95rem; font-weight: 700; cursor: pointer;
}
@media (min-width: 768px) {
  .pending-card { padding: 10px; gap: 6px; }
  .non-batch-input, .btn-confirm-non-batch { min-height: 40px; }
}
</style>
