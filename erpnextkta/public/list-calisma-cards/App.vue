<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import CkSkeleton from "./CkSkeleton.vue";
import CkCard from "./CkCard.vue";
import CkFilters from "./CkFilters.vue";

const loading = ref(false);
const rows = ref([]);
const errorMsg = ref("");
const sortKey = ref("creation_desc");
const statusFilter = ref("all"); // all | ready | running | paused | finished | rejected
const qcFilter = ref("all");     // all | waiting | approved | rejected // all | ready | running | paused | finished

const q = ref(""); // search query
const settings = ref({
  liste_yenileme_araligi_sn: 30,
  detay_yenileme_araligi_sn: 10
});
const pendingUpdate = ref(false);
const lastRefreshTime = ref(0);

async function loadSettings() {
  try {
    const r = await frappe.db.get_doc("KTA Calisma Karti Settings");
    if (r) {
      settings.value = {
        liste_yenileme_araligi_sn: r.liste_yenileme_araligi_sn || 30,
        detay_yenileme_araligi_sn: r.detay_yenileme_araligi_sn || 10
      };
    }
  } catch (e) {
    console.error("Settings load failed", e);
  }
}

// ✅ NEW: customer group filter
const customerGroupFilter = ref("all"); // all | <customer group name>
const pageLength = ref(200);
const start = ref(0);
const hasMore = ref(true);
async function load(opts = {}) {
  const append = !!opts.append;

  // ✅ NEW: default load() = first page
  if (!append) {
    start.value = 0;
    hasMore.value = true;
  }

  loading.value = true;
  const startTime = Date.now();
  errorMsg.value = "";
  try {
    const statusMap = {
      "ready": "Hazır",
      "running": "Çalışıyor",
      "paused": "Duruşta",
      "finished": "Bitmiş",
      "rejected": "Reddedildi"
    };

    const qcMap = {
      "waiting": "Onay Bekliyor",
      "approved": "Onaylandı",
      "rejected": "Reddedildi"
    };

    const r = await frappe.call("erpnextkta.kta_calisma_karti.api.get_my_calisma_kartlari", {
      order_by: sortKey.value,
      start: start.value,
      page_length: pageLength.value,
      durum: statusFilter.value !== "all" ? statusMap[statusFilter.value] : null,
      search_term: q.value,
      customer_group: customerGroupFilter.value !== "all" ? customerGroupFilter.value : null,
      qc_filter: qcFilter.value !== "all" ? qcMap[qcFilter.value] : null
    });

    const data = r.message || [];

    // ✅ NEW: append or replace
    if (append) {
      rows.value = [...(rows.value || []), ...data];
    } else {
      rows.value = data;
    }

    // ✅ NEW: paging bookkeeping
    if (data.length < pageLength.value) {
      hasMore.value = false;
    } else {
      start.value += data.length; // usually +pageLength
    }

    console.log(rows.value);

    // ✅ keep your existing "group disappeared => reset" logic if you already added it
    if (
      customerGroupFilter.value !== "all" &&
      !availableCustomerGroups.value.includes(customerGroupFilter.value)
    ) {
      customerGroupFilter.value = "all";
    }
  } catch (e) {
    errorMsg.value = e?.message || "Liste alınamadı.";
  } finally {
    lastRefreshTime.value = Date.now();
    pendingUpdate.value = false;
    // Ensure skeleton is visible for at least 800ms for a smoother UX
    const elapsed = Date.now() - startTime;
    const minDelay = 1000;
    const remaining = Math.max(0, minDelay - elapsed);
    
    setTimeout(() => {
      loading.value = false;
    }, remaining);
  }
}

// Trigger load on filter changes (debounced)
let searchTimer = null;
watch([q, statusFilter, qcFilter, customerGroupFilter, sortKey], () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        load();
    }, 400); 
}, { deep: true });

// ✅ NEW: load more
function loadMore() {
  if (loading.value || !hasMore.value) return;
  load({ append: true });
}

// --------------------
// Realtime (Socket.IO) - live list refresh
// --------------------
let listHandler = null;
let listTimer = null;

function bindListRealtime() {
  const rt = window?.frappe?.realtime;
  if (!rt) return;

  // Throttled refresh to avoid spamming API calls
  listHandler = (_payload) => {
    if (loading.value) return;

    const now = Date.now();
    const intervalMs = settings.value.liste_yenileme_araligi_sn * 1000;
    const timeSinceLast = now - lastRefreshTime.value;

    if (timeSinceLast >= intervalMs) {
      load();
    } else {
      pendingUpdate.value = true;
      clearTimeout(listTimer);
      listTimer = setTimeout(() => {
        if (!loading.value) load();
      }, intervalMs - timeSinceLast);
    }
  };

  rt.on("kta_calisma_karti:list_changed", listHandler);
}

