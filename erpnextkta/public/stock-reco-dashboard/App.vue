<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type {
  RecoMainTab,
  RecoRelabelMode,
  RecoRouteOptions,
  StockRecoListRow,
  StockRecoPreviewResponse,
  StockRecoRelabelResult,
  StockRecoRelabelSelection,
} from "./types";
import BulkCreateRecoModal from "./components/BulkCreateRecoModal.vue";
import RecoDocumentsList from "./components/RecoDocumentsList.vue";
import RecoLabelingWorkspace from "./components/RecoLabelingWorkspace.vue";
import RecoAnalyticsTab from "./components/RecoAnalyticsTab.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    initialRouteOptions?: RecoRouteOptions | null;
  }>(),
  { initialRouteOptions: null }
);

const activeTab = ref<RecoMainTab>("operations");
const liveConnected = ref<boolean>(false);
const showBulkModal = ref<boolean>(false);

const docs = ref<StockRecoListRow[]>([]);
const docsLoading = ref<boolean>(false);
const statusFilter = ref<string>("all");
const docSearch = ref<string>("");
const selectedDocName = ref<string | null>(null);
const preview = ref<StockRecoPreviewResponse | null>(null);
const previewLoading = ref<boolean>(false);
const submittingRelabel = ref<boolean>(false);

const errorMessage = ref<string | null>(null);
const lastResult = ref<StockRecoRelabelResult | null>(null);
const analyticsRefreshTick = ref<number>(0);

let searchTimer: number | null = null;
let realtimeTimer: number | null = null;
let realtimeHandler: (() => void) | null = null;

function callRpc<T = any>(method: string, args: Record<string, any> = {}): Promise<T> {
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

async function fetchDocs() {
  docsLoading.value = true;
  try {
    const res = await callRpc<StockRecoListRow[]>(
      "erpnextkta.kta_stock.services.stock_reconciliation_service.list_stock_reconciliations",
      {
        status_filter: statusFilter.value,
        search: docSearch.value.trim() || null,
        limit: 50,
      }
    );
    docs.value = Array.isArray(res) ? res : [];
  } catch (err: any) {
    errorMessage.value = extractError(err, __("Sayım belgeleri yüklenemedi."));
  } finally {
    docsLoading.value = false;
  }
}

async function fetchPreview(docName: string | null) {
  if (!docName) {
    preview.value = null;
    return;
  }
  previewLoading.value = true;
  errorMessage.value = null;
  try {
    const res = await callRpc<StockRecoPreviewResponse>(
      "erpnextkta.kta_stock.services.stock_reconciliation_service.get_stock_reconciliation_label_preview",
      { stock_reconciliation: docName }
    );
    preview.value = res || null;
  } catch (err: any) {
    errorMessage.value = extractError(err, __("Belge etiket önizlemesi alınamadı."));
    preview.value = null;
  } finally {
    previewLoading.value = false;
  }
}

function selectDoc(docName: string) {
  selectedDocName.value = docName;
  lastResult.value = null;
  fetchPreview(docName);
}

function refreshActivePreview() {
  if (selectedDocName.value) fetchPreview(selectedDocName.value);
}

async function handleExecuteRelabel(payload: {
  mode: RecoRelabelMode;
  selectedItems: StockRecoRelabelSelection[];
  isDraftSubmit: boolean;
  printLabels: boolean;
}) {
  if (!selectedDocName.value || submittingRelabel.value) return;
  submittingRelabel.value = true;
  errorMessage.value = null;
  lastResult.value = null;
  try {
    const method = payload.isDraftSubmit
      ? "erpnextkta.kta_stock.services.stock_reconciliation_service.submit_and_print_stock_reconciliation"
      : "erpnextkta.kta_stock.services.stock_reconciliation_service.relabel_submitted_stock_reconciliation";
    const res = await callRpc<StockRecoRelabelResult>(method, {
      stock_reconciliation: selectedDocName.value,
      selected_items: payload.selectedItems,
      print_labels: payload.printLabels ? 1 : 0,
    });
    lastResult.value = res;
    const labelCount = res?.labels?.length || 0;
    const printCount = res?.queued_print_count || 0;
    frappe?.show_alert?.({
      message: __("{0} etiket işlendi, {1} baskı kuyruğa alındı.", [labelCount, printCount]),
      indicator: "green",
    });
    await Promise.all([fetchDocs(), fetchPreview(selectedDocName.value)]);
    analyticsRefreshTick.value += 1;
  } catch (err: any) {
    errorMessage.value = extractError(err, __("Etiketleme işlemi sırasında bir hata oluştu."));
  } finally {
    submittingRelabel.value = false;
  }
}

function onBulkQueued(res: any) {
  frappe?.show_alert?.({
    message: res?.message || __("Toplu sayım oluşturma arka plan görevi sıraya alındı."),
    indicator: "blue",
  });
  fetchDocs();
}

async function applyRouteOptions(opts?: RecoRouteOptions | null) {
  if (!opts) return;
  if (opts.tab === "analytics" || opts.tab === "operations") {
    activeTab.value = opts.tab;
  }
  if (opts.doc) {
    activeTab.value = "operations";
    selectedDocName.value = opts.doc;
    lastResult.value = null;
    await fetchPreview(opts.doc);
  }
}

function onRouteEvent(event: Event) {
  const detail = (event as CustomEvent<RecoRouteOptions>).detail;
  applyRouteOptions(detail);
}

function scheduleRealtimeRefresh() {
  if (realtimeTimer !== null) window.clearTimeout(realtimeTimer);
  realtimeTimer = window.setTimeout(async () => {
    await fetchDocs();
    if (selectedDocName.value && activeTab.value === "operations") {
      await fetchPreview(selectedDocName.value);
    }
    analyticsRefreshTick.value += 1;
  }, 450);
}

watch(statusFilter, () => fetchDocs());

watch(docSearch, () => {
  if (searchTimer !== null) window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => fetchDocs(), 250);
});

