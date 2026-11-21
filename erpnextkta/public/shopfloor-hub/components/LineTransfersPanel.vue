<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import type {
  LineTransferSubMode,
  ProductionWarehouseOption,
  LineTransferDeficitItem,
  LineIdleStockItem,
  LineTransferPayloadItem,
  LineTransferResponse,
  ProductionSupplyReturnPayloadItem,
  ProductionSupplyReturnResponse,
  SupplyReturnDraftInput,
  ReservedStockWarning,
} from "../types";
import LineTransferHeader from "./LineTransferHeader.vue";
import LineDeficitTransferTable from "./LineDeficitTransferTable.vue";
import LineIdleStockTable from "./LineIdleStockTable.vue";
import ManualLineTransferModal from "./ManualLineTransferModal.vue";
import ProductionSupplyReturnModal from "./ProductionSupplyReturnModal.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(defineProps<{ initialTargetWarehouse?: string | null }>(), {
  initialTargetWarehouse: null,
});

const productionWarehouses = ref<ProductionWarehouseOption[]>([]);
const activeMode = ref<LineTransferSubMode>("deficit_pull");
const selectedWarehouse = ref<string>("");
const deficitItems = ref<LineTransferDeficitItem[]>([]);
const idleItems = ref<LineIdleStockItem[]>([]);
const loading = ref<boolean>(false);
const submitting = ref<boolean>(false);
const errorMessage = ref<string | null>(null);
const lastSuccess = ref<LineTransferResponse | ProductionSupplyReturnResponse | null>(null);
const lastSuccessKind = ref<"transfer" | "return">("transfer");
const showManualModal = ref<boolean>(false);
const showReturnModal = ref<boolean>(false);
const returnDraftRows = ref<SupplyReturnDraftInput[]>([]);
const showReservedModal = ref<boolean>(false);
const pendingTransfers = ref<LineTransferPayloadItem[]>([]);
const pendingSplitPackages = ref<boolean>(false);
const pendingReturnPayload = ref<{
  items: ProductionSupplyReturnPayloadItem[];
  targetWarehouse: string;
  remarks: string;
} | null>(null);
const pendingWarnings = ref<ReservedStockWarning[]>([]);

const lastSuccessEntries = computed<string[]>(() => {
  const res = lastSuccess.value;
  if (!res) return [];
  if (Array.isArray(res.stock_entries) && res.stock_entries.length > 0) return res.stock_entries;
  if ("stock_entry" in res && res.stock_entry) return [res.stock_entry];
  return [];
});

const lastSuccessPrintedLabels = computed(() => Number(lastSuccess.value?.printed_labels || 0));

function callFrappe<T = any>(method: string, args: Record<string, any> = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    frappe.call({
      method,
      args,
      quiet: true,
      callback: (r: { message?: T }) => {
        if ((window as any).frappe) (window as any).frappe.messages = [];
        resolve(r.message as T);
      },
      error: (err: any) => {
        if ((window as any).frappe) (window as any).frappe.messages = [];
        reject(err);
      },
    });
  });
}

function extractError(err: any, fallback: string): string {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  if (err._server_messages) {
    try {
      const parsed = JSON.parse(err._server_messages);
      if (Array.isArray(parsed) && parsed.length) {
        const msgs = parsed
          .map((x: any) => {
            if (typeof x !== "string") return x?.message || String(x);
            try { return JSON.parse(x)?.message || x; } catch { return x; }
          })
          .filter(Boolean);
        if (msgs.length) return msgs.join(" ");
      }
    } catch { /* fallback */ }
  }
  return err.message || fallback;
}

async function fetchProductionWarehouses() {
  try {
    const res = await callFrappe<ProductionWarehouseOption[]>("erpnextkta.kta_shopfloor.api.get_shopfloor_production_warehouses");
    productionWarehouses.value = Array.isArray(res) ? res : [];
  } catch (err) {
    console.error("get_shopfloor_production_warehouses error:", err);
  }
}

