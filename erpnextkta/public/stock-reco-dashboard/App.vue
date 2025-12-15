<template>
    <div class="sr-wrap">
        <!-- Header -->
        <div class="sr-header">
        <div class="sr-title">
            <div class="sr-title-row">
            <h2>Stock Reconciliation Dashboard</h2>
            <span class="sr-live" :class="{ on: liveConnected }" title="Realtime updates">
                <span class="dot" />
                {{ liveConnected ? "Live" : "Offline" }}
            </span>
            </div>
            <div class="sr-sub">
            <span v-if="lastUpdatedAt">Last update: {{ lastUpdatedAt }}</span>
            <span v-else>Loading…</span>
            </div>
        </div>

        <div class="sr-actions">
            <button class="btn btn-default" @click="refreshNow" :disabled="loading">
            <span class="fa fa-refresh"></span> Refresh
            </button>
            <button class="btn btn-default" @click="exportCSV" :disabled="!filteredRows.length">
            <span class="fa fa-download"></span> Export CSV
            </button>
        </div>
        </div>

        <!-- Filters -->
        <div class="sr-filters">
        <div class="sr-field">
            <label>Year</label>
            <select class="input-with-feedback form-control" v-model="year" @change="onYearChange">
            <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
            </select>
        </div>

        <div class="sr-field">
            <label>Threshold (abs diff)</label>
            <input
            class="input-with-feedback form-control"
            type="number"
            step="0.001"
            v-model.number="threshold"
            @input="persistPrefs"
            placeholder="e.g. 0.001"
            />
        </div>

        <div class="sr-field sr-toggle">
            <label>Direction</label>
            <div class="sr-pill">
            <button class="pill" :class="{ active: direction === 'all' }" @click="setDirection('all')">All</button>
            <button class="pill" :class="{ active: direction === 'plus' }" @click="setDirection('plus')">+</button>
            <button class="pill" :class="{ active: direction === 'minus' }" @click="setDirection('minus')">−</button>
            </div>
        </div>

        <div class="sr-field sr-grow">
            <label>Search</label>
            <input
            class="input-with-feedback form-control"
            v-model="q"
            @input="persistPrefs"
            placeholder="Item code / name / warehouse…"
            />
        </div>
        </div>

        <!-- KPI cards -->
        <div class="sr-kpis">
        <div class="sr-card">
            <div class="kpi-title">Affected Items</div>
            <div class="kpi-value">{{ kpi.itemsCount }}</div>
            <div class="kpi-sub">Filtered view</div>
        </div>

        <div class="sr-card">
            <div class="kpi-title">Warehouses</div>
            <div class="kpi-value">{{ kpi.warehousesCount }}</div>
            <div class="kpi-sub">With movement</div>
        </div>

        <div class="sr-card">
            <div class="kpi-title">Docs (max per item)</div>
            <div class="kpi-value">{{ kpi.maxDocsCount }}</div>
            <div class="kpi-sub">Highest frequency</div>
        </div>

        <div class="sr-card">
            <div class="kpi-title">Total +</div>
            <div class="kpi-value plus">{{ fmt(kpi.totalPlus) }}</div>
            <div class="kpi-sub">Sum of positive diffs</div>
        </div>

        <div class="sr-card">
            <div class="kpi-title">Total −</div>
            <div class="kpi-value minus">{{ fmt(kpi.totalMinus) }}</div>
            <div class="kpi-sub">Sum of negative diffs</div>
        </div>

        <div class="sr-card">
            <div class="kpi-title">Net</div>
            <div class="kpi-value" :class="{ plus: kpi.net >= 0, minus: kpi.net < 0 }">
            {{ fmt(kpi.net) }}
            </div>
            <div class="kpi-sub">(+)+ (−)</div>
        </div>
        </div>

        <!-- Content grid -->
        <div class="sr-grid">
            <!-- Left column: Anomalies + Top risks stacked -->
            <div class="sr-left-col">
                <!-- Anomalies -->
                <div class="sr-panel">
                <div class="sr-panel-head">
                    <h3>Anomalies</h3>
                    <span class="muted">Auto insights (rule-based)</span>
                </div>

                <div v-if="loading" class="sr-loading">Loading…</div>

                <div v-else class="sr-anom-list">
                    <button
                    v-for="a in anomalies"
                    :key="a.id"
                    class="sr-anom-row"
                    @click="handleAnomalyClick(a)"
                    >
                    <div class="left">
                        <div class="sr-badges">
                        <span class="sr-badge" :class="badgeClass(a.severity)">{{ a.severity }}</span>
                        <span class="sr-badge outline">{{ a.type }}</span>
                        <span class="sr-badge outline">Score {{ Math.round(a.score) }}</span>
                        </div>
                        <div class="title">{{ a.title }}</div>
                        <div class="desc">{{ a.desc }}</div>
                    </div>
                    <div class="right">
                        <span class="fa fa-chevron-right muted"></span>
                    </div>
                    </button>

                    <div v-if="!anomalies.length" class="muted sr-empty">
                    No anomalies detected for current filters.
                    </div>
                </div>
                </div>

                <!-- Top risks -->
                <div class="sr-panel">
                <div class="sr-panel-head">
                    <h3>Top Risks</h3>
                    <span class="muted">Score = abs(net) × ln(docs+1)</span>
                </div>

                <div v-if="loading" class="sr-loading">Loading…</div>

                <div v-else class="sr-risk-list">
                    <button
                    v-for="it in topRisks"
                    :key="it.item_code"
                    class="sr-risk-row"
                    @click="openItem(it)"
                    :title="it.item_code"
                    >
                    <div class="left">
                        <div class="code">{{ it.item_code }}</div>
                        <div class="name">{{ it.item_name }}</div>
                    </div>
                    <div class="right">
                        <div class="score">Score: {{ fmt(it.risk_score) }}</div>
                        <div class="net" :class="{ plus: it.net_diff >= 0, minus: it.net_diff < 0 }">
                        Net: {{ fmt(it.net_diff) }} {{ it.uom }}
                        </div>
                        <div class="meta">{{ it.docs_count || 0 }} docs • {{ it.warehouses?.length || 0 }} wh</div>
                    </div>
                    </button>

                    <div v-if="!topRisks.length" class="muted sr-empty">
                    No rows for current filters.
                    </div>
                </div>
                </div>
            </div>
            <!-- Right: Main table -->
            <div class="sr-panel">
                <div class="sr-panel-head">
                    <h3>Items</h3>
                    <div class="sr-mini">
                        <span class="muted">{{ filteredRows.length }} rows</span>
                    </div>
                </div>

                <div v-if="loading" class="sr-loading">Loading…</div>

                <div v-else class="sr-table-wrap">
                    <table class="table table-bordered sr-table">
                        <thead>
                            <tr>
                                <th @click="setSort('item_code')" class="clickable">Item</th>
                                <th @click="setSort('item_name')" class="clickable">Name</th>
                                <th @click="setSort('uom')" class="clickable">UOM</th>
                                <th @click="setSort('net_diff')" class="clickable right">Net</th>
                                <th class="right">+ / −</th>
                                <th class="right">Docs</th>
                                <th class="right">Warehouses</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="it in sortedRows" :key="it.item_code" class="sr-row" @click="openItem(it)">
                                <td class="mono">{{ it.item_code }}</td>
                                <td class="truncate">{{ it.item_name }}</td>
                                <td class="mono">{{ it.uom }}</td>
                                <td class="right mono" :class="{ plus: it.net_diff >= 0, minus: it.net_diff < 0 }">
                                    {{ fmt(it.net_diff) }}
                                </td>
                                <td class="right mono">
                                    <span class="plus">+{{ fmt(it.total_plus) }}</span>
                                    <span class="sep">/</span>
                                    <span class="minus">{{ fmt(it.total_minus) }}</span>
                                </td>
                                <td class="right mono">{{ it.docs_count || 0 }}</td>
                                <td class="right mono">{{ it.warehouses?.length || 0 }}</td>
                            </tr>
                            <tr v-if="!sortedRows.length">
                                <td colspan="7" class="muted sr-empty">No data.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Drawer -->
        <div class="sr-drawer" :class="{ open: !!selected }">
        <div class="sr-drawer-head">
            <div>
            <div class="mono code">{{ selected?.item_code }}</div>
            <div class="name">{{ selected?.item_name }}</div>
            </div>
            <button class="btn btn-default" @click="closeDetails">
            <span class="fa fa-times"></span>
            </button>
        </div>

        <div class="sr-drawer-body">
            <div class="sr-drawer-kpis">
            <div class="mini">
                <div class="t">Net</div>
                <div class="v" :class="{ plus: selected?.net_diff >= 0, minus: selected?.net_diff < 0 }">
                {{ fmt(selected?.net_diff) }} {{ selected?.uom }}
                </div>
            </div>
            <div class="mini">
                <div class="t">Docs</div>
                <div class="v">{{ selected?.docs_count || 0 }}</div>
            </div>
            <div class="mini">
                <div class="t">Warehouses</div>
                <div class="v">{{ selected?.warehouses?.length || 0 }}</div>
            </div>
            <div class="mini">
                <div class="t">Risk</div>
                <div class="v">{{ fmt(selected?.risk_score) }}</div>
            </div>
            </div>

            <div class="sr-section">
            <div class="sr-section-head">
                <h4>Warehouse breakdown</h4>
            </div>

            <div class="sr-bars" v-if="selected?.warehouses?.length">
                <div
                v-for="w in selected.warehouses"
                :key="w.warehouse"
                class="sr-bar-row"
                :title="w.warehouse"
                >
                <div class="wh truncate">{{ w.warehouse }}</div>
                <div class="bar">
                    <div class="fill" :style="{ width: barWidth(w.diff) + '%' }"></div>
                </div>
                <div class="val mono" :class="{ plus: w.diff >= 0, minus: w.diff < 0 }">
                    {{ fmt(w.diff) }}
                </div>
                </div>
            </div>
            <div v-else class="muted">No warehouse data.</div>
            </div>

            <div class="sr-section">
            <div class="sr-section-head">
                <h4>Documents</h4>
                <button class="btn btn-default btn-xs" @click="refreshDetails" :disabled="detailsLoading">
                <span class="fa fa-refresh"></span> Refresh
                </button>
            </div>

            <div v-if="detailsLoading" class="sr-loading">Loading…</div>

            <table v-else class="table table-bordered sr-table">
                <thead>
                <tr>
                    <th>Doc</th>
                    <th>Date</th>
                    <th>Warehouse</th>
                    <th class="right">Diff</th>
                </tr>
                </thead>
                <tbody>
                <tr v-for="d in details" :key="d.name" class="sr-row" @click="openDoc(d.name)">
                    <td class="mono">{{ d.name }}</td>
                    <td class="mono">{{ d.posting_date }}</td>
                    <td class="truncate">{{ d.warehouse }}</td>
                    <td class="right mono" :class="{ plus: d.diff_qty >= 0, minus: d.diff_qty < 0 }">
                    {{ fmt(d.diff_qty) }}
                    </td>
                </tr>

                <tr v-if="!details.length">
                    <td colspan="4" class="muted sr-empty">No documents.</td>
                </tr>
                </tbody>
            </table>
            </div>
        </div>
        </div>

        <!-- Toast -->
        <div v-if="toast.show" class="sr-toast">
        <span class="fa fa-bolt"></span>
        {{ toast.text }}
        </div>
    </div>
