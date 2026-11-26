<script setup lang="ts">
import { onMounted } from "vue";
import { useLineReplenishmentPicking } from "./composables/useLineReplenishmentPicking";
import OrderSelector from "./components/OrderSelector.vue";
import BarcodeScannerBar from "./components/BarcodeScannerBar.vue";
import PickingItemCard from "./components/PickingItemCard.vue";
import TransferFooter from "./components/TransferFooter.vue";
import FifoOverrideModal from "./components/FifoOverrideModal.vue";
import SkipItemModal from "./components/SkipItemModal.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const {
  orders, selectedOrderName, activeOrder, loadingOrders, loadingOrderDetails,
  submittingTransfer, highlightedRow, feedbackMsg, feedbackType, activeTab,
  fifoModalCandidate, skipModalItem, scannerBarRef, totalCount, pendingCount,
  pickedCount, skippedCount, allSkipped, canSkipItems, canCompleteTransfer,
  visibleItems, clearFeedback, loadOpenOrders, onSelectOrder, onBarcodeScan,
  confirmFifoOverride, cancelFifoOverride, requestSkipItem, confirmSkipItem,
  cancelSkipItem, undoRow, onUpdateNonBatchQty, confirmNonBatchRow, onCompleteTransfer,
} = useLineReplenishmentPicking({
  confirmTransfer: (msg, onConfirm) => {
    if (typeof window.frappe?.confirm === "function") window.frappe.confirm(msg, () => void onConfirm());
    else void onConfirm();
  },
});

onMounted(() => void loadOpenOrders());
</script>

<template>
  <div class="line-replenishment-pda-app">
    <header class="pda-header">
      <div class="header-content">
        <h1 class="header-title">{{ __("Hat İkmal Toplama (PDA)") }}</h1>
        <span class="header-badge">PDA</span>
      </div>
    </header>

    <main class="pda-main">
      <div class="pda-top-controls">
        <OrderSelector
          :orders="orders"
          :selected-order-name="selectedOrderName"
          :active-order="activeOrder"
          :loading="loadingOrders || loadingOrderDetails"
          :picked-count="pickedCount"
          :skipped-count="skippedCount"
          :total-count="totalCount"
          @select="onSelectOrder"
          @refresh="loadOpenOrders"
        />
        <BarcodeScannerBar
          v-if="activeOrder"
          ref="scannerBarRef"
          :disabled="loadingOrderDetails || submittingTransfer || Boolean(fifoModalCandidate) || Boolean(skipModalItem)"
          :feedback-msg="feedbackMsg"
          :feedback-type="feedbackType"
          @scan="onBarcodeScan"
          @clear="clearFeedback"
        />
      </div>

      <template v-if="activeOrder">
        <div v-if="loadingOrderDetails" class="empty-state">
          <span class="spinner">⏳</span>
          <p>{{ __("Sipariş Kalemleri Yükleniyor...") }}</p>
        </div>
        <div v-else-if="totalCount === 0" class="empty-state">
          <span class="empty-icon">📭</span>
          <p>{{ __("Bu siparişte toplanacak kalem bulunamadı.") }}</p>
        </div>
        <template v-else>
          <div
            v-if="pendingCount === 0"
            data-testid="picking-ready-banner"
            :class="['pda-ready-banner', allSkipped ? 'ready-amber' : 'ready-green']"
          >
            {{ allSkipped ? __("Tüm kalemler atlandı — Emri iptal edebilirsiniz") : __("Tüm kalemler işlendi — Transferi tamamlamaya hazır") }}
          </div>

          <div class="pda-tabs-bar" role="tablist">
            <button type="button" role="tab" data-testid="tab-pending" :class="['pda-tab-btn', { active: activeTab === 'pending' }]" @click="activeTab = 'pending'">
              {{ __("Bekleyen ({0})", [pendingCount]) }}
            </button>
            <button type="button" role="tab" data-testid="tab-picked" :class="['pda-tab-btn', { active: activeTab === 'picked' }]" @click="activeTab = 'picked'">
              {{ __("Toplanan ({0})", [pickedCount]) }}
            </button>
            <button v-if="skippedCount > 0" type="button" role="tab" data-testid="tab-skipped" :class="['pda-tab-btn', { active: activeTab === 'skipped' }]" @click="activeTab = 'skipped'">
              {{ __("Atlanan ({0})", [skippedCount]) }}
            </button>
          </div>

          <div v-if="visibleItems.length > 0" :class="['items-list', { 'is-pending-grid': activeTab === 'pending' }]">
            <PickingItemCard
              v-for="row in visibleItems"
              :key="row.name"
              :item="row"
              :highlighted="highlightedRow === row.name"
              :can-skip="canSkipItems"
              @undo="undoRow(row)"
              @request-skip="requestSkipItem(row)"
              @update-qty="(val) => onUpdateNonBatchQty(row, val)"
              @confirm-non-batch="confirmNonBatchRow(row)"
            />
          </div>
          <div v-else class="empty-state">{{ __("Bu sekmede gösterilecek kalem yok.") }}</div>
        </template>
      </template>

      <div v-else-if="!loadingOrders" class="empty-state initial-empty">
        <span class="empty-icon">📦</span>
        <p class="empty-text">{{ __("Toplama yapmak için yukarıdan açık bir sipariş seçin.") }}</p>
      </div>
    </main>

    <TransferFooter
      v-if="activeOrder && totalCount > 0"
      :can-complete="canCompleteTransfer"
      :picked-count="pickedCount"
      :skipped-count="skippedCount"
      :pending-count="pendingCount"
      :total-count="totalCount"
      :all-skipped="allSkipped"
      :loading="submittingTransfer"
      @complete="onCompleteTransfer"
    />

    <FifoOverrideModal :candidate="fifoModalCandidate" @confirm="confirmFifoOverride" @cancel="cancelFifoOverride" />
    <SkipItemModal :item="skipModalItem" @confirm="confirmSkipItem" @cancel="cancelSkipItem" />
  </div>
