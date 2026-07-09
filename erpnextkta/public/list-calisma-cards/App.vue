<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
const __ = (...args) => window.__(...args);
import CkSkeleton from "./CkSkeleton.vue";
import CkCard from "./CkCard.vue";
import CkFilters from "./CkFilters.vue";

const loading = ref(false);
const rows = ref([]);
const errorMsg = ref("");
const sortKey = ref("creation_desc");
const statusFilter = ref("all"); // all | ready | running | paused | finished | rejected
const qcFilter = ref("all");     // all | waiting | approved | rejected // all | ready | running | paused | finished
const tagFilter = ref("all");    // all | <tag>

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
      "rejected": "Reddedildi",
      "cancelled": "İptal Edildi"
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
      qc_filter: qcFilter.value !== "all" ? qcMap[qcFilter.value] : null,
      tag_filter: tagFilter.value !== "all" ? tagFilter.value : null
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

    if (
      tagFilter.value !== "all" &&
      !availableTags.value.includes(tagFilter.value)
    ) {
      tagFilter.value = "all";
    }
  } catch (e) {
    errorMsg.value = e?.message || __("Liste alınamadı.");
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
watch([q, statusFilter, qcFilter, customerGroupFilter, tagFilter, sortKey], () => {
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
  if (v.includes("iptal")) return "cancelled";
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

const availableTags = ref([]);
const tagCounts = ref({});

// Görünüm Modu Yönetimi (list | grid | kanban)
const viewMode = ref(localStorage.getItem('ck_view_mode') || 'list');
const isDesktop = ref(window.innerWidth >= 1024);

const handleResize = () => {
  isDesktop.value = window.innerWidth >= 1024;
  if (!isDesktop.value && viewMode.value === 'kanban') {
    viewMode.value = 'list';
  }
};

watch(viewMode, (newVal) => {
  localStorage.setItem('ck_view_mode', newVal);
});

// Kanban Sütunları
const kanbanColumns = computed(() => {
  const cols = {
    ready: { label: __("Hazır"), items: [] },
    running: { label: __("Çalışıyor"), items: [] },
    paused: { label: __("Duruşta"), items: [] },
    finished: { label: __("Bitmiş"), items: [] },
    rejected: { label: __("Reddedildi"), items: [] },
    cancelled: { label: __("İptal Edildi"), items: [] }
  };
  for (const r of rows.value || []) {
    const key = statusKeyFromDurumText(r?.durum);
    if (cols[key]) cols[key].items.push(r);
  }
  return cols;
});

watch([rows, customerGroupFilter, tagFilter], ([newRows, filter, tFilter]) => {
  // Update Customer Groups
  if (filter === "all" || availableCustomerGroups.value.length === 0) {
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
  }

  // Update Tags
  if (tFilter === "all" || availableTags.value.length === 0) {
    const tSet = new Set();
    const tC = { all: (newRows || []).length };

    for (const r of newRows || []) {
      const tagsString = r?._user_tags || "";
      const tags = tagsString.split(",").map(t => t.trim()).filter(t => t);
      const uniqTags = new Set(tags);

      for (const t of uniqTags) {
        tSet.add(t);
        tC[t] = (tC[t] || 0) + 1;
      }
    }

    availableTags.value = Array.from(tSet).sort((a, b) => a.localeCompare(b, "tr"));
    tagCounts.value = tC;
  }
}, { immediate: true });

// Computed counts for filters
const statusCounts = computed(() => {
  const c = { all: rows.value.length, ready: 0, running: 0, paused: 0, finished: 0, rejected: 0, cancelled: 0 };
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
  window.addEventListener("resize", handleResize);
  handleResize();
  
  await loadSettings();
  load();
  bindListRealtime();
});

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  unbindListRealtime();
});
</script>

<template>
  <div class="ck-page">
    <!-- Sticky Header -->
    <div class="ck-header">
      <div class="ck-header-row">
        <div class="ck-title">{{ __("Çalışma Kartları") }}</div>
        
        <div class="ck-view-toggles" v-if="!loading && !errorMsg">
          <button class="ck-view-btn" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'" :title="__('Liste Görünümü')">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
          </button>
          <button class="ck-view-btn" :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'" :title="__('Grid Görünümü')">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
          </button>
          <button v-if="isDesktop" class="ck-view-btn" :class="{ active: viewMode === 'kanban' }" @click="viewMode = 'kanban'" :title="__('Kanban Görünümü')">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line><line x1="15" y1="3" x2="15" y2="21"></line></svg>
          </button>
        </div>

        <Transition name="ck-slide-down">
          <div v-if="pendingUpdate && !loading" class="ck-pending-badge">
            <span class="ck-dot"></span>{{ __("Bekleyen güncellemeler var...") }}</div>
        </Transition>
      </div>

      <CkFilters
        v-model:q="q"
        v-model:sortKey="sortKey"
        v-model:statusFilter="statusFilter"
        v-model:qcFilter="qcFilter"
        v-model:customerGroupFilter="customerGroupFilter"
        v-model:tagFilter="tagFilter"
        :statusCounts="statusCounts"
        :qcCounts="qcCounts"
        :customerGroupCounts="customerGroupCounts"
        :availableCustomerGroups="availableCustomerGroups"
        :tagCounts="tagCounts"
        :availableTags="availableTags"
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
          <div class="ck-empty-title">{{ __("Kayıt yok") }}</div>
          <div class="ck-muted">{{ __("Aramana uygun çalışma kartı bulunamadı.") }}</div>
        </div>

        <div v-else class="ck-views" key="views">
          
          <!-- LİSTE GÖRÜNÜMÜ -->
          <div v-if="viewMode === 'list'" class="ck-list">
            <CkCard v-for="r in rows" :key="r.name" :row="r" @click="openDetail(r.name)" />
          </div>

          <!-- GRİD (GALERİ) GÖRÜNÜMÜ -->
          <div v-else-if="viewMode === 'grid'" class="ck-grid">
            <CkCard v-for="r in rows" :key="r.name" :row="r" @click="openDetail(r.name)" />
          </div>

          <!-- KANBAN (PANO) GÖRÜNÜMÜ -->
          <div v-else-if="viewMode === 'kanban'" class="ck-kanban">
            <div v-for="(col, key) in kanbanColumns" :key="key" class="ck-kanban-col" v-show="col.items.length > 0">
              <div class="ck-kanban-header">
                <span class="ck-kanban-title">{{ col.label }}</span>
                <span class="ck-kanban-count">{{ col.items.length }}</span>
              </div>
              <div class="ck-kanban-items">
                <CkCard v-for="r in col.items" :key="r.name" :row="r" @click="openDetail(r.name)" />
              </div>
            </div>
          </div>

        </div>
      </Transition>

      <div v-if="!loading && !errorMsg && rows.length > 0" class="ck-loadmore">
        <button
          v-if="hasMore"
          class="ck-btn"
          @click="loadMore"
        >{{ __("Daha fazla yükle") }}</button>

        <div v-else class="ck-muted" style="text-align:center; padding:10px 0;">
          Hepsi bu kadar.
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>/* Layout */
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
  flex-wrap: wrap; /* Mobil cihazlarda butonların taşmasını önler */
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

/* Views & Toggles */
.ck-view-toggles {
  display: flex;
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border);
  border-radius: 8px;
  overflow: hidden;
  margin-left: auto;
  margin-right: 10px;
}
.ck-view-btn {
  background: transparent;
  border: none;
  padding: 6px 10px;
  color: inherit;
  opacity: 0.5;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.ck-view-btn:hover {
  background: rgba(0,0,0,0.05);
  opacity: 0.8;
}
.ck-view-btn.active {
  background: rgba(17, 24, 39, 0.1);
  opacity: 1;
}
[data-theme="dark"] .ck-view-btn:hover {
  background: rgba(255,255,255,0.05);
}
[data-theme="dark"] .ck-view-btn.active {
  background: rgba(255,255,255,0.1);
}

/* Grid View */
.ck-grid {
  display: grid;
  /* Mobilde %100 genişlik kullan, masaüstünde 260px'e kadar küçülebilmesini sağla */
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 260px), 1fr));
  gap: 12px;
}

/* Kanban View */
.ck-kanban {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 12px;
  align-items: flex-start;
  min-height: 60vh;
  /* Mobilde pürüzsüz yatay kaydırma (scroll snapping) */
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
}
.ck-kanban-col {
  /* Normal ekrana sığması için 240px'e kadar daralabilir, ama 320px'i geçemez */
  flex: 1 0 240px; 
  max-width: 320px;
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border);
  border-radius: 12px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 80vh;
  scroll-snap-align: start;
}
.ck-kanban-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--ck-glass-border-soft);
  font-weight: 800;
  font-size: 14px;
}
.ck-kanban-count {
  background: rgba(0,0,0,0.1);
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}
[data-theme="dark"] .ck-kanban-count {
  background: rgba(255,255,255,0.1);
}
.ck-kanban-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  padding-right: 4px;
}

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
.w40{ width:40%; }</style>

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
