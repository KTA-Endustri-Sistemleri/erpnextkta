<template>
  <Teleport to="body">
    <div v-if="item" class="pda-modal-backdrop" @click.self="emit('cancel')">
      <div class="pda-modal-card" role="dialog" aria-modal="true" data-testid="skip-item-modal">
        <div class="pda-modal-header">
          <span class="pda-modal-badge-skip">⊘ {{ __("Eksik Kalem Atlama Onayı") }}</span>
          <div class="pda-modal-item-title">
            <strong class="mono">{{ item.item_code }}</strong>
            <span v-if="item.item_name" class="item-sub">{{ item.item_name }}</span>
          </div>
        </div>

        <div class="skip-item-meta">
          <div>📍 {{ item.suggested_source_warehouse || "-" }}</div>
          <div v-if="item.suggested_batch_no" class="mono">🏷️ {{ item.suggested_batch_no }}</div>
          <div>📦 {{ item.deficit_qty }} {{ item.uom || "" }}</div>
        </div>

        <p class="pda-modal-warning-text">
          {{ __("Bu kalem mevcut transferden hariç tutulacak ve bir sonraki ikmal taramasında otomatik olarak yeniden listelenecektir.") }}
        </p>

        <div class="pda-modal-actions">
          <button type="button" class="btn-modal-cancel" data-testid="skip-item-cancel-btn" @click="emit('cancel')">
            {{ __("İptal") }}
          </button>
          <button type="button" class="btn-modal-confirm-skip" data-testid="skip-item-confirm-btn" @click="emit('confirm')">
            {{ __("Kalemi Atla") }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import type { PickingItem } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{ item: PickingItem | null }>();
const emit = defineEmits<{ (e: "confirm"): void; (e: "cancel"): void }>();

function onKeydown(e: KeyboardEvent) {
  if (props.item && e.key === "Escape") {
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
.pda-modal-badge-skip {
  display: inline-flex; align-self: flex-start; padding: 4px 10px; border-radius: 999px;
  font-size: 0.78rem; font-weight: 800; background: rgba(220, 38, 38, 0.14); color: var(--pda-danger, #dc2626);
}
.pda-modal-item-title { display: flex; flex-direction: column; gap: 2px; }
.mono { font-family: monospace; }
.item-sub { font-size: 0.85rem; color: var(--text-muted, #64748b); }
.skip-item-meta {
  display: flex; flex-wrap: wrap; gap: 8px 14px; padding: 10px; border-radius: 10px;
  background: var(--pda-surface-alt, #f1f5f9); border: 1px solid var(--border-color, #e2e8f0);
  font-size: 0.84rem; font-weight: 700;
}
.pda-modal-warning-text { margin: 0; font-size: 0.86rem; line-height: 1.45; color: var(--text-muted, #475569); }
.pda-modal-actions { display: flex; gap: 8px; }
.btn-modal-cancel {
  min-height: 44px; padding: 8px 14px; border-radius: 10px; border: 1px solid var(--border-color, #cbd5e1);
  background: var(--pda-surface-alt, #f1f5f9); color: var(--text-color, #0f172a); font-weight: 700; cursor: pointer;
}
.btn-modal-confirm-skip {
  flex: 1; min-height: 44px; padding: 8px 14px; border: none; border-radius: 10px;
  background: var(--pda-danger, #dc2626); color: #ffffff; font-size: 0.92rem; font-weight: 800; cursor: pointer;
}
.btn-modal-confirm-skip:active { opacity: 0.9; }
</style>
