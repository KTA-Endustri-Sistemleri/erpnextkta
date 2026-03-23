<script setup lang="ts">
const props = defineProps<{ doc: any }>();
</script>

<template>
  <div class="ck-info-grid">
    <div class="ck-info-cell">
      <span>İş Emri</span>
      <b>{{ props.doc.custom_work_order || "-" }}</b>
    </div>
    <div class="ck-info-cell">
      <span>İş Kartı</span>
      <b>{{ props.doc.is_karti || "-" }}</b>
    </div>
    <div class="ck-info-cell">
      <span>Ürün</span>
      <b>{{ props.doc.urun_kodu || "-" }}</b>
    </div>
    <div class="ck-info-cell">
      <span>Operasyon</span>
      <b>{{ props.doc.operasyon || "-" }}</b>
    </div>
    <div class="ck-info-cell">
      <span>İstasyon</span>
      <b>{{ props.doc.is_istasyonu || "-" }}</b>
    </div>
    <div class="ck-info-cell">
      <span>Operatör</span>
      <b>{{ props.doc.operator || "-" }}</b>
    </div>
    <div class="ck-info-cell ck-cell-full">
      <span>Belge Yaratılış Tarihi</span>
      <b>{{ props.doc.creation || "-" }}</b>
    </div>
  </div>
</template>

<style scoped>
.ck-info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  padding: 4px;
}

.ck-info-cell {
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border-soft);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: var(--ck-glass-highlight);
}

.ck-info-cell.ck-cell-full {
  grid-column: 1 / -1;
}

.ck-info-cell span {
  font-size: 11px;
  color: var(--ck-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.8;
}

.ck-info-cell b {
  font-size: 14px;
  font-weight: 800;
  color: var(--ck-text);
  word-break: break-word;
}
</style>
