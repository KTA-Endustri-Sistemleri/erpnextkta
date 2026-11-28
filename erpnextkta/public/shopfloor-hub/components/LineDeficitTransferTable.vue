<script setup lang="ts">
import { ref, computed, watch } from "vue";
import type {
  LineTransferDeficitItem,
  LineTransferSourceOption,
  LineTransferPayloadItem,
} from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

interface RowDraftState {
  selected: boolean;
  sourceWarehouse: string;
  qty: number;
}

const props = withDefaults(
  defineProps<{
    items: LineTransferDeficitItem[];
    targetWarehouse: string;
    loading: boolean;
    submitting?: boolean;
  }>(),
  { submitting: false }
);

const emit = defineEmits<{
  (e: "execute-transfer", items: LineTransferPayloadItem[]): void;
}>();

const rowState = ref<Record<string, RowDraftState>>({});

function rowKey(item: LineTransferDeficitItem): string {
  return `${item.item_code}::${item.target_warehouse}`;
}

watch(
  () => props.items,
  (list) => {
    const next: Record<string, RowDraftState> = {};
    for (const item of list || []) {
      const key = rowKey(item);
      const firstSource = item.available_sources?.[0]?.warehouse || "";
      next[key] = {
        selected: Boolean(item.default_selected),
        sourceWarehouse: item.suggested_source_warehouse || firstSource,
        qty: Number(item.suggested_qty) || 0,
      };
    }
    rowState.value = next;
  },
  { immediate: true }
);

function getDraft(item: LineTransferDeficitItem): RowDraftState {
  const key = rowKey(item);
  if (!rowState.value[key]) {
    rowState.value[key] = {
      selected: Boolean(item.default_selected),
      sourceWarehouse:
        item.suggested_source_warehouse ||
        item.available_sources?.[0]?.warehouse ||
        "",
      qty: Number(item.suggested_qty) || 0,
    };
  }
  return rowState.value[key];
}

function getActiveSource(
  item: LineTransferDeficitItem
): LineTransferSourceOption | undefined {
  const draft = getDraft(item);
  return (
    item.available_sources.find((s) => s.warehouse === draft.sourceWarehouse) ||
    item.available_sources[0]
  );
}

function onSourceChange(item: LineTransferDeficitItem, event: Event) {
  const target = event.target as HTMLSelectElement | null;
  const nextWh = target ? target.value : "";
  const draft = getDraft(item);
  draft.sourceWarehouse = nextWh;
  const src = item.available_sources.find((s) => s.warehouse === nextWh);
  if (src) {
    const cap = src.free_qty > 0 ? src.free_qty : src.actual_qty;
    draft.qty = Number(Math.min(item.deficit_qty, cap).toFixed(4));
  }
}

function isRowInvalid(item: LineTransferDeficitItem): boolean {
  const draft = getDraft(item);
  const src = getActiveSource(item);
  if (!src || !draft.sourceWarehouse) return true;
  const qty = Number(draft.qty);
  return Number.isNaN(qty) || qty <= 0 || qty > Number(src.actual_qty || 0);
}

function usesReserved(item: LineTransferDeficitItem): boolean {
  const draft = getDraft(item);
  const src = getActiveSource(item);
  if (!src) return false;
  const qty = Number(draft.qty) || 0;
  return qty > Number(src.free_qty || 0) && qty <= Number(src.actual_qty || 0);
}

const selectableRows = computed(() =>
  (props.items || []).filter(
    (item) => item.available_sources && item.available_sources.length > 0
  )
);

const selectedRows = computed(() =>
  selectableRows.value.filter((item) => getDraft(item).selected)
);

const isAllSelected = computed(
  () =>
    selectableRows.value.length > 0 &&
    selectedRows.value.length === selectableRows.value.length
);

const isIndeterminate = computed(
  () =>
    selectedRows.value.length > 0 &&
    selectedRows.value.length < selectableRows.value.length
);

const hasInvalidSelected = computed(() =>
  selectedRows.value.some((item) => isRowInvalid(item))
);

const reservedSelectedCount = computed(
  () => selectedRows.value.filter((item) => usesReserved(item)).length
);

const totalTransferQty = computed(() =>
  selectedRows.value.reduce(
    (acc, item) => acc + (Number(getDraft(item).qty) || 0),
    0
  )
);