onMounted(async () => {
  window.addEventListener("kta-stock-reco-route", onRouteEvent);
  if (typeof frappe !== "undefined" && frappe?.realtime?.on) {
    realtimeHandler = () => scheduleRealtimeRefresh();
    frappe.realtime.on("stock_reco_dashboard_update", realtimeHandler);
    liveConnected.value = true;
  }
  await fetchDocs();
  await applyRouteOptions(props.initialRouteOptions);
});

onBeforeUnmount(() => {
  window.removeEventListener("kta-stock-reco-route", onRouteEvent);
  if (realtimeHandler && typeof frappe !== "undefined" && frappe?.realtime?.off) {
    frappe.realtime.off("stock_reco_dashboard_update", realtimeHandler);
  }
  if (searchTimer !== null) window.clearTimeout(searchTimer);
  if (realtimeTimer !== null) window.clearTimeout(realtimeTimer);
});
</script>

<template>
  <div class="sr-hub-root">
    <header class="sr-hub-header">
      <div class="sr-hub-title-wrap">
        <div class="sr-hub-title-row">
          <h2 class="sr-hub-title">📦 {{ __("KTA Sayım ve Etiket Merkezi") }}</h2>
          <span class="sr-live-pill" :class="{ on: liveConnected }">
            <span class="dot" />
            <span>{{ liveConnected ? __("Canlı") : __("Çevrimdışı") }}</span>
          </span>
        </div>

        <nav class="sr-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            :aria-selected="activeTab === 'operations'"
            class="sr-tab-btn"
            :class="{ active: activeTab === 'operations' }"
            @click="activeTab = 'operations'"
          >
            🏷️ {{ __("Sayım Operasyonları & Etiketleme") }}
          </button>
          <button
            type="button"
            role="tab"
            :aria-selected="activeTab === 'analytics'"
            class="sr-tab-btn"
            :class="{ active: activeTab === 'analytics' }"
            @click="activeTab = 'analytics'"
          >
            📊 {{ __("Fark & Anomali Analizi") }}
          </button>
        </nav>
      </div>

      <button type="button" class="sr-bulk-btn" @click="showBulkModal = true">
        + {{ __("Toplu Sayım Oluştur") }}
      </button>
    </header>

    <div v-if="errorMessage" class="sr-banner sr-banner-error" role="alert">
      <span>⚠️ {{ errorMessage }}</span>
      <button type="button" class="sr-banner-close" @click="errorMessage = null">✕</button>
    </div>

    <div v-if="lastResult && activeTab === 'operations'" class="sr-banner sr-banner-success" role="status">
      <div class="sr-result-info">
        <strong>
          ✅ {{ __("Etiketleme Tamamlandı:") }}
          {{ lastResult.stock_reconciliation || lastResult.stock_conciliation }}
        </strong>
        <span>
          {{ __("{0} etiket oluşturuldu/güncellendi · {1} baskı Zebra kuyruğuna eklendi.", [lastResult.labels?.length || 0, lastResult.queued_print_count || 0]) }}
        </span>
        <span v-if="lastResult.stock_entries?.length" class="sr-se-links">
          {{ __("Oluşan Stok Fişleri:") }}
          <a v-for="se in lastResult.stock_entries" :key="se" :href="`/app/stock-entry/${se}`" target="_blank" class="sr-se-link">
            {{ se }}
          </a>
        </span>
      </div>
      <button type="button" class="sr-banner-close" @click="lastResult = null">✕</button>
    </div>

    <section v-if="activeTab === 'operations'" class="sr-ops-grid">
      <RecoDocumentsList
        :docs="docs"
        :selected-doc-name="selectedDocName"
        :loading="docsLoading"
        :status-filter="statusFilter"
        :search="docSearch"
        @select-doc="selectDoc"
        @update:status-filter="statusFilter = $event"
        @update:search="docSearch = $event"
        @refresh="fetchDocs"
      />
      <RecoLabelingWorkspace
        :preview="preview"
        :loading="previewLoading"
        :submitting="submittingRelabel"
        @refresh="refreshActivePreview"
        @execute="handleExecuteRelabel"
      />
    </section>

    <section v-else>
      <RecoAnalyticsTab :live-connected="liveConnected" :refresh-tick="analyticsRefreshTick" />
    </section>

    <BulkCreateRecoModal
      :show="showBulkModal"
      :default-company="preview?.doc?.company || null"
      @close="showBulkModal = false"
      @queued="onBulkQueued"
    />
  </div>