async function loadActiveList() {
  if (!selectedWarehouse.value) {
    deficitItems.value = [];
    idleItems.value = [];
    return;
  }
  loading.value = true;
  errorMessage.value = null;
  try {
    if (activeMode.value === "deficit_pull") {
      const res = await callFrappe<LineTransferDeficitItem[]>("erpnextkta.kta_shopfloor.api.get_shopfloor_line_deficits", { target_warehouse: selectedWarehouse.value });
      deficitItems.value = Array.isArray(res) ? res : [];
    } else {
      const res = await callFrappe<LineIdleStockItem[]>("erpnextkta.kta_shopfloor.api.get_shopfloor_idle_stock", { source_warehouse: selectedWarehouse.value });
      idleItems.value = Array.isArray(res) ? res : [];
    }
  } catch (err: any) {
    errorMessage.value = extractError(err, __("Hat transfer listesi yüklenirken bir hata oluştu."));
  } finally {
    loading.value = false;
  }
}

function handleModeChange(mode: LineTransferSubMode) {
  activeMode.value = mode;
  errorMessage.value = null;
  if (selectedWarehouse.value) loadActiveList();
}

function handleWarehouseChange(wh: string) {
  selectedWarehouse.value = wh;
  lastSuccess.value = null;
  loadActiveList();
}

function findReservedOverages(transfers: LineTransferPayloadItem[]): ReservedStockWarning[] {
  const aggQty = new Map<string, number>();
  const metaMap = new Map<string, { free_qty: number; actual_qty: number; item_name?: string; uom?: string; target: string }>();
  for (const t of transfers) {
    const key = `${t.item_code}::${t.source_warehouse}`;
    aggQty.set(key, (aggQty.get(key) || 0) + Number(t.qty || 0));
    if (metaMap.has(key)) continue;
    if (activeMode.value === "deficit_pull") {
      const defRow = deficitItems.value.find((d) => d.item_code === t.item_code);
      const src = defRow?.available_sources.find((s) => s.warehouse === t.source_warehouse);
      if (src) metaMap.set(key, { free_qty: Number(src.free_qty || 0), actual_qty: Number(src.actual_qty || 0), item_name: defRow?.item_name, uom: defRow?.uom, target: t.target_warehouse });
    } else {
      const idleRow = idleItems.value.find((i) => i.item_code === t.item_code && i.source_warehouse === t.source_warehouse);
      if (idleRow) metaMap.set(key, { free_qty: Number(idleRow.free_qty || 0), actual_qty: Number(idleRow.actual_qty || 0), item_name: idleRow.item_name, uom: idleRow.uom, target: t.target_warehouse });
    }
  }
  const warnings: ReservedStockWarning[] = [];
  for (const [key, totalQty] of aggQty.entries()) {
    const info = metaMap.get(key);
    if (info && totalQty > info.free_qty) {
      const [item_code, source_warehouse] = key.split("::");
      warnings.push({ item_code, item_name: info.item_name, uom: info.uom, source_warehouse, target_warehouse: info.target, qty: totalQty, free_qty: info.free_qty, actual_qty: info.actual_qty });
    }
  }
  return warnings;
}

function initiateTransfer(transfers: LineTransferPayloadItem[], explicitWarnings?: ReservedStockWarning[], splitPackages = false) {
  const warnings = explicitWarnings !== undefined ? explicitWarnings : findReservedOverages(transfers);
  pendingReturnPayload.value = null;
  pendingSplitPackages.value = Boolean(splitPackages);
  if (warnings.length > 0) {
    pendingTransfers.value = transfers;
    pendingWarnings.value = warnings;
    showReservedModal.value = true;
    return;
  }
  executeTransfer(transfers, false, Boolean(splitPackages));
}

function openSupplyReturnModal(rows: SupplyReturnDraftInput[]) {
  returnDraftRows.value = rows;
  showReturnModal.value = true;
}

function handleSupplyReturnSubmit(
  payload: { items: ProductionSupplyReturnPayloadItem[]; targetWarehouse: string; remarks: string },
  reservedWarnings: ReservedStockWarning[]
) {
  pendingTransfers.value = [];
  pendingSplitPackages.value = false;
  pendingReturnPayload.value = payload;
  if (reservedWarnings.length > 0) {
    pendingWarnings.value = reservedWarnings;
    showReservedModal.value = true;
    return;
  }
  executeSupplyReturn(payload, false);
}

function confirmReservedOverride() {
  if (pendingReturnPayload.value) executeSupplyReturn(pendingReturnPayload.value, true);
  else executeTransfer(pendingTransfers.value, true, pendingSplitPackages.value);
}

