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
