<template>
  <div class="line-replenishment-pda-app">
    <!-- Header -->
    <header class="pda-header">
      <div class="header-content">
        <h1 class="header-title">{{ __("Hat İkmal Toplama (PDA)") }}</h1>
        <span class="header-badge">PDA</span>
      </div>
    </header>

    <!-- Main Container -->
    <main class="pda-main">
      <!-- Order Selector Card -->
      <OrderSelector
        :orders="orders"
        :selected-order-name="selectedOrderName"
        :active-order="activeOrder"
        :loading="loadingOrders"
        @select="onOrderSelected"
        @refresh="loadOpenOrders"
      />

      <!-- Barcode Scanner Bar (visible when an order is active) -->
      <BarcodeScannerBar
        v-if="activeOrder"
        ref="scannerBarRef"
        :disabled="loadingOrderDetails || submittingTransfer"
        :feedback-msg="feedbackMsg"
        :feedback-type="feedbackType"
        @scan="handleBarcodeScan"
        @clear="clearFeedback"
      />

      <!-- Items List -->
      <div v-if="activeOrder" class="items-list-section">
        <div v-if="loadingOrderDetails" class="loading-state">
          <span class="spinner">⏳</span>
          <p>{{ __("Sipariş Kalemleri Yükleniyor...") }}</p>
        </div>

        <div
          v-else-if="!activeOrder.items || activeOrder.items.length === 0"
          class="empty-state"
        >
          <span class="empty-icon">📭</span>
          <p>{{ __("Bu siparişte toplanacak kalem bulunamadı.") }}</p>
        </div>

        <div v-else class="items-list">
          <PickingItemCard
            v-for="item in activeOrder.items"
            :key="item.name"
            :item="item"
            :highlighted="highlightedRowName === item.name"
            @update-qty="(newQty) => updateItemQty(item.name, newQty)"
            @toggle-picked="(isPicked) => toggleItemPicked(item.name, isPicked)"
            @pick-all="pickAllItem(item.name)"
          />
        </div>
      </div>

      <!-- Empty State when no order is selected -->
      <div v-else-if="!loadingOrders" class="empty-state initial-empty">
        <span class="empty-icon">📦</span>
        <p class="empty-text">
          {{ __("Toplama yapmak için yukarıdan açık bir sipariş seçin.") }}
        </p>
      </div>
    </main>

    <!-- Sticky Transfer Footer -->
    <TransferFooter
      v-if="activeOrder && activeOrder.items && activeOrder.items.length > 0"
      :can-complete="canCompleteTransfer"
      :picked-count="pickedItemsCount"
      :total-count="activeOrder.items.length"
      :loading="submittingTransfer"
      @complete="onCompleteTransfer"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from "vue";
import type { ReplenishmentOrder, PickingItem } from "./types";
import { isOverTolerance } from "./types";
import { playBeep } from "./utils/audio";
import OrderSelector from "./components/OrderSelector.vue";
import BarcodeScannerBar from "./components/BarcodeScannerBar.vue";
import PickingItemCard from "./components/PickingItemCard.vue";
import TransferFooter from "./components/TransferFooter.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const orders = ref<ReplenishmentOrder[]>([]);
const selectedOrderName = ref<string>("");
const activeOrder = ref<ReplenishmentOrder | null>(null);
const loadingOrders = ref<boolean>(false);
const loadingOrderDetails = ref<boolean>(false);
const submittingTransfer = ref<boolean>(false);

const feedbackMsg = ref<string>("");
const feedbackType = ref<"success" | "error" | "">("");
const highlightedRowName = ref<string | null>(null);

const scannerBarRef = ref<InstanceType<typeof BarcodeScannerBar> | null>(null);

const pickedItemsCount = computed(() => {
  if (!activeOrder.value || !activeOrder.value.items) return 0;
  return activeOrder.value.items.filter((i) => Boolean(i.is_picked)).length;
});

