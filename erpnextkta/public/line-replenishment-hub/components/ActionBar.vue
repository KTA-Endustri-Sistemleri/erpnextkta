<template>
  <div v-if="items.length > 0" class="action-bar-container">
    <div class="action-bar-card">
      <!-- Left side: Summary -->
      <div class="summary-section">
        <div class="summary-icon">📋</div>
        <div class="summary-text">
          <span class="summary-highlight">
            {{
              __("{0} hammadde seçildi, toplam {1} adet aktarılacak", [
                selectedCount,
                formatNumber(totalQty),
              ])
            }}
          </span>
          <span v-if="unselectedCount > 0" class="summary-subtext">
            ({{
              __(
                "{0} adet seçilmemiş veya temin edilemeyen kalem hariç tutuldu",
                [unselectedCount]
              )
            }})
          </span>
        </div>
      </div>

      <!-- Right side: Action Button -->
      <div class="action-section">
        <button
          type="button"
          class="btn-create-order"
          :disabled="selectedCount === 0 || submitting"
          @click="createOrder"
        >
          <span v-if="submitting" class="spinner">🔄</span>
          <span v-else class="btn-icon">⚡</span>
          <span>{{
            submitting ? __("Oluşturuluyor...") : __("Hat İkmal Emri Oluştur")
          }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { type DeficitItem, isSelectable } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

interface Props {
  items: DeficitItem[];
  targetWarehouse: string;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: "refresh"): void;
  (e: "order-created", orderName: string): void;
}>();

const submitting = ref(false);

const selectedItems = computed(() =>
  props.items.filter((item) => item.selected && isSelectable(item))
);

const selectedCount = computed(() => selectedItems.value.length);

const unselectedCount = computed(
  () => props.items.length - selectedCount.value
);

const totalQty = computed(() =>
  selectedItems.value.reduce(
    (sum, item) => sum + (Number(item.available_stock) || 0),
    0
  )
);

function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return "0";
  return new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 3,
  }).format(num);
}

function createOrder() {
  if (selectedCount.value === 0 || submitting.value) return;

  if (!props.targetWarehouse) {
    if (typeof frappe !== "undefined" && frappe.msgprint) {
      frappe.msgprint({
        title: __("Hedef Depo Seçimi Zorunlu"),
        indicator: "orange",
        message: __("Lütfen önce bir Hedef WIP Deposu seçin."),
      });
    }
    return;
  }

  const payloadItems = selectedItems.value.map((row) => ({
    item_code: row.item_code,
    item_name: row.item_name,
    deficit_qty: row.deficit_qty,
    reserved_qty: row.reserved_qty || 0,
    line_actual_qty: row.line_actual_qty ?? row.line_stock_qty ?? 0,
    suggested_source_warehouse: row.suggested_source_warehouse,
    suggested_batch_no: row.suggested_batch_no || null,
    allocated_batches: row.allocated_batches || [],
    uom: row.uom || "",
  }));

  submitting.value = true;

  if (typeof frappe !== "undefined" && frappe.call) {
    frappe.call({
      method:
        "erpnextkta.kta_stock.line_replenishment_service.create_line_replenishment_order",
      args: {
        target_warehouse: props.targetWarehouse,
        items: payloadItems,
      },
      freeze: true,
      freeze_message: __("Hat İkmal Emri Oluşturuluyor..."),
      callback: (r: any) => {
        submitting.value = false;
        if (r && r.message) {
          const orderName = r.message;
          const escapeHtml =
            (typeof frappe !== "undefined" && frappe.utils?.escape_html) ||
            ((s: string) => s);
          const safeOrder = escapeHtml(orderName);
          const linkHtml = `<a href="/app/kta-line-replenishment-order/${safeOrder}" class="font-bold underline" target="_blank">${safeOrder}</a>`;
          frappe.msgprint({
            title: __("Hat İkmal Emri Oluşturuldu"),
            indicator: "green",
            message: __("Hat İkmal Emri başarıyla oluşturuldu: {0}", [
              linkHtml,
            ]),
          });
          emit("order-created", orderName);
          emit("refresh");
        }
      },
      error: () => {
        submitting.value = false;
      },
    });
  } else {
    submitting.value = false;
  }
}
</script>

<style scoped>
.action-bar-container {
  width: 100%;
  margin-top: 1rem;
}

.action-bar-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem;
  padding: 1.1rem 1.5rem;
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.08);
  flex-wrap: wrap;
}

[data-theme="dark"] .action-bar-card {
  background: var(--ck-glass-bg, #1c2127);
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12));
}

.summary-section {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.summary-icon {
  font-size: 1.6rem;
}

.summary-text {
  display: flex;
  flex-direction: column;
}

.summary-highlight {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-color, #0f172a);
}

.summary-subtext {
  font-size: 0.78rem;
  color: var(--text-muted, #64748b);
  margin-top: 0.15rem;
}

.action-section {
  display: flex;
  align-items: center;
}

.btn-create-order {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1.4rem;
  font-size: 0.92rem;
  font-weight: 700;
  color: #ffffff;
  background: var(--primary, #2563eb);
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(37, 99, 235, 0.3);
}

.btn-create-order:hover:not(:disabled) {
  background: #1d4ed8;
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(37, 99, 235, 0.35);
}

.btn-create-order:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.btn-icon {
  font-size: 1.05rem;
}

.spinner {
  display: inline-block;
  animation: spin 1s infinite linear;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
