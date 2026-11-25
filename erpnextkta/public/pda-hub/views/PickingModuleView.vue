<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import type { PickingItem, ReplenishmentOrder } from "../../line-replenishment-pda/types";
import { isOverTolerance } from "../../line-replenishment-pda/types";
import { playBeep } from "../../line-replenishment-pda/utils/audio";
import OrderSelector from "../../line-replenishment-pda/components/OrderSelector.vue";
import BarcodeScannerBar from "../../line-replenishment-pda/components/BarcodeScannerBar.vue";
import PickingItemCard from "../../line-replenishment-pda/components/PickingItemCard.vue";
import TransferFooter from "../../line-replenishment-pda/components/TransferFooter.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const emit = defineEmits<{
  (e: "orders-updated", count: number): void;
}>();

const orders = ref<ReplenishmentOrder[]>([]);
const selectedOrderName = ref("");
const activeOrder = ref<ReplenishmentOrder | null>(null);
const loadingOrders = ref(false);
const loadingOrderDetails = ref(false);
const submittingTransfer = ref(false);
const highlightedRow = ref<string | null>(null);
const feedbackMsg = ref("");
const feedbackType = ref<"success" | "error" | "info" | "">("");
const scannerBarRef = ref<InstanceType<typeof BarcodeScannerBar> | null>(null);

let highlightTimer: ReturnType<typeof setTimeout> | null = null;

const pickedItemsCount = computed(() => {
  if (!activeOrder.value?.items) return 0;
  return activeOrder.value.items.filter(
    (row) => row.is_picked && Number(row.picked_qty || 0) > 0,
  ).length;
});

const canCompleteTransfer = computed(() => {
  return Boolean(activeOrder.value && !submittingTransfer.value && pickedItemsCount.value > 0);
});

function showFeedback(msg: string, type: "success" | "error" | "info") {
  feedbackMsg.value = msg;
  feedbackType.value = type;
}

function clearFeedback() {
  feedbackMsg.value = "";
  feedbackType.value = "";
}

