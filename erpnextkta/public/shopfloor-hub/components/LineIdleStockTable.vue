<script setup lang="ts">
import { ref, computed, watch } from "vue";
import type {
  LineIdleStockItem,
  ProductionWarehouseOption,
  LineTransferPayloadItem,
} from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

interface IdleDraftState {
  selected: boolean;
  targetWarehouse: string;
  qty: number;
}

const props = withDefaults(
  defineProps<{
    items: LineIdleStockItem[];
    sourceWarehouse: string;
    productionWarehouses: ProductionWarehouseOption[];
    loading: boolean;
    submitting?: boolean;
  }>(),
  { submitting: false }
);

const emit = defineEmits<{
  (e: "execute-transfer", items: LineTransferPayloadItem[]): void;
}>();

const fallbackWarehouses: ProductionWarehouseOption[] = [
  { warehouse: "1501 KESMELER - KTA", label: "1501 KESMELER" },
  { warehouse: "1502 JK - KTA", label: "1502 JK" },
  { warehouse: "1503 RATIONAL - KTA", label: "1503 RATIONAL" },
  {
    warehouse: "1504 ARCELIK / GRAMMER - KTA",
    label: "1504 ARCELIK / GRAMMER",
  },
  { warehouse: "1509 BOSCH - KTA", label: "1509 BOSCH" },
];

const rowState = ref<Record<string, IdleDraftState>>({});

function rowKey(item: LineIdleStockItem): string {
  return `${item.item_code}::${item.source_warehouse}`;
}

watch(
  () => props.items,
  (list) => {
    const next: Record<string, IdleDraftState> = {};
    for (const item of list || []) {
      const hasSuggested = Boolean(item.suggested_target_warehouse);
      next[rowKey(item)] = {
        selected: hasSuggested,
        targetWarehouse: item.suggested_target_warehouse || "",
        qty: Number(item.suggested_qty) || 0,
      };
    }
    rowState.value = next;
  },
  { immediate: true }
);

function getDraft(item: LineIdleStockItem): IdleDraftState {
  const key = rowKey(item);
  if (!rowState.value[key]) {
    const hasSuggested = Boolean(item.suggested_target_warehouse);
    rowState.value[key] = {
      selected: hasSuggested,
      targetWarehouse: item.suggested_target_warehouse || "",
      qty: Number(item.suggested_qty) || 0,
    };
  }
  return rowState.value[key];
}

function getTargetOptions(item: LineIdleStockItem): ProductionWarehouseOption[] {
  const base =
    props.productionWarehouses && props.productionWarehouses.length > 0
      ? props.productionWarehouses
      : fallbackWarehouses;
  const filtered = base.filter((w) => w.warehouse !== props.sourceWarehouse);
  if (
    item.suggested_target_warehouse &&
    !filtered.some((w) => w.warehouse === item.suggested_target_warehouse)
  ) {
    filtered.unshift({
      warehouse: item.suggested_target_warehouse,
      label: item.suggested_target_warehouse,
    });
  }
  return filtered;
}

function onTargetChange(item: LineIdleStockItem, event: Event) {
  const target = event.target as HTMLSelectElement | null;
  const targetWh = target ? target.value : "";
  const draft = getDraft(item);
  draft.targetWarehouse = targetWh;
  draft.selected = Boolean(targetWh);
}

function isQtyInvalid(item: LineIdleStockItem): boolean {
  const qty = Number(getDraft(item).qty);
  return (
    Number.isNaN(qty) || qty <= 0 || qty > Number(item.actual_qty || 0)
  );
}

function isRowInvalid(item: LineIdleStockItem): boolean {
  const draft = getDraft(item);
  return !draft.targetWarehouse || isQtyInvalid(item);
}

function usesReserved(item: LineIdleStockItem): boolean {
  const qty = Number(getDraft(item).qty) || 0;
  return (
    qty > Number(item.free_qty || 0) && qty <= Number(item.actual_qty || 0)
  );
}

const selectedRows = computed(() =>
  (props.items || []).filter((item) => getDraft(item).selected)
);

const isAllSelected = computed(
  () =>
    props.items.length > 0 && selectedRows.value.length === props.items.length
);

