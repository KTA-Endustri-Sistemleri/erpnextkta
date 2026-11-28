<script setup lang="ts">
import { computed, ref } from "vue";
import type {
  BoxScanResult,
  StockLookupItemResult,
  StockLookupResult,
  StockLookupWarehouseResult,
} from "../types";
import BarcodeScannerBar from "../../line-replenishment-pda/components/BarcodeScannerBar.vue";
import { playBeep } from "../../line-replenishment-pda/utils/audio";

const __ = (...args: any[]) => (window as any).__(...args);

const scannerBarRef = ref<InstanceType<typeof BarcodeScannerBar> | null>(null);
const loading = ref(false);
const result = ref<StockLookupResult | null>(null);
const feedbackMsg = ref("");
const feedbackType = ref<"success" | "error" | "">("");

const batchResult = computed(() =>
  result.value?.kind === "batch"
    ? (result.value as BoxScanResult & { kind: "batch" })
    : null,
);

const warehouseResult = computed(() =>
  result.value?.kind === "warehouse"
    ? (result.value as StockLookupWarehouseResult)
    : null,
);

const itemResult = computed(() =>
  result.value?.kind === "item" ? (result.value as StockLookupItemResult) : null,
);

function clearFeedback() {
  feedbackMsg.value = "";
  feedbackType.value = "";
}

async function onScanLookup(code: string) {
  const cleanCode = code.trim();
  if (!cleanCode || loading.value) return;

  loading.value = true;
  clearFeedback();
  try {
    const res = await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_stock_lookup",
      type: "GET",
      args: { barcode: cleanCode },
      quiet: true,
    });
    const payload = res?.message as StockLookupResult | undefined;
    if (!payload || !payload.kind) {
      playBeep(false);
      feedbackMsg.value = __("Okutulan barkod için kayıt bulunamadı.");
      feedbackType.value = "error";
      return;
    }
    result.value = payload;
    playBeep(true);
    feedbackMsg.value = __("Stok sorgusu güncellendi.");
    feedbackType.value = "success";
  } catch (err: any) {
    playBeep(false);
    result.value = null;
    feedbackMsg.value = err?.message || __("Stok sorgusu yapılamadı.");
    feedbackType.value = "error";
  } finally {
    loading.value = false;
    scannerBarRef.value?.focusInput?.(true);
  }
}
</script>