</template>

<style scoped>
.sr-hub-root { display: flex; flex-direction: column; gap: 1rem; padding: 1rem 1.25rem; color: var(--text-color, #0f172a); }
.sr-hub-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; flex-wrap: wrap; padding: 0.95rem 1.15rem; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; }
[data-theme="dark"] .sr-hub-header { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12)); color: #f8fafc; }
.sr-hub-title-wrap { display: flex; flex-direction: column; gap: 0.7rem; }
.sr-hub-title-row { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
.sr-hub-title { margin: 0; font-size: 1.25rem; font-weight: 800; }
.sr-live-pill { display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.6rem; border-radius: 9999px; border: 1px solid var(--border-color, #cbd5e1); color: var(--text-muted, #64748b); }
.sr-live-pill .dot { width: 8px; height: 8px; border-radius: 50%; background: #94a3b8; }
.sr-live-pill.on { border-color: #86efac; color: #15803d; background: rgba(34, 197, 94, 0.1); }
.sr-live-pill.on .dot { background: #22c55e; }
.sr-tabs { display: flex; gap: 0.45rem; flex-wrap: wrap; }
.sr-tab-btn { padding: 0.45rem 0.9rem; border-radius: 0.5rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--bg-color, #f8fafc); color: var(--text-muted, #64748b); font-size: 0.84rem; font-weight: 700; cursor: pointer; }
[data-theme="dark"] .sr-tab-btn { background: rgba(255, 255, 255, 0.05); border-color: rgba(255, 255, 255, 0.14); color: #94a3b8; }
.sr-tab-btn.active { background: #2563eb; border-color: #2563eb; color: #ffffff; }
.sr-bulk-btn { padding: 0.52rem 1.05rem; border: none; border-radius: 0.5rem; background: #2563eb; color: #ffffff; font-size: 0.85rem; font-weight: 700; cursor: pointer; white-space: nowrap; }
.sr-bulk-btn:hover { background: #1d4ed8; }
.sr-banner { display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; padding: 0.8rem 1.1rem; border-radius: 0.65rem; font-size: 0.84rem; }
.sr-banner-error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
[data-theme="dark"] .sr-banner-error { background: rgba(239, 68, 68, 0.16); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.sr-banner-success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
[data-theme="dark"] .sr-banner-success { background: rgba(34, 197, 94, 0.16); border-color: rgba(74, 222, 128, 0.35); color: #86efac; }
.sr-result-info { display: flex; flex-direction: column; gap: 0.2rem; }
.sr-se-links { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
.sr-se-link { font-weight: 700; text-decoration: underline; color: inherit; }
.sr-banner-close { background: transparent; border: none; color: inherit; cursor: pointer; font-size: 1rem; }
.sr-ops-grid { display: grid; grid-template-columns: 340px minmax(0, 1fr); gap: 1rem; align-items: start; }
@media (max-width: 980px) { .sr-ops-grid { grid-template-columns: 1fr; } }
</style>