</template>

<script setup>
/* English comments as requested */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const years = ref([]);
const year = ref(new Date().getFullYear());

const loading = ref(false);
const items = ref([]);

const threshold = ref(loadPrefNumber("sr_threshold", 0.0000001));
const direction = ref(loadPref("sr_direction", "all")); // all | plus | minus
const q = ref(loadPref("sr_q", ""));

const selected = ref(null);
const detailsLoading = ref(false);
const details = ref([]);

const lastUpdatedAt = ref("");
const liveConnected = ref(false);

const toast = ref({ show: false, text: "" });
let toastTimer = null;

// --- RPC helper ---
function call(method, args = {}) {
  return new Promise((resolve, reject) => {
    frappe.call({
      method,
      args,
      callback: (r) => resolve(r.message),
      error: (e) => reject(e),
    });
  });
}

function fmt(v) {
  const n = Number(v || 0);
  return n.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

function nowLabel() {
  return new Date().toLocaleString();
}

function showToast(text) {
  toast.value = { show: true, text };
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (toast.value.show = false), 2000);
}

function persistPrefs() {
  localStorage.setItem("sr_threshold", String(threshold.value ?? ""));
  localStorage.setItem("sr_direction", String(direction.value ?? "all"));
  localStorage.setItem("sr_q", String(q.value ?? ""));
}