</template>

<style scoped>
.line-replenishment-pda-app { min-height: 100vh; display: flex; flex-direction: column; overflow-x: clip; max-width: 100%; background-color: var(--bg-color, #f8fafc); color: var(--text-color, #0f172a); }
.pda-header { background-color: #1e293b; color: #ffffff; padding: 12px 16px; border-bottom: 2px solid #334155; position: sticky; top: 0; z-index: 30; }
.header-content { max-width: 960px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; }
.header-title { margin: 0; font-size: 1.15rem; font-weight: 700; }
.header-badge { background-color: #2563eb; color: #ffffff; font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 9999px; }
.pda-main { flex: 1; width: 100%; min-width: 0; max-width: 100%; overflow-x: clip; padding: 12px 12px 112px; display: flex; flex-direction: column; gap: 10px; }
.pda-top-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 8px;
  position: sticky;
  top: 52px;
  z-index: 28;
  background: var(--bg-color, #f8fafc);
  padding: 4px 0 8px;
}
.pda-ready-banner { padding: 9px 12px; border-radius: 8px; font-size: 0.85rem; font-weight: 700; }
.ready-green { background: rgba(22, 163, 74, 0.14); border: 1px solid rgba(22, 163, 74, 0.35); color: var(--pda-success, #16a34a); }
.ready-amber { background: rgba(217, 119, 6, 0.16); border: 1px solid rgba(217, 119, 6, 0.4); color: #b45309; }
[data-theme="dark"] .ready-amber { color: #fcd34d; }
.pda-tabs-bar { display: flex; gap: 6px; background: var(--pda-surface-alt, #f1f5f9); border: 1px solid var(--border-color, #e2e8f0); border-radius: 8px; padding: 4px; }
.pda-tab-btn { flex: 1; min-height: 36px; border: none; border-radius: 6px; background: transparent; color: var(--text-muted, #64748b); font-size: 0.84rem; font-weight: 700; cursor: pointer; padding: 4px 8px; }
.pda-tab-btn.active { background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08); }
.items-list { display: flex; flex-direction: column; gap: 8px; }
.empty-state { text-align: center; padding: 32px 16px; background: var(--card-bg, #ffffff); border: 1px dashed var(--border-color, #cbd5e1); border-radius: 10px; color: var(--text-muted, #64748b); }
.empty-icon { font-size: 2.2rem; display: block; margin-bottom: 8px; }
@media (min-width: 768px) {
  .pda-main { max-width: 960px; margin: 0 auto; padding: 12px 16px 84px; }
  .pda-top-controls { grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr); align-items: stretch; gap: 10px; }
  .items-list.is-pending-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
}
</style>
