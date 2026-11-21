<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import type {
  ProductionWarehouseOption,
  ManualTransferItemOption,
  LineTransferPayloadItem,
  ReservedStockWarning,
} from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

interface SelectedManualLine extends ManualTransferItemOption {
  qty: number;
}

const props = withDefaults(
  defineProps<{
    show: boolean;
    sourceWarehouse?: string;
    productionWarehouses: ProductionWarehouseOption[];
    submitting?: boolean;
  }>(),
  { sourceWarehouse: "", submitting: false }
);

const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", transfers: LineTransferPayloadItem[], reservedWarnings: ReservedStockWarning[]): void;
}>();

const fallbackWarehouses: ProductionWarehouseOption[] = [
  { warehouse: "1501 KESMELER - KTA", label: "1501 KESMELER" },
  { warehouse: "1502 JK - KTA", label: "1502 JK" },
  { warehouse: "1503 RATIONAL - KTA", label: "1503 RATIONAL" },
  { warehouse: "1504 ARCELIK / GRAMMER - KTA", label: "1504 ARCELIK / GRAMMER" },
  { warehouse: "1509 BOSCH - KTA", label: "1509 BOSCH" },
];

const localSource = ref<string>("");
const localTarget = ref<string>("");
const searchText = ref<string>("");
const searchResults = ref<ManualTransferItemOption[]>([]);
const searching = ref<boolean>(false);
const searchError = ref<string | null>(null);
const addedLines = ref<SelectedManualLine[]>([]);

let searchTimer: number | null = null;
let latestSearchId = 0;

const warehouseOptions = computed<ProductionWarehouseOption[]>(() =>
  props.productionWarehouses?.length ? props.productionWarehouses : fallbackWarehouses
);

const targetOptions = computed<ProductionWarehouseOption[]>(() =>
  warehouseOptions.value.filter((w) => w.warehouse !== localSource.value)
);

watch(
  () => props.show,
  (isOpen) => {
    if (!isOpen) return;
    const validSource = warehouseOptions.value.some((w) => w.warehouse === props.sourceWarehouse)
      ? props.sourceWarehouse || ""
      : warehouseOptions.value[0]?.warehouse || "";
    localSource.value = validSource;
    localTarget.value = "";
    searchText.value = "";
    searchResults.value = [];
    searchError.value = null;
    addedLines.value = [];
    if (localSource.value) fetchSourceItems();
  }
);

watch(localSource, (newVal, oldVal) => {
  if (!props.show || newVal === oldVal) return;
  if (localTarget.value === newVal) localTarget.value = "";
  addedLines.value = [];
  searchResults.value = [];
  if (newVal) fetchSourceItems();
});

function scheduleSearch() {
  if (searchTimer !== null) window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => fetchSourceItems(), 250);
}

async function fetchSourceItems() {
  if (!localSource.value) {
    searchResults.value = [];
    return;
  }
  const reqId = ++latestSearchId;
  searching.value = true;
  searchError.value = null;
  try {
    const res = await new Promise<ManualTransferItemOption[]>((resolve, reject) => {
      frappe.call({
        method: "erpnextkta.kta_shopfloor.api.search_shopfloor_transfer_items",
        args: { source_warehouse: localSource.value, search: searchText.value.trim() || null, limit: 30 },
        quiet: true,
        callback: (r: { message?: ManualTransferItemOption[] }) => resolve(r.message || []),
        error: (err: any) => reject(err),
      });
    });
    if (reqId !== latestSearchId) return;
    searchResults.value = Array.isArray(res) ? res : [];
  } catch (err: any) {
    if (reqId !== latestSearchId) return;
    searchError.value = err?.message || __("Kaynak depodaki malzemeler yüklenemedi.");
    searchResults.value = [];
  } finally {
    if (reqId === latestSearchId) searching.value = false;
  }
}

function isAdded(itemCode: string): boolean {
  return addedLines.value.some((l) => l.item_code === itemCode);
}

function addLine(item: ManualTransferItemOption) {
  if (isAdded(item.item_code)) return;
  const defaultQty = item.free_qty > 0 ? item.free_qty : item.actual_qty;
  addedLines.value.push({ ...item, qty: Number(defaultQty) || 0 });
}

function removeLine(itemCode: string) {
  addedLines.value = addedLines.value.filter((l) => l.item_code !== itemCode);
}

function isLineInvalid(line: SelectedManualLine): boolean {
  const q = Number(line.qty);
  return Number.isNaN(q) || q <= 0 || q > Number(line.actual_qty || 0);
}