function unbindListRealtime() {
  const rt = window?.frappe?.realtime;
  if (!rt) return;

  if (listHandler) rt.off("kta_calisma_karti:list_changed", listHandler);
  listHandler = null;

  clearTimeout(listTimer);
  listTimer = null;
}

// ** HELPERS ** //
function normalizeTR(s) {
  return (s || "")
    .toString()
    .trim()
    .toLowerCase()
    .replaceAll("ı", "i")
    .replaceAll("İ", "i")
    .replaceAll("ğ", "g")
    .replaceAll("ü", "u")
    .replaceAll("ş", "s")
    .replaceAll("ö", "o")
    .replaceAll("ç", "c");
}

function openDetail(name) {
  frappe.set_route("view-calisma-karti", name);
}

function statusKeyFromDurumText(durum) {
  const v = (durum || "").toLowerCase();
  if (v.includes("redd")) return "rejected";
  if (v.includes("bit")) return "finished";
  if (v.includes("duru")) return "paused";
  if (v.includes("çalı") || v.includes("calis")) return "running";
  if (v.includes("haz")) return "ready";
  return "ready";
}

function qcKeyFromText(qc) {
  const v = normalizeTR(qc);

  if (v === "onaylandi" || v === "onaylandı") return "approved";
  if (v === "onay bekliyor") return "waiting";
  if (v === "reddedildi") return "rejected";

  // fallback: boşsa default waiting
  if (!v) return "waiting";

  // fallback: “onay” geçiyor ama tam eşleşmiyorsa
  if (v.includes("redd")) return "rejected";
  if (v.includes("onay") && v.includes("bek")) return "waiting";
  if (v.includes("onay")) return "approved";

  return "waiting";
}

const availableCustomerGroups = ref([]);
const customerGroupCounts = ref({});

watch([rows, customerGroupFilter], ([newRows, filter]) => {
  if (filter !== "all" && availableCustomerGroups.value.length > 0) {
    // Keep previously calculated groups and counts visible so user can switch away
    return;
  }
  
  const set = new Set();
  const c = { all: (newRows || []).length };

  for (const r of newRows || []) {
    const groups = Array.isArray(r?.customer_groups) ? r.customer_groups : [];
    const single = r?.customer_group;
    const uniq = new Set(groups);
    if (single) uniq.add(single);

    for (const g of uniq) {
      if (!g) continue;
      set.add(g);
      c[g] = (c[g] || 0) + 1;
    }
  }

  availableCustomerGroups.value = Array.from(set).sort((a, b) => a.localeCompare(b, "tr"));
  customerGroupCounts.value = c;
}, { immediate: true });

// Computed counts for filters
const statusCounts = computed(() => {
  const c = { all: rows.value.length, ready: 0, running: 0, paused: 0, finished: 0, rejected: 0 };
  for (const r of rows.value || []) {
    c[statusKeyFromDurumText(r?.durum)]++;
  }
  return c;
});

const qcCounts = computed(() => {
  const c = { all: rows.value.length, waiting: 0, approved: 0, rejected: 0 };
  for (const r of rows.value || []) {
    c[qcKeyFromText(r?.kalite_kontrol)]++;
  }
  return c;
});

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ✅ NEW: setter for customer group filter (optional, v-model already works)
function setCustomerGroupFilter(v) {
  customerGroupFilter.value = v;
  scrollToTop();
}

onMounted(async () => {
  await loadSettings();
  load();
  bindListRealtime();
});

onUnmounted(() => {
  unbindListRealtime();
});
</script>

<template>
  <div class="ck-page">
    <!-- Sticky Header -->
    <div class="ck-header">
      <div class="ck-header-row">
        <div class="ck-title">Çalışma Kartları</div>
        <Transition name="ck-slide-down">
          <div v-if="pendingUpdate && !loading" class="ck-pending-badge">
            <span class="ck-dot"></span>
            Bekleyen güncellemeler var...
          </div>
        </Transition>
      </div>

      <CkFilters
        v-model:q="q"
        v-model:sortKey="sortKey"
        v-model:statusFilter="statusFilter"
        v-model:qcFilter="qcFilter"
        v-model:customerGroupFilter="customerGroupFilter"
        :statusCounts="statusCounts"
        :qcCounts="qcCounts"
        :customerGroupCounts="customerGroupCounts"
        :availableCustomerGroups="availableCustomerGroups"
      />

    </div>

    <!-- Content -->
    <div class="ck-body">
      <Transition name="ck-fade" mode="out-in">
        <!-- Loading skeleton -->
        <CkSkeleton v-if="loading" :count="6" key="skeleton" />

        <div v-else-if="errorMsg" class="ck-error" key="error">
          <div class="ck-error-title">Hata</div>
          <div class="ck-error-msg">{{ errorMsg }}</div>
          <button class="ck-btn" @click="load">Tekrar dene</button>
        </div>

        <div v-else-if="rows.length === 0" class="ck-empty" key="empty">
          <div class="ck-empty-title">Kayıt yok</div>
          <div class="ck-muted">
            Aramana uygun çalışma kartı bulunamadı.
          </div>
        </div>

        <div v-else class="ck-list" key="list">
          <CkCard
            v-for="r in rows"
            :key="r.name"
            :row="r"
            @click="openDetail(r.name)"
          />
        </div>
      </Transition>

      <div v-if="!loading && !errorMsg && rows.length > 0" class="ck-loadmore">
        <button
          v-if="hasMore"
          class="ck-btn"
          @click="loadMore"
        >
          Daha fazla yükle
        </button>

        <div v-else class="ck-muted" style="text-align:center; padding:10px 0;">
          Hepsi bu kadar.
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Layout */
.ck-page{
  padding:0;
  background: var(--subtle-fg);
  min-height:100vh;
}