function highlightCard(rowName: string) {
  highlightedRow.value = rowName;
  if (highlightTimer) clearTimeout(highlightTimer);
  highlightTimer = setTimeout(() => {
    highlightedRow.value = null;
  }, 1600);
  nextTick(() => {
    const el = document.getElementById(`card-row-${rowName}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  });
}

async function loadOpenOrders() {
  loadingOrders.value = true;
  try {
    const res = await window.frappe.call({
      method:
        "erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.get_open_replenishment_orders",
    });
    orders.value = Array.isArray(res?.message) ? res.message : [];
    emit("orders-updated", orders.value.length);
    if (orders.value.length === 1 && !selectedOrderName.value) {
      await onSelectOrder(orders.value[0].name);
    }
  } catch (err: any) {
    showFeedback(err?.message || __("Açık ikmal emirleri yüklenemedi."), "error");
  } finally {
    loadingOrders.value = false;
  }
}

async function loadOrderDetails(orderName: string) {
  loadingOrderDetails.value = true;
  clearFeedback();
  try {
    const res = await window.frappe.call({
      method:
        "erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.get_replenishment_order_details",
      args: { order_name: orderName },
    });
    const order = res?.message as ReplenishmentOrder | undefined;
    if (!order) {
      activeOrder.value = null;
      return;
    }
    if (Array.isArray(order.items)) {
      order.items.forEach((row) => {
        if (Number(row.picked_qty || 0) <= 0) {
          row.picked_qty = row.deficit_qty;
        }
      });
    }
    activeOrder.value = order;
    await nextTick();
    scannerBarRef.value?.focusInput?.(false);
  } catch (err: any) {
    showFeedback(err?.message || __("Emir detayları alınamadı."), "error");
  } finally {
    loadingOrderDetails.value = false;
  }
}

async function onSelectOrder(orderName: string) {
  selectedOrderName.value = orderName;
  if (!orderName) {
    activeOrder.value = null;
    clearFeedback();
    return;
  }
  await loadOrderDetails(orderName);
}

function findMatchingRow(itemCode: string, batchNo?: string): PickingItem | undefined {
  const items = activeOrder.value?.items || [];
  if (batchNo) {
    const exactMatch = items.find(
      (r) =>
        r.item_code === itemCode &&
        !r.is_picked &&
        (r.picked_batch_no === batchNo || r.suggested_batch_no === batchNo),
    );
    if (exactMatch) return exactMatch;
  }
  const unpicked = items.find((r) => r.item_code === itemCode && !r.is_picked);
  if (unpicked) return unpicked;
  return items.find((r) => r.item_code === itemCode);
}

async function onBarcodeScan(code: string) {
  const cleanCode = code.trim();
  if (!cleanCode || !activeOrder.value) return;

  clearFeedback();
  try {
    const res = await window.frappe.call({
      method:
        "erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.resolve_scanned_barcode",
      args: { barcode: cleanCode },
    });
    const resolved = res?.message;
    if (!resolved?.item_code) {
      playBeep(false);
      showFeedback(__("Barkod tanınamadı veya sistemde bulunamadı."), "error");
      scannerBarRef.value?.focusInput?.(true);
      return;
    }

    const row = findMatchingRow(resolved.item_code, resolved.batch_no);
    if (!row) {
      playBeep(false);
      showFeedback(
        __("Okutulan malzeme bu ikmal emrinde yer almıyor."),
        "error",
      );
      scannerBarRef.value?.focusInput?.(true);
      return;
    }

    const scanQty = Number(resolved.qty || 0) > 0 ? Number(resolved.qty) : row.deficit_qty;
    const nextQty = row.is_picked
      ? Number(row.picked_qty || 0) + scanQty
      : scanQty;

    if (isOverTolerance(nextQty, row.deficit_qty)) {
      playBeep(false);
      showFeedback(__("Okutulan miktar tolerans sınırını aşıyor."), "error");
      scannerBarRef.value?.focusInput?.(true);
      return;
    }

    row.picked_qty = nextQty;
    if (resolved.batch_no) {
      row.picked_batch_no = resolved.batch_no;
    }
    if (resolved.warehouse) {
      row.picked_source_warehouse = resolved.warehouse;
    }
    row.is_picked = true;
    playBeep(true);
    highlightCard(row.name);
    showFeedback(
      __("Malzeme okutuldu ve toplandı olarak işaretlendi."),
      "success",
    );
    scannerBarRef.value?.focusInput?.(true);
  } catch (err: any) {
    playBeep(false);
    showFeedback(err?.message || __("Barkod çözümleme sırasında hata oluştu."), "error");
    scannerBarRef.value?.focusInput?.(true);
  }
}

function onUpdateQty(row: PickingItem, newQty: number) {
  const numericQty = Number(newQty);
  if (Number.isNaN(numericQty) || numericQty < 0) return;
  if (isOverTolerance(numericQty, row.deficit_qty)) {
    playBeep(false);
    showFeedback(__("Girilen miktar tolerans sınırını aşıyor."), "error");
    return;
  }
  clearFeedback();
  row.picked_qty = numericQty;
  row.is_picked = numericQty > 0;
}

function onTogglePicked(row: PickingItem) {
  clearFeedback();
  row.is_picked = !row.is_picked;
  if (row.is_picked && Number(row.picked_qty || 0) <= 0) {
    row.picked_qty = row.deficit_qty;
  }
}

function onPickAll(row: PickingItem) {
  clearFeedback();
  row.picked_qty = row.deficit_qty;
  row.is_picked = true;
  playBeep(true);
}

async function onCompleteTransfer() {
  if (!activeOrder.value || submittingTransfer.value) return;

  const pickedPayload = activeOrder.value.items
    .filter((row) => row.is_picked && Number(row.picked_qty || 0) > 0)
    .map((row) => ({
      name: row.name,
      item_code: row.item_code,
      deficit_qty: row.deficit_qty,
      picked_qty: row.picked_qty,
      picked_source_warehouse:
        row.picked_source_warehouse || row.suggested_source_warehouse || "",
      picked_batch_no: row.picked_batch_no || row.suggested_batch_no || "",
      is_picked: row.is_picked,
    }));

  if (pickedPayload.length === 0) {
    showFeedback(__("Transfer için en az bir kalem seçilmelidir."), "error");
    return;
  }

  submittingTransfer.value = true;
  clearFeedback();
  try {
    await window.frappe.call({
      method:
        "erpnextkta.kta_stock.line_replenishment_service.complete_line_replenishment_picking",
      args: {
        order_name: activeOrder.value.name,
        picked_items: JSON.stringify(pickedPayload),
      },
      freeze: true,
      freeze_message: __("Malzeme Transferi Gerçekleştiriliyor..."),
    });
    playBeep(true);
    window.frappe.show_alert({
      message: __("Malzeme transferi başarıyla tamamlandı."),
      indicator: "green",
    });
    activeOrder.value = null;
    selectedOrderName.value = "";
    await loadOpenOrders();
  } catch (err: any) {
    playBeep(false);
    showFeedback(err?.message || __("Transfer tamamlanamadı."), "error");
  } finally {
    submittingTransfer.value = false;
  }
}

onMounted(() => {
  void loadOpenOrders();
});
</script>

<template>
  <div class="pda-picking-view">
    <OrderSelector
      :orders="orders"
      :selected-order-name="selectedOrderName"
      :active-order="activeOrder"
      :loading="loadingOrders || loadingOrderDetails"
      @select="onSelectOrder"
      @refresh="loadOpenOrders"
    />

    <BarcodeScannerBar
      v-if="activeOrder"
      ref="scannerBarRef"
      :disabled="loadingOrderDetails || submittingTransfer"
      :feedback-msg="feedbackMsg"
      :feedback-type="feedbackType"
      @scan="onBarcodeScan"
      @clear="clearFeedback"
    />

    <div v-else-if="feedbackMsg" class="pda-picking-alert">
      {{ feedbackMsg }}
    </div>

    <div v-if="activeOrder" class="pda-picking-list">
      <PickingItemCard
        v-for="row in activeOrder.items"
        :key="row.name"
        :item="row"
        :highlighted="highlightedRow === row.name"
        @update-qty="(val) => onUpdateQty(row, val)"
        @toggle-picked="onTogglePicked(row)"
        @pick-all="onPickAll(row)"
      />
    </div>

    <div v-else-if="!loadingOrders && orders.length === 0" class="pda-picking-empty">
      <div class="pda-picking-empty-icon">📦</div>
      <div class="pda-picking-empty-title">{{ __("Açık İkmal Emri Yok") }}</div>
      <div class="pda-picking-empty-sub">
        {{ __("Yeni hat ikmal emri oluşturulduğunda burada listelenir.") }}
      </div>
    </div>

    <TransferFooter
      v-if="activeOrder"
      :can-complete="canCompleteTransfer"
      :picked-count="pickedItemsCount"
      :total-count="activeOrder.items.length"
      :loading="submittingTransfer"
      @complete="onCompleteTransfer"
    />
  </div>
</template>

<style scoped>
.pda-picking-view {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 56px);
  padding-bottom: 92px;
  background: var(--bg-color);
  color: var(--text-color);
}

.pda-picking-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 12px 16px;
}

.pda-picking-alert {
  margin: 10px 12px 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--pda-danger);
  font-size: 0.9rem;
  font-weight: 600;
}

.pda-picking-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 48px 20px;
  margin: 16px 12px;
  background: var(--card-bg);
  border: 1px dashed var(--border-color);
  border-radius: 14px;
}

.pda-picking-empty-icon {
  font-size: 2.2rem;
  margin-bottom: 8px;
}

.pda-picking-empty-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-color);
}

.pda-picking-empty-sub {
  margin-top: 4px;
  font-size: 0.85rem;
  color: var(--text-muted);
}
</style>
