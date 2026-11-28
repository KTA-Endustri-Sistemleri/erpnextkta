<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import type {
  AvailableBatchOption,
  RawMaterialReturnWarehouseOption,
  ProductionSupplyReturnPayloadItem,
  ReservedStockWarning,
  SupplyReturnDraftInput,
} from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

interface ReturnRowDraft {
  item_code: string;
  item_name: string;
  uom: string;
  source_warehouse: string;
  actual_qty: number;
  reserved_qty: number;
  free_qty: number;
  available_batches: AvailableBatchOption[];
  qty: number;
  batch_no: string;
}

const props = withDefaults(
  defineProps<{
    show: boolean;
    sourceWarehouse: string;
    initialItems: SupplyReturnDraftInput[];
    submitting?: boolean;
  }>(),
  { submitting: false }
);

const emit = defineEmits<{
  (e: "close"): void;
  (
    e: "submit",
    payload: {
      items: ProductionSupplyReturnPayloadItem[];
      targetWarehouse: string;
      remarks: string;
    },
    reservedWarnings: ReservedStockWarning[]
  ): void;
}>();

const returnWarehouses = ref<RawMaterialReturnWarehouseOption[]>([]);
const loadingWarehouses = ref<boolean>(false);
const warehouseError = ref<string | null>(null);
const targetWarehouse = ref<string>("");
const remarks = ref<string>("");
const rows = ref<ReturnRowDraft[]>([]);

async function fetchReturnWarehouses() {
  loadingWarehouses.value = true;
  warehouseError.value = null;
  try {
    const res = await new Promise<RawMaterialReturnWarehouseOption[]>(
      (resolve, reject) => {
        frappe.call({
          method: "erpnextkta.kta_shopfloor.api.get_raw_material_return_warehouses",
          args: {},
          quiet: true,
          callback: (r: { message?: RawMaterialReturnWarehouseOption[] }) =>
            resolve(r.message || []),
          error: (err: any) => reject(err),
        });
      }
    );
    returnWarehouses.value = Array.isArray(res) ? res : [];
    if (
      targetWarehouse.value &&
      !returnWarehouses.value.some((w) => w.warehouse === targetWarehouse.value)
    ) {
      targetWarehouse.value = "";
    }
    if (!targetWarehouse.value && returnWarehouses.value.length === 1) {
      targetWarehouse.value = returnWarehouses.value[0].warehouse;
    }
  } catch (err: any) {
    warehouseError.value =
      err?.message || __("110 hammadde iade rafları yüklenemedi.");
    returnWarehouses.value = [];
  } finally {
    loadingWarehouses.value = false;
  }
}

watch(
  () => props.show,
  (isOpen) => {
    if (!isOpen) return;
    remarks.value = "";
    rows.value = (props.initialItems || []).map((entry) => ({
      item_code: entry.item.item_code,
      item_name: entry.item.item_name || entry.item.item_code,
      uom: entry.item.uom || "",
      source_warehouse: entry.item.source_warehouse,
      actual_qty: Number(entry.item.actual_qty || 0),
      reserved_qty: Number(entry.item.reserved_qty || 0),
      free_qty: Number(entry.item.free_qty || 0),
      available_batches: entry.item.available_batches || [],
      qty: Number(entry.qty || 0),
      batch_no: "",
    }));
    fetchReturnWarehouses();
  },
  { immediate: true }
);

function getSelectedBatch(row: ReturnRowDraft): AvailableBatchOption | undefined {
  if (!row.batch_no) return undefined;
  return row.available_batches.find((b) => b.batch_no === row.batch_no);
}

function getRowMaxQty(row: ReturnRowDraft): number {
  const batch = getSelectedBatch(row);
  if (batch) return Math.min(Number(batch.qty || 0), Number(row.actual_qty || 0));
  return Number(row.actual_qty || 0);
}

function onBatchChange(row: ReturnRowDraft) {
  const max = getRowMaxQty(row);
  if (row.batch_no && Number(row.qty) > max) {
    row.qty = Number(max.toFixed(4));
  }
}