function toggleAll(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  for (const item of selectableRows.value) {
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

function handleTransfer() {
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
      source_warehouse: draft.sourceWarehouse,
      target_warehouse: item.target_warehouse,
    };
  });
  emit("execute-transfer", payload);
}
</script>

<template>
  <div class="lt-table-wrap">
    <div v-if="!targetWarehouse" class="lt-empty-card">
      <div class="lt-empty-icon">🏭</div>
      <h3 class="lt-empty-title">{{ __("Hedef Üretim Hattı Seçin") }}</h3>
      <p class="lt-empty-desc">
        {{
          __(
            "Kardeş üretim hatlarından karşılanabilecek hammadde açıklarını görmek için yukarıdan bir hedef hat seçin."
          )
        }}
      </p>
    </div>

    <div v-else-if="loading && items.length === 0" class="lt-empty-card">
      <div class="lt-spinner">🔄</div>
      <h3 class="lt-empty-title">{{ __("Hat Açıkları Taranıyor...") }}</h3>
      <p class="lt-empty-desc">
        {{ __("Üretim hatlarındaki serbest ve rezerve stoklar kontrol ediliyor.") }}
      </p>
    </div>

    <div
      v-else-if="items.length === 0 && !loading"
      class="lt-empty-card success"
    >
      <div class="lt-empty-icon">✅</div>
      <h3 class="lt-empty-title">
        {{ __("Kardeş Hatlardan Karşılanacak Açık Yok") }}
      </h3>
      <p class="lt-empty-desc">
        {{
          __(
            "Seçilen hatta bekleyen üretim açığı bulunmuyor veya diğer üretim hatlarında kullanılabilir stok mevcut değil."
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
                  :disabled="selectableRows.length === 0 || submitting"
                  :title="__('Tümünü Seç / Kaldır')"
                  @change="toggleAll"
                />
              </th>
              <th>{{ __("Hammadde Kodu & Adı") }}</th>
              <th class="text-right">{{ __("Hat Stoğu / Açık") }}</th>
              <th>{{ __("Kaynak 150x Hat") }}</th>
              <th class="text-right">{{ __("Aktarılacak Miktar") }}</th>
              <th>{{ __("Durum") }}</th>
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
                  :disabled="submitting || !item.available_sources?.length"
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
                <div class="stock-pair">
                  <span class="line-actual">
                    {{ __("Hat:") }} {{ formatQty(item.line_actual_qty) }}
                    {{ item.uom }}
                  </span>
                  <span class="deficit-val">
                    {{ __("Açık:") }} {{ formatQty(item.deficit_qty) }}
                    {{ item.uom }}
                  </span>
                </div>
              </td>
              <td>
                <select
                  :value="getDraft(item).sourceWarehouse"
                  class="lt-select"
                  :disabled="submitting"
                  @change="onSourceChange(item, $event)"
                >
                  <option
                    v-for="src in item.available_sources"
                    :key="src.warehouse"
                    :value="src.warehouse"
                  >
                    {{ src.warehouse }} ({{ __("Serbest Stok") }}:
                    {{ formatQty(src.free_qty) }} / {{ __("Fiziksel") }}:
                    {{ formatQty(src.actual_qty) }})
                  </option>
                </select>
              </td>
              <td class="text-right">
                <div class="qty-input-wrap">
                  <input
                    v-model.number="getDraft(item).qty"
                    type="number"
                    min="0.0001"
                    :max="getActiveSource(item)?.actual_qty || 0"
                    step="any"
                    class="lt-qty-input"
                    :class="{ 'is-error': isRowInvalid(item) }"
                    :disabled="submitting"
                  />
                  <span v-if="item.uom" class="uom-txt">{{ item.uom }}</span>
                </div>
              </td>
              <td>
                <span
                  v-if="isRowInvalid(item)"
                  class="lt-badge badge-danger"
                >
                  🔴 {{ __("Geçersiz Miktar") }}
                </span>
                <span
                  v-else-if="usesReserved(item)"
                  class="lt-badge badge-warning"
                >
                  ⚠️ {{ __("Öncelik Kaydırma (Rezerve)") }}
                </span>
                <span v-else class="lt-badge badge-success">
                  🟢 {{ __("Serbestten Hazır") }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="lt-action-bar">
        <div class="lt-summary">
          <strong>
            {{
              __("{0} kalem seçildi, toplam {1} miktar aktarılacak", [
                selectedRows.length,
                formatQty(totalTransferQty),
              ])
            }}
          </strong>
          <span v-if="reservedSelectedCount > 0" class="summary-warn">
            ⚠️
            {{
              __("{0} kalemde rezerve stok kullanılacak", [
                reservedSelectedCount,
              ])
            }}
          </span>
          <span v-if="hasInvalidSelected" class="summary-err">
            🔴
            {{
              __(
                "Seçili satırlarda stok sınırını aşan veya geçersiz miktar var"
              )
            }}
          </span>
        </div>

        <button
          type="button"
          class="lt-submit-btn"
          :disabled="
            selectedRows.length === 0 || hasInvalidSelected || submitting
          "
          @click="handleTransfer"
        >
          <span>⚡</span>
          <span>
            {{
              submitting
                ? __("Transfer Yapılıyor...")
                : __("Seçilenleri Hatta Aktar")
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
.lt-empty-card.success { border-color: #86efac; background: rgba(240, 253, 244, 0.55); }
[data-theme="dark"] .lt-empty-card.success { border-color: rgba(74, 222, 128, 0.35); background: rgba(22, 163, 74, 0.12); }
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
.item-name { font-size: 0.77rem; color: var(--text-muted, #64748b); max-width: 240px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stock-pair { display: inline-flex; flex-direction: column; align-items: flex-end; gap: 0.15rem; white-space: nowrap; }
.line-actual { font-size: 0.76rem; color: var(--text-muted, #64748b); }
.deficit-val { font-weight: 800; color: #dc2626; }
[data-theme="dark"] .deficit-val { color: #f87171; }
.lt-select { min-width: 240px; max-width: 340px; width: 100%; padding: 0.4rem 0.55rem; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-size: 0.8rem; font-weight: 600; }
[data-theme="dark"] .lt-select { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #f8fafc; }
.qty-input-wrap { display: inline-flex; align-items: center; gap: 0.35rem; }
.lt-qty-input { width: 96px; padding: 0.38rem 0.5rem; text-align: right; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-weight: 700; font-size: 0.84rem; }
[data-theme="dark"] .lt-qty-input { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #f8fafc; }
.lt-qty-input.is-error { border-color: #dc2626; background: rgba(239, 68, 68, 0.08); }
.uom-txt { font-size: 0.75rem; color: var(--text-muted, #64748b); }
.lt-badge { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.25rem 0.6rem; border-radius: 9999px; font-size: 0.74rem; font-weight: 700; white-space: nowrap; }
.badge-success { background: #dcfce7; color: #15803d; border: 1px solid #86efac; }
.badge-warning { background: #fef3c7; color: #b45309; border: 1px solid #fde68a; }
.badge-danger { background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }
[data-theme="dark"] .badge-success { background: rgba(34, 197, 94, 0.2); border-color: rgba(74, 222, 128, 0.35); color: #86efac; }
[data-theme="dark"] .badge-warning { background: rgba(245, 158, 11, 0.2); border-color: rgba(251, 191, 36, 0.35); color: #fcd34d; }
[data-theme="dark"] .badge-danger { background: rgba(239, 68, 68, 0.2); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.lt-action-bar { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; padding: 0.95rem 1.25rem; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; box-shadow: 0 2px 6px rgba(15, 23, 42, 0.05); }
[data-theme="dark"] .lt-action-bar { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12)); }
.lt-summary { display: flex; flex-direction: column; gap: 0.2rem; font-size: 0.88rem; color: var(--text-color, #0f172a); }
.summary-warn { font-size: 0.78rem; font-weight: 700; color: #b45309; }
[data-theme="dark"] .summary-warn { color: #fcd34d; }
.summary-err { font-size: 0.78rem; font-weight: 700; color: #dc2626; }
[data-theme="dark"] .summary-err { color: #f87171; }
.lt-submit-btn { display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.6rem 1.25rem; border: none; border-radius: 0.55rem; background: #2563eb; color: #ffffff; font-size: 0.88rem; font-weight: 700; cursor: pointer; transition: all 0.15s ease; }
.lt-submit-btn:hover:not(:disabled) { background: #1d4ed8; box-shadow: 0 3px 10px rgba(37, 99, 235, 0.28); }
.lt-submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
