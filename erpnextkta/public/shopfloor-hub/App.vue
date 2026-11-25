<script setup lang="ts">
import { ref, nextTick } from 'vue';
import ShopfloorNavbar from './components/ShopfloorNavbar.vue';
import WorkOrderSidebar from './components/WorkOrderSidebar.vue';
import WoStatsCard from './components/WoStatsCard.vue';
import OperationsList from './components/OperationsList.vue';
import ConfirmationPanel from './components/ConfirmationPanel.vue';
import ConfirmationHistory from './components/ConfirmationHistory.vue';
import CreateWorkOrderModal from './components/CreateWorkOrderModal.vue';
import MaterialStagingModal from './components/MaterialStagingModal.vue';
import WorkOrderReleasePanel from './components/WorkOrderReleasePanel.vue';
import WorkCardAnalyticsPanel from './components/WorkCardAnalyticsPanel.vue';
import WorkspaceHeader from './components/WorkspaceHeader.vue';
import ShopfloorAlerts from './components/ShopfloorAlerts.vue';
import ReportsSidebar from './components/ReportsSidebar.vue';
import ReportsWorkspace from './components/ReportsWorkspace.vue';
import ConfirmationsManagementPanel from './components/ConfirmationsManagementPanel.vue';
import { REPORT_CATALOG } from './reports/registry';
import type {
  WorkOrderContext,
  OperationInfo,
  ConfirmationResponse,
  WorkOrderViewMode,
  MaterialShortageItem,
  MaterialShortageCheckResponse,
  MaterialTransferItem,
  MaterialStagingResponse,
} from './types';

const __ = (...args: any[]) => (window as any).__(...args);

const activeView = ref<WorkOrderViewMode>('work_orders');
const activeReportId = ref<string>(REPORT_CATALOG[0]?.id || 'operation_completion');
const sidebarRef = ref<InstanceType<typeof WorkOrderSidebar> | null>(null);
const showCreateModal = ref<boolean>(false);
const showStagingModal = ref<boolean>(false);
const currentShortages = ref<MaterialShortageItem[]>([]);
const stagingSubmitting = ref<boolean>(false);
const selectedWorkOrder = ref<string | null>(null);
const loading = ref<boolean>(false);
const submitting = ref<boolean>(false);
const errorMessage = ref<string | null>(null);
const successResult = ref<ConfirmationResponse | null>(null);
const context = ref<WorkOrderContext | null>(null);
const selectedOperation = ref<OperationInfo | null>(null);
const yieldQty = ref<number>(0);
const isFinalConfirmation = ref<boolean>(false);
const historyRefreshKey = ref<number>(0);

