<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { RecoAnalyticsItem, RecoAnomalyItem, RecoDocDetail } from "../types";
import {
  buildBaseAnomalies,
  buildDrawerAnomalies,
  computeAnalyticsKpi,
  exportAnalyticsCsv,
  formatAnalyticsNumber as fmt,
  normalizeAnalyticsRow,
} from "../utils/analyticsHelpers";
import RecoItemDrawer from "./RecoItemDrawer.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{ liveConnected: boolean; refreshTick?: number }>(),
  { refreshTick: 0 }
);

function loadPref(key: string, fallback: string): string {
  const v = localStorage.getItem(key);
  return v === null ? fallback : v;
}

function loadPrefNumber(key: string, fallback: number): number {
  const v = localStorage.getItem(key);
  if (v === null || v === "") return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

const years = ref<number[]>([]);
const year = ref<number>(new Date().getFullYear());
const dateFrom = ref<string>(loadPref("sr_dateFrom", ""));
const dateTo = ref<string>(loadPref("sr_dateTo", ""));
const loading = ref<boolean>(false);
const items = ref<RecoAnalyticsItem[]>([]);
const threshold = ref<number>(loadPrefNumber("sr_threshold", 0.0000001));
const direction = ref<string>(loadPref("sr_direction", "all"));
const q = ref<string>(loadPref("sr_q", ""));
const sortKey = ref<string>(loadPref("sr_sortKey", "risk_score"));
const sortDir = ref<string>(loadPref("sr_sortDir", "desc"));
const selected = ref<RecoAnalyticsItem | null>(null);
const detailsLoading = ref<boolean>(false);
const details = ref<RecoDocDetail[]>([]);
const lastUpdatedAt = ref<string>("");
const progress = ref({ draft: 0, submitted: 0, submittedPct: 0, openPct: 0 });
const toast = ref({ show: false, text: "" });
let toastTimer: number | null = null;

function callRpc<T = any>(method: string, args: Record<string, any> = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    frappe.call({
      method,
      args,
      quiet: true,
      callback: (r: { message?: T }) => resolve(r.message as T),
      error: (e: any) => reject(e),
    });
  });
}

function showToast(text: string) {
  toast.value = { show: true, text };
  if (toastTimer !== null) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => (toast.value.show = false), 2000);
}

function persistPrefs() {
  localStorage.setItem("sr_threshold", String(threshold.value ?? ""));
  localStorage.setItem("sr_direction", String(direction.value ?? "all"));
  localStorage.setItem("sr_q", String(q.value ?? ""));
  localStorage.setItem("sr_sortKey", String(sortKey.value ?? "risk_score"));
  localStorage.setItem("sr_sortDir", String(sortDir.value ?? "desc"));
  localStorage.setItem("sr_dateFrom", String(dateFrom.value ?? ""));
  localStorage.setItem("sr_dateTo", String(dateTo.value ?? ""));
}

async function loadYears() {
  const res = await callRpc<number[]>("erpnextkta.kta_stock.services.stock_reconciliation_dashboard_service.get_years");
  years.value = Array.isArray(res) ? res : [];
  if (years.value.length && !years.value.includes(year.value)) year.value = years.value[0];
}

function buildDashboardArgs() {
  return { year: year.value, from_date: dateFrom.value || null, to_date: dateTo.value || null };
}

async function loadDashboard(resetSelection = true) {
  loading.value = true;
  try {
    if (resetSelection) {
      selected.value = null;
      details.value = [];
    }
    const res = await callRpc<any>(
      "erpnextkta.kta_stock.services.stock_reconciliation_dashboard_service.get_dashboard",
      buildDashboardArgs()
    );
    items.value = (res?.items || []).map(normalizeAnalyticsRow);
    lastUpdatedAt.value = new Date().toLocaleString();
    const counts = res?.meta?.counts || {};
    progress.value = {
      draft: Number(counts.draft || 0),
      submitted: Number(counts.submitted || 0),
      submittedPct: Number(res?.meta?.progress_pct || 0),
      openPct: Number(res?.meta?.open_pct || 0),
    };
  } finally {
    loading.value = false;
  }
}

async function openItem(it: RecoAnalyticsItem) {
  selected.value = it;
  await refreshDetails();
}

async function refreshDetails() {
  if (!selected.value?.item_code) return;
  detailsLoading.value = true;
  details.value = [];
  try {
    const res = await callRpc<any>(
      "erpnextkta.kta_stock.services.stock_reconciliation_dashboard_service.get_item_details",
      { item_code: selected.value.item_code, ...buildDashboardArgs() }
    );
    details.value = res?.docs || [];
  } finally {
    detailsLoading.value = false;
  }
}