const canCompleteTransfer = computed(() => {
  if (
    !activeOrder.value ||
    !activeOrder.value.items ||
    activeOrder.value.items.length === 0
  ) {
    return false;
  }
  // All items must be marked as picked and have picked_qty > 0
  const allPicked = activeOrder.value.items.every(
    (i) => (i.is_picked === 1 || Boolean(i.is_picked)) && i.picked_qty > 0
  );
  if (!allPicked) return false;

  // No item should exceed 15% tolerance
  const anyOver = activeOrder.value.items.some((i) =>
    isOverTolerance(i.picked_qty, i.deficit_qty)
  );
  return !anyOver;
});

function clearFeedback() {
  feedbackMsg.value = "";
  feedbackType.value = "";
}

function showFeedback(msg: string, type: "success" | "error") {
  feedbackMsg.value = msg;
  feedbackType.value = type;
}

function focusScanner(clear = false) {
  nextTick(() => {
    if (scannerBarRef.value) {
      scannerBarRef.value.focusInput(clear);
    }
  });
}

function loadOpenOrders() {
  loadingOrders.value = true;
  if (typeof frappe === "undefined" || !frappe.call) {
    loadingOrders.value = false;
    return;
  }

  frappe.call({
    method:
      "erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.get_open_replenishment_orders",
    callback: (r: any) => {
      loadingOrders.value = false;
      orders.value = r.message || [];

      // Auto-select if there is only 1 open order and none selected yet
      if (!selectedOrderName.value && orders.value.length === 1) {
        onOrderSelected(orders.value[0].name);
      }
    },
    error: () => {
      loadingOrders.value = false;
    },
  });
}

function onOrderSelected(orderName: string) {
  selectedOrderName.value = orderName;
  clearFeedback();
  if (!orderName) {
    activeOrder.value = null;
    return;
  }
  loadOrderDetails(orderName);
}

function loadOrderDetails(orderName: string) {
  loadingOrderDetails.value = true;
  if (typeof frappe === "undefined" || !frappe.call) {
    loadingOrderDetails.value = false;
    return;
  }

  frappe.call({
    method:
      "erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.get_replenishment_order_details",
    args: { order_name: orderName },
    callback: (r: any) => {
      loadingOrderDetails.value = false;
      if (r.message) {
        const orderData: ReplenishmentOrder = r.message;
        if (orderData.items) {
          orderData.items.forEach((item) => {
            if (!item.picked_qty || item.picked_qty <= 0) {
              item.picked_qty = item.deficit_qty;
            }
          });
        }
        activeOrder.value = orderData;
        focusScanner(true);
      } else {
        activeOrder.value = null;
      }
    },
    error: () => {
      loadingOrderDetails.value = false;
      activeOrder.value = null;
    },
  });
}

