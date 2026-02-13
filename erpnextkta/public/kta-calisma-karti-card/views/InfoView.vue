<script setup lang="ts">
const props = defineProps<{ doc: any }>();
</script>

<template>
  <div class="ck-card">
    <div class="ck-row"><span>İş Emri</span><b>{{ props.doc.custom_work_order || "-" }}</b></div>
    <div class="ck-row"><span>İş Kartı</span><b>{{ props.doc.is_karti || "-" }}</b></div>
    <div class="ck-row"><span>Ürün</span><b>{{ props.doc.urun_kodu || "-" }}</b></div>
    <div class="ck-row"><span>Operasyon</span><b>{{ props.doc.operasyon || "-" }}</b></div>
    <div class="ck-row"><span>İstasyon</span><b>{{ props.doc.is_istasyonu || "-" }}</b></div>
    <div class="ck-row"><span>Operatör</span><b>{{ props.doc.operator || "-" }}</b></div>
  </div>
</template>