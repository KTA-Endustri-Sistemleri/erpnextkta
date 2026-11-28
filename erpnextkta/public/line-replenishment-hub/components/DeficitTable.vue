<template>
  <div class="deficit-table-container">
    <!-- Empty State: No warehouse selected -->
    <div v-if="!targetWarehouse" class="empty-state-card">
      <div class="empty-state-icon">🏭</div>
      <h3 class="empty-state-title">{{ __("Hedef WIP Deposu Seçin") }}</h3>
      <p class="empty-state-desc">
        {{
          __(
            "Lütfen hammadde rezervasyon açıklarını görüntülemek için yukarıdaki hızlı butonlardan veya diğer ambar seçeneğinden bir üretim hattı seçin."
          )
        }}
      </p>
    </div>

    <!-- Empty State: Warehouse selected but 0 deficits -->
    <div
      v-else-if="items.length === 0 && !loading"
      class="empty-state-card success"
    >
      <div class="empty-state-icon">✅</div>
      <h3 class="empty-state-title">
        {{ __("Rezervasyon Açığı Bulunmamaktadır") }}
      </h3>
      <p class="empty-state-desc">
        {{
          __(
            "Seçilen hatta üretim emirleri için rezerve edilmiş tüm hammaddeler hat stoğunda mevcuttur veya bekleyen açık bulunmamaktadır."
          )
        }}
      </p>
    </div>

    <!-- Loading Skeleton / Spinner State -->
    <div v-else-if="loading && items.length === 0" class="empty-state-card">
      <div class="spinner-large">🔄</div>
      <h3 class="empty-state-title">{{ __("Açıklar Taranıyor...") }}</h3>
      <p class="empty-state-desc">
        {{ __("Hat rezervasyonları ve ambar stok durumu sorgulanıyor.") }}
      </p>
    </div>

    <!-- Data Table -->
    <div v-else class="table-wrapper">
      <table class="deficit-table">
        <thead>
          <tr>
            <th class="col-check">
              <input
                type="checkbox"
                class="row-checkbox"
                :checked="isAllSelected"
                :indeterminate="isIndeterminate"
                :disabled="selectableCount === 0"
                :title="__('Tümünü Seç / Kaldır')"
                @change="toggleSelectAll"
              />
            </th>
            <th class="col-item">{{ __("Hammadde Kodu & Adı") }}</th>
            <th class="col-num">{{ __("Net Açık (Deficit)") }}</th>
            <th class="col-num">{{ __("Hat Stoğu") }}</th>
            <th class="col-num col-prominent">
              <span class="prominent-header-title">
                ⚡ {{ __("Depodan Çıkacak Miktar") }}
              </span>
            </th>
            <th class="col-source">{{ __("Ana Ambar Raf / Parti") }}</th>
            <th class="col-status">{{ __("Durum") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in items"
            :key="item.item_code"
            :class="{
              'row-disabled': !isRowSelectable(item),
              'row-selected': item.selected && isRowSelectable(item),
            }"
            @click="onRowClick(item)"
          >
            <!-- Checkbox Column -->
            <td class="col-check" @click.stop>
              <input
                type="checkbox"
                class="row-checkbox"
                :checked="Boolean(item.selected && isRowSelectable(item))"
                :disabled="!isRowSelectable(item)"
                @change="toggleRowSelection(item)"
              />
            </td>

            <!-- Item Code & Name -->
            <td class="col-item">
              <div class="item-cell">
                <div class="item-header-row">
                  <span class="item-code">{{ item.item_code }}</span>
                  <button
                    type="button"
                    class="btn-copy"
                    :title="__('Kodu Kopyala')"
                    @click.stop="copyItemCode(item.item_code)"
                  >
                    📋
                  </button>
                </div>
                <div class="item-name" :title="item.item_name">
                  {{ item.item_name }}
                </div>
                <div v-if="item.uom" class="item-uom">
                  {{ __("Birim:") }} {{ item.uom }}
                </div>
              </div>
            </td>

            <!-- Net Açık (Deficit) -->
            <td class="col-num">
              <div class="qty-cell deficit-qty">
                <span class="qty-val">{{ formatNumber(item.deficit_qty) }}</span>
                <span v-if="item.uom" class="qty-uom">{{ item.uom }}</span>
              </div>
            </td>

            <!-- Hat Stoğu -->
            <td class="col-num">
              <div class="qty-cell line-qty">
                <span class="qty-val">
                  {{ formatNumber(item.line_stock_qty ?? item.line_actual_qty ?? 0) }}
                </span>
                <span v-if="item.uom" class="qty-uom">{{ item.uom }}</span>
              </div>
            </td>

            <!-- Depodan Çıkacak Miktar (PROMINENT COLUMN) -->
            <td class="col-num col-prominent">
              <div
                class="prominent-cell"
                :class="{
                  'has-stock': item.available_stock > 0,
                  'no-stock': item.available_stock <= 0,
                }"
              >
                <span class="prominent-val">
                  {{ formatNumber(item.available_stock) }}
                </span>
                <span v-if="item.uom" class="prominent-uom">{{ item.uom }}</span>
              </div>
            </td>

            <!-- Ana Ambar Raf / Parti -->
            <td class="col-source">
              <div class="source-cell">
                <div
                  v-if="getBoxes(item).length > 1"
                  class="multi-box-row"
                >
                  <span class="multi-box-badge">
                    📦 {{ __("{0} Koli", [getBoxes(item).length]) }}
                    <template v-if="getUniqueShelfCount(item) > 1">
                      · {{ __("{0} Raf", [getUniqueShelfCount(item)]) }}
                    </template>
                  </span>
                  <button
                    type="button"
                    class="btn-expand-boxes"
                    @click.stop="toggleExpandItem(item.item_code)"
                  >
                    {{
                      expandedItems[item.item_code]
                        ? __("Gizle")
                        : __("+{0} koli daha", [getBoxes(item).length - 1])
                    }}
                  </button>
                </div>

                <span
                  class="warehouse-badge"
                  :title="item.suggested_source_warehouse"
                >
                  🏢 {{ formatWarehouse(item.suggested_source_warehouse) }}
                </span>
                <span
                  v-if="item.suggested_batch_no"
                  class="batch-pill"
                  :title="item.suggested_batch_no"
                >
                  🏷️ {{ item.suggested_batch_no }}
                </span>

                <div
                  v-if="getBoxes(item).length > 1 && expandedItems[item.item_code]"
                  class="box-sublist"
                  @click.stop
                >
                  <div
                    v-for="(box, idx) in getBoxes(item)"
                    :key="`${box.warehouse}-${box.batch_no}-${idx}`"
                    class="box-sublist-item"
                  >
                    <div class="box-loc">
                      <span class="box-wh" :title="box.warehouse">
                        🏢 {{ formatWarehouse(box.warehouse) }}
                      </span>
                      <span
                        v-if="box.batch_no"
                        class="box-batch"
                        :title="box.batch_no"
                      >
                        🏷️ {{ box.batch_no }}
                      </span>
                    </div>
                    <span class="box-qty">
                      {{
                        formatNumber(box.allocated_qty) +
                        (item.uom ? " " + item.uom : "")
                      }}
                    </span>
                  </div>
                </div>
              </div>
            </td>

            <!-- Durum (Status Badge) -->
            <td class="col-status">
              <span
                v-if="item.covered_by_draft"
                class="status-badge badge-draft"
                :title="getDraftTooltip(item)"
              >
                ⏳ {{ __("Taslak İkmalde") }} ({{ getInFlightDrafts(item)[0] || "" }})
              </span>
              <span
                v-else-if="!item.has_stock || item.available_stock <= 0"
                class="status-badge badge-out-of-stock"
              >
                🔴 {{ __("Stok Yok") }}
              </span>
              <div
                v-else-if="item.has_stock && item.available_stock >= item.deficit_qty"
                class="status-cell-group"
              >
                <span class="status-badge badge-ready">
                  🟢 {{ __("Hazır") }}
                </span>
                <span
                  v-if="getInFlightDrafts(item).length > 0"
                  class="status-badge badge-sub-draft"
                  :title="getDraftTooltip(item)"
                >
                  ⏳ {{ __("Kısmi Taslak:") }} {{ getInFlightDrafts(item)[0] }}
                </span>
              </div>
              <div
                v-else-if="item.has_stock && item.available_stock < item.deficit_qty"
                class="status-cell-group"
              >
                <span class="status-badge badge-partial">
                  🟡 {{ __("Kısmi Stok") }} ({{ formatNumber(item.available_stock) }}/{{ formatNumber(item.deficit_qty) }})
                </span>
                <span
                  v-if="getInFlightDrafts(item).length > 0"
                  class="status-badge badge-sub-draft"
                  :title="getDraftTooltip(item)"
                >
                  ⏳ {{ __("Kısmi Taslak:") }} {{ getInFlightDrafts(item)[0] }}
                </span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import {
  type DeficitItem,
  type AllocatedBatch,
  isSelectable,
  getInFlightDrafts,
} from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const expandedItems = ref<Record<string, boolean>>({});