function loadPref(key, fallback) {
  const v = localStorage.getItem(key);
  return v === null ? fallback : v;
}
function loadPrefNumber(key, fallback) {
  const v = localStorage.getItem(key);
  if (v === null || v === "") return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

// --- Data loaders ---
async function loadYears() {
  years.value = await call("erpnextkta.rest-api.stock_reconciliation_dashboard.get_years");
  if (years.value.length && !years.value.includes(year.value)) {
    year.value = years.value[0];
  }
}

function normalizeRow(it) {
  // Compute extra fields used by UI (plus/minus totals + risk score)
  const net = Number(it.net_diff || 0);

  let plus = 0;
  let minus = 0;

  const wh = Array.isArray(it.warehouses) ? it.warehouses : [];
  wh.forEach((w) => {
    const d = Number(w.diff || 0);
    if (d >= 0) plus += d;
    else minus += d;
  });

  const docs = Number(it.docs_count || 0);
  const risk = Math.abs(net) * Math.log(docs + 1);

  return {
    ...it,
    net_diff: net,
    total_plus: plus,
    total_minus: minus,
    docs_count: docs,
    risk_score: risk,
    warehouses: wh,
  };
}

async function loadDashboard(resetSelection = true) {
  loading.value = true;
  try {
    if (resetSelection) {
      selected.value = null;
      details.value = [];
    }

    const res = await call("erpnextkta.rest-api.stock_reconciliation_dashboard.get_dashboard", {
      year: year.value,
    });

    items.value = (res?.items || []).map(normalizeRow);
    lastUpdatedAt.value = nowLabel();
  } finally {
    loading.value = false;
  }
}

async function openItem(it) {
  selected.value = it;
  await refreshDetails();
}

async function refreshDetails() {
  if (!selected.value?.item_code) return;

  detailsLoading.value = true;
  details.value = [];
  try {
    const res = await call("erpnextkta.rest-api.stock_reconciliation_dashboard.get_item_details", {
      item_code: selected.value.item_code,
      year: year.value,
    });
    details.value = res?.docs || [];
  } finally {
    detailsLoading.value = false;
  }
}

function closeDetails() {
  selected.value = null;
  details.value = [];
}

function openDoc(name) {
  frappe.set_route("Form", "Stock Reconciliation", name);
}

function onYearChange() {
  persistPrefs();
  loadDashboard(true);
}

function setDirection(v) {
  direction.value = v;
  persistPrefs();
}

async function refreshNow() {
  await loadDashboard(false);
  if (selected.value) await refreshDetails();
  showToast("Refreshed");
}

// --- Filtering / sorting ---
const filteredRows = computed(() => {
  const t = Number(threshold.value || 0);
  const text = (q.value || "").trim().toLowerCase();

  return (items.value || []).filter((it) => {
    const net = Number(it.net_diff || 0);

    if (Math.abs(net) < t) return false;
    if (direction.value === "plus" && net < 0) return false;
    if (direction.value === "minus" && net > 0) return false;

    if (!text) return true;

    const hay = [
      it.item_code,
      it.item_name,
      it.uom,
      ...(it.warehouses || []).map((w) => w.warehouse),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return hay.includes(text);
  });
});

const topRisks = computed(() => {
  return [...filteredRows.value]
    .sort((a, b) => Number(b.risk_score || 0) - Number(a.risk_score || 0))
    .slice(0, 10);
});

const sortKey = ref(loadPref("sr_sortKey", "risk_score"));
const sortDir = ref(loadPref("sr_sortDir", "desc")); // asc/desc

function setSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === "asc" ? "desc" : "asc";
  } else {
    sortKey.value = key;
    sortDir.value = "desc";
  }
  localStorage.setItem("sr_sortKey", sortKey.value);
  localStorage.setItem("sr_sortDir", sortDir.value);
}

