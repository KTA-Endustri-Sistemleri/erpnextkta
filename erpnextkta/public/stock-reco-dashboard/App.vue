<template>
  <div class="srd">
    <div class="srd-toolbar">
      <div>
        <div class="srd-title">Stock Reconciliation Dashboard</div>
        <div class="srd-sub">Draft Stock Reconciliation belgelerinden ürün bazlı net etki</div>
      </div>

      <div class="srd-actions">
        <label class="srd-label">Yıl</label>
        <select v-model="year" @change="load" class="srd-select">
          <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
        </select>

        <button class="srd-btn" :disabled="loading" @click="load">
          {{ loading ? "Yükleniyor..." : "Yenile" }}
        </button>
      </div>
    </div>

    <div class="srd-card">
      <table class="srd-table">
        <thead>
          <tr>
            <th style="width: 22%;">Item</th>
            <th style="width: 12%;">Net Etki</th>
            <th>Depo Dağılımı</th>
            <th style="width: 10%;">Belge</th>
          </tr>
        </thead>

        <tbody v-if="!loading && items.length === 0">
          <tr>
            <td colspan="4" class="srd-muted">Bu yıl için draft etki bulunamadı.</td>
          </tr>
        </tbody>

        <tbody>
          <tr
            v-for="it in items"
            :key="it.item_code"
            class="srd-row"
            @click="openItem(it)"
          >
            <td>
              <div class="srd-strong">{{ it.item_code }}</div>
              <div class="srd-muted">{{ it.item_name }} • {{ it.uom }}</div>
            </td>

            <td>
              <span class="srd-badge">{{ fmt(it.net_diff) }}</span>
            </td>

            <td>
              <div v-if="it.warehouses?.length">
                <div v-for="w in it.warehouses" :key="w.warehouse" class="srd-wh">
                  <span class="srd-muted">{{ w.warehouse }}</span>
                  <span class="srd-strong" style="margin-left: 6px;">{{ fmt(w.diff) }}</span>
                </div>
              </div>
              <div v-else class="srd-muted">-</div>
            </td>

            <td class="srd-muted">{{ it.docs_count }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="selected" class="srd-card" style="margin-top: 12px;">
      <div class="srd-detail-head">
        <div>
          <div class="srd-strong">{{ selected.item_code }}</div>
          <div class="srd-muted">{{ selected.item_name }}</div>
        </div>
        <button class="srd-btn" @click="closeDetails">Kapat</button>
      </div>

      <div v-if="detailsLoading" class="srd-muted">Detay yükleniyor...</div>

      <table v-else class="srd-table">
        <thead>
          <tr>
            <th style="width: 22%;">Belge</th>
            <th style="width: 18%;">Posting Date</th>
            <th>Warehouse</th>
            <th style="width: 12%;">Diff</th>
            <th style="width: 12%;">Aksiyon</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in details" :key="d.name + '|' + (d.warehouse || '')">
            <td class="srd-strong">{{ d.name }}</td>
            <td class="srd-muted">{{ d.posting_date }}</td>
            <td class="srd-muted">{{ d.warehouse || d.set_warehouse || "-" }}</td>
            <td class="srd-strong">{{ fmt(d.diff_qty) }}</td>
            <td>
              <button class="srd-btn" @click="openDoc(d.name)">Aç</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from "vue";

const years = ref([]);
const year = ref(new Date().getFullYear());

const loading = ref(false);
const items = ref([]);

const selected = ref(null);
const detailsLoading = ref(false);
const details = ref([]);

// --- RPC helper (unchanged) ---
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

// --- Data loaders (mostly unchanged) ---
async function loadYears() {
  years.value = await call(
    "erpnextkta.rest-api.stock_reconciliation_dashboard.get_years"
  );
  if (years.value.length && !years.value.includes(year.value)) {
    year.value = years.value[0];
  }
}

// We keep load() idempotent so it can be called by realtime updates safely.
async function load() {
  loading.value = true;
  selected.value = null;
  details.value = [];
  try {
    const res = await call(
      "erpnextkta.rest-api.stock_reconciliation_dashboard.get_dashboard",
      { year: year.value }
    );
    items.value = res?.items || [];
  } finally {
    loading.value = false;
  }
}

// Keep a separate refresher that DOES NOT reset selected/details.
// This is useful when realtime updates arrive while a details modal is open.
async function refreshDashboardOnly() {
  loading.value = true;
  try {
    const res = await call(
      "erpnextkta.rest-api.stock_reconciliation_dashboard.get_dashboard",
      { year: year.value }
    );
    items.value = res?.items || [];
  } finally {
    loading.value = false;
  }
}

async function refreshDetailsIfOpen() {
  if (!selected.value?.item_code) return;

  detailsLoading.value = true;
  try {
    const res = await call(
      "erpnextkta.rest-api.stock_reconciliation_dashboard.get_item_details",
      { item_code: selected.value.item_code, year: year.value }
    );
    details.value = res?.docs || [];
  } finally {
    detailsLoading.value = false;
  }
}

async function openItem(it) {
  selected.value = it;
  detailsLoading.value = true;
  details.value = [];
  try {
    const res = await call(
      "erpnextkta.rest-api.stock_reconciliation_dashboard.get_item_details",
      { item_code: it.item_code, year: year.value }
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

function openDoc(name) {
  frappe.set_route("Form", "Stock Reconciliation", name);
}

// --- Realtime (Socket.IO) integration ---
// We debounce refreshes because a single SR save can fire multiple events.
let realtimeHandler = null;
let debounceTimer = null;

function scheduleRealtimeRefresh() {
  if (debounceTimer) clearTimeout(debounceTimer);

  debounceTimer = setTimeout(async () => {
    // Refresh main table
    await refreshDashboardOnly();

    // If a details panel is open, refresh it too
    await refreshDetailsIfOpen();
  }, 400);
}

onMounted(async () => {
  await loadYears();
  await load();

  // Subscribe to Frappe realtime updates
  realtimeHandler = () => scheduleRealtimeRefresh();

  // Frappe provides frappe.realtime in Desk
  if (frappe?.realtime?.on) {
    frappe.realtime.on("stock_reco_dashboard_update", realtimeHandler);
  }
});

onBeforeUnmount(() => {
  // Cleanup listener to prevent duplicates on remount
  if (realtimeHandler && frappe?.realtime?.off) {
    frappe.realtime.off("stock_reco_dashboard_update", realtimeHandler);
  }

  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }

  realtimeHandler = null;
});
</script>


<style scoped>
.srd { padding: 12px; }
.srd-toolbar { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom: 12px; }
.srd-title { font-size: 18px; font-weight: 800; }
.srd-sub { font-size: 12px; opacity: 0.7; }
.srd-actions { display:flex; align-items:center; gap:8px; }
.srd-label { font-size: 12px; opacity: 0.7; }
.srd-select { padding: 6px 8px; border-radius: 10px; border: 1px solid #e5e7eb; }
.srd-btn { padding: 6px 10px; border-radius: 10px; border: 1px solid #e5e7eb; background: #fff; cursor: pointer; }
.srd-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.srd-card { background:#fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px; }
.srd-table { width: 100%; border-collapse: collapse; }
.srd-table th, .srd-table td { border-bottom: 1px solid #eef2f7; padding: 10px 8px; text-align:left; vertical-align:top; }
.srd-muted { opacity: 0.7; font-size: 12px; }
.srd-strong { font-weight: 800; }
.srd-row { cursor: pointer; }
.srd-row:hover { background: #fafafa; }
.srd-badge { display:inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; border: 1px solid #e5e7eb; font-weight: 800; }
.srd-wh { font-size: 12px; }
.srd-detail-head { display:flex; align-items:center; justify-content:space-between; margin-bottom: 8px; }
</style>