<template>
  <div class="line-replenishment-hub-app">
    <!-- Top Workspace Header -->
    <WorkspaceHeader
      :target-warehouse="targetWarehouse"
      :loading="loading"
      @update:target-warehouse="onWarehouseChange"
      @refresh="fetchDeficits"
    />

    <!-- Main Content Container -->
    <main class="hub-main-content">
      <!-- Error Alert Banner -->
      <div v-if="error" class="error-banner">
        <div class="error-message">
          <span class="error-icon">⚠️</span>
          <span>{{ error }}</span>
        </div>
        <button
          type="button"
          class="btn-dismiss-error"
          :title="__('Kapat')"
          @click="error = null"
        >
          ✕
        </button>
      </div>

      <!-- Responsive Deficit Table -->
      <DeficitTable
        :items="items"
        :target-warehouse="targetWarehouse"
        :loading="loading"
        @toggle-select="onToggleSelect"
        @toggle-select-all="onToggleSelectAll"
      />

      <!-- Action Bar (directly below table, hidden if 0 items) -->
      <ActionBar
        :items="items"
        :target-warehouse="targetWarehouse"
        @refresh="fetchDeficits"
        @order-created="onOrderCreated"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import WorkspaceHeader from "./components/WorkspaceHeader.vue";
import DeficitTable from "./components/DeficitTable.vue";
import ActionBar from "./components/ActionBar.vue";
import { type DeficitItem, isSelectable } from "./types";

const __ = (...args: any[]) => (window as any).__(...args);

const targetWarehouse = ref<string>("");
const items = ref<DeficitItem[]>([]);
const loading = ref<boolean>(false);
const error = ref<string | null>(null);

function onWarehouseChange(wh: string) {
  targetWarehouse.value = wh;
  fetchDeficits();
}

function onToggleSelect(item: DeficitItem) {
  item.selected = !item.selected;
}

function onToggleSelectAll(selectAll: boolean) {
  items.value.forEach((item) => {
    if (item.selectable) {
      item.selected = selectAll;
    }
  });
}

function onOrderCreated(orderName: string) {
  if (typeof frappe !== "undefined" && frappe.show_alert) {
    frappe.show_alert({
      message: __("İkmal Emri listesi güncellendi: {0}", [orderName]),
      indicator: "green",
    });
  }
}

async function fetchDeficits() {
  if (!targetWarehouse.value) {
    items.value = [];
    return;
  }

  loading.value = true;
  error.value = null;

  if (typeof frappe === "undefined" || !frappe.call) {
    loading.value = false;
    return;
  }

  frappe.call({
    method: "erpnextkta.kta_shopfloor.api.get_line_deficits",
    args: {
      target_warehouse: targetWarehouse.value,
    },
    freeze: false,
    callback: (r: any) => {
      loading.value = false;
      const rawList = r.message || [];
      items.value = rawList.map((row: any) => {
        const drafts = row.in_flight_draft_orders || row.draft_orders || [];
        const availableStock = Number(row.available_stock || 0);
        const hasStock = Boolean(row.has_stock);
        const selectable = isSelectable({
          ...row,
          available_stock: availableStock,
          has_stock: hasStock,
          draft_orders: drafts,
        });

        return {
          item_code: row.item_code,
          item_name: row.item_name || row.item_code,
          uom: row.uom || row.stock_uom || "",
          deficit_qty: Number(row.deficit_qty || 0),
          line_stock_qty: Number(
            row.line_stock_qty ?? row.line_actual_qty ?? 0
          ),
          line_actual_qty: Number(
            row.line_actual_qty ?? row.line_stock_qty ?? 0
          ),
          reserved_qty: Number(row.reserved_qty || 0),
          available_stock: availableStock,
          suggested_source_warehouse: row.suggested_source_warehouse || "",
          suggested_batch_no: row.suggested_batch_no || null,
          has_stock: hasStock,
          in_flight_draft_orders: drafts,
          draft_orders: drafts,
          covered_by_draft: Boolean(row.covered_by_draft),
          draft_covered_qty: Number(row.draft_covered_qty || 0),
          allocated_batches: row.allocated_batches || [],
          selectable: selectable,
          selected: selectable,
        } as DeficitItem;
      });
    },
    error: (err: any) => {
      loading.value = false;
      const msg =
        err?.message ||
        __("Hat rezervasyon açıkları taranırken bir hata oluştu.");
      error.value = msg;
    },
  });
}

onMounted(() => {
  // Check if route_options or window parameter specifies a target warehouse
  if (typeof frappe !== "undefined" && frappe.route_options?.target_warehouse) {
    targetWarehouse.value = String(frappe.route_options.target_warehouse);
    frappe.route_options.target_warehouse = null;
    fetchDeficits();
  }
});
</script>

<style scoped>
.line-replenishment-hub-app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--bg-color, #f8fafc);
  color: var(--text-color, #1e293b);
  font-family: inherit;
}

[data-theme="dark"] .line-replenishment-hub-app {
  background: var(--ck-bg-dark, #0f172a);
  color: #f1f5f9;
}

.hub-main-content {
  padding: 0 1.5rem 2rem 1.5rem;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}

.error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.85rem 1.25rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #991b1b;
  font-size: 0.88rem;
  font-weight: 600;
  margin-bottom: 1.25rem;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.error-icon {
  font-size: 1.1rem;
}

.btn-dismiss-error {
  background: transparent;
  border: none;
  font-size: 1rem;
  color: #991b1b;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  opacity: 0.7;
}

.btn-dismiss-error:hover {
  opacity: 1;
}
</style>
