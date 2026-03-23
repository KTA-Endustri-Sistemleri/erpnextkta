<script setup lang="ts">
import { hurdaFields } from "../composables/prompts";

const props = defineProps<{
  doc: any;
  onAdd: (payload: any) => Promise<void>;
  onUpdate: (payload: any) => Promise<void>;
  onDelete: (rowname: string) => Promise<void>;
}>();

function onHurdaEkle() {
  frappe.prompt(
    hurdaFields({
      calisma_karti_name: props.doc.name, // 🔴 KRİTİK: filtre bununla çalışıyor
    }),
    async (v: any) => {
      await props.onAdd({
        parca_no: v.parca_no,
        hurda_nedeni: v.hurda_nedeni,
        miktar: v.miktar,
        birim: v.birim,
        depo: v.depo || null,
      });
      frappe.show_alert({ message: "Hurda eklendi", indicator: "green" });
    },
    "Hurda Ekle",
    "Kaydet"
  );
}

function onHurdaDuzenle(h: any) {
  if (!h?.name) {
    frappe.msgprint("Hurda satır kimliği (row name) bulunamadı.");
    return;
  }

  frappe.prompt(
    hurdaFields({
      ...h,
      calisma_karti_name: props.doc.name, // 🔴 KRİTİK: edit için de şart
    }),
    async (v: any) => {
      await props.onUpdate({
        rowname: h.name,
        parca_no: v.parca_no,
        hurda_nedeni: v.hurda_nedeni,
        miktar: v.miktar,
        birim: v.birim,
        depo: v.depo || null,
      });
      frappe.show_alert({ message: "Hurda güncellendi", indicator: "green" });
    },
    "Hurda Düzenle",
    "Kaydet"
  );
}

function onHurdaSil(h: any) {
  if (!h?.name) {
    frappe.msgprint("Hurda satır kimliği (row name) bulunamadı.");
    return;
  }

  frappe.confirm("Bu hurda satırı silinecek. Emin misiniz?", async () => {
    await props.onDelete(h.name);
    frappe.show_alert({ message: "Hurda silindi", indicator: "green" });
  });
}
</script>

<template>
  <div class="ck-card">
    <div class="ck-view-action" v-if="doc.durum !== 'Hazır' && doc.durum !== 'Bitmiş'">
      <button class="ck-btn ck-btn--ghost ck-btn--wide" @click="onHurdaEkle">Hurda Ekle</button>
    </div>

    <div v-if="(doc.hurdalar||[]).length===0" class="ck-empty-state">Hurda kaydı yok.</div>

    <div v-else class="ck-mini-list">
      <div v-for="(h, i) in doc.hurdalar" :key="h.name || i" class="ck-mini-item">
        <div class="ck-mini-content">
            <b class="ck-mini-title">{{ h.parca_no || ('Hurda #' + (Number(i) + 1)) }}</b>
            <div class="ck-muted ck-mini-sub">{{ h.hurda_nedeni || "-" }}</div>
            <div class="ck-muted ck-mini-sub">{{ h.miktar ?? "-" }} {{ h.birim || "" }}</div>
            <div v-if="h.depo" class="ck-muted ck-mini-sub">Depo: {{ h.depo }}</div>
        </div>

        <div class="ck-mini-actions">
          <button class="ck-btn ck-btn--ghost ck-btn-small" @click="onHurdaDuzenle(h)">Düzenle</button>
          <button class="ck-btn ck-btn--danger ck-btn-small" @click="onHurdaSil(h)">Sil</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ck-view-action {
  padding: 0 10px 14px 10px;
  display: flex;
}
.ck-empty-state {
  padding: 10px;
  text-align: center;
  color: var(--ck-text-muted);
  font-size: 13px;
  opacity: 0.7;
}
.ck-mini-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 10px 10px;
}
.ck-mini-item {
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border-soft);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  box-shadow: var(--ck-glass-highlight), 0 2px 8px rgba(0,0,0,0.02);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.ck-mini-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--ck-glass-highlight), 0 6px 16px rgba(0,0,0,0.06);
}
@media (max-width: 480px) {
  .ck-mini-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
.ck-mini-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ck-mini-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--ck-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ck-mini-sub {
  font-size: 12px;
  opacity: 0.8;
}
.ck-mini-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.ck-btn-small {
  padding: 8px 14px;
  font-size: 13px;
  border-radius: 8px;
  font-weight: 700;
}
</style>