const isIndeterminate = computed(
  () =>
    selectedRows.value.length > 0 &&
    selectedRows.value.length < props.items.length
);

const hasInvalidSelected = computed(() =>
  selectedRows.value.some((item) => isRowInvalid(item))
);

const totalTransferQty = computed(() =>
  selectedRows.value.reduce(
    (sum, item) => sum + (Number(getDraft(item).qty) || 0),
    0
  )
);

function toggleAll(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  for (const item of props.items) {
    getDraft(item).selected = checked;
  }
}

function formatQty(val: number | null | undefined): string {
  const num = Number(val ?? 0);
  if (Number.isNaN(num)) return "0";
  return new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 3,
  }).format(num);
}

function handleSend() {
  if (
    selectedRows.value.length === 0 ||
    hasInvalidSelected.value ||
    props.submitting
  ) {
    return;
  }
  const payload: LineTransferPayloadItem[] = selectedRows.value.map((item) => {
    const draft = getDraft(item);
    return {
      item_code: item.item_code,
      qty: Number(draft.qty),
      source_warehouse: item.source_warehouse,
      target_warehouse: draft.targetWarehouse,
    };
  });
  emit("execute-transfer", payload);
}
</script>

<template>
  <div class="lt-table-wrap">
    <div v-if="!sourceWarehouse" class="lt-empty-card">
      <div class="lt-empty-icon">📤</div>
      <h3 class="lt-empty-title">{{ __("Kaynak Üretim Hattı Seçin") }}</h3>
      <p class="lt-empty-desc">
        {{
          __(
            "Hatta boşta bekleyen (serbest) stokları diğer hatlara göndermek için yukarıdan bir kaynak hat seçin."
          )
        }}
      </p>
    </div>

    <div v-else-if="loading && items.length === 0" class="lt-empty-card">
      <div class="lt-spinner">🔄</div>
      <h3 class="lt-empty-title">{{ __("Atıl Stoklar Taranıyor...") }}</h3>
      <p class="lt-empty-desc">
        {{ __("Seçilen hattaki rezerve dışı serbest stoklar analiz ediliyor.") }}
      </p>
    </div>

    <div
      v-else-if="items.length === 0 && !loading"
      class="lt-empty-card success"
    >
      <div class="lt-empty-icon">📦</div>
      <h3 class="lt-empty-title">{{ __("Atıl Serbest Stok Bulunamadı") }}</h3>
      <p class="lt-empty-desc">
        {{
          __(
            "Bu üretim hattında iş emri rezervasyonu dışında boşta bekleyen hammadde bulunmamaktadır."
          )
        }}
      </p>
    </div>

    <template v-else>
      <div class="lt-table-scroll">
        <table class="lt-table">
          <thead>
            <tr>
              <th class="col-check">
                <input
                  type="checkbox"
                  class="lt-checkbox"
                  :checked="isAllSelected"
                  :indeterminate="isIndeterminate"
                  :disabled="submitting"
                  :title="__('Tümünü Seç / Kaldır')"
                  @change="toggleAll"
                />
              </th>
              <th>{{ __("Hammadde Kodu & Adı") }}</th>
              <th class="text-right">
                {{ __("Fiziksel / Rezerve / Boşta (Serbest)") }}
              </th>
              <th>{{ __("Hedef 150x Hat") }}</th>
              <th class="text-right">{{ __("Gönderilecek Miktar") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in items"
              :key="rowKey(item)"
              :class="{ 'row-selected': getDraft(item).selected }"
            >
              <td class="col-check">
                <input
                  v-model="getDraft(item).selected"
                  type="checkbox"
                  class="lt-checkbox"
                  :disabled="submitting"
                />
              </td>
              <td>
                <div class="item-cell">
                  <span class="item-code">{{ item.item_code }}</span>
                  <span
                    v-if="item.item_name && item.item_name !== item.item_code"
                    class="item-name"
                    :title="item.item_name"
                  >
                    {{ item.item_name }}
                  </span>
                </div>
              </td>
              <td class="text-right">
                <div class="stock-breakdown">
                  <span class="stock-sub">
                    {{ __("Fiziksel") }}: {{ formatQty(item.actual_qty) }} ·
                    {{ __("Rezerve") }}: {{ formatQty(item.reserved_qty) }}
                  </span>
                  <span class="free-badge">
                    {{ __("Serbest Stok") }}: {{ formatQty(item.free_qty) }}
                    {{ item.uom }}
                  </span>
                </div>
              </td>
              <td>
                <div class="target-col">
                  <select
                    :value="getDraft(item).targetWarehouse"
                    class="lt-select"
                    :disabled="submitting"
                    @change="onTargetChange(item, $event)"
                  >
                    <option value="">{{ __("-- Hedef Hat Seçin --") }}</option>
                    <option
                      v-for="wh in getTargetOptions(item)"
                      :key="wh.warehouse"
                      :value="wh.warehouse"
                    >
                      {{ wh.warehouse
                      }}{{
                        wh.warehouse === item.suggested_target_warehouse &&
                        item.target_deficit_qty > 0
                          ? ` (${__("Açık")}: ${formatQty(item.target_deficit_qty)})`
                          : ""
                      }}
                    </option>
                  </select>
                  <span
                    v-if="
                      item.suggested_target_warehouse &&
                      item.target_deficit_qty > 0
                    "
                    class="hint-pill"
                  >
                    🎯 {{ __("Önerilen Açık:") }}
                    {{ formatQty(item.target_deficit_qty) }} {{ item.uom }}
                  </span>
                </div>
              </td>
              <td class="text-right">
                <div class="qty-col">
                  <div class="qty-input-wrap">
                    <input
                      v-model.number="getDraft(item).qty"
                      type="number"
                      min="0.0001"
                      :max="item.actual_qty"
                      step="any"
                      class="lt-qty-input"
                      :class="{ 'is-error': isQtyInvalid(item) }"
                      :disabled="submitting"
                    />
                    <span v-if="item.uom" class="uom-txt">{{ item.uom }}</span>
                  </div>
                  <span v-if="isQtyInvalid(item)" class="inline-err">
                    🔴 {{ __("Stok sınırı aşıldı veya geçersiz") }}
                  </span>
                  <span v-else-if="usesReserved(item)" class="inline-warn">
                    ⚠️ {{ __("Rezerve") }}
                  </span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="lt-action-bar">
        <div class="lt-summary">
          <strong>
            {{
              __("{0} kalem seçildi, toplam {1} miktar gönderilecek", [
                selectedRows.length,
                formatQty(totalTransferQty),
              ])
            }}
          </strong>
          <span v-if="hasInvalidSelected" class="summary-err">
            🔴
            {{
              __("Seçili satırlarda geçerli bir hedef hat ve miktar belirtin")
            }}
          </span>
        </div>

        <button
          type="button"
          class="lt-submit-btn"
          :disabled="
            selectedRows.length === 0 || hasInvalidSelected || submitting
          "
          @click="handleSend"
        >
          <span>⚡</span>
          <span>
            {{
              submitting
                ? __("Gönderiliyor...")
                : __("Seçilenleri Gönder")
            }}
          </span>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.lt-table-wrap { display: flex; flex-direction: column; gap: 1rem; }
.lt-empty-card { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 3.25rem 1.5rem; background: var(--card-bg, #ffffff); border: 1px dashed var(--border-color, #cbd5e1); border-radius: 0.75rem; }
[data-theme="dark"] .lt-empty-card { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); }
.lt-empty-card.success { border-color: #cbd5e1; }
.lt-empty-icon { font-size: 2.6rem; margin-bottom: 0.65rem; }
.lt-empty-title { margin: 0 0 0.35rem; font-size: 1.1rem; font-weight: 800; color: var(--text-color, #0f172a); }
.lt-empty-desc { margin: 0; font-size: 0.86rem; color: var(--text-muted, #64748b); max-width: 520px; }
.lt-spinner { font-size: 2.4rem; animation: lt-spin 1s linear infinite; margin-bottom: 0.65rem; }
@keyframes lt-spin { to { transform: rotate(360deg); } }
.lt-table-scroll { overflow-x: auto; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; box-shadow: 0 1px 4px rgba(15, 23, 42, 0.05); }
[data-theme="dark"] .lt-table-scroll { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12)); }
.lt-table { width: 100%; border-collapse: collapse; font-size: 0.84rem; text-align: left; }
.lt-table th { padding: 0.75rem 0.9rem; background: var(--bg-color, #f8fafc); color: var(--text-muted, #475569); font-size: 0.76rem; font-weight: 700; text-transform: uppercase; border-bottom: 1.5px solid var(--border-color, #cbd5e1); white-space: nowrap; }
[data-theme="dark"] .lt-table th { background: rgba(255, 255, 255, 0.04); color: #cbd5e1; }
.lt-table td { padding: 0.7rem 0.9rem; border-bottom: 1px solid var(--border-color, #e2e8f0); vertical-align: middle; }
.lt-table tbody tr:last-child td { border-bottom: none; }
.lt-table tbody tr.row-selected { background: rgba(37, 99, 235, 0.06); }
.col-check { width: 42px; text-align: center; }
.lt-checkbox { width: 16px; height: 16px; cursor: pointer; accent-color: #2563eb; }
.text-right { text-align: right !important; }
.item-cell { display: flex; flex-direction: column; gap: 0.15rem; }
.item-code { font-family: monospace; font-weight: 800; color: var(--text-color, #0f172a); }
.item-name { font-size: 0.77rem; color: var(--text-muted, #64748b); max-width: 230px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stock-breakdown { display: inline-flex; flex-direction: column; align-items: flex-end; gap: 0.2rem; white-space: nowrap; }
.stock-sub { font-size: 0.75rem; color: var(--text-muted, #64748b); }
.free-badge { font-weight: 800; font-size: 0.82rem; color: #15803d; }
[data-theme="dark"] .free-badge { color: #4ade80; }
.target-col { display: flex; flex-direction: column; gap: 0.25rem; }
.lt-select { min-width: 240px; max-width: 340px; width: 100%; padding: 0.4rem 0.55rem; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-size: 0.8rem; font-weight: 600; }
[data-theme="dark"] .lt-select { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #f8fafc; }
.hint-pill { font-size: 0.73rem; font-weight: 700; color: #1d4ed8; }
[data-theme="dark"] .hint-pill { color: #93c5fd; }
.qty-col { display: inline-flex; flex-direction: column; align-items: flex-end; gap: 0.2rem; }
.qty-input-wrap { display: inline-flex; align-items: center; gap: 0.35rem; }
.lt-qty-input { width: 96px; padding: 0.38rem 0.5rem; text-align: right; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-weight: 700; font-size: 0.84rem; }
[data-theme="dark"] .lt-qty-input { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #f8fafc; }
.lt-qty-input.is-error { border-color: #dc2626; background: rgba(239, 68, 68, 0.08); }
.uom-txt { font-size: 0.75rem; color: var(--text-muted, #64748b); }
.inline-warn { font-size: 0.73rem; font-weight: 700; color: #b45309; }
[data-theme="dark"] .inline-warn { color: #fcd34d; }
.inline-err { font-size: 0.73rem; font-weight: 700; color: #dc2626; }
[data-theme="dark"] .inline-err { color: #f87171; }
.lt-action-bar { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; padding: 0.95rem 1.25rem; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; box-shadow: 0 2px 6px rgba(15, 23, 42, 0.05); }
[data-theme="dark"] .lt-action-bar { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12)); }
.lt-summary { display: flex; flex-direction: column; gap: 0.2rem; font-size: 0.88rem; color: var(--text-color, #0f172a); }
.summary-err { font-size: 0.78rem; font-weight: 700; color: #dc2626; }
[data-theme="dark"] .summary-err { color: #f87171; }
.lt-submit-btn { display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.6rem 1.25rem; border: none; border-radius: 0.55rem; background: #2563eb; color: #ffffff; font-size: 0.88rem; font-weight: 700; cursor: pointer; transition: all 0.15s ease; }
.lt-submit-btn:hover:not(:disabled) { background: #1d4ed8; box-shadow: 0 3px 10px rgba(37, 99, 235, 0.28); }
.lt-submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