function usesReserved(line: SelectedManualLine): boolean {
  const q = Number(line.qty) || 0;
  return q > Number(line.free_qty || 0) && q <= Number(line.actual_qty || 0);
}

const canSubmit = computed(() => {
  if (props.submitting || !localSource.value || !localTarget.value) return false;
  if (localSource.value === localTarget.value || addedLines.value.length === 0) return false;
  return addedLines.value.every((l) => !isLineInvalid(l));
});

function handleClose() {
  if (!props.submitting) emit("close");
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === "Escape" && props.show) handleClose();
}

function handleSubmit() {
  if (!canSubmit.value) return;
  const transfers: LineTransferPayloadItem[] = addedLines.value.map((l) => ({
    item_code: l.item_code,
    qty: Number(l.qty),
    source_warehouse: localSource.value,
    target_warehouse: localTarget.value,
  }));
  const reservedWarnings: ReservedStockWarning[] = addedLines.value
    .filter((l) => usesReserved(l))
    .map((l) => ({
      item_code: l.item_code,
      item_name: l.item_name,
      uom: l.uom,
      source_warehouse: localSource.value,
      target_warehouse: localTarget.value,
      qty: Number(l.qty),
      free_qty: Number(l.free_qty),
      actual_qty: Number(l.actual_qty),
    }));
  emit("submit", transfers, reservedWarnings);
}

function formatQty(val: number | null | undefined): string {
  const num = Number(val ?? 0);
  if (Number.isNaN(num)) return "0";
  return new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 3 }).format(num);
}

