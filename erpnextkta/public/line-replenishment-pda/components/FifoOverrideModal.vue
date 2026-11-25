<template>
  <Teleport to="body">
    <div v-if="candidate" class="pda-modal-backdrop" @click.self="emit('cancel')">
      <div class="pda-modal-card" role="dialog" aria-modal="true" data-testid="fifo-override-modal">
        <div class="pda-modal-header">
          <span class="pda-modal-badge-warn">⚠️ {{ __("FIFO Sapması Tespit Edildi") }}</span>
          <div class="pda-modal-item-title">
            <strong class="mono">{{ candidate.row.item_code }}</strong>
            <span v-if="candidate.row.item_name" class="item-sub">{{ candidate.row.item_name }}</span>
          </div>
        </div>

        <div class="fifo-compare-grid">
          <div class="fifo-box fifo-suggested">
            <div class="fifo-box-label">{{ __("Önerilen FIFO") }}</div>
            <div class="fifo-box-batch mono">🏷️ {{ candidate.row.suggested_batch_no || "-" }}</div>
            <div class="fifo-box-meta">📍 {{ candidate.row.suggested_source_warehouse || "-" }}</div>
            <div class="fifo-box-qty">{{ candidate.row.deficit_qty }} {{ candidate.row.uom || "" }}</div>
          </div>
          <div class="fifo-box fifo-scanned">
            <div class="fifo-box-label">{{ __("Okutulan Koli") }}</div>
            <div class="fifo-box-batch mono">🏷️ {{ candidate.resolved.batch_no || "-" }}</div>
            <div class="fifo-box-meta">📍 {{ candidate.resolved.warehouse || "-" }}</div>
            <div class="fifo-box-qty">{{ scannedQty }} {{ candidate.row.uom || "" }}</div>
          </div>
        </div>

        <p class="pda-modal-audit-note">
          {{ __("Bu değişim Stock Entry notlarına otomatik kaydedilecektir.") }}
        </p>

        <div class="pda-modal-actions">
          <button type="button" class="btn-modal-cancel" data-testid="fifo-override-cancel-btn" @click="emit('cancel')">
            {{ __("İptal") }}
          </button>
          <button type="button" class="btn-modal-confirm-warn" data-testid="fifo-override-confirm-btn" @click="emit('confirm')">
            {{ __("Yine de Kullan (FIFO Sapması)") }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from "vue";
import type { FifoOverrideCandidate } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{ candidate: FifoOverrideCandidate | null }>();
const emit = defineEmits<{ (e: "confirm"): void; (e: "cancel"): void }>();

const scannedQty = computed(() => {
  if (!props.candidate) return 0;
  const q = Number(props.candidate.resolved.qty || 0);
  return q > 0 ? q : props.candidate.row.deficit_qty;
});

function onKeydown(e: KeyboardEvent) {
  if (props.candidate && e.key === "Escape") {
    e.preventDefault();
    emit("cancel");
  }
}

onMounted(() => window.addEventListener("keydown", onKeydown));
onUnmounted(() => window.removeEventListener("keydown", onKeydown));
</script>

<style scoped>
.pda-modal-backdrop {
  position: fixed; inset: 0; z-index: 1070; background: rgba(15, 23, 42, 0.68);
  display: flex; align-items: center; justify-content: center; padding: 12px;
}
.pda-modal-card {
  max-width: 460px; width: calc(100% - 24px); background: var(--card-bg, #ffffff);
  color: var(--text-color, #0f172a); border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 14px; padding: 16px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35);
  display: flex; flex-direction: column; gap: 12px;
}
.pda-modal-header { display: flex; flex-direction: column; gap: 6px; }
.pda-modal-badge-warn {
  display: inline-flex; align-self: flex-start; padding: 4px 10px; border-radius: 999px;
  font-size: 0.78rem; font-weight: 800; background: rgba(245, 158, 11, 0.18); color: #b45309;
}
[data-theme="dark"] .pda-modal-badge-warn { background: rgba(245, 158, 11, 0.24); color: #fcd34d; }
.pda-modal-item-title { display: flex; flex-direction: column; gap: 2px; }
.mono { font-family: monospace; }
.item-sub { font-size: 0.85rem; color: var(--text-muted, #64748b); }
.fifo-compare-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.fifo-box {
  padding: 10px; border-radius: 10px; border: 1px solid var(--border-color, #e2e8f0);
  background: var(--pda-surface-alt, #f1f5f9); display: flex; flex-direction: column; gap: 4px;
}
.fifo-scanned { border-color: rgba(245, 158, 11, 0.55); background: rgba(245, 158, 11, 0.08); }
.fifo-box-label { font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted, #64748b); }
.fifo-box-batch { font-size: 0.86rem; font-weight: 800; word-break: break-word; }
.fifo-box-meta { font-size: 0.78rem; color: var(--text-muted, #64748b); word-break: break-word; }
.fifo-box-qty { font-size: 0.9rem; font-weight: 800; margin-top: 2px; }
.pda-modal-audit-note {
  margin: 0; padding: 8px 10px; border-radius: 8px; background: var(--pda-surface-alt, #f1f5f9);
  border: 1px solid var(--border-color, #e2e8f0); font-size: 0.82rem; color: var(--text-muted, #475569);
}
.pda-modal-actions { display: flex; gap: 8px; }
.btn-modal-cancel {
  min-height: 44px; padding: 8px 14px; border-radius: 10px; border: 1px solid var(--border-color, #cbd5e1);
  background: var(--pda-surface-alt, #f1f5f9); color: var(--text-color, #0f172a); font-weight: 700; cursor: pointer;
}
.btn-modal-confirm-warn {
  flex: 1; min-height: 44px; padding: 8px 14px; border: none; border-radius: 10px;
  background: #d97706; color: #ffffff; font-size: 0.92rem; font-weight: 800; cursor: pointer;
}
.btn-modal-confirm-warn:active { background: #b45309; }
</style>