function getRowError(row: ReturnRowDraft): string | null {
  const qty = Number(row.qty);
  if (Number.isNaN(qty) || qty <= 0) return __("Geçersiz miktar");
  const batch = getSelectedBatch(row);
  if (batch && qty > Number(batch.qty || 0)) {
    return __("Seçili parti bakiyesi aşıldı ({0})", [formatQty(batch.qty)]);
  }
  if (qty > Number(row.actual_qty || 0)) {
    return __("Hat stoğu sınırı aşıldı");
  }
  return null;
}

function usesReserved(row: ReturnRowDraft): boolean {
  if (getRowError(row)) return false;
  return Number(row.qty) > Number(row.free_qty || 0);
}

function removeRow(itemCode: string) {
  rows.value = rows.value.filter((r) => r.item_code !== itemCode);
}

const canSubmit = computed(() => {
  if (props.submitting || loadingWarehouses.value) return false;
  if (!targetWarehouse.value || rows.value.length === 0) return false;
  return rows.value.every((r) => !getRowError(r));
});

function handleClose() {
  if (!props.submitting) emit("close");
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === "Escape" && props.show) handleClose();
}

function handleSubmit() {
  if (!canSubmit.value) return;
  const items: ProductionSupplyReturnPayloadItem[] = rows.value.map((r) => ({
    item_code: r.item_code,
    qty: Number(r.qty),
    source_warehouse: r.source_warehouse,
    target_warehouse: targetWarehouse.value,
    batch_no: r.batch_no || null,
  }));
  const reservedWarnings: ReservedStockWarning[] = rows.value
    .filter((r) => usesReserved(r))
    .map((r) => ({
      item_code: r.item_code,
      item_name: r.item_name,
      uom: r.uom,
      source_warehouse: r.source_warehouse,
      target_warehouse: targetWarehouse.value,
      qty: Number(r.qty),
      free_qty: Number(r.free_qty),
      actual_qty: Number(r.actual_qty),
    }));
  emit(
    "submit",
    {
      items,
      targetWarehouse: targetWarehouse.value,
      remarks: remarks.value.trim(),
    },
    reservedWarnings
  );
}

function formatQty(val: number | null | undefined): string {
  const num = Number(val ?? 0);
  if (Number.isNaN(num)) return "0";
  return new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 3,
  }).format(num);
}