function closeDetails() {
  selected.value = null;
  details.value = [];
}

function openDoc(name: string) {
  frappe?.set_route?.("Form", "Stock Reconciliation", name);
}

function onYearOrDateChange() {
  persistPrefs();
  loadDashboard(true);
}

function setDirection(v: string) {
  direction.value = v;
  persistPrefs();
}

async function refreshNow() {
  await loadDashboard(false);
  if (selected.value) await refreshDetails();
  showToast(__("Yenilendi"));
}

const filteredRows = computed(() => {
  const t = Number(threshold.value || 0);
  const text = (q.value || "").trim().toLowerCase();
  return (items.value || []).filter((it) => {
    const net = Number(it.net_diff || 0);
    if (Math.abs(net) < t) return false;
    if (direction.value === "plus" && net < 0) return false;
    if (direction.value === "minus" && net > 0) return false;
    if (!text) return true;
    const hay = [it.item_code, it.item_name, it.uom, ...(it.warehouses || []).map((w) => w.warehouse)]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(text);
  });
});

const topRisks = computed(() =>
  [...filteredRows.value].sort((a, b) => Number(b.risk_score || 0) - Number(a.risk_score || 0)).slice(0, 10)
);

function setSort(key: string) {
  if (sortKey.value === key) sortDir.value = sortDir.value === "asc" ? "desc" : "asc";
  else {
    sortKey.value = key;
    sortDir.value = "desc";
  }
  persistPrefs();
}

const sortedRows = computed(() => {
  const key = sortKey.value as keyof RecoAnalyticsItem;
  const dir = sortDir.value === "asc" ? 1 : -1;
  return [...filteredRows.value].sort((a, b) => {
    const av = a?.[key];
    const bv = b?.[key];
    if (typeof av === "string" || typeof bv === "string") {
      return String(av || "").localeCompare(String(bv || "")) * dir;
    }
    return (Number(av || 0) - Number(bv || 0)) * dir;
  });
});

const kpi = computed(() => computeAnalyticsKpi(filteredRows.value || []));

function handleExportCSV() {
  exportAnalyticsCsv(sortedRows.value, year.value);
  showToast(__("CSV dışa aktarıldı"));
}

const anomalies = computed(() => {
  const merged = [...buildDrawerAnomalies(selected.value, details.value, __), ...buildBaseAnomalies(filteredRows.value || [], __)];
  const seen = new Set<string>();
  const uniq: RecoAnomalyItem[] = [];
  for (const a of merged) {
    if (seen.has(a.id)) continue;
    seen.add(a.id);
    uniq.push(a);
  }
  return uniq.sort((a, b) => b.score - a.score).slice(0, 8);
});

async function handleAnomalyClick(a: RecoAnomalyItem) {
  if (a.action?.kind === "doc" && a.action.docname) return openDoc(a.action.docname);
  if (a.action?.kind === "item" && a.action.item_code) {
    const it = (items.value || []).find((x) => x.item_code === a.action.item_code);
    if (it) await openItem(it);
    else showToast(__("Ürün mevcut listede bulunamadı: {0}", [a.action.item_code]));
  }
}

watch(
  () => props.refreshTick,
  async (val, oldVal) => {
    if (val && val !== oldVal) {
      await loadDashboard(false);
      if (selected.value) await refreshDetails();
    }
  }
);

defineExpose({ refreshNow });

onMounted(async () => {
  await loadYears();
  await loadDashboard(true);
});

onBeforeUnmount(() => {
  if (toastTimer !== null) window.clearTimeout(toastTimer);
});
</script>