async function executeTransfer(transfers: LineTransferPayloadItem[], allowReservedOverride: boolean, splitPackages: boolean) {
  if (submitting.value || !transfers.length) return;
  submitting.value = true;
  errorMessage.value = null;
  try {
    const res = await callFrappe<LineTransferResponse>("erpnextkta.kta_shopfloor.api.execute_shopfloor_line_transfer", {
      transfers,
      allow_reserved_override: allowReservedOverride ? 1 : 0,
      split_packages: splitPackages ? 1 : 0,
    });
    if (res && res.success) {
      showReservedModal.value = false;
      showManualModal.value = false;
      pendingTransfers.value = [];
      pendingWarnings.value = [];
      lastSuccessKind.value = "transfer";
      lastSuccess.value = res;
      (window as any).frappe?.show_alert?.({ message: __("Hatlar Arası Transfer Tamamlandı: {0}", [res.stock_entry]), indicator: "green" });
      await loadActiveList();
    } else {
      throw new Error(res?.message || __("Transfer tamamlanamadı."));
    }
  } catch (err: any) {
    errorMessage.value = extractError(err, __("Hatlar arası transfer sırasında bir hata oluştu."));
    showReservedModal.value = false;
  } finally {
    submitting.value = false;
  }
}

async function executeSupplyReturn(
  payload: { items: ProductionSupplyReturnPayloadItem[]; targetWarehouse: string; remarks: string },
  allowReservedOverride: boolean
) {
  if (submitting.value || !payload.items.length) return;
  submitting.value = true;
  errorMessage.value = null;
  try {
    const res = await callFrappe<ProductionSupplyReturnResponse>("erpnextkta.kta_shopfloor.api.execute_shopfloor_supply_return", {
      items: payload.items,
      target_warehouse: payload.targetWarehouse,
      allow_reserved_override: allowReservedOverride ? 1 : 0,
      remarks: payload.remarks || null,
    });
    if (res && res.success) {
      showReservedModal.value = false;
      showReturnModal.value = false;
      pendingReturnPayload.value = null;
      pendingWarnings.value = [];
      lastSuccessKind.value = "return";
      lastSuccess.value = res;
      (window as any).frappe?.show_alert?.({ message: res.message || __("Depoya iade işlemi başarıyla tamamlandı."), indicator: "green" });
      await loadActiveList();
    } else {
      throw new Error(res?.message || __("Depoya iade işlemi tamamlanamadı."));
    }
  } catch (err: any) {
    errorMessage.value = extractError(err, __("Depoya iade işlemi sırasında bir hata oluştu."));
    showReservedModal.value = false;
  } finally {
    submitting.value = false;
  }
}

function closeReservedModal() {
  if (!submitting.value) showReservedModal.value = false;
}

function handleEsc(e: KeyboardEvent) {
  if (e.key === "Escape" && showReservedModal.value) closeReservedModal();
}

function formatQty(val: number | null | undefined): string {
  const num = Number(val ?? 0);
  if (Number.isNaN(num)) return "0";
  return new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 3 }).format(num);
}

watch(
  () => props.initialTargetWarehouse,
  (wh) => {
    if (wh) {
      activeMode.value = "deficit_pull";
      selectedWarehouse.value = wh;
      lastSuccess.value = null;
      loadActiveList();
    }
  }
);

onMounted(() => {
  window.addEventListener("keydown", handleEsc);
  fetchProductionWarehouses();
  if (props.initialTargetWarehouse) {
    activeMode.value = "deficit_pull";
    selectedWarehouse.value = props.initialTargetWarehouse;
    loadActiveList();
  }
});

onUnmounted(() => window.removeEventListener("keydown", handleEsc));
</script>

