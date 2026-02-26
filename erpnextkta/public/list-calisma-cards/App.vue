<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

const loading = ref(false);
const rows = ref([]);
const errorMsg = ref("");
const sortKey = ref("creation_desc");

const q = ref(""); // search query

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
  errorMsg.value = "";
  try {
    const r = await frappe.call("erpnextkta.kta_calisma_karti.api.get_my_calisma_kartlari", {
      order_by: sortKey.value,

      // ✅ NEW: paging args
      start: start.value,
      page_length: pageLength.value,
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
    loading.value = false;
  }
}
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

  // Debounced refresh to avoid spamming API calls
  listHandler = (_payload) => {
    clearTimeout(listTimer);
    listTimer = setTimeout(() => {
      // Don't hammer if user is already loading
      if (!loading.value) load();
    }, 250);
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

const statusFilter = ref("all"); // all | ready | running | paused | finished | rejected
const qcFilter = ref("all");     // all | waiting | approved | rejected // all | ready | running | paused | finished

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

// ✅ NEW: available customer groups from rows
const availableCustomerGroups = computed(() => {
  const set = new Set();

  for (const r of rows.value || []) {
    const arr = Array.isArray(r?.customer_groups) ? r.customer_groups : [];
    for (const g of arr) if (g) set.add(g);

    if (r?.customer_group) set.add(r.customer_group);
  }

  return Array.from(set).sort((a, b) => a.localeCompare(b, "tr"));
});

// ✅ NEW: counts per group (optional but useful for UI)
const customerGroupCounts = computed(() => {
  const c = { all: rows.value.length };

  for (const r of rows.value || []) {
    const groups = Array.isArray(r?.customer_groups) ? r.customer_groups : [];
    const single = r?.customer_group;

    const uniq = new Set(groups);
    if (single) uniq.add(single);

    for (const g of uniq) {
      if (!g) continue;
      c[g] = (c[g] || 0) + 1;
    }
  }

  return c;
});

// Lightweight client-side search
const filteredRows = computed(() => {
  const needle = (q.value || "").trim().toLowerCase();

  return (rows.value || []).filter((r) => {
    // 1) Status filter
    if (statusFilter.value !== "all") {
      const k = statusKeyFromDurumText(r?.durum);
      if (k !== statusFilter.value) return false;
    }

    // 2) QC filter
    if (qcFilter.value !== "all") {
      const qk = qcKeyFromText(r?.kalite_kontrol);
      if (qk !== qcFilter.value) return false;
    }

    // ✅ NEW: 3) Customer Group filter
    if (customerGroupFilter.value !== "all") {
      const target = customerGroupFilter.value;

      const groups = Array.isArray(r?.customer_groups) ? r.customer_groups : [];
      const single = r?.customer_group;

      const hit = (single === target) || (groups || []).includes(target);
      if (!hit) return false;
    }

    // 3) Search filter
    if (!needle) return true;

    const hay = [
      r?.name,
      r?.operator,
      r?.custom_work_order,
      r?.is_karti,
      r?.operasyon,
      r?.durum,
      r?.kalite_kontrol, // QC da aransın
      r?.urun_kodu,

      // ✅ NEW (optional): search in customer group too
      r?.customer_group,
      ...(Array.isArray(r?.customer_groups) ? r.customer_groups : []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return hay.includes(needle);
  });
});

function statusTone(durum) {
  // Map your text labels to tones (adjust if your API uses different strings)
  const v = (durum || "").toLowerCase();
  if (v.includes("redd")) return "rejected";
  if (v.includes("bit")) return "finished";
  if (v.includes("duru")) return "paused";
  if (v.includes("çalı") || v.includes("calis")) return "running";
  if (v.includes("haz")) return "ready";
  return "ready";
}

// Optional: badge counts
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

// Scroll to top and load data on mount
function scrollToTop() {
  // Smooth scroll inside app/page
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function setStatusFilter(v) {
  statusFilter.value = v;
  scrollToTop();
}
function setQcFilter(v) {
  qcFilter.value = v;
  scrollToTop();
}

// ✅ NEW: setter for customer group filter (optional, v-model already works)
function setCustomerGroupFilter(v) {
  customerGroupFilter.value = v;
  scrollToTop();
}

watch(sortKey, () => {
  load();
});
watch([statusFilter, qcFilter, customerGroupFilter], () => {
  load();
});
onMounted(() => {
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
      </div>

      <div class="ck-search">
        <span class="ck-search-ic">🔎</span>
        <input
          v-model="q"
          class="ck-search-input"
          type="text"
          placeholder="Ara: iş emri, kart, operasyon..."
          inputmode="search"
        />
        <button v-if="q" class="ck-clear" @click="q=''">✕</button>
      </div>

      <div class="ck-sort">
        <select v-model="sortKey" class="ck-sort-select">
          <option value="modified_desc">Son Güncellenen ↓</option>
          <option value="modified_asc">Son Güncellenen ↑</option>
          <option value="creation_desc">Yeni Oluşturulan ↓</option>
          <option value="creation_asc">Yeni Oluşturulan ↑</option>
          <option value="name_asc">Kart No A → Z</option>
          <option value="name_desc">Kart No Z → A</option>
        </select>
      </div>

      <div class="ck-filters" v-if="!loading">
        <button class="ck-filter" :class="{ active: statusFilter === 'all' }" @click="setStatusFilter('all')">
          Tümü <span class="ck-filter-count">{{ statusCounts.all }}</span>
        </button>

        <button class="ck-filter" :class="{ active: statusFilter === 'ready' }" @click="setStatusFilter('ready')">
          Hazır <span class="ck-filter-count">{{ statusCounts.ready }}</span>
        </button>

        <button class="ck-filter" :class="{ active: statusFilter === 'running' }" @click="setStatusFilter('running')">
          Çalışıyor <span class="ck-filter-count">{{ statusCounts.running }}</span>
        </button>

        <button class="ck-filter" :class="{ active: statusFilter === 'paused' }" @click="setStatusFilter('paused')">
          Duruşta <span class="ck-filter-count">{{ statusCounts.paused }}</span>
        </button>

        <button class="ck-filter" :class="{ active: statusFilter === 'finished' }" @click="setStatusFilter('finished')">
          Bitmiş <span class="ck-filter-count">{{ statusCounts.finished }}</span>
        </button>

        <button class="ck-filter" :class="{ active: statusFilter === 'rejected' }" @click="setStatusFilter('rejected')">
          Reddedildi <span class="ck-filter-count">{{ statusCounts.rejected }}</span>
        </button>
      </div>

      <div class="ck-filters ck-filters--sub" v-if="!loading">
        <button class="ck-filter ck-filter--qc" :class="{ active: qcFilter === 'all' }" @click="setQcFilter('all')">
          QC Tümü <span class="ck-filter-count">{{ qcCounts.all }}</span>
        </button>

        <button class="ck-filter ck-filter--qc" :class="{ active: qcFilter === 'waiting' }" @click="setQcFilter('waiting')">
          Onay Bekliyor <span class="ck-filter-count">{{ qcCounts.waiting }}</span>
        </button>

        <button class="ck-filter ck-filter--qc" :class="{ active: qcFilter === 'approved' }" @click="setQcFilter('approved')">
          Onaylandı <span class="ck-filter-count">{{ qcCounts.approved }}</span>
        </button>

        <button class="ck-filter ck-filter--qc" :class="{ active: qcFilter === 'rejected' }" @click="setQcFilter('rejected')">
          Reddedildi <span class="ck-filter-count">{{ qcCounts.rejected }}</span>
        </button>
      </div>

      <!-- ✅ Customer Group Filters (QC style) -->
      <div class="ck-filters ck-filters--sub" v-if="!loading && availableCustomerGroups.length">
        <button
          class="ck-filter ck-filter--qc"
          :class="{ active: customerGroupFilter === 'all' }"
          @click="setCustomerGroupFilter('all')"
        >
          Customer Tümü <span class="ck-filter-count">{{ customerGroupCounts.all }}</span>
        </button>

        <button
          v-for="g in availableCustomerGroups"
          :key="g"
          class="ck-filter ck-filter--qc"
          :class="{ active: customerGroupFilter === g }"
          @click="setCustomerGroupFilter(g)"
          :title="g"
        >
          {{ g }} <span class="ck-filter-count">{{ customerGroupCounts[g] || 0 }}</span>
        </button>
      </div>

    </div>

    <!-- Content -->
    <div class="ck-body">
      <!-- Loading skeleton -->
      <div v-if="loading" class="ck-skel">
        <div v-for="i in 6" :key="i" class="ck-skel-card">
          <div class="ck-skel-row">
            <div class="ck-skel-pill"></div>
            <div class="ck-skel-line w60"></div>
          </div>
          <div class="ck-skel-line w90"></div>
          <div class="ck-skel-line w75"></div>
          <div class="ck-skel-line w50"></div>
        </div>
      </div>

      <div v-else-if="errorMsg" class="ck-error">
        <div class="ck-error-title">Hata</div>
        <div class="ck-error-msg">{{ errorMsg }}</div>
        <button class="ck-btn" @click="load">Tekrar dene</button>
      </div>

      <div v-else-if="filteredRows.length === 0" class="ck-empty">
        <div class="ck-empty-title">Kayıt yok</div>
        <div class="ck-muted">
          {{ rows.length === 0 ? "Atanmış çalışma kartı yok." : "Aramana uygun kayıt bulunamadı." }}
        </div>
      </div>

      <div v-else class="ck-list">
        <button
          v-for="r in filteredRows"
          :key="r.name"
          class="ck-card"
          @click="openDetail(r.name)"
        >
          <div class="row no-gutters" :class="{
            'ck-status-card-qc--running': r.kalite_kontrol === 'Onaylandı',
            'ck-status-card-qc--rejected': r.kalite_kontrol === 'Reddedildi',
            'ck-status-card-qc--pending': r.kalite_kontrol === 'Onay Bekliyor',
          }">
            <div class="col-2 p-0 ck-pill" :data-tone="statusTone(r.durum)">
              <span>{{ r.durum || "-" }}</span>
            </div>
            <div class="col-9 py-2 pl-2">
              <div class="ck-name">{{ r.operator }}</div>
              <div class="ck-kv">
                <div class="ck-kv-item">
                  <span>Ürün Kodu</span>
                  <b>{{ r.urun_kodu|| "-" }}</b>
                </div>

                <div class="ck-kv-item">
                  <span>İş Emri</span>
                  <b>{{ r.custom_work_order || "-" }}</b>
                </div>
                <div class="ck-kv-item">
                  <span>İş Kartı</span>
                  <b>{{ r.is_karti || "-" }}</b>
                </div>
                <div class="ck-kv-item">
                  <span>Operasyon</span>
                  <b>{{ r.operasyon || "-" }}</b>
                </div>
              </div>
            </div>
            <div class="col-1 p-0 d-flex align-items-center">
              <span class="ck-chevron">›</span>
            </div>
          </div>
        </button>
      </div>

      <div v-if="!loading && !errorMsg && filteredRows.length > 0" class="ck-loadmore">
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

.ck-iconbtn{
  width:40px;
  height:40px;
  border-radius:12px;
  border:1px solid rgba(0,0,0,.10);
  background: var(--blue-500);
  color: var(--text-dark);
  font-size:16px;
}
.ck-iconbtn:active{ transform:scale(.98); }

/* Search */
.ck-search{
  display:flex;
  align-items:center;
  gap:8px;
  background:#fff;
  border:1px solid rgba(0,0,0,.10);
  border-radius:14px;
  padding:10px 12px;
}

.ck-search-ic{ opacity:.6; font-size:14px; }
.ck-search-input{
  flex:1;
  border:0;
  outline:none;
  font-size:14px;
  background:transparent;
  color: var(--dark);
}
.ck-clear{
  border:0;
  background:transparent;
  font-size:14px;
  opacity:.6;
}

/* States */
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

/* List Cards */
.ck-list{ display:grid; gap:12px; }

.ck-card{
  width:100%;
  text-align:left;
  background:var(--card-bg);
  border:1px solid rgba(0,0,0,.08);
  border-radius:18px;
  padding:0px 0px 0px;
  box-shadow:0 1px 0 rgba(0,0,0,.02);
}
.ck-pill span{
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(270deg);
  transform-origin: center;
  white-space: nowrap;
  text-transform: uppercase;
}
.ck-card:active{ transform:scale(.995); }

.ck-card-top{
  display:flex;
  align-items:center;
  justify-content:space-between;
  margin-bottom:10px;
}

.ck-chevron{
  font-size:48px;
  opacity:.25;
  line-height:1;
}

.ck-name{
  font-weight:900;
  font-size:14px;
  line-height:1.2;
  margin-bottom:10px;
  word-break:break-word;
}

/* Pill */
.ck-pill{
  font-size:12px;
  font-weight:900;
  padding:6px 10px;
  border-radius:18px 0px 0px 18px;
  line-height:1;
  border:1px solid rgba(0,0,0,.08);
  position: relative;
  overflow: hidden; /* kritik */
}
/* tone mapping */
.ck-pill[data-tone="ready"]{
  background: var(--blue);
  color: var(--white-overlay-900);
  border-right: solid 0px var(--card-bg);
}
.ck-pill[data-tone="ready"]::after{
  content:"";
  position:absolute;
  top:-1px;             /* üstte de bindir (anti-alias çizgisi için) */
  bottom:-1px;          /* altta da bindir */
  right:-1px;           /* sağa 1px taşır */
  width:15px;           /* 14 yerine 15 (bindirmeyi telafi) */
  height:100%;
  background: var(--card-bg);

  clip-path: polygon(
    100% 0%,
    0% 8%,
    100% 16%,
    0% 24%,
    100% 32%,
    0% 40%,
    100% 48%,
    0% 56%,
    100% 64%,
    0% 72%,
    100% 80%,
    0% 88%,
    100% 100%
  );
}
.ck-pill[data-tone="running"]{
  background: var(--yellow-500);
  color: var(--white-overlay-900);
  border-right: solid 0px var(--card-bg);
}
.ck-pill[data-tone="running"]::after{
  content:"";
  position:absolute;
  top:-1px;             /* üstte de bindir (anti-alias çizgisi için) */
  bottom:-1px;          /* altta da bindir */
  right:-1px;           /* sağa 1px taşır */
  width:15px;           /* 14 yerine 15 (bindirmeyi telafi) */
  height:100%;
  background: var(--card-bg);

  clip-path: polygon(
    100% 0%,
    0% 8%,
    100% 16%,
    0% 24%,
    100% 32%,
    0% 40%,
    100% 48%,
    0% 56%,
    100% 64%,
    0% 72%,
    100% 80%,
    0% 88%,
    100% 100%
  );
}
.ck-pill[data-tone="paused"]{
  background: var(--orange-500);
  color: var(--white-overlay-900);
  border-right: solid 0px var(--card-bg);
}
.ck-pill[data-tone="paused"]::after{
  content:"";
  position:absolute;
  top:-1px;             /* üstte de bindir (anti-alias çizgisi için) */
  bottom:-1px;          /* altta da bindir */
  right:-1px;           /* sağa 1px taşır */
  width:15px;           /* 14 yerine 15 (bindirmeyi telafi) */
  height:100%;
  background: var(--card-bg);

  clip-path: polygon(
    100% 0%,
    0% 8%,
    100% 16%,
    0% 24%,
    100% 32%,
    0% 40%,
    100% 48%,
    0% 56%,
    100% 64%,
    0% 72%,
    100% 80%,
    0% 88%,
    100% 100%
  );
}
.ck-pill[data-tone="finished"]{
  background: var(--green);
  color: var(--white-overlay-900);
  border-right: solid 0px var(--card-bg);
}
.ck-pill[data-tone="finished"]::after{
  content:"";
  position:absolute;
  top:-1px;             /* üstte de bindir (anti-alias çizgisi için) */
  bottom:-1px;          /* altta da bindir */
  right:-1px;           /* sağa 1px taşır */
  width:15px;           /* 14 yerine 15 (bindirmeyi telafi) */
  height:100%;
  background: var(--card-bg);

  clip-path: polygon(
    100% 0%,
    0% 8%,
    100% 16%,
    0% 24%,
    100% 32%,
    0% 40%,
    100% 48%,
    0% 56%,
    100% 64%,
    0% 72%,
    100% 80%,
    0% 88%,
    100% 100%
  );
}

.ck-pill[data-tone="rejected"]{
  background: var(--red);
  color: var(--white-overlay-900);
  border-right: solid 0px var(--card-bg);
}
.ck-pill[data-tone="rejected"]::after{
  content:"";
  position:absolute;
  top:-1px;             /* üstte de bindir (anti-alias çizgisi için) */
  bottom:-1px;          /* altta da bindir */
  right:-1px;           /* sağa 1px taşır */
  width:15px;           /* 14 yerine 15 (bindirmeyi telafi) */
  height:100%;
  background: var(--card-bg);

  clip-path: polygon(
    100% 0%,
    0% 8%,
    100% 16%,
    0% 24%,
    100% 32%,
    0% 40%,
    100% 48%,
    0% 56%,
    100% 64%,
    0% 72%,
    100% 80%,
    0% 88%,
    100% 100%
  );
}

/* KV grid */
.ck-kv{
  display:grid;
  gap:10px;
}

.ck-kv-item span{
  display:block;
  font-size:11px;
  opacity:.65;
  margin-bottom:3px;
}
.ck-kv-item b{
  display:block;
  font-size:13px;
  font-weight:900;
  word-break:break-word;
}

/* Skeleton */
.ck-skel{ display:grid; gap:12px; }
.ck-skel-card{
  background:#fff;
  border:1px solid rgba(0,0,0,.08);
  border-radius:18px;
  padding:12px;
}
.ck-skel-row{ display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.ck-skel-pill{
  width:90px; height:26px; border-radius:999px;
  background:rgba(0,0,0,.06);
}
.ck-skel-line{
  height:12px; border-radius:10px;
  background:rgba(0,0,0,.06);
}
.w90{ width:90%; }
.w75{ width:75%; }
.w60{ width:60%; }
.w50{ width:50%; }

.ck-filters{
  display:flex;
  gap:8px;
  overflow:auto;
  padding:10px 0 0;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  justify-content: space-between;
}
.ck-filters::-webkit-scrollbar{ display:none; }

.ck-filters--sub{
  padding-top:8px;
  justify-content: space-between;
}

.ck-filter{
  border:1px solid rgba(0,0,0,.10);
  background: var(--bg-color);
  border-radius:999px;
  padding:8px 10px;
  font-size:12px;
  font-weight:900;
  white-space:nowrap;
  display:flex;
  align-items:center;
  gap:6px;
}
.ck-filter:active{ transform:scale(.99); }

.ck-filter.active{
  background: var(--bg-light-blue);
  color: var(--text-color) !important;
  border-color: var(--blue-400);
}

.ck-filter-count{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-width:18px;
  height:18px;
  padding:0 6px;
  border-radius:999px;
  font-size:11px;
  font-weight:900;
  background: var(--fg-hover-color);
}
.ck-filter.active .ck-filter-count{
  background: var(--blue-400);
}
.ck-status-card-qc--running {
  background: linear-gradient(270deg, var(--green), transparent, transparent);
  border-radius: 16px;
}
.ck-status-card-qc--rejected {
  background: linear-gradient(270deg, var(--red), transparent, transparent);
  border-radius: 16px;
}
.ck-status-card-qc--pending {
    background: linear-gradient(270deg, var(--blue), transparent, transparent);
    border-radius: 16px;
}
.ck-sort{
  margin-top:10px;
}

.ck-sort-select{
  width: 100%;
  border: 1px solid rgba(0, 0, 0, .10);
  background: var(--bg-color);
  border-radius: 14px;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-color);
}
</style>