const sortedRows = computed(() => {
  const key = sortKey.value;
  const dir = sortDir.value === "asc" ? 1 : -1;

  return [...filteredRows.value].sort((a, b) => {
    const av = a?.[key];
    const bv = b?.[key];

    // string sort
    if (typeof av === "string" || typeof bv === "string") {
      return String(av || "").localeCompare(String(bv || "")) * dir;
    }
    // number sort
    return (Number(av || 0) - Number(bv || 0)) * dir;
  });
});

// --- KPI computation ---
const kpi = computed(() => {
  const rows = filteredRows.value || [];

  const whSet = new Set();
  let totalPlus = 0;
  let totalMinus = 0;
  let net = 0;
  let maxDocs = 0;

  rows.forEach((it) => {
    net += Number(it.net_diff || 0);
    totalPlus += Number(it.total_plus || 0);
    totalMinus += Number(it.total_minus || 0);
    maxDocs = Math.max(maxDocs, Number(it.docs_count || 0));
    (it.warehouses || []).forEach((w) => whSet.add(w.warehouse));
  });

  return {
    itemsCount: rows.length,
    warehousesCount: whSet.size,
    totalPlus,
    totalMinus,
    net,
    maxDocsCount: maxDocs,
  };
});

// --- Simple bar visual for warehouse breakdown ---
function barWidth(diff) {
  const abs = Math.abs(Number(diff || 0));
  const wh = selected.value?.warehouses || [];
  const max = Math.max(...wh.map((w) => Math.abs(Number(w.diff || 0))), 0.0000001);
  return Math.min(100, (abs / max) * 100);
}