.ck-header{
  position:sticky;
  top: 48px;
  z-index:5;
  padding:12px 12px 10px;
  background: var(--subtle-fg);
}

.ck-body{
  padding:12px;
}

/* Header */
.ck-header-row{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  margin-bottom:10px;
}

.ck-title{
  font-weight:900;
  font-size:16px;
  letter-spacing:.2px;
}

/* States & Utilities */
.ck-muted{ opacity:.75; font-size:12px; }

.ck-error{
  background:#fff;
  border:1px solid rgba(185, 28, 28, .25);
  border-radius:16px;
  padding:14px;
}
.ck-error-title{ color:#b91c1c; font-weight:900; margin-bottom:6px; }
.ck-error-msg{ font-size:13px; opacity:.85; margin-bottom:12px; }
.ck-btn{
  width:100%;
  border-radius:14px;
  border:0;
  padding:12px 14px;
  background:#111827;
  color:#fff;
  font-weight:800;
}
.ck-btn:active{ transform:scale(.99); }

.ck-empty{
  text-align:center;
  padding:18px 6px;
}
.ck-empty-title{ font-weight:900; margin-bottom:4px; }

.ck-list{ display:grid; gap:12px; }

/* Pending Update Badge */
.ck-pending-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--ck-info-bg);
  color: var(--ck-info);
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  border: 1px solid rgba(59, 130, 246, 0.2);
  backdrop-filter: blur(8px);
}

.ck-dot {
  width: 6px;
  height: 6px;
  background: var(--ck-info);
  border-radius: 50%;
  animation: ck-pulse 1.5s infinite;
}

@keyframes ck-pulse {
  0% { transform: scale(0.95); opacity: 0.5; }
  50% { transform: scale(1.1); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.5; }
}

/* Transitions */
.ck-slide-down-enter-active, .ck-slide-down-leave-active {
  transition: all 0.3s ease;
}
.ck-slide-down-enter-from, .ck-slide-down-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* Transition: Smooth Fade for Loading Skeleton */
.ck-fade-enter-active,
.ck-fade-leave-active {
  transition: opacity 0.4s ease;
}

.ck-fade-enter-from,
.ck-fade-leave-to {
  opacity: 0;
}

/* Skeleton placeholder util classes (if needed elsewhere) */
.w90{ width:90%; }
.w80{ width:80%; }
.w75{ width:75%; }
.w60{ width:60%; }
.w50{ width:50%; }
.w40{ width:40%; }
</style>

<style>
/* Global Glassmorphism Variables for List App */
:root {
  --ck-glass-bg: rgba(255, 255, 255, 0.45);
  --ck-glass-border: rgba(0, 0, 0, 0.1);
  --ck-glass-border-soft: rgba(0, 0, 0, 0.05);
  --ck-glass-shadow: rgba(0, 0, 0, 0.03);
  --ck-glass-highlight: rgba(255, 255, 255, 0.9);
  --ck-glass-bottom-edge: rgba(0, 0, 0, 0.05);
  --ck-skeleton-shine: rgba(255, 255, 255, 0.85); /* Much more visible light shine */
  --ck-success-bg: rgba(34, 197, 94, 0.55);
  --ck-danger-bg: rgba(239, 68, 68, 0.55);
}

[data-theme="dark"] {
  --ck-glass-bg: rgba(28, 33, 39, 0.8);
  --ck-glass-border: rgba(255, 255, 255, 0.12);
  --ck-glass-border-soft: rgba(255, 255, 255, 0.05);
  --ck-glass-shadow: rgba(0, 0, 0, 0.5);
  --ck-glass-highlight: rgba(255, 255, 255, 0.15);
  --ck-glass-bottom-edge: rgba(0, 0, 0, 0.3);
  --ck-skeleton-shine: rgba(255, 255, 255, 0.18); /* Clearly visible shimmer in dark mode */
  --ck-success-bg: rgba(34, 197, 94, 0.55);
  --ck-danger-bg: rgba(239, 68, 68, 0.55);
}
</style>