onMounted(() => window.addEventListener("keydown", handleKeyDown));
onUnmounted(() => window.removeEventListener("keydown", handleKeyDown));
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="psr-overlay" @click.self="handleClose">
      <div class="psr-modal" role="dialog" aria-modal="true">
        <div class="psr-header">
          <div class="psr-title-wrap">
            <span class="psr-icon">↩️</span>
            <div>
              <h3 class="psr-title">{{ __("Üretim Tedarik Alanından Depoya İade (110)") }}</h3>
              <p class="psr-subtitle">{{ __("Kaynak Üretim Hattı: {0}", [sourceWarehouse]) }}</p>
            </div>
          </div>
          <button type="button" class="psr-close-btn" :disabled="submitting" :title="__('Kapat')" @click="handleClose">✕</button>
        </div>

        <div class="psr-body">
          <div class="psr-info-banner">
            <span>ℹ️</span>
            <span>
              {{ __("Tam kalan standart kutular Return from Production Supply fişiyle iade edilir; kısmi bölünen veya LEGACY partiler otomatik Package Split ile 110 depoya etiketlenerek aktarılır.") }}
            </span>
          </div>

          <div v-if="warehouseError" class="psr-err-banner">⚠️ {{ warehouseError }}</div>

          <div class="psr-form-grid">
            <div class="psr-field">
              <label class="psr-label">{{ __("Hedef 110 Hammadde Rafı") }}</label>
              <select v-model="targetWarehouse" class="psr-input" :disabled="loadingWarehouses || submitting">
                <option value="">{{ loadingWarehouses ? __("Yükleniyor...") : __("-- Hedef 110 Rafı Seçin --") }}</option>
                <option v-for="wh in returnWarehouses" :key="wh.warehouse" :value="wh.warehouse">
                  {{ wh.warehouse }}
                </option>
              </select>
            </div>
            <div class="psr-field">
              <label class="psr-label">{{ __("Açıklama (Opsiyonel)") }}</label>
              <input v-model="remarks" type="text" class="psr-input" :disabled="submitting" :placeholder="__('İade nedeni veya not ekleyin...')" />
            </div>
          </div>

          <div v-if="rows.length === 0" class="psr-empty">{{ __("İade edilecek kalem bulunmuyor.") }}</div>
          <div v-else class="psr-table-wrap">
            <table class="psr-table">
              <thead>
                <tr>
                  <th>{{ __("Malzeme") }}</th>
                  <th>{{ __("Kaynak Kutu / Parti") }}</th>
                  <th class="text-right">{{ __("Serbest / Fiziksel") }}</th>
                  <th class="text-right">{{ __("İade Miktarı") }}</th>
                  <th class="text-center">{{ __("İşlem") }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rows" :key="row.item_code">
                  <td>
                    <div class="psr-item-cell">
                      <strong>{{ row.item_code }}</strong>
                      <span v-if="row.item_name !== row.item_code" class="psr-muted">{{ row.item_name }}</span>
                    </div>
                  </td>
                  <td>
                    <select v-model="row.batch_no" class="psr-input psr-batch-select" :disabled="submitting" @change="onBatchChange(row)">
                      <option value="">{{ __("Otomatik (LIFO — Yeni Açılan İlk)") }}</option>
                      <option v-for="b in row.available_batches" :key="b.batch_no" :value="b.batch_no">
                        {{ b.batch_no }} ({{ formatQty(b.qty) }} {{ row.uom }})
                      </option>
                    </select>
                  </td>
                  <td class="text-right psr-nowrap">
                    {{ formatQty(row.free_qty) }} / {{ formatQty(row.actual_qty) }} {{ row.uom }}
                  </td>
                  <td class="text-right">
                    <div class="psr-qty-col">
                      <input
                        v-model.number="row.qty"
                        type="number"
                        step="any"
                        min="0.0001"
                        :max="getRowMaxQty(row)"
                        class="psr-qty-input"
                        :class="{ 'is-error': Boolean(getRowError(row)) }"
                        :disabled="submitting"
                      />
                      <span v-if="getRowError(row)" class="psr-inline-err">🔴 {{ getRowError(row) }}</span>
                      <span v-else-if="usesReserved(row)" class="psr-inline-warn">⚠️ {{ __("Rezerve stok kullanılacak") }}</span>
                    </div>
                  </td>
                  <td class="text-center">
                    <button type="button" class="psr-del-btn" :disabled="submitting || rows.length <= 1" :title="__('Satırı Kaldır')" @click="removeRow(row.item_code)">🗑️</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="psr-footer">
          <button type="button" class="psr-btn psr-btn-cancel" :disabled="submitting" @click="handleClose">{{ __("Vazgeç") }}</button>
          <button type="button" class="psr-btn psr-btn-primary" :disabled="!canSubmit" @click="handleSubmit">
            {{ submitting ? __("İade İşleniyor...") : __("↩️ Depoya İade Et") }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.psr-overlay { position: fixed; inset: 0; z-index: 1060; background: rgba(15, 23, 42, 0.58); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.psr-modal { width: 100%; max-width: 880px; max-height: 90vh; background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.85rem; box-shadow: 0 24px 50px rgba(15, 23, 42, 0.28); display: flex; flex-direction: column; overflow: hidden; }
[data-theme="dark"] .psr-modal { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); color: #f8fafc; }
.psr-header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.35rem; border-bottom: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .psr-header { background: rgba(255, 255, 255, 0.03); }
.psr-title-wrap { display: flex; align-items: center; gap: 0.65rem; }
.psr-icon { font-size: 1.35rem; }
.psr-title { margin: 0; font-size: 1.05rem; font-weight: 800; }
.psr-subtitle { margin: 0.15rem 0 0; font-size: 0.78rem; color: var(--text-muted, #64748b); }
.psr-close-btn { background: transparent; border: none; font-size: 1.2rem; color: var(--text-muted, #64748b); cursor: pointer; width: 32px; height: 32px; border-radius: 0.4rem; }
.psr-body { padding: 1.15rem 1.35rem; overflow-y: auto; display: flex; flex-direction: column; gap: 0.95rem; }
.psr-info-banner { display: flex; gap: 0.6rem; align-items: flex-start; padding: 0.7rem 0.95rem; border-radius: 0.55rem; background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; font-size: 0.8rem; font-weight: 600; line-height: 1.4; }
[data-theme="dark"] .psr-info-banner { background: rgba(59, 130, 246, 0.15); border-color: rgba(96, 165, 250, 0.35); color: #93c5fd; }
.psr-err-banner { padding: 0.65rem 0.85rem; border-radius: 0.5rem; background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; font-size: 0.8rem; font-weight: 600; }
.psr-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.85rem; }
@media (max-width: 640px) { .psr-form-grid { grid-template-columns: 1fr; } }
.psr-field { display: flex; flex-direction: column; gap: 0.3rem; }
.psr-label { font-size: 0.78rem; font-weight: 700; color: var(--text-muted, #475569); }
.psr-input { width: 100%; padding: 0.46rem 0.65rem; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-size: 0.82rem; font-weight: 600; box-sizing: border-box; }
[data-theme="dark"] .psr-input { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #f8fafc; }
.psr-batch-select { min-width: 220px; }
.psr-empty { padding: 1.5rem; text-align: center; color: var(--text-muted, #64748b); }
.psr-table-wrap { border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.55rem; overflow-x: auto; }
.psr-table { width: 100%; border-collapse: collapse; font-size: 0.81rem; text-align: left; }
.psr-table th { padding: 0.6rem 0.75rem; background: var(--bg-color, #f8fafc); border-bottom: 1px solid var(--border-color, #e2e8f0); font-weight: 700; color: var(--text-muted, #64748b); white-space: nowrap; }
[data-theme="dark"] .psr-table th { background: rgba(255, 255, 255, 0.04); }
.psr-table td { padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--border-color, #e2e8f0); vertical-align: middle; }
.psr-item-cell { display: flex; flex-direction: column; gap: 0.1rem; }
.psr-muted { font-size: 0.74rem; color: var(--text-muted, #64748b); }
.psr-nowrap { white-space: nowrap; }
.psr-qty-col { display: inline-flex; flex-direction: column; align-items: flex-end; gap: 0.15rem; }
.psr-qty-input { width: 92px; padding: 0.34rem 0.45rem; text-align: right; border-radius: 0.4rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-weight: 700; }
[data-theme="dark"] .psr-qty-input { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #f8fafc; }
.psr-qty-input.is-error { border-color: #dc2626; }
.psr-inline-warn { font-size: 0.72rem; font-weight: 700; color: #b45309; }
[data-theme="dark"] .psr-inline-warn { color: #fcd34d; }
.psr-inline-err { font-size: 0.72rem; font-weight: 700; color: #dc2626; }
.psr-del-btn { background: transparent; border: none; cursor: pointer; font-size: 0.95rem; }
.psr-del-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.text-right { text-align: right !important; }
.text-center { text-align: center !important; }
.psr-footer { display: flex; justify-content: flex-end; gap: 0.7rem; padding: 0.95rem 1.35rem; border-top: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .psr-footer { background: rgba(255, 255, 255, 0.02); }
.psr-btn { padding: 0.52rem 1.1rem; border-radius: 0.5rem; font-size: 0.84rem; font-weight: 700; cursor: pointer; border: none; }
.psr-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.psr-btn-cancel { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #cbd5e1); color: var(--text-muted, #475569); }
[data-theme="dark"] .psr-btn-cancel { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #cbd5e1; }
.psr-btn-primary { background: #2563eb; color: #ffffff; }
.psr-btn-primary:hover:not(:disabled) { background: #1d4ed8; }
</style>