interface Props {
  items: DeficitItem[];
  targetWarehouse: string;
  loading: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: "toggle-select", item: DeficitItem): void;
  (e: "toggle-select-all", selectAll: boolean): void;
}>();

function getDraftTooltip(item: DeficitItem): string {
  const drafts = getInFlightDrafts(item);
  return `${__("Açık siparişler:")} ${drafts.join(", ")}`;
}

function isRowSelectable(item: DeficitItem): boolean {
  return isSelectable(item);
}

const selectableItems = computed(() =>
  props.items.filter((item) => isRowSelectable(item))
);

const selectableCount = computed(() => selectableItems.value.length);

const selectedCount = computed(
  () => selectableItems.value.filter((item) => item.selected).length
);

const isAllSelected = computed(
  () => selectableCount.value > 0 && selectedCount.value === selectableCount.value
);

const isIndeterminate = computed(
  () => selectedCount.value > 0 && selectedCount.value < selectableCount.value
);

function toggleRowSelection(item: DeficitItem) {
  if (!isRowSelectable(item)) return;
  emit("toggle-select", item);
}

function onRowClick(item: DeficitItem) {
  if (!isRowSelectable(item)) return;
  emit("toggle-select", item);
}

function toggleSelectAll(event: Event) {
  const checkbox = event.target as HTMLInputElement;
  emit("toggle-select-all", checkbox.checked);
}