function callFrappe<T = any>(method: string, args: Record<string, any> = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    frappe.call({
      method, args, quiet: true,
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

async function fetchHubContext(barcode: string): Promise<WorkOrderContext> {
  try {
    return await callFrappe<WorkOrderContext>('erpnextkta.kta_shopfloor.api.get_shopfloor_hub_context', { barcode });
  } catch {
    return await callFrappe<WorkOrderContext>('erpnextkta.kta_shopfloor.api.get_co11n_context', { barcode });
  }
}

function selectOperation(op: OperationInfo | null) {
  selectedOperation.value = op;
  yieldQty.value = op && op.pending_qty > 0 ? Number(op.pending_qty) : 0;
  isFinalConfirmation.value = false;
}

async function loadWorkOrder(woName: string, preferredOperation?: string) {
  if (!woName) return;
  selectedWorkOrder.value = woName;
  loading.value = true;
  errorMessage.value = null;
  successResult.value = null;
  try {
    const data = await fetchHubContext(woName);
    if (!data || !data.work_order) throw new Error(__('İş Emri detayları alınamadı.'));
    context.value = data;
    selectedWorkOrder.value = data.work_order;
    historyRefreshKey.value += 1;
    const targetOpName = preferredOperation || data.selected_operation;
    const matched = (data.operations || []).find((op) => op.operation === targetOpName);
    selectOperation(matched || data.operations?.[0] || null);
  } catch (err: any) {
    console.error('loadWorkOrder error:', err);
    errorMessage.value = err?.message || err?._server_messages || __('İş Emri yüklenirken hata oluştu.');
  } finally {
    loading.value = false;
  }
}

function clearSelection() {
  selectedWorkOrder.value = null;
  context.value = null;
  selectedOperation.value = null;
  yieldQty.value = 0;
  isFinalConfirmation.value = false;
  errorMessage.value = null;
  successResult.value = null;
}

async function handleViewChange(view: WorkOrderViewMode) {
  activeView.value = view;
  if (view === 'reports' || view === 'confirmations') return;
  if (
    (view === 'operations' || view === 'work_cards') &&
    context.value?.status === 'Draft'
  ) {
    clearSelection();
  }
  await nextTick();
  await sidebarRef.value?.fetchWorkOrders();
}

async function handleOpenWorkOrderFromReport(workOrderName: string, operationName?: string) {
  activeView.value = 'work_orders';
  await nextTick();
  await loadWorkOrder(workOrderName, operationName);
}

async function handleOpenWorkOrderFromConfirmations(workOrderName: string, operationName?: string) {
  activeView.value = 'operations';
  await nextTick();
  await sidebarRef.value?.fetchWorkOrders();
  await loadWorkOrder(workOrderName, operationName);
}

function handleOpenCreateModal() {
  showCreateModal.value = true;
}

async function handleWorkOrderCreated(workOrderName: string) {
  await sidebarRef.value?.fetchWorkOrders();
  await loadWorkOrder(workOrderName);
}

async function handleWorkOrderReleased(workOrderName: string) {
  await sidebarRef.value?.fetchWorkOrders();
  await loadWorkOrder(workOrderName);
}

async function handleRefreshCurrentWorkOrder() {
  if (selectedWorkOrder.value) {
    await loadWorkOrder(selectedWorkOrder.value);
  }
  await sidebarRef.value?.fetchWorkOrders();
}

async function handleSwitchToOperations(workOrderName: string) {
  activeView.value = 'operations';
  await nextTick();
  await sidebarRef.value?.fetchWorkOrders();
  if (!context.value || context.value.work_order !== workOrderName) {
    await loadWorkOrder(workOrderName);
  }
}

async function refreshCurrentContext() {
  if (!context.value?.work_order) return;
  try {
    const currentOpName = selectedOperation.value?.operation;
    const refreshed = await fetchHubContext(context.value.work_order);
    if (refreshed) {
      context.value = refreshed;
      const matched = (refreshed.operations || []).find((o) => o.operation === currentOpName);
      selectOperation(matched || refreshed.operations?.[0] || null);
      historyRefreshKey.value += 1;
    }
  } catch (err) {
    console.error('refreshCurrentContext error:', err);
  }
}

async function executeConfirmation(qty: number) {
  if (!context.value || !selectedOperation.value) return;
  submitting.value = true;
  errorMessage.value = null;
  successResult.value = null;

  try {
    const payload = {
      work_order: context.value.work_order,
      operation: selectedOperation.value.operation,
      job_card: selectedOperation.value.job_card || null,
      yield_qty: qty,
      is_final_confirmation: isFinalConfirmation.value ? 1 : 0,
    };
    let res: ConfirmationResponse | null = null;
    try {
      res = await callFrappe<ConfirmationResponse>('erpnextkta.kta_shopfloor.api.submit_production_confirmation', { payload });
    } catch {
      res = await callFrappe<ConfirmationResponse>('erpnextkta.kta_shopfloor.api.submit_co11n_confirmation', { payload });
    }
    if (res && res.success) {
      successResult.value = res;
      (window as any).frappe?.show_alert?.({ message: __('Teyit Başarıyla Kaydedildi: {0}', [res.confirmation]), indicator: 'green' });
      await refreshCurrentContext();
    } else {
      throw new Error(__('Teyit işlemi başarısız oldu.'));
    }
  } catch (err: any) {
    console.error('executeConfirmation error:', err);
    errorMessage.value = err?.message || err?._server_messages || __('Teyit işlemi sırasında bir hata oluştu.');
  } finally {
    submitting.value = false;
  }
}

async function submitConfirmation() {
  if (!context.value || !selectedOperation.value) {
    errorMessage.value = __('Lütfen önce bir İş Emri ve Operasyon seçin.');
    return;
  }
  const qty = Number(yieldQty.value);
  if (isNaN(qty) || qty <= 0) {
    errorMessage.value = __('Sağlam Miktar sıfırdan büyük bir sayı olmalıdır.');
    return;
  }
  submitting.value = true;
  errorMessage.value = null;
  successResult.value = null;

  try {
    const check = await callFrappe<MaterialShortageCheckResponse>(
      'erpnextkta.kta_shopfloor.api.check_confirmation_materials',
      {
        work_order: context.value.work_order,
        operation: selectedOperation.value.operation,
        yield_qty: qty,
        is_final_confirmation: isFinalConfirmation.value ? 1 : 0,
      }
    );

    if (check?.has_shortage && Array.isArray(check.shortages) && check.shortages.length > 0) {
      currentShortages.value = check.shortages;
      showStagingModal.value = true;
      submitting.value = false;
      return;
    }
  } catch (checkErr: any) {
    console.error('check_confirmation_materials error:', checkErr);
    errorMessage.value = checkErr?.message || checkErr?._server_messages || __('Malzeme kontrolü sırasında hata oluştu.');
    submitting.value = false;
    return;
  }

  await executeConfirmation(qty);
}

async function handleConfirmStage(transfers: MaterialTransferItem[]) {
  if (!context.value || !selectedOperation.value) return;
  const qty = Number(yieldQty.value);
  stagingSubmitting.value = true;
  errorMessage.value = null;

  try {
    const res = await callFrappe<MaterialStagingResponse>(
      'erpnextkta.kta_shopfloor.api.stage_confirmation_materials',
      {
        work_order: context.value.work_order,
        transfers,
      }
    );

    if (res && res.success) {
      showStagingModal.value = false;
      (window as any).frappe?.show_alert?.({
        message: __('Hat İkmali Yapıldı: {0}', [res.stock_entry]),
        indicator: 'blue',
      });
      await executeConfirmation(qty);
    } else {
      throw new Error(res?.message || __('Hat ikmali transferi gerçekleştirilemedi.'));
    }
  } catch (err: any) {
    console.error('handleConfirmStage error:', err);
    errorMessage.value = err?.message || err?._server_messages || __('Hat ikmali transferi sırasında bir hata oluştu.');
  } finally {
    stagingSubmitting.value = false;
  }
}
</script>

<template>
  <div class="shopfloor-hub-root">
    <ShopfloorNavbar :active-view="activeView" @change-view="handleViewChange" />

    <div class="co11n-shell">
      <ReportsSidebar
        v-if="activeView === 'reports'"
        :reports="REPORT_CATALOG"
        :active-report-id="activeReportId"
        @select-report="activeReportId = $event"
      />
      <WorkOrderSidebar
        v-else-if="activeView !== 'confirmations'"
        ref="sidebarRef"
        :active-view="activeView"
        :current-work-order="selectedWorkOrder || context?.work_order"
        @select-work-order="loadWorkOrder"
        @open-create-modal="handleOpenCreateModal"
      />

      <main class="co11n-workspace">
        <WorkspaceHeader>
          <template #title>
            {{
              activeView === 'reports'
                ? __('Raporlar')
                : activeView === 'confirmations'
                ? __('Teyitler')
                : activeView === 'work_cards'
                ? __('Çalışma Kartları')
                : __('Shopfloor Hub')
            }}
          </template>
          <template #subtitle>
            {{
              activeView === 'reports'
                ? __('Üretim Teyitleri ve Saha Analiz Raporları')
                : activeView === 'confirmations'
                ? __('Çoklu İş Emri Teyit İzleme ve Toplu Ters Kayıt Yönetimi')
                : activeView === 'work_cards'
                ? __('Alt Operasyon Analitiği ve Tüketim Mutabakatı')
                : __('Gerçek Zamanlı İş Emri Yürütme ve Üretim Teyidi')
            }}
          </template>
          <template #actions>
            <button
              v-if="activeView !== 'reports' && activeView !== 'confirmations' && (selectedWorkOrder || context)"
              type="button"
              class="btn-clear-selection"
              @click="clearSelection"
            >
              ✕ {{ __('Seçimi Temizle') }}
            </button>
          </template>
        </WorkspaceHeader>

        <ShopfloorAlerts
          :error-message="errorMessage"
          :success-result="successResult"
          @clear-error="errorMessage = null"
          @clear-success="successResult = null"
        />

        <template v-if="activeView === 'reports'">
          <ReportsWorkspace
            :reports="REPORT_CATALOG"
            :active-report-id="activeReportId"
            @select-work-order="handleOpenWorkOrderFromReport"
          />
        </template>

        <ConfirmationsManagementPanel
          v-else-if="activeView === 'confirmations'"
          @select-work-order="handleOpenWorkOrderFromConfirmations"
        />

        <template v-else-if="activeView === 'work_orders'">
          <WorkOrderReleasePanel
            v-if="selectedWorkOrder"
            :work-order="selectedWorkOrder"
            :context="context"
            :loading-context="loading"
            @released="handleWorkOrderReleased"
            @switch-to-operations="handleSwitchToOperations"
            @refresh="handleRefreshCurrentWorkOrder"
          />
          <div v-else class="empty-state">
            <div class="empty-icon">⚡</div>
            <h3 class="empty-title">{{ __('Work Orders') }}</h3>
            <p class="empty-desc">
              {{ __('Lütfen sol listeden bir iş emri seçin veya yeni bir iş emri açın.') }}
            </p>
          </div>
        </template>

        <template v-else-if="activeView === 'work_cards'">
          <WorkCardAnalyticsPanel
            v-if="selectedWorkOrder"
            :work-order="selectedWorkOrder"
            :loading-work-order="loading"
          />
          <div v-else class="empty-state">
            <div class="empty-icon">⏱️</div>
            <h3 class="empty-title">{{ __('Work Cards') }}</h3>
            <p class="empty-desc">
              {{ __('Lütfen sol paneldeki listeden bir İş Emri seçin.') }}
            </p>
          </div>
        </template>

        <template v-else>
          <div v-if="context" class="co11n-content-flow">
            <WoStatsCard :context="context" />
            <div class="co11n-ops-grid">
              <OperationsList
                :operations="context.operations"
                :selected-operation="selectedOperation"
                :target-qty="context.qty"
                @select="selectOperation"
              />
              <ConfirmationPanel
                v-model="yieldQty"
                v-model:is-final-confirmation="isFinalConfirmation"
                :selected-operation="selectedOperation"
                :target-qty="context.qty"
                :submitting="submitting"
                @submit="submitConfirmation"
              />
            </div>
            <ConfirmationHistory
              :work-order="context.work_order"
              :refresh-key="historyRefreshKey"
              :can-cancel="context.can_cancel_confirmations !== false"
              @confirmation-cancelled="refreshCurrentContext"
            />
          </div>

          <div v-else-if="loading" class="empty-state">
            <div class="workspace-spinner" />
            <h3 class="empty-title">{{ __('İş Emri Yükleniyor…') }}</h3>
          </div>

          <div v-else class="empty-state">
            <div class="empty-icon">👈</div>
            <h3 class="empty-title">{{ __('Bir İş Emri Seçin') }}</h3>
            <p class="empty-desc">
              {{ __('Lütfen sol paneldeki listeden işlem yapmak istediğiniz bir İş Emri seçin.') }}
            </p>
          </div>
        </template>
      </main>
    </div>

    <CreateWorkOrderModal
      :show="showCreateModal"
      @close="showCreateModal = false"
      @created="handleWorkOrderCreated"
    />

    <MaterialStagingModal
      :show="showStagingModal"
      :work-order="context?.work_order || ''"
      :shortages="currentShortages"
      :submitting="stagingSubmitting"
      @close="showStagingModal = false"
      @confirm-stage="handleConfirmStage"
    />
  </div>
</template>

<style scoped>
.shopfloor-hub-root { display: flex; flex-direction: column; width: 100%; height: calc(100vh - 60px); overflow: hidden; box-sizing: border-box; font-family: inherit; color: var(--text-color, #0f172a); }
.co11n-shell { display: flex; flex: 1; min-height: 0; width: 100%; overflow: hidden; box-sizing: border-box; }
@media (max-width: 700px) { .co11n-shell { flex-direction: column; } }
.co11n-workspace { flex: 1; min-width: 0; height: 100%; overflow-y: auto; padding: 1.25rem 2rem 3rem; display: flex; flex-direction: column; gap: 1.25rem; box-sizing: border-box; }
.btn-clear-selection { background: var(--bg-color, #f1f5f9); border: 1px solid var(--border-color, #cbd5e1); padding: 0.45rem 0.9rem; border-radius: 0.5rem; font-size: 0.82rem; font-weight: 700; color: var(--text-muted, #475569); cursor: pointer; transition: all 0.15s; }
.btn-clear-selection:hover { background: #e2e8f0; color: #0f172a; }
.co11n-content-flow { display: flex; flex-direction: column; gap: 1.25rem; }
.co11n-ops-grid { display: grid; grid-template-columns: 1fr 420px; gap: 1.25rem; }
@media (max-width: 1000px) { .co11n-ops-grid { grid-template-columns: 1fr; } }
.empty-state { text-align: center; padding: 5rem 1rem; background: var(--card-bg, #ffffff); border: 2px dashed var(--border-color, #e2e8f0); border-radius: 0.85rem; display: flex; flex-direction: column; align-items: center; gap: 0.4rem; }
.empty-icon { font-size: 3.5rem; margin-bottom: 0.5rem; }
.empty-title { font-size: 1.25rem; font-weight: 800; margin: 0; color: var(--text-color, #0f172a); }
.empty-desc { font-size: 0.88rem; color: var(--text-muted, #64748b); max-width: 420px; margin: 0; }
.workspace-spinner { width: 32px; height: 32px; border: 3px solid rgba(37, 99, 235, 0.2); border-radius: 50%; border-top-color: #2563eb; animation: spin 0.8s linear infinite; margin-bottom: 0.5rem; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>

<style>
#page-shopfloor_hub .page-head, [data-page-route="shopfloor_hub"] .page-head,
#page-kta_co11n .page-head, [data-page-route="kta_co11n"] .page-head { display: none !important; }

#page-shopfloor_hub .page-body, #page-shopfloor_hub .layout-main-section, #page-shopfloor_hub .content.page-container.no-list-sidebar,
#page-kta_co11n .page-body, #page-kta_co11n .layout-main-section, #page-kta_co11n .content.page-container.no-list-sidebar { max-width: 100% !important; padding: 0 !important; margin: 0 !important; }
</style>