onMounted(() => window.addEventListener("keydown", handleKeyDown));
onUnmounted(() => {
  window.removeEventListener("keydown", handleKeyDown);
  if (searchTimer !== null) window.clearTimeout(searchTimer);
});
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="mlt-overlay" @click.self="handleClose">
      <div class="mlt-modal" role="dialog" aria-modal="true">
        <div class="mlt-header">
          <div class="mlt-title-wrap">
            <span class="mlt-icon">🔄</span>
            <div>
              <h3 class="mlt-title">{{ __("Manuel Hat Transferi") }}</h3>
              <p class="mlt-subtitle">{{ __("Üretim hatları arasında serbest veya onaylı stok aktarımı") }}</p>
            </div>
          </div>
          <button type="button" class="mlt-close-btn" :disabled="submitting" :title="__('Kapat')" @click="handleClose">✕</button>
        </div>

        <div class="mlt-body">
          <div class="mlt-wh-grid">
            <div class="mlt-field">
              <label class="mlt-label">{{ __("Kaynak Üretim Hattı") }}</label>
              <select v-model="localSource" class="mlt-input" :disabled="submitting">
                <option value="">{{ __("-- Kaynak Hat Seçin --") }}</option>
                <option v-for="wh in warehouseOptions" :key="wh.warehouse" :value="wh.warehouse">{{ wh.warehouse }}</option>
              </select>
            </div>
            <div class="mlt-field">
              <label class="mlt-label">{{ __("Hedef Üretim Hattı") }}</label>
              <select v-model="localTarget" class="mlt-input" :disabled="submitting || !localSource">
                <option value="">{{ __("-- Hedef Hat Seçin --") }}</option>
                <option v-for="wh in targetOptions" :key="wh.warehouse" :value="wh.warehouse">{{ wh.warehouse }}</option>
              </select>
            </div>
          </div>

          <div class="mlt-search-box">
            <input
              v-model="searchText"
              type="text"
              class="mlt-input"
              :disabled="!localSource || submitting"
              :placeholder="__('Kaynak hatta stoklu hammadde kodu veya adı ara...')"
              @input="scheduleSearch"
              @keydown.enter.prevent="fetchSourceItems"
            />
            <button type="button" class="mlt-search-btn" :disabled="!localSource || searching || submitting" @click="fetchSourceItems">
              🔍 {{ searching ? __("Aranıyor...") : __("Malzeme Ara") }}
            </button>
          </div>

          <div v-if="searchError" class="mlt-err-banner">⚠️ {{ searchError }}</div>

          <div class="mlt-results-box">
            <div class="mlt-section-title">
              {{ __("Kaynak Hat Stok Listesi") }}
              <span v-if="searching" class="mlt-muted">({{ __("Yükleniyor...") }})</span>
            </div>
            <div v-if="searchResults.length === 0 && !searching" class="mlt-empty-small">{{ __("Gösterilecek stoklu malzeme bulunamadı.") }}</div>
            <div v-else class="mlt-results-list">
              <div v-for="item in searchResults" :key="item.item_code" class="mlt-result-row">
                <div class="mlt-result-info">
                  <strong>{{ item.item_code }}</strong>
                  <span class="mlt-muted">{{ item.item_name }}</span>
                  <span class="mlt-stock-chip">
                    {{ __("Serbest Stok") }}: {{ formatQty(item.free_qty) }} / {{ __("Fiziksel") }}: {{ formatQty(item.actual_qty) }} {{ item.uom }}
                  </span>
                </div>
                <button type="button" class="mlt-add-btn" :disabled="isAdded(item.item_code) || submitting" @click="addLine(item)">
                  {{ isAdded(item.item_code) ? `✓ ${__("Eklendi")}` : `+ ${__("Ekle")}` }}
                </button>
              </div>
            </div>
          </div>

          <div v-if="addedLines.length > 0" class="mlt-added-box">
            <div class="mlt-section-title">{{ __("Transfer Edilecek Kalemler ({0})", [addedLines.length]) }}</div>
            <div class="mlt-table-wrap">
              <table class="mlt-table">
                <thead>
                  <tr>
                    <th>{{ __("Malzeme") }}</th>
                    <th class="text-right">{{ __("Serbest / Fiziksel") }}</th>
                    <th class="text-right">{{ __("Aktarılacak Miktar") }}</th>
                    <th class="text-center">{{ __("İşlem") }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="line in addedLines" :key="line.item_code">
                    <td>
                      <div class="mlt-line-item">
                        <strong>{{ line.item_code }}</strong>
                        <span class="mlt-muted">{{ line.item_name }}</span>
                      </div>
                    </td>
                    <td class="text-right">{{ formatQty(line.free_qty) }} / {{ formatQty(line.actual_qty) }} {{ line.uom }}</td>
                    <td class="text-right">
                      <div class="mlt-qty-col">
                        <input
                          v-model.number="line.qty"
                          type="number"
                          min="0.0001"
                          :max="line.actual_qty"
                          step="any"
                          class="mlt-qty-input"
                          :class="{ 'is-error': isLineInvalid(line) }"
                          :disabled="submitting"
                        />
                        <span v-if="isLineInvalid(line)" class="mlt-inline-err">🔴 {{ __("Geçersiz miktar") }}</span>
                        <span v-else-if="usesReserved(line)" class="mlt-inline-warn">⚠️ {{ __("Rezerve stok kullanılacak") }}</span>
                      </div>
                    </td>
                    <td class="text-center">
                      <button type="button" class="mlt-del-btn" :disabled="submitting" :title="__('Satırı Kaldır')" @click="removeLine(line.item_code)">🗑️</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="mlt-footer">
          <button type="button" class="mlt-btn mlt-btn-cancel" :disabled="submitting" @click="handleClose">{{ __("Vazgeç") }}</button>
          <button type="button" class="mlt-btn mlt-btn-primary" :disabled="!canSubmit || submitting" @click="handleSubmit">
            {{ submitting ? __("Transfer Ediliyor...") : __("⚡ Transferi Başlat") }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.mlt-overlay { position: fixed; inset: 0; z-index: 1060; background: rgba(15, 23, 42, 0.58); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.mlt-modal { width: 100%; max-width: 820px; max-height: 90vh; background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.85rem; box-shadow: 0 24px 50px rgba(15, 23, 42, 0.28); display: flex; flex-direction: column; overflow: hidden; }
[data-theme="dark"] .mlt-modal { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); color: #f8fafc; }
.mlt-header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.35rem; border-bottom: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .mlt-header { background: rgba(255, 255, 255, 0.03); }
.mlt-title-wrap { display: flex; align-items: center; gap: 0.65rem; }
.mlt-icon { font-size: 1.35rem; }
.mlt-title { margin: 0; font-size: 1.05rem; font-weight: 800; }
.mlt-subtitle { margin: 0.15rem 0 0; font-size: 0.78rem; color: var(--text-muted, #64748b); }
.mlt-close-btn { background: transparent; border: none; font-size: 1.2rem; color: var(--text-muted, #64748b); cursor: pointer; width: 32px; height: 32px; border-radius: 0.4rem; }
.mlt-close-btn:hover:not(:disabled) { background: rgba(148, 163, 184, 0.18); color: var(--text-color, #0f172a); }
.mlt-body { padding: 1.15rem 1.35rem; overflow-y: auto; display: flex; flex-direction: column; gap: 1rem; }
.mlt-wh-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.85rem; }
@media (max-width: 640px) { .mlt-wh-grid { grid-template-columns: 1fr; } }
.mlt-field { display: flex; flex-direction: column; gap: 0.3rem; }
.mlt-label { font-size: 0.78rem; font-weight: 700; color: var(--text-muted, #475569); }
.mlt-input { width: 100%; padding: 0.48rem 0.65rem; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-size: 0.84rem; font-weight: 600; box-sizing: border-box; }
[data-theme="dark"] .mlt-input { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #f8fafc; }
.mlt-search-box { display: flex; gap: 0.5rem; }
.mlt-search-btn { padding: 0.48rem 0.9rem; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--bg-color, #f1f5f9); color: var(--text-color, #0f172a); font-size: 0.82rem; font-weight: 700; cursor: pointer; white-space: nowrap; }
[data-theme="dark"] .mlt-search-btn { background: rgba(255, 255, 255, 0.08); border-color: rgba(255, 255, 255, 0.18); color: #f8fafc; }
.mlt-err-banner { padding: 0.6rem 0.85rem; border-radius: 0.45rem; background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; font-size: 0.8rem; font-weight: 600; }
.mlt-section-title { font-size: 0.8rem; font-weight: 800; color: var(--text-muted, #475569); margin-bottom: 0.4rem; }
.mlt-results-list { max-height: 190px; overflow-y: auto; border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.5rem; }
.mlt-result-row { display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; padding: 0.55rem 0.8rem; border-bottom: 1px solid var(--border-color, #e2e8f0); }
.mlt-result-row:last-child { border-bottom: none; }
.mlt-result-info { display: flex; flex-direction: column; gap: 0.1rem; font-size: 0.8rem; min-width: 0; }
.mlt-muted { font-size: 0.75rem; color: var(--text-muted, #64748b); }
.mlt-stock-chip { font-size: 0.73rem; font-weight: 700; color: #2563eb; }
[data-theme="dark"] .mlt-stock-chip { color: #60a5fa; }
.mlt-add-btn { padding: 0.32rem 0.7rem; border-radius: 0.4rem; border: 1px solid #2563eb; background: rgba(37, 99, 235, 0.08); color: #2563eb; font-size: 0.76rem; font-weight: 700; cursor: pointer; white-space: nowrap; }
.mlt-add-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.mlt-empty-small { padding: 1rem; text-align: center; font-size: 0.8rem; color: var(--text-muted, #64748b); border: 1px dashed var(--border-color, #cbd5e1); border-radius: 0.5rem; }
.mlt-table-wrap { border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.5rem; overflow-x: auto; }
.mlt-table { width: 100%; border-collapse: collapse; font-size: 0.81rem; text-align: left; }
.mlt-table th { padding: 0.55rem 0.75rem; background: var(--bg-color, #f8fafc); border-bottom: 1px solid var(--border-color, #e2e8f0); font-weight: 700; color: var(--text-muted, #64748b); }
[data-theme="dark"] .mlt-table th { background: rgba(255, 255, 255, 0.04); }
.mlt-table td { padding: 0.55rem 0.75rem; border-bottom: 1px solid var(--border-color, #e2e8f0); vertical-align: middle; }
.mlt-line-item { display: flex; flex-direction: column; }
.mlt-qty-col { display: inline-flex; flex-direction: column; align-items: flex-end; gap: 0.15rem; }
.mlt-qty-input { width: 90px; padding: 0.32rem 0.45rem; text-align: right; border-radius: 0.4rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-weight: 700; }
[data-theme="dark"] .mlt-qty-input { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #f8fafc; }
.mlt-qty-input.is-error { border-color: #dc2626; }
.mlt-inline-warn { font-size: 0.72rem; font-weight: 700; color: #b45309; }
[data-theme="dark"] .mlt-inline-warn { color: #fcd34d; }
.mlt-inline-err { font-size: 0.72rem; font-weight: 700; color: #dc2626; }
.mlt-del-btn { background: transparent; border: none; cursor: pointer; font-size: 0.95rem; }
.text-right { text-align: right !important; }
.text-center { text-align: center !important; }
.mlt-footer { display: flex; justify-content: flex-end; gap: 0.7rem; padding: 0.95rem 1.35rem; border-top: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .mlt-footer { background: rgba(255, 255, 255, 0.02); }
.mlt-btn { padding: 0.52rem 1.1rem; border-radius: 0.5rem; font-size: 0.84rem; font-weight: 700; cursor: pointer; border: none; }
.mlt-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.mlt-btn-cancel { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #cbd5e1); color: var(--text-muted, #475569); }
[data-theme="dark"] .mlt-btn-cancel { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #cbd5e1; }
.mlt-btn-primary { background: #2563eb; color: #ffffff; }
.mlt-btn-primary:hover:not(:disabled) { background: #1d4ed8; }
</style>
