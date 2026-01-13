<script setup>
import { onMounted, ref } from "vue";

const loading = ref(false);
const rows = ref([]);
const errorMsg = ref("");

async function load() {
  loading.value = true;
  errorMsg.value = "";
  try {
    const r = await frappe.call("erpnextkta.kta_calisma_karti.api.get_my_calisma_kartlari");
    rows.value = r.message || [];
  } catch (e) {
    errorMsg.value = e?.message || "Liste alınamadı.";
  } finally {
    loading.value = false;
  }
}

function openDetail(name) {
  frappe.set_route("kta-calisma-karti-card", name);
}

onMounted(load);
</script>

<template>
  <div class="ck-page">
    <div v-if="loading" class="ck-muted">Yükleniyor...</div>
    <div v-else-if="errorMsg" class="ck-error">{{ errorMsg }}</div>
    <div v-else-if="rows.length === 0" class="ck-empty">Atanmış çalışma kartı yok.</div>

    <div v-else class="ck-list">
      <button v-for="r in rows" :key="r.name" class="ck-list-item" @click="openDetail(r.name)">
        <div class="ck-li-head">
          <div class="ck-li-name">{{ r.name }}</div>
          <div class="ck-li-status">{{ r.durum || "-" }}</div>
        </div>

        <div class="ck-li-meta">
          <div><span>İş Emri</span><b>{{ r.custom_work_order || "-" }}</b></div>
          <div><span>İş Kartı</span><b>{{ r.is_karti || "-" }}</b></div>
          <div><span>Operasyon</span><b>{{ r.operasyon || "-" }}</b></div>
        </div>
      </button>
    </div>
  </div>
</template>
<style lang="css" scoped>
.ck-page{ padding:12px; }
.ck-muted{ opacity:.75; font-size:12px; }
.ck-empty{ opacity:.8; padding:16px 0; text-align:center; }
.ck-error{ color:#b91c1c; font-weight:800; }
.ck-list{ display:grid; gap:10px; }
.ck-list-item{ text-align:left; border:1px solid rgba(0,0,0,.08); border-radius:14px; padding:10px 12px; background:#fff; }
.ck-li-head{ display:flex; justify-content:space-between; gap:10px; margin-bottom:8px; }
.ck-li-name{ font-weight:800; font-size:13px; }
.ck-li-status{ font-size:12px; opacity:.8; white-space:nowrap; }
.ck-li-meta{ display:grid; gap:6px; }
.ck-li-meta span{ font-size:11px; opacity:.75; display:block; }
.ck-li-meta b{ font-size:13px; }
</style>
