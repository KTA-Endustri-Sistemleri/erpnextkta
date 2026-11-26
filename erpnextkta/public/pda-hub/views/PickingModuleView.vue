<script setup lang="ts">
import { onMounted } from "vue";
import { useLineReplenishmentPicking } from "../../line-replenishment-pda/composables/useLineReplenishmentPicking";
import OrderSelector from "../../line-replenishment-pda/components/OrderSelector.vue";
import BarcodeScannerBar from "../../line-replenishment-pda/components/BarcodeScannerBar.vue";
import PickingItemCard from "../../line-replenishment-pda/components/PickingItemCard.vue";
import TransferFooter from "../../line-replenishment-pda/components/TransferFooter.vue";
import FifoOverrideModal from "../../line-replenishment-pda/components/FifoOverrideModal.vue";
import SkipItemModal from "../../line-replenishment-pda/components/SkipItemModal.vue";

const __ = (...args: any[]) => (window as any).__(...args);
const emit = defineEmits<{ (e: "orders-updated", count: number): void }>();

const {
  orders, selectedOrderName, activeOrder, loadingOrders, loadingOrderDetails,
  submittingTransfer, highlightedRow, feedbackMsg, feedbackType, activeTab,
  fifoModalCandidate, skipModalItem, scannerBarRef, totalCount, pendingCount,
  pickedCount, skippedCount, allSkipped, canSkipItems, canCompleteTransfer,
  visibleItems, clearFeedback, loadOpenOrders, onSelectOrder, onBarcodeScan,
  confirmFifoOverride, cancelFifoOverride, requestSkipItem, confirmSkipItem,
  cancelSkipItem, undoRow, onUpdateNonBatchQty, confirmNonBatchRow, onCompleteTransfer,
} = useLineReplenishmentPicking({
  onOrdersUpdated: (count) => emit("orders-updated", count),
});

onMounted(() => void loadOpenOrders());
</script>

<template>
  <div class="pda-picking-view">
    <div class="pda-picking-container">
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

      <div v-if="!activeOrder && feedbackMsg" class="pda-picking-alert">{{ feedbackMsg }}</div>

      <template v-if="activeOrder">
        <div
          v-if="pendingCount === 0 && totalCount > 0"
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

        <div v-if="visibleItems.length > 0" :class="['pda-picking-list', { 'is-pending-grid': activeTab === 'pending' }]">
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
        <div v-else class="pda-tab-empty">{{ __("Bu sekmede gösterilecek kalem yok.") }}</div>
      </template>

      <div v-else-if="!loadingOrders && orders.length === 0" class="pda-picking-empty">
        <div class="pda-picking-empty-icon">📦</div>
        <div class="pda-picking-empty-title">{{ __("Açık İkmal Emri Yok") }}</div>
        <div class="pda-picking-empty-sub">{{ __("Yeni hat ikmal emri oluşturulduğunda burada listelenir.") }}</div>
      </div>
    </div>

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
.pda-picking-view { min-height: calc(100vh - 56px); padding: 10px 12px 112px; overflow-x: clip; max-width: 100%; background: var(--bg-color); color: var(--text-color); }
.pda-picking-container { width: 100%; min-width: 0; max-width: 100%; display: flex; flex-direction: column; gap: 10px; }
.pda-top-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 8px;
  position: sticky;
  top: var(--pda-sticky-top, 100px);
  z-index: 30;
  background: var(--bg-color);
  padding: 4px 0 8px;
  transition: top 0.2s ease;
}
.pda-ready-banner { padding: 9px 12px; border-radius: 8px; font-size: 0.85rem; font-weight: 700; }
.ready-green { background: rgba(22, 163, 74, 0.14); border: 1px solid rgba(22, 163, 74, 0.35); color: var(--pda-success); }
.ready-amber { background: rgba(217, 119, 6, 0.16); border: 1px solid rgba(217, 119, 6, 0.4); color: #b45309; }
[data-theme="dark"] .ready-amber { color: #fcd34d; }
.pda-tabs-bar { display: flex; gap: 6px; background: var(--pda-surface-alt); border: 1px solid var(--border-color); border-radius: 8px; padding: 4px; }
.pda-tab-btn {
  flex: 1; min-height: 36px; border: none; border-radius: 6px; background: transparent;
  color: var(--text-muted); font-size: 0.84rem; font-weight: 700; cursor: pointer; padding: 4px 8px;
}
.pda-tab-btn.active { background: var(--card-bg); color: var(--text-color); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08); }
.pda-picking-list { display: flex; flex-direction: column; gap: 8px; }
.pda-tab-empty, .pda-picking-empty {
  text-align: center; padding: 36px 16px; background: var(--card-bg); border: 1px dashed var(--border-color); border-radius: 12px; color: var(--text-muted);
}
.pda-picking-empty-icon { font-size: 2.2rem; margin-bottom: 8px; }
.pda-picking-empty-title { font-size: 1rem; font-weight: 700; color: var(--text-color); }
.pda-picking-empty-sub { margin-top: 4px; font-size: 0.85rem; }
.pda-picking-alert {
  padding: 10px 12px; border-radius: 10px; background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3); color: var(--pda-danger); font-size: 0.9rem; font-weight: 600;
}
@media (min-width: 768px) {
  .pda-picking-view { padding: 12px 16px 84px; }
  .pda-picking-container { max-width: 960px; margin: 0 auto; }
  .pda-top-controls { grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr); align-items: stretch; gap: 10px; }
  .pda-picking-list.is-pending-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
}
</style>
