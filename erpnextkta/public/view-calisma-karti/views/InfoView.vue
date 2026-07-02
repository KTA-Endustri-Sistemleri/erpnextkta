<script setup lang="ts">
const props = defineProps<{ doc: any }>();

function openDoc(doctype: string, docname: string) {
  if (!docname || docname === "-") return;
  // Slugify doctype (e.g. "Work Order" -> "work-order")
  const slug = doctype.toLowerCase().split(" ").join("-");
  window.open(`/app/${slug}/${docname}`, "_blank");
}
</script>

<template>
  <div class="row no-gutters ck-info-row">
    <div class="col-xs-6 col-sm-4 col-lg-2 ck-info-col">
      <div class="ck-info-cell is-link" @click="openDoc('Work Order', props.doc.custom_work_order)">
        <svg class="ck-link-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
          <polyline points="15 3 21 3 21 9"></polyline>
          <line x1="10" y1="14" x2="21" y2="3"></line>
        </svg>
        <span>{{ __("İş Emri") }}</span>
        <b>{{ props.doc.custom_work_order || "-" }}</b>
      </div>
    </div>
    <div class="col-xs-6 col-sm-4 col-lg-2 ck-info-col">
      <div class="ck-info-cell is-link" @click="openDoc('Job Card', props.doc.is_karti)">
        <svg class="ck-link-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
          <polyline points="15 3 21 3 21 9"></polyline>
          <line x1="10" y1="14" x2="21" y2="3"></line>
        </svg>
        <span>{{ __("İş Kartı") }}</span>
        <b>{{ props.doc.is_karti || "-" }}</b>
      </div>
    </div>
    <div class="col-xs-6 col-sm-4 col-lg-2 ck-info-col">
      <div class="ck-info-cell">
        <span>{{ __("Ürün") }}</span>
        <b>{{ props.doc.urun_kodu || "-" }}</b>
      </div>
    </div>
    <div class="col-xs-6 col-sm-4 col-lg-2 ck-info-col">
      <div class="ck-info-cell">
        <span>{{ __("Operasyon") }}</span>
        <b>{{ props.doc.operasyon || "-" }}</b>
      </div>
    </div>
    <div class="col-xs-6 col-sm-4 col-lg-2 ck-info-col">
      <div class="ck-info-cell">
        <span>{{ __("İstasyon") }}</span>
        <b>{{ props.doc.is_istasyonu || "-" }}</b>
      </div>
    </div>
    <div class="col-xs-6 col-sm-4 col-lg-2 ck-info-col">
      <div class="ck-info-cell">
        <span>{{ __("Operatör") }}</span>
        <b>{{ props.doc.operator || "-" }}</b>
      </div>
    </div>
    <div class="col-xs-12 ck-info-col">
      <div class="ck-info-cell ck-cell-full">
        <span>{{ __("Belge Yaratılış Tarihi") }}</span>
        <b>{{ props.doc.creation || "-" }}</b>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ck-info-row {
  margin: 0 -8px;
  display: flex;
  flex-wrap: wrap;
}

.ck-info-col {
  padding: 8px;
}

.ck-info-cell {
  height: 100%;
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border-soft);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  box-shadow: var(--ck-glass-shadow), var(--ck-glass-highlight);
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  overflow: hidden;
}

.ck-info-cell:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12), var(--ck-glass-highlight);
  border-color: var(--ck-glass-border);
  background: var(--ck-surface);
}

.ck-info-cell.is-link {
  cursor: pointer;
}

.ck-info-cell.is-link:hover b {
  color: var(--ck-primary, #3b82f6);
  text-decoration: underline;
}

.ck-link-icon {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 12px;
  height: 12px;
  opacity: 0.35;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  color: var(--ck-text-muted);
}

.ck-info-cell.is-link:hover .ck-link-icon {
  opacity: 1;
  color: var(--ck-primary, #3b82f6);
  transform: translate(2px, -2px);
}

.ck-info-cell.ck-cell-full {
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  border-style: dashed;
}

@media (max-width: 576px) {
  .ck-info-cell.ck-cell-full {
    flex-direction: column;
    align-items: flex-start;
  }
}

.ck-info-cell span {
  font-size: 10px;
  color: var(--ck-text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 700;
  opacity: 0.7;
}

.ck-info-cell b {
  font-size: 14px;
  font-weight: 800;
  color: var(--ck-text);
  word-break: break-word;
  line-height: 1.3;
}
</style>