// --- Export CSV (client-side) ---
function exportCSV() {
  const rows = sortedRows.value || [];
  const headers = ["item_code", "item_name", "uom", "net_diff", "total_plus", "total_minus", "docs_count", "warehouses_count"];

  const lines = [];
  lines.push(headers.join(","));

  rows.forEach((it) => {
    const line = [
      csv(it.item_code),
      csv(it.item_name),
      csv(it.uom),
      Number(it.net_diff || 0),
      Number(it.total_plus || 0),
      Number(it.total_minus || 0),
      Number(it.docs_count || 0),
      Number(it.warehouses?.length || 0),
    ].join(",");
    lines.push(line);
  });

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = `stock-reco-dashboard-${year.value}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();

  URL.revokeObjectURL(url);
  showToast("CSV exported");
}

function csv(v) {
  const s = String(v ?? "");
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}
/* ---------- Anomalies (rule-based insights) ---------- */

/* Small helpers */
function clamp(n, a, b) {
  return Math.max(a, Math.min(b, n));
}
function abs(n) {
  return Math.abs(Number(n || 0));
}

function severityFromScore(score) {
  if (score >= 75) return "HIGH";
  if (score >= 45) return "MED";
  return "LOW";
}

function badgeClass(sev) {
  return sev === "HIGH" ? "high" : sev === "MED" ? "med" : "low";
}

/* Warehouse stats per item (from get_dashboard warehouses[]) */
function whStats(it) {
  const wh = Array.isArray(it.warehouses) ? it.warehouses : [];
  let hasPos = false;
  let hasNeg = false;
  let totalAbs = 0;
  let maxAbs = 0;
  let maxWh = null;
  let maxDiff = 0;

  for (const w of wh) {
    const d = Number(w.diff || 0);
    if (d > 0) hasPos = true;
    if (d < 0) hasNeg = true;
    const a = Math.abs(d);
    totalAbs += a;
    if (a > maxAbs) {
      maxAbs = a;
      maxWh = w.warehouse;
      maxDiff = d;
    }
  }

  const ratio = totalAbs > 0 ? maxAbs / totalAbs : 0;

  return {
    hasPos,
    hasNeg,
    totalAbs,
    maxAbs,
    maxWh,
    maxDiff,
    ratio,
    whCount: wh.length,
  };
}

/* Document stats per selected item (from get_item_details docs[]) */
function docStats(docs) {
  const rows = Array.isArray(docs) ? docs : [];
  const absList = rows.map((d) => Math.abs(Number(d.diff_qty || 0))).filter((x) => Number.isFinite(x));
  const maxAbs = absList.length ? Math.max(...absList) : 0;
  const sumAbs = absList.reduce((a, b) => a + b, 0);
  const avgAbs = absList.length ? sumAbs / absList.length : 0;

  let maxDoc = null;
  for (const d of rows) {
    const a = Math.abs(Number(d.diff_qty || 0));
    if (!maxDoc || a > Math.abs(Number(maxDoc.diff_qty || 0))) maxDoc = d;
  }

  return { maxAbs, sumAbs, avgAbs, maxDoc, count: rows.length };
}

/* Build anomalies from dashboard rows (fast + impressive) */
function buildBaseAnomalies(rows) {
  const out = [];

  for (const it of rows) {
    const net = Number(it.net_diff || 0);
    const docsCount = Number(it.docs_count || 0);
    const st = whStats(it);

    // 1) Contradiction: same item has + and - across warehouses
    if (st.hasPos && st.hasNeg && st.totalAbs > 0) {
      const score =
        20 +
        25 * Math.log10(st.totalAbs + 1) +
        10 * Math.log(docsCount + 1) +
        8 * st.whCount;

      out.push({
        id: `contr-${it.item_code}`,
        type: "CONTRADICTION",
        severity: severityFromScore(score),
        score: clamp(score, 0, 100),
        title: "Opposite direction across warehouses",
        desc: `${it.item_code} shows both + and − diffs across warehouses.`,
        action: { kind: "item", item_code: it.item_code },
      });
    }

    // 2) Concentration: most impact in one warehouse
    if (st.ratio >= 0.8 && st.totalAbs > 0) {
      const score =
        15 +
        30 * st.ratio +
        22 * Math.log10(st.totalAbs + 1) +
        6 * Math.log(docsCount + 1);

      out.push({
        id: `conc-${it.item_code}`,
        type: "CONCENTRATION",
        severity: severityFromScore(score),
        score: clamp(score, 0, 100),
        title: "Concentrated in a single warehouse",
        desc: `${Math.round(st.ratio * 100)}% of movement is from "${st.maxWh}" (${fmt(st.maxDiff)}).`,
        action: { kind: "item", item_code: it.item_code },
      });
    }

    // 3) Churn: too many docs for same item
    if (docsCount >= 8) {
      const score =
        18 +
        14 * Math.log(docsCount + 1) +
        18 * Math.log10(Math.abs(net) + 1) +
        6 * st.whCount;

      out.push({
        id: `churn-${it.item_code}`,
        type: "CHURN",
        severity: severityFromScore(score),
        score: clamp(score, 0, 100),
        title: "Frequent changes",
        desc: `${it.item_code} appears in ${docsCount} documents (higher audit risk).`,
        action: { kind: "item", item_code: it.item_code },
      });
    }

    // 4) Oscillation (approx): big total abs but net small (uses warehouses sumAbs)
    // Note: this is approximate without doc-level, but still useful.
    if (st.totalAbs > 0) {
      const ratioNet = Math.abs(net) / st.totalAbs; // small => oscillation
      if (st.totalAbs >= 10 && ratioNet <= 0.15) {
        const score =
          22 +
          30 * (1 - ratioNet) +
          20 * Math.log10(st.totalAbs + 1) +
          8 * Math.log(docsCount + 1);

        out.push({
          id: `osci-${it.item_code}`,
          type: "OSCILLATION",
          severity: severityFromScore(score),
          score: clamp(score, 0, 100),
          title: "Back-and-forth movement",
          desc: `Total movement ${fmt(st.totalAbs)} but net ${fmt(net)} (ratio ${Math.round(ratioNet * 100)}%).`,
          action: { kind: "item", item_code: it.item_code },
        });
      }
    }
  }

  return out;
}

/* Drawer-based anomalies (more accurate, uses docs list) */
const drawerAnomalies = computed(() => {
  if (!selected.value || !details.value?.length) return [];

  const it = selected.value;
  const docs = details.value;
  const ds = docStats(docs);

  const net = Number(it.net_diff || 0);
  const out = [];

  // A) Single document spike
  if (ds.count >= 2 && ds.maxDoc) {
    const amax = Math.abs(Number(ds.maxDoc.diff_qty || 0));
    // Spike if 3x average OR contributes >= 70% of total abs
    const contributes = ds.sumAbs > 0 ? amax / ds.sumAbs : 0;
    if (amax >= ds.avgAbs * 3 || contributes >= 0.7) {
      const score = 35 + 35 * contributes + 20 * Math.log10(amax + 1);
      out.push({
        id: `spike-${it.item_code}-${ds.maxDoc.name}`,
        type: "DOC_SPIKE",
        severity: severityFromScore(score),
        score: clamp(score, 0, 100),
        title: "Single document dominates the result",
        desc: `${ds.maxDoc.name} drives ${Math.round(contributes * 100)}% of item movement (${fmt(ds.maxDoc.diff_qty)}).`,
        action: { kind: "doc", docname: ds.maxDoc.name },
      });
    }
  }

  // B) Oscillation (doc-level): sumAbs big, net small
  if (ds.sumAbs > 0) {
    const ratioNet = Math.abs(net) / ds.sumAbs;
    if (ds.sumAbs >= 10 && ratioNet <= 0.12 && ds.count >= 3) {
      const score = 30 + 35 * (1 - ratioNet) + 18 * Math.log10(ds.sumAbs + 1);
      out.push({
        id: `osci-doc-${it.item_code}`,
        type: "DOC_OSCILLATION",
        severity: severityFromScore(score),
        score: clamp(score, 0, 100),
        title: "Back-and-forth across documents",
        desc: `Total doc movement ${fmt(ds.sumAbs)} but net ${fmt(net)} (ratio ${Math.round(ratioNet * 100)}%).`,
        action: { kind: "item", item_code: it.item_code },
      });
    }
  }

  return out.sort((a, b) => b.score - a.score);
});

/* Main anomalies list: base anomalies + (if drawer open) drawer anomalies */
const anomalies = computed(() => {
  const base = buildBaseAnomalies(filteredRows.value || []);

  // If drawer open, merge item-specific deeper anomalies on top
  const merged = [...drawerAnomalies.value, ...base];

  // Deduplicate by id
  const seen = new Set();
  const uniq = [];
  for (const a of merged) {
    if (seen.has(a.id)) continue;
    seen.add(a.id);
    uniq.push(a);
  }

  return uniq.sort((a, b) => b.score - a.score).slice(0, 8);
});

/* Click handling */
async function handleAnomalyClick(a) {
  if (a.action?.kind === "doc" && a.action.docname) {
    openDoc(a.action.docname);
    return;
  }

  if (a.action?.kind === "item" && a.action.item_code) {
    const it = (items.value || []).find((x) => x.item_code === a.action.item_code);
    if (it) {
      await openItem(it);
    } else {
      // Fallback: just show toast
      showToast(`Item not found in current list: ${a.action.item_code}`);
    }
  }
}

// --- Realtime integration (Socket.IO) ---
let realtimeHandler = null;
let debounceTimer = null;

function scheduleRealtimeRefresh() {
  if (debounceTimer) clearTimeout(debounceTimer);

  debounceTimer = setTimeout(async () => {
    // Refresh main dashboard without closing details
    await loadDashboard(false);
    // If drawer open, refresh details too
    if (selected.value) await refreshDetails();
    showToast("Live update");
  }, 450);
}

onMounted(async () => {
  await loadYears();
  await loadDashboard(true);

  // Subscribe to realtime events from backend
  realtimeHandler = () => scheduleRealtimeRefresh();

  if (frappe?.realtime?.on) {
    frappe.realtime.on("stock_reco_dashboard_update", realtimeHandler);
    liveConnected.value = true;
  } else {
    liveConnected.value = false;
  }
});

onBeforeUnmount(() => {
  if (realtimeHandler && frappe?.realtime?.off) {
    frappe.realtime.off("stock_reco_dashboard_update", realtimeHandler);
  }
  if (debounceTimer) clearTimeout(debounceTimer);
  if (toastTimer) clearTimeout(toastTimer);
});
</script>

<style scoped>
/* Keep it close to Frappe look & feel */
.sr-wrap { padding: 16px; }

.sr-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 12px; margin-bottom: 12px;
}
.sr-title h2 { margin: 0; font-size: 20px; }
.sr-title-row { display: flex; align-items: center; gap: 10px; }
.sr-sub { margin-top: 2px; color: #6b7280; font-size: 12px; }
.sr-actions { display: flex; gap: 8px; }

.sr-live {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; padding: 4px 10px; border-radius: 999px;
  border: 1px solid #ddd; color: #6b7280; background: #fff;
}
.sr-live .dot { width: 8px; height: 8px; border-radius: 50%; background: #999; }
.sr-live.on { border-color: #b7eb8f; color: #1f7a1f; }
.sr-live.on .dot { background: #22c55e; }

.sr-filters {
  display: flex; flex-wrap: wrap; gap: 10px;
  margin: 12px 0 14px;
}
.sr-field { min-width: 160px; }
.sr-field label { display: block; font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.sr-grow { flex: 1; min-width: 260px; }

.sr-pill { display: inline-flex; gap: 6px; }
.pill {
  border: 1px solid #ddd; background: #fff; padding: 6px 10px;
  border-radius: 10px; font-size: 12px;
}
.pill.active { border-color: #111827; background: #111827; color: #fff; }

.sr-kpis {
  display: grid; grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px; margin-bottom: 14px;
}
.sr-card {
  border: 1px solid #e5e7eb; background: #fff; border-radius: 12px;
  padding: 10px 12px;
}
.kpi-title { font-size: 12px; color: #6b7280; }
.kpi-value { margin-top: 6px; font-size: 18px; font-weight: 700; }
.kpi-sub { margin-top: 2px; font-size: 12px; color: #9ca3af; }
.plus { color: #15803d; }
.minus { color: #b91c1c; }

.sr-grid {
  display: grid; grid-template-columns: 360px 1fr; gap: 12px;
}

.sr-panel {
  border: 1px solid #e5e7eb; background: #fff; border-radius: 12px;
  padding: 10px 12px;
  min-height: 340px;
}
.sr-panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
.sr-panel-head h3 { margin: 0; font-size: 14px; }
.muted { color: #6b7280; font-size: 12px; }

.sr-loading { padding: 14px; color: #6b7280; }

.sr-risk-list { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
.sr-risk-row {
  width: 100%;
  text-align: left;
  border: 1px solid #eef2f7;
  background: #fff;
  border-radius: 12px;
  padding: 10px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  cursor: pointer;
}
.sr-risk-row:hover { border-color: #d1d5db; }
.sr-risk-row .code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono"; font-size: 12px; }
.sr-risk-row .name { font-size: 12px; color: #374151; margin-top: 2px; }
.sr-risk-row .score { font-size: 12px; color: #6b7280; }
.sr-risk-row .net { font-size: 12px; margin-top: 2px; }
.sr-risk-row .meta { font-size: 11px; color: #9ca3af; margin-top: 2px; }

.sr-table-wrap { margin-top: 10px; }
.sr-table th { font-size: 12px; user-select: none; }
.sr-table td { font-size: 12px; }
.clickable { cursor: pointer; }
.right { text-align: right; }
.truncate { max-width: 340px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono"; }
.sr-row { cursor: pointer; }
.sr-row:hover { background: #f9fafb; }
.sep { margin: 0 6px; color: #9ca3af; }

.sr-empty { padding: 14px; text-align: center; }

.sr-drawer {
  /* Frappe top navbar height: v15 genelde ~60px */
  --sr-navbar-h: var(--navbar-height, 60px);

  position: fixed;
  top: var(--sr-navbar-h);                 /* ✅ navbar altından başla */
  right: 0;
  height: calc(100vh - var(--sr-navbar-h));/* ✅ ekranı doğru doldur */
  width: 520px;
  max-width: 92vw;

  background: #fff;
  border-left: 1px solid #e5e7eb;

  transform: translateX(100%);
  transition: transform .2s ease;

  z-index: 1040;                           /* ✅ desk overlay seviyesine yakın */
  display: flex;
  flex-direction: column;
}
.sr-drawer.open { transform: translateX(0); }

.sr-drawer-head {
  padding: 12px; border-bottom: 1px solid #e5e7eb;
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 10px;
}
.sr-drawer-head .code { font-size: 12px; }
.sr-drawer-head .name { font-size: 14px; font-weight: 700; margin-top: 2px; }

.sr-drawer-body { padding: 12px; overflow: auto; }
.sr-drawer-kpis {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px; margin-bottom: 12px;
}
.mini { border: 1px solid #eef2f7; border-radius: 12px; padding: 10px; }
.mini .t { font-size: 12px; color: #6b7280; }
.mini .v { font-size: 14px; font-weight: 700; margin-top: 6px; }

.sr-section { margin-top: 12px; }
.sr-section-head { display: flex; justify-content: space-between; align-items: center; }
.sr-section-head h4 { margin: 0; font-size: 13px; }

.sr-bars { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.sr-bar-row { display: grid; grid-template-columns: 1fr 160px 90px; gap: 10px; align-items: center; }
.sr-bar-row .bar { height: 10px; background: #f3f4f6; border-radius: 999px; overflow: hidden; }
.sr-bar-row .fill { height: 100%; background: #111827; border-radius: 999px; opacity: .2; }
.sr-bar-row .wh { font-size: 12px; }

.sr-toast {
  position: fixed; bottom: 18px; left: 18px;
  background: #111827; color: #fff;
  padding: 10px 12px; border-radius: 12px;
  font-size: 12px; z-index: 60;
  display: inline-flex; align-items: center; gap: 8px;
  box-shadow: 0 10px 30px rgba(0,0,0,.12);
}

/* Left column stacking */
.sr-left-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Anomaly list */
.sr-anom-list { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }

.sr-anom-row {
  width: 100%;
  text-align: left;
  border: 1px solid #eef2f7;
  background: #fff;
  border-radius: 12px;
  padding: 10px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  cursor: pointer;
}
.sr-anom-row:hover { border-color: #d1d5db; }

.sr-badges { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
.sr-badge {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid transparent;
  background: #f3f4f6;
  color: #374151;
}
.sr-badge.outline { background: #fff; border-color: #e5e7eb; color: #6b7280; }

.sr-badge.high { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
.sr-badge.med  { background: #ffedd5; color: #9a3412; border-color: #fed7aa; }
.sr-badge.low  { background: #dcfce7; color: #166534; border-color: #bbf7d0; }

.sr-anom-row .title { font-size: 12px; font-weight: 700; color: #111827; }
.sr-anom-row .desc { font-size: 12px; color: #6b7280; margin-top: 2px; }


/* Responsive */
@media (max-width: 1100px) {
  .sr-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .sr-grid { grid-template-columns: 1fr; }
}
</style>