<template>
  <div class="pda-module-page">
    <BarcodeScannerBar
      ref="scannerBarRef"
      :disabled="loading"
      :feedback-msg="feedbackMsg"
      :feedback-type="feedbackType"
      @scan="onScanLookup"
      @clear="clearFeedback"
    />

    <section v-if="batchResult" class="pda-module-card" data-testid="lookup-batch-card">
      <div class="card-head">
        <div>
          <span class="kind-pill kind-batch">{{ __("Koli / Parti") }}</span>
          <h3 class="pda-empty-title">{{ batchResult.batch_no }}</h3>
          <p class="pda-empty-desc">
            {{ batchResult.item_code }} · {{ batchResult.item_name || batchResult.item_code }}
          </p>
        </div>
        <div class="total-box">
          <span class="pda-meta-label">{{ __("Toplam Bakiye") }}</span>
          <strong class="total-qty">{{ batchResult.total_qty }} {{ batchResult.stock_uom || "" }}</strong>
        </div>
      </div>

      <div class="pda-meta-grid">
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Etiket No") }}</span>
          <strong class="pda-meta-value">{{ batchResult.label_name || "-" }}</strong>
        </div>
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("SUT Barkodu") }}</span>
          <strong class="pda-meta-value">{{ batchResult.sut_barcode || "-" }}</strong>
        </div>
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Son Kullanma") }}</span>
          <strong class="pda-meta-value">{{ batchResult.expiry_date || "-" }}</strong>
        </div>
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Etiket Tipi") }}</span>
          <strong class="pda-meta-value">{{ batchResult.label_type || "-" }}</strong>
        </div>
      </div>

      <div class="rows-section">
        <div class="pda-meta-label">{{ __("Bulunduğu Depolar") }}</div>
        <div v-if="batchResult.balances.length === 0" class="empty-rows">
          {{ __("Aktif stok bakiyesi yok.") }}
        </div>
        <div v-for="row in batchResult.balances" :key="row.warehouse" class="balance-row">
          <span class="row-primary">{{ row.warehouse }}</span>
          <strong class="row-qty">{{ row.qty }} {{ batchResult.stock_uom || "" }}</strong>
        </div>
      </div>
    </section>

    <section v-else-if="warehouseResult" class="pda-module-card" data-testid="lookup-warehouse-card">
      <div class="card-head">
        <div>
          <span class="kind-pill kind-warehouse">{{ __("Depo / Raf") }}</span>
          <h3 class="pda-empty-title">{{ warehouseResult.warehouse_name || warehouseResult.warehouse }}</h3>
          <p class="pda-empty-desc">{{ warehouseResult.warehouse }} · {{ warehouseResult.company }}</p>
        </div>
        <div class="total-box">
          <span class="pda-meta-label">{{ __("Kalem Sayısı") }}</span>
          <strong class="total-qty">{{ warehouseResult.items.length }}</strong>
        </div>
      </div>

      <div class="rows-section">
        <div class="pda-meta-label">{{ __("Raftaki Malzemeler") }}</div>
        <div v-if="warehouseResult.items.length === 0" class="empty-rows">
          {{ __("Bu rafta stok bulunmuyor.") }}
        </div>
        <div v-for="item in warehouseResult.items" :key="item.item_code" class="balance-row">
          <div class="row-stack">
            <span class="row-primary">{{ item.item_code }}</span>
            <span class="row-sub">{{ item.item_name || "" }}</span>
          </div>
          <div class="row-right">
            <strong class="row-qty">{{ item.actual_qty }} {{ item.stock_uom || "" }}</strong>
            <span v-if="Number(item.reserved_qty || 0) > 0" class="row-sub">
              {{ __("Rezerve") }}: {{ item.reserved_qty }}
            </span>
          </div>
        </div>
      </div>
    </section>

    <section v-else-if="itemResult" class="pda-module-card" data-testid="lookup-item-card">
      <div class="card-head">
        <div>
          <span class="kind-pill kind-item">{{ __("Malzeme") }}</span>
          <h3 class="pda-empty-title">{{ itemResult.item_code }}</h3>
          <p class="pda-empty-desc">{{ itemResult.item_name || itemResult.item_code }}</p>
        </div>
        <div class="total-box">
          <span class="pda-meta-label">{{ __("Toplam Stok") }}</span>
          <strong class="total-qty">{{ itemResult.total_qty }} {{ itemResult.stock_uom || "" }}</strong>
        </div>
      </div>

      <div class="rows-section">
        <div class="pda-meta-label">{{ __("Depo Bakiyeleri") }}</div>
        <div v-if="itemResult.warehouses.length === 0" class="empty-rows">
          {{ __("Depolarda stok bulunmuyor.") }}
        </div>
        <div v-for="wh in itemResult.warehouses" :key="wh.warehouse" class="balance-row">
          <span class="row-primary">{{ wh.warehouse }}</span>
          <div class="row-right">
            <strong class="row-qty">{{ wh.qty }} {{ itemResult.stock_uom || "" }}</strong>
            <span v-if="Number(wh.reserved_qty || 0) > 0" class="row-sub">
              {{ __("Rezerve") }}: {{ wh.reserved_qty }}
            </span>
          </div>
        </div>
      </div>

      <div v-if="itemResult.batches.length > 0" class="rows-section">
        <div class="pda-meta-label">{{ __("Parti Dağılımı") }}</div>
        <div v-for="b in itemResult.batches" :key="`${b.warehouse}-${b.batch_no}`" class="balance-row">
          <div class="row-stack">
            <span class="row-primary">{{ b.batch_no }}</span>
            <span class="row-sub">{{ b.warehouse }}</span>
          </div>
          <strong class="row-qty">{{ b.qty }} {{ itemResult.stock_uom || "" }}</strong>
        </div>
      </div>
    </section>

    <div v-else class="pda-empty-hint-card">
      <div class="pda-empty-icon">🔍</div>
      <div class="pda-empty-title">{{ __("Stok ve Etiket Sorgula") }}</div>
      <p class="pda-empty-desc">
        {{ __("Koli, raf veya malzeme barkodunu okutarak anlık stok durumunu görüntüleyin.") }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.kind-pill {
  display: inline-block;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
  margin-bottom: 4px;
}
.kind-batch { background: rgba(37, 99, 235, 0.14); color: var(--pda-primary); }
.kind-warehouse { background: rgba(22, 163, 74, 0.14); color: var(--pda-success); }
.kind-item { background: rgba(99, 102, 241, 0.16); color: #4f46e5; }
[data-theme="dark"] .kind-item { color: #a5b4fc; }
.total-box { text-align: right; display: flex; flex-direction: column; }
.total-qty { font-size: 1.1rem; font-weight: 800; color: var(--pda-primary); }
.rows-section { display: flex; flex-direction: column; gap: 6px; }
.balance-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 9px 11px;
  border-radius: 10px;
  background: var(--pda-surface-alt);
  border: 1px solid var(--border-color);
}
.row-stack, .row-right { display: flex; flex-direction: column; min-width: 0; }
.row-right { text-align: right; white-space: nowrap; }
.row-primary { font-size: 0.88rem; font-weight: 700; word-break: break-word; }
.row-sub { font-size: 0.74rem; color: var(--text-muted); }
.row-qty { font-size: 0.94rem; font-weight: 800; }
.empty-rows { font-size: 0.84rem; color: var(--text-muted); padding: 8px 0; }
</style>