<template>
  <div class="lt-panel">
    <LineTransferHeader
      :mode="activeMode"
      :selected-warehouse="selectedWarehouse"
      :production-warehouses="productionWarehouses"
      :loading="loading || submitting"
      @update:mode="handleModeChange"
      @update:selected-warehouse="handleWarehouseChange"
      @refresh="loadActiveList"
      @open-manual="showManualModal = true"
    />

    <div v-if="errorMessage" class="lt-alert lt-alert-danger" role="alert">
      <div class="lt-alert-left"><span>⚠️</span><span>{{ errorMessage }}</span></div>
      <button type="button" class="lt-alert-close" @click="errorMessage = null">✕</button>
    </div>

    <div v-if="lastSuccess" class="lt-alert lt-alert-success" role="status">
      <div class="lt-alert-left">
        <span>✅</span>
        <div>
          <strong>
            {{ lastSuccessKind === "return" ? __("Depoya İade İşlemi Tamamlandı") : __("Hatlar Arası Transfer Başarıyla Tamamlandı") }}
          </strong>
          <div class="lt-success-meta">
            <a v-for="se in lastSuccessEntries" :key="se" :href="`/app/stock-entry/${se}`" target="_blank" class="lt-se-link">
              📦 {{ __("Stok Fişi") }}: {{ se }} ↗
            </a>
            <span v-if="lastSuccessPrintedLabels > 0" class="lt-printed-badge">
              🏷️ {{ __("{0} adet etiket yazdırıldı / kuyruğa alındı.", [lastSuccessPrintedLabels]) }}
            </span>
          </div>
        </div>
      </div>
      <button type="button" class="lt-alert-close" @click="lastSuccess = null">✕</button>
    </div>

    <LineDeficitTransferTable
      v-if="activeMode === 'deficit_pull'"
      :items="deficitItems"
      :target-warehouse="selectedWarehouse"
      :loading="loading"
      :submitting="submitting"
      @execute-transfer="(items) => initiateTransfer(items, undefined, false)"
    />

    <LineIdleStockTable
      v-else
      :items="idleItems"
      :source-warehouse="selectedWarehouse"
      :production-warehouses="productionWarehouses"
      :loading="loading"
      :submitting="submitting"
      @execute-transfer="(items, splitPkgs) => initiateTransfer(items, undefined, splitPkgs)"
      @open-supply-return="openSupplyReturnModal"
    />

    <ManualLineTransferModal
      :show="showManualModal"
      :source-warehouse="selectedWarehouse"
      :production-warehouses="productionWarehouses"
      :submitting="submitting"
      @close="showManualModal = false"
      @submit="(t, w, splitPkgs) => initiateTransfer(t, w, splitPkgs)"
    />

    <ProductionSupplyReturnModal
      :show="showReturnModal"
      :source-warehouse="selectedWarehouse"
      :initial-items="returnDraftRows"
      :submitting="submitting"
      @close="showReturnModal = false"
      @submit="handleSupplyReturnSubmit"
    />

    <Teleport to="body">
      <div v-if="showReservedModal" class="lt-modal-overlay" @click.self="closeReservedModal">
        <div class="lt-modal" role="dialog" aria-modal="true">
          <div class="lt-modal-header">
            <h3 class="lt-modal-title">⚠️ {{ __("Öncelik Kaydırma (Rezerve Stok Kullanımı) Onayı") }}</h3>
            <button type="button" class="lt-modal-close" :disabled="submitting" @click="closeReservedModal">✕</button>
          </div>
          <div class="lt-modal-body">
            <p class="lt-modal-desc">
              {{ __("Aşağıdaki kalemlerde istenen transfer miktarı kaynak hattaki serbest (rezerve dışı) stoğu aşmaktadır. Onaylarsanız diğer iş emirlerine rezerve edilmiş stoktan öncelik kaydırılarak transfer yapılacaktır.") }}
            </p>
            <div class="lt-warn-table-wrap">
              <table class="lt-warn-table">
                <thead>
                  <tr>
                    <th>{{ __("Malzeme") }}</th>
                    <th>{{ __("Kaynak Hat") }}</th>
                    <th class="text-right">{{ __("Talep Edilen") }}</th>
                    <th class="text-right">{{ __("Serbest Stok") }}</th>
                    <th class="text-right">{{ __("Fiziksel") }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="w in pendingWarnings" :key="`${w.item_code}::${w.source_warehouse}`">
                    <td><strong>{{ w.item_code }}</strong></td>
                    <td>{{ w.source_warehouse }}</td>
                    <td class="text-right warn-qty">{{ formatQty(w.qty) }} {{ w.uom || "" }}</td>
                    <td class="text-right">{{ formatQty(w.free_qty) }} {{ w.uom || "" }}</td>
                    <td class="text-right">{{ formatQty(w.actual_qty) }} {{ w.uom || "" }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="lt-modal-footer">
            <button type="button" class="lt-mbtn lt-mbtn-cancel" :disabled="submitting" @click="closeReservedModal">{{ __("Vazgeç") }}</button>
            <button type="button" class="lt-mbtn lt-mbtn-confirm" :disabled="submitting" @click="confirmReservedOverride">
              {{ submitting ? __("Transfer Ediliyor...") : __("Onayla ve Transfer Et") }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.lt-panel { display: flex; flex-direction: column; gap: 1rem; }
.lt-alert { display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; padding: 0.85rem 1.15rem; border-radius: 0.65rem; font-size: 0.86rem; }
.lt-alert-danger { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
[data-theme="dark"] .lt-alert-danger { background: rgba(239, 68, 68, 0.16); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.lt-alert-success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
[data-theme="dark"] .lt-alert-success { background: rgba(34, 197, 94, 0.16); border-color: rgba(74, 222, 128, 0.35); color: #86efac; }
.lt-alert-left { display: flex; align-items: center; gap: 0.65rem; }
.lt-success-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem; margin-top: 0.25rem; }
.lt-se-link { font-weight: 700; text-decoration: underline; color: inherit; }
.lt-printed-badge { font-weight: 700; font-size: 0.8rem; }
.lt-alert-close { background: transparent; border: none; color: inherit; cursor: pointer; font-size: 1rem; opacity: 0.7; }
.lt-modal-overlay { position: fixed; inset: 0; z-index: 1070; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.lt-modal { width: 100%; max-width: 660px; max-height: 88vh; display: flex; flex-direction: column; background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.85rem; box-shadow: 0 24px 50px rgba(15, 23, 42, 0.28); overflow: hidden; }
[data-theme="dark"] .lt-modal { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); color: #f8fafc; }
.lt-modal-header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.25rem; background: #fffbeb; border-bottom: 1px solid #fde68a; color: #b45309; }
[data-theme="dark"] .lt-modal-header { background: rgba(245, 158, 11, 0.18); border-bottom-color: rgba(251, 191, 36, 0.3); color: #fcd34d; }
.lt-modal-title { margin: 0; font-size: 1rem; font-weight: 800; }
.lt-modal-close { background: transparent; border: none; color: inherit; font-size: 1.15rem; cursor: pointer; }
.lt-modal-body { padding: 1.15rem 1.25rem; overflow-y: auto; display: flex; flex-direction: column; gap: 0.85rem; }
.lt-modal-desc { margin: 0; font-size: 0.85rem; line-height: 1.45; }
.lt-warn-table-wrap { border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.5rem; overflow-x: auto; }
.lt-warn-table { width: 100%; border-collapse: collapse; font-size: 0.81rem; text-align: left; }
.lt-warn-table th { padding: 0.55rem 0.75rem; background: var(--bg-color, #f8fafc); border-bottom: 1px solid var(--border-color, #e2e8f0); color: var(--text-muted, #64748b); }
[data-theme="dark"] .lt-warn-table th { background: rgba(255, 255, 255, 0.04); }
.lt-warn-table td { padding: 0.55rem 0.75rem; border-bottom: 1px solid var(--border-color, #e2e8f0); }
.text-right { text-align: right !important; }
.warn-qty { font-weight: 800; color: #d97706; }
[data-theme="dark"] .warn-qty { color: #fbbf24; }
.lt-modal-footer { display: flex; justify-content: flex-end; gap: 0.65rem; padding: 0.9rem 1.25rem; border-top: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .lt-modal-footer { background: rgba(255, 255, 255, 0.02); }
.lt-mbtn { padding: 0.52rem 1.05rem; border-radius: 0.5rem; font-size: 0.84rem; font-weight: 700; cursor: pointer; border: none; }
.lt-mbtn:disabled { opacity: 0.55; cursor: not-allowed; }
.lt-mbtn-cancel { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #cbd5e1); color: var(--text-muted, #475569); }
[data-theme="dark"] .lt-mbtn-cancel { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #cbd5e1; }
.lt-mbtn-confirm { background: #d97706; color: #ffffff; }
.lt-mbtn-confirm:hover:not(:disabled) { background: #b45309; }
</style>