<template>
  <div class="sr-analytics">
    <div class="sr-top-bar">
      <div class="sr-sub">
        <span v-if="lastUpdatedAt">{{ __("Son güncelleme: {0}", [lastUpdatedAt]) }}</span>
        <span v-else>{{ __("Yükleniyor...") }}</span>
      </div>
      <div class="sr-actions">
        <button type="button" class="sr-btn" :disabled="loading" @click="refreshNow">🔄 {{ __("Yenile") }}</button>
        <button type="button" class="sr-btn" :disabled="!filteredRows.length" @click="handleExportCSV">⬇️ {{ __("CSV Dışa Aktar") }}</button>
      </div>
    </div>

    <div class="sr-filters">
      <div class="sr-field">
        <label>{{ __("Yıl") }}</label>
        <select v-model="year" class="sr-input" @change="onYearOrDateChange">
          <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
        </select>
      </div>
      <div class="sr-field">
        <label>{{ __("Başlangıç Tarihi") }}</label>
        <input v-model="dateFrom" type="date" class="sr-input" @change="onYearOrDateChange" />
      </div>
      <div class="sr-field">
        <label>{{ __("Bitiş Tarihi") }}</label>
        <input v-model="dateTo" type="date" class="sr-input" @change="onYearOrDateChange" />
      </div>
      <div class="sr-field">
        <label>{{ __("Eşik (Mutlak Fark)") }}</label>
        <input v-model.number="threshold" type="number" step="0.001" class="sr-input" @input="persistPrefs" />
      </div>
      <div class="sr-field">
        <label>{{ __("Yön") }}</label>
        <div class="sr-pill-group">
          <button type="button" class="sr-pill" :class="{ active: direction === 'all' }" @click="setDirection('all')">{{ __("Tümü") }}</button>
          <button type="button" class="sr-pill" :class="{ active: direction === 'plus' }" @click="setDirection('plus')">+</button>
          <button type="button" class="sr-pill" :class="{ active: direction === 'minus' }" @click="setDirection('minus')">−</button>
        </div>
      </div>
      <div class="sr-field sr-grow">
        <label>{{ __("Malzeme Ara") }}</label>
        <input v-model="q" type="text" class="sr-input" :placeholder="__('Ürün kodu, adı veya depo...')" @input="persistPrefs" />
      </div>
    </div>

    <div class="sr-kpis">
      <div class="sr-card"><div class="kpi-title">{{ __("Etkilenen Ürünler") }}</div><div class="kpi-value">{{ kpi.itemsCount }}</div><div class="kpi-sub">{{ __("Filtrelenmiş görünüm") }}</div></div>
      <div class="sr-card"><div class="kpi-title">{{ __("Depolar") }}</div><div class="kpi-value">{{ kpi.warehousesCount }}</div><div class="kpi-sub">{{ __("Hareket gören") }}</div></div>
      <div class="sr-card"><div class="kpi-title">{{ __("Belge (Ürün Başı Maks)") }}</div><div class="kpi-value">{{ kpi.maxDocsCount }}</div><div class="kpi-sub">{{ __("En yüksek sıklık") }}</div></div>
      <div class="sr-card"><div class="kpi-title">{{ __("Toplam +") }}</div><div class="kpi-value plus">{{ fmt(kpi.totalPlus) }}</div><div class="kpi-sub">{{ __("Artı farklar toplamı") }}</div></div>
      <div class="sr-card"><div class="kpi-title">{{ __("Toplam −") }}</div><div class="kpi-value minus">{{ fmt(kpi.totalMinus) }}</div><div class="kpi-sub">{{ __("Eksi farklar toplamı") }}</div></div>
      <div class="sr-card"><div class="kpi-title">{{ __("Net") }}</div><div class="kpi-value" :class="{ plus: kpi.net >= 0, minus: kpi.net < 0 }">{{ fmt(kpi.net) }}</div><div class="kpi-sub">(+) + (−)</div></div>
      <div class="sr-card">
        <div class="kpi-title">{{ __("İlerleme %") }}</div>
        <div class="kpi-value">{{ progress.submittedPct }}%</div>
        <div class="kpi-sub">{{ __("Taslak: {0} • Onaylı: {1}", [progress.draft, progress.submitted]) }}</div>
        <div class="sr-progress">
          <div class="bar"><div class="fill" :style="{ width: progress.submittedPct + '%' }" /></div>
          <div class="muted">{{ __("Açık: %{0}", [progress.openPct]) }}</div>
        </div>
      </div>
    </div>

    <div class="sr-grid">
      <div class="sr-left-col">
        <div class="sr-panel">
          <div class="sr-panel-head"><h3>{{ __("Anomaliler") }}</h3><span class="muted">{{ __("Otomatik Kural Analizi") }}</span></div>
          <div v-if="loading" class="sr-loading">{{ __("Yükleniyor...") }}</div>
          <div v-else class="sr-list">
            <button v-for="a in anomalies" :key="a.id" type="button" class="sr-list-row" @click="handleAnomalyClick(a)">
              <div>
                <div class="sr-badges">
                  <span class="sr-badge" :class="a.severity.toLowerCase()">{{ a.severity }}</span>
                  <span class="sr-badge outline">{{ a.type }}</span>
                  <span class="sr-badge outline">{{ __("Skor: {0}", [Math.round(a.score)]) }}</span>
                </div>
                <div class="title">{{ a.title }}</div>
                <div class="desc">{{ a.desc }}</div>
              </div>
              <span class="muted">›</span>
            </button>
            <div v-if="!anomalies.length" class="muted sr-empty">{{ __("Mevcut filtreler için anomali tespit edilmedi.") }}</div>
          </div>
        </div>

        <div class="sr-panel">
          <div class="sr-panel-head"><h3>{{ __("En Yüksek Riskler") }}</h3><span class="muted">abs(net) × ln(docs+1)</span></div>
          <div v-if="loading" class="sr-loading">{{ __("Yükleniyor...") }}</div>
          <div v-else class="sr-list">
            <button v-for="it in topRisks" :key="it.item_code" type="button" class="sr-list-row" @click="openItem(it)">
              <div><div class="mono code">{{ it.item_code }}</div><div class="desc">{{ it.item_name }}</div></div>
              <div class="right">
                <div class="muted">{{ __("Skor: {0}", [fmt(it.risk_score)]) }}</div>
                <div class="net" :class="{ plus: it.net_diff >= 0, minus: it.net_diff < 0 }">{{ fmt(it.net_diff) }} {{ it.uom }}</div>
                <div class="muted">{{ __("{0} belge • {1} depo", [it.docs_count, it.warehouses?.length || 0]) }}</div>
              </div>
            </button>
            <div v-if="!topRisks.length" class="muted sr-empty">{{ __("Mevcut filtreler için kayıt yok.") }}</div>
          </div>
        </div>
      </div>

      <div class="sr-panel">
        <div class="sr-panel-head"><h3>{{ __("Ürünler") }}</h3><span class="muted">{{ __("{0} satır", [filteredRows.length]) }}</span></div>
        <div v-if="loading" class="sr-loading">{{ __("Yükleniyor...") }}</div>
        <div v-else class="sr-table-wrap">
          <table class="sr-table">
            <thead>
              <tr>
                <th class="clickable" @click="setSort('item_code')">{{ __("Ürün Kodu") }}</th>
                <th class="clickable" @click="setSort('item_name')">{{ __("Ürün Adı") }}</th>
                <th class="clickable" @click="setSort('uom')">{{ __("Birim") }}</th>
                <th class="clickable right" @click="setSort('net_diff')">{{ __("Net") }}</th>
                <th class="right">+ / −</th>
                <th class="clickable right" @click="setSort('docs_count')">{{ __("Belgeler") }}</th>
                <th class="right">{{ __("Depolar") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="it in sortedRows" :key="it.item_code" class="sr-row" @click="openItem(it)">
                <td class="mono">{{ it.item_code }}</td>
                <td class="truncate">{{ it.item_name }}</td>
                <td class="mono">{{ it.uom }}</td>
                <td class="right mono" :class="{ plus: it.net_diff >= 0, minus: it.net_diff < 0 }">{{ fmt(it.net_diff) }}</td>
                <td class="right mono"><span class="plus">+{{ fmt(it.total_plus) }}</span> / <span class="minus">{{ fmt(it.total_minus) }}</span></td>
                <td class="right mono">{{ it.docs_count || 0 }}</td>
                <td class="right mono">{{ it.warehouses?.length || 0 }}</td>
              </tr>
              <tr v-if="!sortedRows.length"><td colspan="7" class="muted sr-empty">{{ __("Veri bulunamadı.") }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <RecoItemDrawer :selected="selected" :details="details" :details-loading="detailsLoading" :live-connected="liveConnected" @close="closeDetails" @refresh-details="refreshDetails" @open-doc="openDoc" />
    <div v-if="toast.show" class="sr-toast">⚡ {{ toast.text }}</div>
  </div>
</template>

<style scoped>
.sr-analytics { display: flex; flex-direction: column; gap: 0.9rem; }
.sr-top-bar { display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
.sr-sub, .muted { color: var(--text-muted, #64748b); font-size: 0.78rem; }
.sr-actions { display: flex; gap: 0.5rem; }
.sr-btn, .sr-pill { padding: 0.42rem 0.82rem; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-size: 0.8rem; font-weight: 700; cursor: pointer; }
[data-theme="dark"] .sr-btn, [data-theme="dark"] .sr-pill { background: rgba(255, 255, 255, 0.06); border-color: rgba(255, 255, 255, 0.16); color: #f8fafc; }
.sr-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.sr-pill.active { background: #2563eb; border-color: #2563eb; color: #ffffff; }
.sr-filters { display: flex; flex-wrap: wrap; gap: 0.65rem; padding: 0.85rem 1rem; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; }
[data-theme="dark"] .sr-filters { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12)); }
.sr-field { min-width: 145px; display: flex; flex-direction: column; gap: 0.25rem; }
.sr-field label { font-size: 0.74rem; font-weight: 700; color: var(--text-muted, #64748b); margin: 0; }
.sr-grow { flex: 1; min-width: 220px; }
.sr-input { width: 100%; padding: 0.4rem 0.6rem; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-size: 0.82rem; box-sizing: border-box; }
[data-theme="dark"] .sr-input { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #f8fafc; }
.sr-pill-group { display: inline-flex; gap: 0.3rem; }
.sr-kpis { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 0.65rem; }
@media (max-width: 1180px) { .sr-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 640px) { .sr-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.sr-card, .sr-panel { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; padding: 0.8rem 0.95rem; }
[data-theme="dark"] .sr-card, [data-theme="dark"] .sr-panel { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12)); }
.kpi-title { font-size: 0.74rem; color: var(--text-muted, #64748b); font-weight: 600; }
.kpi-value { margin-top: 0.35rem; font-size: 1.15rem; font-weight: 800; }
.kpi-sub { margin-top: 0.15rem; font-size: 0.72rem; color: var(--text-muted, #64748b); }
.plus { color: #15803d; }
.minus { color: #dc2626; }
[data-theme="dark"] .plus { color: #4ade80; }
[data-theme="dark"] .minus { color: #f87171; }
.sr-progress { margin-top: 0.4rem; display: grid; gap: 0.3rem; }
.sr-progress .bar { height: 7px; background: var(--bg-color, #f1f5f9); border-radius: 9999px; overflow: hidden; }
[data-theme="dark"] .sr-progress .bar { background: rgba(255, 255, 255, 0.1); }
.sr-progress .fill { height: 100%; background: #2563eb; }
.sr-grid { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 0.85rem; }
@media (max-width: 1050px) { .sr-grid { grid-template-columns: 1fr; } }
.sr-left-col { display: flex; flex-direction: column; gap: 0.85rem; }
.sr-panel-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.6rem; }
.sr-panel-head h3 { margin: 0; font-size: 0.92rem; font-weight: 800; }
.sr-list { display: flex; flex-direction: column; gap: 0.5rem; }
.sr-list-row { width: 100%; text-align: left; background: var(--bg-color, #f8fafc); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.6rem; padding: 0.65rem 0.75rem; display: flex; justify-content: space-between; gap: 0.6rem; cursor: pointer; color: inherit; }
[data-theme="dark"] .sr-list-row { background: rgba(255, 255, 255, 0.03); border-color: rgba(255, 255, 255, 0.1); }
.sr-list-row:hover { border-color: #2563eb; }
.sr-badges { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.35rem; }
.sr-badge { font-size: 0.68rem; padding: 0.12rem 0.45rem; border-radius: 9999px; font-weight: 700; }
.sr-badge.outline { border: 1px solid var(--border-color, #cbd5e1); color: var(--text-muted, #64748b); }
.sr-badge.high { background: #fee2e2; color: #b91c1c; }
.sr-badge.med { background: #ffedd5; color: #c2410c; }
.sr-badge.low { background: #dcfce7; color: #15803d; }
.title { font-size: 0.8rem; font-weight: 700; }
.desc { font-size: 0.75rem; color: var(--text-muted, #64748b); }
.sr-table-wrap { overflow-x: auto; }
.sr-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; text-align: left; }
.sr-table th { padding: 0.55rem 0.65rem; background: var(--bg-color, #f8fafc); border-bottom: 1.5px solid var(--border-color, #cbd5e1); color: var(--text-muted, #475569); white-space: nowrap; }
[data-theme="dark"] .sr-table th { background: rgba(255, 255, 255, 0.04); color: #cbd5e1; }
.sr-table td { padding: 0.55rem 0.65rem; border-bottom: 1px solid var(--border-color, #e2e8f0); }
.sr-row { cursor: pointer; }
.sr-row:hover { background: rgba(37, 99, 235, 0.05); }
.clickable { cursor: pointer; user-select: none; }
.right { text-align: right; }
.truncate { max-width: 240px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.sr-loading, .sr-empty { padding: 1.25rem; text-align: center; }
.sr-toast { position: fixed; bottom: 18px; left: 18px; background: #0f172a; color: #ffffff; padding: 0.55rem 0.9rem; border-radius: 0.6rem; font-size: 0.8rem; z-index: 1080; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2); }
</style>