function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return "0";
  return new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 3,
  }).format(num);
}

function getBoxes(item: DeficitItem): AllocatedBatch[] {
  return item.allocated_batches || [];
}

function getUniqueShelfCount(item: DeficitItem): number {
  const warehouses = new Set(
    getBoxes(item)
      .map((box) => box.warehouse)
      .filter(Boolean)
  );
  return warehouses.size;
}

function toggleExpandItem(itemCode: string) {
  expandedItems.value[itemCode] = !expandedItems.value[itemCode];
}

function formatWarehouse(wh: string | undefined): string {
  if (!wh) return __("Belirtilmemiş");
  return wh;
}

function copyItemCode(code: string) {
  if (!code) return;
  if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(code).then(() => {
      if (typeof frappe !== "undefined" && frappe.show_alert) {
        frappe.show_alert({
          message: __("Kopyalandı: {0}", [code]),
          indicator: "green",
        });
      }
    });
  }
}
</script>

<style scoped>
.deficit-table-container { width: 100%; margin-bottom: 1rem; }
.empty-state-card { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 3.5rem 1.5rem; background: var(--card-bg, #ffffff); border: 1px dashed var(--border-color, #cbd5e1); border-radius: 8px; text-align: center; }
[data-theme="dark"] .empty-state-card { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); }
.empty-state-card.success { border-color: #86efac; background: rgba(240, 253, 244, 0.6); }
[data-theme="dark"] .empty-state-card.success { border-color: rgba(74, 222, 128, 0.35); background: rgba(22, 163, 74, 0.12); }
.empty-state-icon { font-size: 2.8rem; margin-bottom: 0.75rem; }
.empty-state-title { font-size: 1.15rem; font-weight: 700; color: var(--text-color, #1e293b); margin: 0 0 0.4rem 0; }
.empty-state-desc { font-size: 0.88rem; color: var(--text-muted, #64748b); max-width: 540px; margin: 0; line-height: 1.45; }
.spinner-large { font-size: 2.5rem; animation: spin 1s infinite linear; margin-bottom: 0.75rem; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.table-wrapper { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 8px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05); }
[data-theme="dark"] .table-wrapper { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12)); }
.deficit-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.85rem; text-align: left; }
.deficit-table thead th { position: sticky; top: 0; z-index: 5; background: var(--control-bg, #f8fafc); color: var(--text-muted, #475569); font-weight: 700; font-size: 0.8rem; padding: 0.75rem 0.85rem; border-bottom: 2px solid var(--border-color, #cbd5e1); white-space: nowrap; }
[data-theme="dark"] .deficit-table thead th { background: #1e2530; color: #cbd5e1; border-bottom-color: rgba(255, 255, 255, 0.12); }
.deficit-table tbody tr { border-bottom: 1px solid var(--border-color, #f1f5f9); transition: background-color 0.15s ease; cursor: pointer; }
.deficit-table tbody tr:hover:not(.row-disabled) { background: rgba(37, 99, 235, 0.04); }
.deficit-table tbody tr.row-selected { background: rgba(37, 99, 235, 0.08); }
.deficit-table tbody tr.row-disabled { background: rgba(241, 245, 249, 0.5); cursor: not-allowed; opacity: 0.85; }
[data-theme="dark"] .deficit-table tbody tr.row-disabled { background: rgba(255, 255, 255, 0.03); }
.deficit-table tbody td { padding: 0.7rem 0.85rem; border-bottom: 1px solid var(--border-color, #e2e8f0); vertical-align: middle; }
.col-check { width: 44px; text-align: center; }
.row-checkbox { width: 17px; height: 17px; cursor: pointer; accent-color: var(--primary, #2563eb); }
.row-checkbox:disabled { cursor: not-allowed; opacity: 0.45; }
.col-item { min-width: 220px; }
.item-cell { display: flex; flex-direction: column; gap: 0.15rem; }
.item-header-row { display: flex; align-items: center; gap: 0.45rem; }
.item-code { font-weight: 700; font-family: monospace; font-size: 0.88rem; color: var(--text-color, #0f172a); }
.btn-copy { background: transparent; border: none; cursor: pointer; padding: 0 0.2rem; font-size: 0.8rem; opacity: 0.6; transition: opacity 0.2s; }
.btn-copy:hover { opacity: 1; }
.item-name { font-size: 0.8rem; color: var(--text-muted, #475569); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 260px; }
.item-uom { font-size: 0.72rem; color: var(--text-muted, #94a3b8); }
.col-num { text-align: right; min-width: 110px; white-space: nowrap; }
.qty-cell { display: inline-flex; flex-direction: column; align-items: flex-end; }
.qty-val { font-weight: 700; font-size: 0.88rem; color: var(--text-color, #1e293b); }
.deficit-qty .qty-val { color: #dc2626; }
[data-theme="dark"] .deficit-qty .qty-val { color: #f87171; }
.qty-uom { font-size: 0.72rem; color: var(--text-muted, #94a3b8); }
.col-prominent { background: rgba(37, 99, 235, 0.03); border-left: 2px solid rgba(37, 99, 235, 0.2); border-right: 2px solid rgba(37, 99, 235, 0.2); text-align: right; min-width: 140px; }
.prominent-header-title { color: var(--primary, #1d4ed8); font-weight: 800; }
[data-theme="dark"] .prominent-header-title { color: #60a5fa; }
.prominent-cell { display: inline-flex; flex-direction: column; align-items: flex-end; padding: 0.25rem 0.5rem; border-radius: 6px; background: rgba(37, 99, 235, 0.08); }
.prominent-cell.no-stock { background: rgba(239, 68, 68, 0.08); }
.prominent-cell .prominent-val { font-size: 0.95rem; font-weight: 800; color: var(--primary, #1d4ed8); }
[data-theme="dark"] .prominent-cell .prominent-val { color: #60a5fa; }
.prominent-cell.no-stock .prominent-val { color: #dc2626; }
[data-theme="dark"] .prominent-cell.no-stock .prominent-val { color: #f87171; }
.prominent-cell .prominent-uom { font-size: 0.72rem; font-weight: 600; color: var(--text-muted, #64748b); }
.col-source { min-width: 190px; }
.source-cell { display: flex; flex-direction: column; gap: 0.25rem; align-items: flex-start; }
.multi-box-row { display: flex; align-items: center; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.1rem; }
.multi-box-badge { display: inline-flex; align-items: center; gap: 0.2rem; padding: 0.15rem 0.45rem; font-size: 0.72rem; font-weight: 700; border-radius: 4px; background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; white-space: nowrap; }
[data-theme="dark"] .multi-box-badge { background: rgba(245, 158, 11, 0.18); color: #fcd34d; border-color: rgba(245, 158, 11, 0.38); }
.btn-expand-boxes { padding: 0.14rem 0.42rem; font-size: 0.7rem; font-weight: 600; border-radius: 4px; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; cursor: pointer; transition: background-color 0.15s ease; white-space: nowrap; }
.btn-expand-boxes:hover { background: #dbeafe; }
[data-theme="dark"] .btn-expand-boxes { background: rgba(59, 130, 246, 0.18); color: #93c5fd; border-color: rgba(59, 130, 246, 0.38); }
[data-theme="dark"] .btn-expand-boxes:hover { background: rgba(59, 130, 246, 0.28); }
.warehouse-badge { display: inline-block; padding: 0.2rem 0.5rem; font-size: 0.76rem; font-weight: 600; background: var(--control-bg, #f1f5f9); color: var(--text-color, #334155); border-radius: 4px; border: 1px solid var(--border-color, #cbd5e1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px; }
[data-theme="dark"] .warehouse-badge { background: rgba(255, 255, 255, 0.06); border-color: rgba(255, 255, 255, 0.14); color: #e2e8f0; }
.batch-pill { display: inline-block; font-size: 0.72rem; font-family: monospace; font-weight: 600; color: #0369a1; background: #e0f2fe; padding: 0.15rem 0.4rem; border-radius: 4px; }
[data-theme="dark"] .batch-pill { color: #7dd3fc; background: rgba(14, 165, 233, 0.18); }
.box-sublist { width: 100%; margin-top: 0.2rem; padding: 0.35rem 0.45rem; border-radius: 6px; background: var(--control-bg, #f8fafc); border: 1px solid var(--border-color, #e2e8f0); display: flex; flex-direction: column; gap: 0.25rem; cursor: default; }
[data-theme="dark"] .box-sublist { background: rgba(255, 255, 255, 0.04); border-color: rgba(255, 255, 255, 0.12); }
.box-sublist-item { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; font-size: 0.72rem; line-height: 1.3; padding-bottom: 0.2rem; border-bottom: 1px dashed var(--border-color, #e2e8f0); }
.box-sublist-item:last-child { padding-bottom: 0; border-bottom: none; }
[data-theme="dark"] .box-sublist-item { border-bottom-color: rgba(255, 255, 255, 0.1); }
.box-loc { display: flex; flex-wrap: wrap; align-items: center; gap: 0.3rem; }
.box-wh { font-weight: 600; color: var(--text-color, #334155); }
[data-theme="dark"] .box-wh { color: #e2e8f0; }
.box-batch { font-family: monospace; color: #0369a1; }
[data-theme="dark"] .box-batch { color: #7dd3fc; }
.box-qty { font-weight: 700; color: var(--primary, #1d4ed8); white-space: nowrap; }
[data-theme="dark"] .box-qty { color: #60a5fa; }
.col-status { min-width: 160px; }
.status-cell-group { display: inline-flex; flex-direction: column; gap: 0.25rem; align-items: flex-start; }
.status-badge { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.3rem 0.65rem; font-size: 0.76rem; font-weight: 700; border-radius: 9999px; white-space: nowrap; }
.badge-ready { background: #dcfce7; color: #15803d; border: 1px solid #86efac; }
.badge-partial { background: #fef9c3; color: #a16207; border: 1px solid #fde047; }
.badge-out-of-stock { background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }
.badge-draft { background: #e0e7ff; color: #3730a3; border: 1px solid #c7d2fe; }
.badge-sub-draft { background: #ede9fe; color: #6d28d9; border: 1px solid #ddd6fe; font-size: 0.7rem; padding: 0.15rem 0.45rem; }
</style>