function handleBarcodeScan(barcode: string) {
  const cleanCode = (barcode || "").trim();
  if (!cleanCode || !activeOrder.value || !activeOrder.value.items) return;

  const items = activeOrder.value.items;

  // 1. Check local items: prioritize unpicked item matching suggested_batch_no or item_code
  let matchedItem = items.find(
    (i) =>
      !i.is_picked &&
      (i.suggested_batch_no === cleanCode || i.picked_batch_no === cleanCode)
  );

  if (!matchedItem) {
    matchedItem = items.find((i) => !i.is_picked && i.item_code === cleanCode);
  }

  // Fallback to already picked items if all matching items are already picked
  if (!matchedItem) {
    matchedItem = items.find(
      (i) =>
        i.suggested_batch_no === cleanCode ||
        i.picked_batch_no === cleanCode ||
        i.item_code === cleanCode
    );
  }

  if (matchedItem) {
    const isBatchScan =
      matchedItem.suggested_batch_no === cleanCode ||
      matchedItem.picked_batch_no === cleanCode;

    applySuccessfulMatch(matchedItem, {
      item_code: matchedItem.item_code,
      batch_no: isBatchScan
        ? cleanCode
        : matchedItem.picked_batch_no || matchedItem.suggested_batch_no || null,
      qty: matchedItem.deficit_qty || matchedItem.picked_qty,
      source: isBatchScan ? "Batch" : "Item",
    });
    return;
  }

  // 2. Resolve via backend API (KTA Stock Label, Item Barcode, Batch)
  if (typeof frappe === "undefined" || !frappe.call) return;

  frappe.call({
    method:
      "erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.resolve_scanned_barcode",
    args: { barcode: cleanCode },
    callback: (r: any) => {
      const info = r.message;
      if (info && info.item_code) {
        let backendMatch: PickingItem | undefined;

        // Prioritize unpicked row with matching batch if info has batch_no
        if (info.batch_no) {
          backendMatch = items.find(
            (i) =>
              !i.is_picked &&
              i.item_code === info.item_code &&
              (i.suggested_batch_no === info.batch_no ||
                i.picked_batch_no === info.batch_no)
          );
        }

        // Prioritize unpicked row with matching item_code
        if (!backendMatch) {
          backendMatch = items.find(
            (i) => !i.is_picked && i.item_code === info.item_code
          );
        }

        // Fallback to already picked row
        if (!backendMatch) {
          backendMatch = items.find((i) => i.item_code === info.item_code);
        }

        if (backendMatch) {
          applySuccessfulMatch(backendMatch, info);
          return;
        }
      }

      // Not found in this replenishment order
      playBeep(false);
      showFeedback(
        `❌ ${__("Barkod eşleşmedi veya bu sipariş listesinde yok: {0}", [
          cleanCode,
        ])}`,
        "error"
      );
      focusScanner(true);
    },
    error: () => {
      playBeep(false);
      showFeedback(`❌ ${__("Barkod sorgulanırken hata oluştu.")}`, "error");
      focusScanner(true);
    },
  });
}

