// Copyright (c) 2026, KTA and Contributors
// See license.txt

import { computed, nextTick, ref } from "vue";
import {
  type FifoOverrideCandidate,
  type PickingItem,
  type ReplenishmentOrder,
  type ScanResult,
  compareShelfNames,
  isOverTolerance,
} from "../types";
import { playBeep } from "../utils/audio";

const __ = (...args: any[]) => (window as any).__(...args);

export interface UseLineReplenishmentPickingOptions {
  onOrdersUpdated?: (count: number) => void;
  confirmTransfer?: (
    message: string,
    onConfirm: () => void | Promise<void>,
  ) => void;
}

export function isBatchTrackedRow(row: PickingItem): boolean {
  if (row.suggested_batch_no) return true;
  return row.has_batch_no !== 0 && row.has_batch_no !== false;
}

export function useLineReplenishmentPicking(
  options: UseLineReplenishmentPickingOptions = {},
) {
  const orders = ref<ReplenishmentOrder[]>([]);
  const selectedOrderName = ref("");
  const activeOrder = ref<ReplenishmentOrder | null>(null);
  const loadingOrders = ref(false);
  const loadingOrderDetails = ref(false);
  const submittingTransfer = ref(false);
  const highlightedRow = ref<string | null>(null);
  const feedbackMsg = ref("");
  const feedbackType = ref<"success" | "error" | "info" | "">("");
  const activeTab = ref<"pending" | "picked" | "skipped">("pending");
  const fifoModalCandidate = ref<FifoOverrideCandidate | null>(null);
  const skipModalItem = ref<PickingItem | null>(null);
  const scannerBarRef = ref<any>(null);

  let highlightTimer: ReturnType<typeof setTimeout> | null = null;

  const allItems = computed(() => activeOrder.value?.items || []);

  const pendingItems = computed(() =>
    allItems.value.filter(
      (r) => !Boolean(r.is_picked) && !Boolean(r.is_skipped),
    ),
  );

  const pickedItems = computed(() =>
    allItems.value.filter(
      (r) => Boolean(r.is_picked) && !Boolean(r.is_skipped),
    ),
  );

  const skippedItems = computed(() =>
    allItems.value.filter((r) => Boolean(r.is_skipped)),
  );

  const totalCount = computed(() => allItems.value.length);
  const pendingCount = computed(() => pendingItems.value.length);
  const pickedCount = computed(() => pickedItems.value.length);
  const skippedCount = computed(() => skippedItems.value.length);

  const allSkipped = computed(
    () =>
      totalCount.value > 0 &&
      pendingCount.value === 0 &&
      pickedCount.value === 0 &&
      skippedCount.value === totalCount.value,
  );

  const canSkipItems = computed(() =>
    Boolean(activeOrder.value?.can_skip_items),
  );

  const anyNonBatchOverTolerance = computed(() =>
    pickedItems.value.some(
      (r) =>
        !isBatchTrackedRow(r) && isOverTolerance(r.picked_qty, r.deficit_qty),
    ),
  );

  const canCompleteTransfer = computed(() => {
    if (!activeOrder.value || submittingTransfer.value) return false;
    if (totalCount.value === 0 || pendingCount.value > 0) return false;
    if (anyNonBatchOverTolerance.value) return false;
    return pickedItems.value.every((r) => Number(r.picked_qty || 0) > 0);
  });

  const visibleItems = computed(() => {
    if (activeTab.value === "picked") return pickedItems.value;
    if (activeTab.value === "skipped") return skippedItems.value;
    return pendingItems.value;
  });

  function showFeedback(msg: string, type: "success" | "error" | "info") {
    feedbackMsg.value = msg;
    feedbackType.value = type;
  }

  function clearFeedback() {
    feedbackMsg.value = "";
    feedbackType.value = "";
  }

  function focusScanner(clear = false) {
    nextTick(() => {
      scannerBarRef.value?.focusInput?.(clear);
    });
  }

  function highlightCard(rowName: string) {
    highlightedRow.value = rowName;
    if (highlightTimer) clearTimeout(highlightTimer);
    highlightTimer = setTimeout(() => {
      if (highlightedRow.value === rowName) {
        highlightedRow.value = null;
      }
    }, 1600);
    nextTick(() => {
      const el = document.getElementById(`card-row-${rowName}`);
      el?.scrollIntoView?.({ behavior: "smooth", block: "center" });
    });
  }

  async function loadOpenOrders() {
    loadingOrders.value = true;
    try {
      const res = await window.frappe.call({
        method:
          "erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.get_open_replenishment_orders",
        quiet: true,
      });
      orders.value = Array.isArray(res?.message) ? res.message : [];
      options.onOrdersUpdated?.(orders.value.length);
      if (orders.value.length === 1 && !selectedOrderName.value) {
        await onSelectOrder(orders.value[0].name);
      }
    } catch (err: any) {
      showFeedback(
        err?.message || __("Açık ikmal emirleri yüklenemedi."),
        "error",
      );
    } finally {
      loadingOrders.value = false;
    }
  }

  async function loadOrderDetails(orderName: string) {
    loadingOrderDetails.value = true;
    clearFeedback();
    fifoModalCandidate.value = null;
    skipModalItem.value = null;
    activeTab.value = "pending";
    try {
      const res = await window.frappe.call({
        method:
          "erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.get_replenishment_order_details",
        args: { order_name: orderName },
        quiet: true,
      });
      const order = res?.message as ReplenishmentOrder | undefined;
      if (!order) {
        activeOrder.value = null;
        return;
      }
      if (Array.isArray(order.items)) {
        const indexed = order.items.map((row, idx) => ({ row, idx }));
        indexed.sort((a, b) => {
          const whCmp = compareShelfNames(
            a.row.suggested_source_warehouse,
            b.row.suggested_source_warehouse,
          );
          if (whCmp !== 0) return whCmp;
          const itemCmp = (a.row.item_code || "").localeCompare(
            b.row.item_code || "",
          );
          if (itemCmp !== 0) return itemCmp;
          const batchCmp = (a.row.suggested_batch_no || "").localeCompare(
            b.row.suggested_batch_no || "",
          );
          if (batchCmp !== 0) return batchCmp;
          return a.idx - b.idx;
        });

        order.items = indexed.map(({ row }) => {
          const isSkipped = Boolean(row.is_skipped) ? 1 : 0;
          const isPicked = !isSkipped && Boolean(row.is_picked) ? 1 : 0;
          return {
            ...row,
            is_picked: isPicked,
            is_skipped: isSkipped,
            is_fifo_override: Boolean(row.is_fifo_override) ? 1 : 0,
            picked_qty: isSkipped
              ? 0
              : Number(row.picked_qty || 0) > 0
                ? Number(row.picked_qty)
                : Number(row.deficit_qty || 0),
          };
        });
      } else {
        order.items = [];
      }

      activeOrder.value = order;
      focusScanner(false);
    } catch (err: any) {
      activeOrder.value = null;
      showFeedback(err?.message || __("Emir detayları alınamadı."), "error");
    } finally {
      loadingOrderDetails.value = false;
    }
  }

  async function onSelectOrder(orderName: string) {
    selectedOrderName.value = orderName;
    if (!orderName) {
      activeOrder.value = null;
      fifoModalCandidate.value = null;
      skipModalItem.value = null;
      clearFeedback();
      return;
    }
    await loadOrderDetails(orderName);
  }

  async function onBarcodeScan(code: string) {
    const cleanCode = (code || "").trim();
    if (!cleanCode || !activeOrder.value) return;
    if (fifoModalCandidate.value || skipModalItem.value) return;

    clearFeedback();
    try {
      const res = await window.frappe.call({
        method:
          "erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.resolve_scanned_barcode",
        args: {
          barcode: cleanCode,
          order_name: activeOrder.value.name,
        },
        quiet: true,
      });
      const resolved = res?.message as ScanResult | undefined;

      // Case 1: Unknown barcode
      if (!resolved?.item_code) {
        playBeep(false);
        showFeedback(
          __("Barkod tanınamadı veya sistemde bulunamadı."),
          "error",
        );
        focusScanner(true);
        return;
      }

      // Case 2: Item not in this order
      const items = allItems.value;
      const itemRows = items.filter((r) => r.item_code === resolved.item_code);
      if (itemRows.length === 0) {
        playBeep(false);
        showFeedback(
          __("Okutulan malzeme bu ikmal emrinde yer almıyor."),
          "error",
        );
        focusScanner(true);
        return;
      }

      // Case 3: Duplicate scan guard
      if (resolved.batch_no) {
        const duplicateBatchRow = items.find(
          (r) =>
            Boolean(r.is_picked) &&
            !Boolean(r.is_skipped) &&
            r.picked_batch_no === resolved.batch_no,
        );
        if (duplicateBatchRow) {
          playBeep(false);
          showFeedback(
            __("Bu koli ({0}) zaten okutuldu.", [resolved.batch_no]),
            "info",
          );
          focusScanner(true);
          return;
        }
      }

      const pendingItemRows = itemRows.filter(
        (r) => !Boolean(r.is_picked) && !Boolean(r.is_skipped),
      );

      if (
        !resolved.batch_no &&
        pendingItemRows.length === 0 &&
        itemRows.some((r) => Boolean(r.is_picked) && !isBatchTrackedRow(r))
      ) {
        playBeep(false);
        showFeedback(
          __("Bu koli ({0}) zaten okutuldu.", [resolved.item_code]),
          "info",
        );
        focusScanner(true);
        return;
      }

      // Case 4: Disabled batch / already in target / zero balance
      if (resolved.batch_disabled) {
        playBeep(false);
        showFeedback(__("Okutulan parti pasif durumdadır."), "error");
        focusScanner(true);
        return;
      }

      if (resolved.already_in_target) {
        playBeep(false);
        showFeedback(
          __("Bu koli zaten hedef üretim hattında ({0}) bulunuyor.", [
            activeOrder.value.target_warehouse,
          ]),
          "error",
        );
        focusScanner(true);
        return;
      }

      if (
        resolved.batch_no &&
        (!resolved.warehouse || Number(resolved.qty || 0) <= 0)
      ) {
        playBeep(false);
        showFeedback(
          __("Bu partinin uygun kaynak raflarda kullanılabilir bakiyesi yok."),
          "error",
        );
        focusScanner(true);
        return;
      }

      // Case 5: Bare item_code / item barcode on batch-tracked item
      if (
        !resolved.batch_no &&
        pendingItemRows.some((r) => isBatchTrackedRow(r))
      ) {
        playBeep(false);
        showFeedback(
          __(
            "Bu malzeme parti takiplidir. Lütfen koli/SUT parti barkodunu okutun.",
          ),
          "error",
        );
        focusScanner(true);
        return;
      }

      if (resolved.batch_no) {
        // Case 6: Out-of-order exact FIFO batch match across ALL pending rows
        const exactPendingRow = pendingItemRows.find(
          (r) => r.suggested_batch_no === resolved.batch_no,
        );
        if (exactPendingRow) {
          exactPendingRow.is_picked = 1;
          exactPendingRow.is_skipped = 0;
          exactPendingRow.is_fifo_override = 0;
          exactPendingRow.picked_batch_no = resolved.batch_no;
          exactPendingRow.picked_source_warehouse =
            resolved.warehouse ||
            exactPendingRow.suggested_source_warehouse ||
            "";
          exactPendingRow.picked_qty =
            Number(resolved.qty || 0) > 0
              ? Number(resolved.qty)
              : exactPendingRow.deficit_qty;
          playBeep(true);
          highlightCard(exactPendingRow.name);
          showFeedback(
            __("Okutuldu: {0} [{1}]", [
              exactPendingRow.item_code,
              resolved.batch_no,
            ]),
            "success",
          );
          focusScanner(true);
          return;
        }

        // Case 7: FIFO deviation -> open confirmation modal
        const candidateRow =
          pendingItemRows.find((r) => isBatchTrackedRow(r)) ||
          pendingItemRows[0];
        if (!candidateRow) {
          playBeep(false);
          showFeedback(__("Bu malzemenin bekleyen kolisi kalmadı."), "error");
          focusScanner(true);
          return;
        }

        playBeep(false);
        fifoModalCandidate.value = { row: candidateRow, resolved };
        return;
      }

      // Case 8: Non-batch item exception
      const nonBatchRow = pendingItemRows.find((r) => !isBatchTrackedRow(r));
      if (!nonBatchRow) {
        playBeep(false);
        showFeedback(__("Bu malzemenin bekleyen kolisi kalmadı."), "error");
        focusScanner(true);
        return;
      }

      const nextQty =
        Number(nonBatchRow.picked_qty || 0) > 0
          ? Number(nonBatchRow.picked_qty)
          : Number(nonBatchRow.deficit_qty || 0);
      if (isOverTolerance(nextQty, nonBatchRow.deficit_qty)) {
        playBeep(false);
        showFeedback(__("Okutulan miktar tolerans sınırını aşıyor."), "error");
        focusScanner(true);
        return;
      }

      nonBatchRow.picked_qty = nextQty;
      nonBatchRow.is_picked = 1;
      nonBatchRow.is_skipped = 0;
      nonBatchRow.is_fifo_override = 0;
      nonBatchRow.picked_source_warehouse =
        nonBatchRow.picked_source_warehouse ||
        nonBatchRow.suggested_source_warehouse ||
        "";
      playBeep(true);
      highlightCard(nonBatchRow.name);
      showFeedback(__("Okutuldu: {0}", [nonBatchRow.item_code]), "success");
      focusScanner(true);
    } catch (err: any) {
      playBeep(false);
      showFeedback(
        err?.message || __("Barkod çözümleme sırasında hata oluştu."),
        "error",
      );
      focusScanner(true);
    }
  }

  function confirmFifoOverride() {
    const candidate = fifoModalCandidate.value;
    if (!candidate) return;
    const { row, resolved } = candidate;
    row.is_picked = 1;
    row.is_skipped = 0;
    row.is_fifo_override = 1;
    row.picked_batch_no = resolved.batch_no || "";
    row.picked_source_warehouse =
      resolved.warehouse || row.suggested_source_warehouse || "";
    row.picked_qty =
      Number(resolved.qty || 0) > 0 ? Number(resolved.qty) : row.deficit_qty;
    fifoModalCandidate.value = null;
    playBeep(true);
    highlightCard(row.name);
    showFeedback(
      __("FIFO sapması onaylandı: {0} [{1}]", [
        row.item_code,
        row.picked_batch_no,
      ]),
      "success",
    );
    focusScanner(true);
  }

  function cancelFifoOverride() {
    fifoModalCandidate.value = null;
    focusScanner(true);
  }

  function requestSkipItem(row: PickingItem) {
    if (!canSkipItems.value) return;
    skipModalItem.value = row;
  }

  function confirmSkipItem() {
    const row = skipModalItem.value;
    if (!row || !canSkipItems.value) return;
    row.is_skipped = 1;
    row.is_picked = 0;
    row.picked_qty = 0;
    row.is_fifo_override = 0;
    row.picked_batch_no = "";
    row.picked_source_warehouse = "";
    skipModalItem.value = null;
    playBeep(true);
    showFeedback(__("Kalem atlandı: {0}", [row.item_code]), "info");
    focusScanner(true);
  }

  function cancelSkipItem() {
    skipModalItem.value = null;
    focusScanner(false);
  }

  function undoRow(row: PickingItem) {
    if (Boolean(row.is_skipped) && !canSkipItems.value) return;
    row.is_picked = 0;
    row.is_skipped = 0;
    row.skipped_by = null;
    row.is_fifo_override = 0;
    row.picked_batch_no = "";
    row.picked_source_warehouse = "";
    row.picked_qty = row.deficit_qty;
    clearFeedback();
    focusScanner(false);
  }

  function onUpdateNonBatchQty(row: PickingItem, newQty: number) {
    if (isBatchTrackedRow(row)) return;
    const numericQty = Number(newQty);
    if (Number.isNaN(numericQty) || numericQty < 0) return;
    row.picked_qty = numericQty;
    clearFeedback();
  }

  function confirmNonBatchRow(row: PickingItem) {
    if (isBatchTrackedRow(row)) return;
    const qty = Number(row.picked_qty || 0);
    if (qty <= 0) {
      playBeep(false);
      showFeedback(__("Girilen miktar sıfırdan büyük olmalıdır."), "error");
      return;
    }
    if (isOverTolerance(qty, row.deficit_qty)) {
      playBeep(false);
      showFeedback(__("Girilen miktar tolerans sınırını aşıyor."), "error");
      return;
    }
    row.is_picked = 1;
    row.is_skipped = 0;
    row.is_fifo_override = 0;
    row.picked_source_warehouse =
      row.picked_source_warehouse || row.suggested_source_warehouse || "";
    playBeep(true);
    highlightCard(row.name);
    showFeedback(__("Onaylandı: {0}", [row.item_code]), "success");
    focusScanner(false);
  }

  async function executeCompleteTransfer() {
    if (!activeOrder.value || !canCompleteTransfer.value) return;

    const payload = allItems.value.map((row) => {
      const skipped = Boolean(row.is_skipped);
      return {
        name: row.name,
        item_code: row.item_code,
        deficit_qty: row.deficit_qty,
        picked_qty: skipped ? 0 : row.picked_qty,
        picked_source_warehouse: skipped
          ? ""
          : row.picked_source_warehouse || row.suggested_source_warehouse || "",
        picked_batch_no: skipped
          ? ""
          : row.picked_batch_no || row.suggested_batch_no || "",
        is_picked: skipped ? 0 : 1,
        is_skipped: skipped ? 1 : 0,
        is_fifo_override: skipped ? 0 : row.is_fifo_override ? 1 : 0,
      };
    });

    submittingTransfer.value = true;
    clearFeedback();
    try {
      const res = await window.frappe.call({
        method:
          "erpnextkta.kta_stock.line_replenishment_service.complete_line_replenishment_picking",
        args: {
          order_name: activeOrder.value.name,
          picked_items: JSON.stringify(payload),
        },
        freeze: true,
        freeze_message: allSkipped.value
          ? __("İkmal Emri İptal Ediliyor...")
          : __("Malzeme Transferi Gerçekleştiriliyor..."),
        quiet: true,
      });

      const seName = typeof res?.message === "string" ? res.message.trim() : "";
      playBeep(true);
      if (seName) {
        window.frappe.show_alert?.(
          {
            message: __("Transfer Tamamlandı: {0}", [seName]),
            indicator: "green",
          },
          7,
        );
      } else {
        window.frappe.show_alert?.(
          {
            message: __(
              "Tüm kalemler atlandığı için ikmal emri iptal edildi.",
            ),
            indicator: "orange",
          },
          7,
        );
      }

      activeOrder.value = null;
      selectedOrderName.value = "";
      fifoModalCandidate.value = null;
      skipModalItem.value = null;
      activeTab.value = "pending";
      await loadOpenOrders();
    } catch (err: any) {
      playBeep(false);
      showFeedback(err?.message || __("Transfer tamamlanamadı."), "error");
    } finally {
      submittingTransfer.value = false;
    }
  }

  function onCompleteTransfer() {
    if (!canCompleteTransfer.value || submittingTransfer.value) return;
    if (options.confirmTransfer) {
      const msg = allSkipped.value
        ? __(
            "Tüm kalemler atlandığı için ikmal emri iptal edilsin mi?",
          )
        : __(
            "Seçilen kalemler için Malzeme Transferi (Stock Entry) oluşturulsun mu?",
          );
      options.confirmTransfer(msg, () => executeCompleteTransfer());
      return;
    }
    void executeCompleteTransfer();
  }

  return {
    orders,
    selectedOrderName,
    activeOrder,
    loadingOrders,
    loadingOrderDetails,
    submittingTransfer,
    highlightedRow,
    feedbackMsg,
    feedbackType,
    activeTab,
    fifoModalCandidate,
    skipModalItem,
    scannerBarRef,
    allItems,
    pendingItems,
    pickedItems,
    skippedItems,
    totalCount,
    pendingCount,
    pickedCount,
    skippedCount,
    allSkipped,
    canSkipItems,
    canCompleteTransfer,
    visibleItems,
    showFeedback,
    clearFeedback,
    focusScanner,
    loadOpenOrders,
    loadOrderDetails,
    onSelectOrder,
    onBarcodeScan,
    confirmFifoOverride,
    cancelFifoOverride,
    requestSkipItem,
    confirmSkipItem,
    cancelSkipItem,
    undoRow,
    onUpdateNonBatchQty,
    confirmNonBatchRow,
    onCompleteTransfer,
  };
}