function applySuccessfulMatch(item: PickingItem, info: any) {
  item.is_picked = 1;
  if (info.batch_no) {
    item.picked_batch_no = info.batch_no;
  }
  if (info.qty && info.qty > 0) {
    item.picked_qty = info.qty;
  } else if (!item.picked_qty || item.picked_qty <= 0) {
    item.picked_qty = item.deficit_qty;
  }

  playBeep(true);
  const batchLabel = info.batch_no ? ` [${info.batch_no}]` : "";
  showFeedback(
    `✅ ${__("Eşleşti: {0}{1}", [item.item_code, batchLabel])}`,
    "success"
  );

  // Trigger highlight animation and scroll
  highlightedRowName.value = item.name;
  setTimeout(() => {
    if (highlightedRowName.value === item.name) {
      highlightedRowName.value = null;
    }
  }, 1500);

  nextTick(() => {
    const el = document.getElementById(`card-row-${item.name}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });

  focusScanner(true);
}

function updateItemQty(itemName: string, newQty: number) {
  if (!activeOrder.value || !activeOrder.value.items) return;
  const item = activeOrder.value.items.find((i) => i.name === itemName);
  if (item) {
    item.picked_qty = newQty;
    if (newQty > 0) {
      if (!item.is_picked) {
        item.is_picked = 1;
      }
    } else {
      item.is_picked = 0;
    }
  }
}

function toggleItemPicked(itemName: string, isPicked: boolean) {
  if (!activeOrder.value || !activeOrder.value.items) return;
  const item = activeOrder.value.items.find((i) => i.name === itemName);
  if (item) {
    if (isPicked && item.picked_qty <= 0) {
      item.picked_qty = item.deficit_qty;
    }
    item.is_picked = isPicked ? 1 : 0;
  }
}

function pickAllItem(itemName: string) {
  if (!activeOrder.value || !activeOrder.value.items) return;
  const item = activeOrder.value.items.find((i) => i.name === itemName);
  if (item) {
    item.picked_qty = item.deficit_qty;
    item.is_picked = 1;
    playBeep(true);
  }
}

function onCompleteTransfer() {
  if (!activeOrder.value) {
    if (typeof frappe !== "undefined" && frappe.msgprint) {
      frappe.msgprint(__("Lütfen önce bir ikmal siparişi seçiniz."));
    }
    return;
  }

  // Guard: all items must be picked with positive quantity
  const unpickedItems: string[] = [];
  if (activeOrder.value.items) {
    activeOrder.value.items.forEach((item) => {
      if (!item.is_picked || item.picked_qty <= 0) {
        unpickedItems.push(item.item_code);
      }
    });
  }

  if (unpickedItems.length > 0) {
    if (typeof frappe !== "undefined" && frappe.msgprint) {
      frappe.msgprint(
        __(
          "Tüm kalemler toplanmalı ve miktarlar sıfırdan büyük olmalıdır: {0}",
          [unpickedItems.join(", ")]
        )
      );
    }
    return;
  }

  // Double check tolerance
  const overItems: string[] = [];
  if (activeOrder.value.items) {
    activeOrder.value.items.forEach((item) => {
      if (isOverTolerance(item.picked_qty, item.deficit_qty)) {
        overItems.push(item.item_code);
      }
    });
  }

  if (overItems.length > 0) {
    if (typeof frappe !== "undefined" && frappe.msgprint) {
      frappe.msgprint(
        __(
          "Aşağıdaki kalemler için toplanan miktar %15 tolerans sınırını aşıyor: {0}",
          [overItems.join(", ")]
        )
      );
    }
    return;
  }

  const pickedPayload = (activeOrder.value.items || []).map((row) => ({
    name: row.name,
    item_code: row.item_code,
    picked_qty: row.picked_qty,
    picked_source_warehouse:
      row.picked_source_warehouse || row.suggested_source_warehouse,
    picked_batch_no: row.picked_batch_no || row.suggested_batch_no,
    is_picked: row.is_picked,
  }));

  const confirmMsg = __(
    "Seçilen kalemler için Malzeme Transferi (Stock Entry) oluşturulsun mu?"
  );

  const executeTransfer = () => {
    submittingTransfer.value = true;
    frappe.call({
      method:
        "erpnextkta.kta_stock.line_replenishment_service.complete_line_replenishment_picking",
      args: {
        order_name: activeOrder.value!.name,
        picked_items: JSON.stringify(pickedPayload),
      },
      freeze: true,
      freeze_message: __("Malzeme Transferi Gerçekleştiriliyor..."),
      callback: (r: any) => {
        submittingTransfer.value = false;
        if (r.message) {
          playBeep(true);
          if (frappe.show_alert) {
            frappe.show_alert(
              {
                message: `🎉 ${__("Transfer Tamamlandı: {0}", [r.message])}`,
                indicator: "green",
              },
              7
            );
          }
          activeOrder.value = null;
          selectedOrderName.value = "";
          loadOpenOrders();
        }
      },
      error: () => {
        submittingTransfer.value = false;
        playBeep(false);
      },
    });
  };

  if (typeof frappe !== "undefined" && frappe.confirm) {
    frappe.confirm(confirmMsg, () => {
      executeTransfer();
    });
  } else {
    executeTransfer();
  }
}

onMounted(() => {
  loadOpenOrders();
});
</script>

<style scoped>
.line-replenishment-pda-app {
  max-width: 640px;
  margin: 0 auto;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-color, #f8fafc);
  color: var(--text-color, #0f172a);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen,
    Ubuntu, Cantarell, "Open Sans", "Helvetica Neue", sans-serif;
}

.pda-header {
  background-color: #1e293b;
  color: #ffffff;
  padding: 12px 16px;
  border-bottom: 2px solid #334155;
  position: sticky;
  top: 0;
  z-index: 30;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.header-badge {
  background-color: #2563eb;
  color: #ffffff;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 9999px;
  letter-spacing: 0.05em;
}

.pda-main {
  flex: 1;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.items-list-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.loading-state,
.empty-state {
  text-align: center;
  padding: 32px 16px;
  background: var(--card-bg, #ffffff);
  border: 1px dashed var(--border-color, #cbd5e1);
  border-radius: 8px;
  color: #64748b;
}

.initial-empty {
  margin-top: 24px;
}

.empty-icon {
  font-size: 2.5rem;
  display: block;
  margin-bottom: 8px;
}

.empty-text {
  font-size: 0.95rem;
  font-weight: 500;
}

.spinner {
  font-size: 2rem;
  display: inline-block;
  margin-bottom: 8px;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}
</style>
