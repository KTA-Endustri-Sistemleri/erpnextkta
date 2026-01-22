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
    <div style="display:flex; gap:8px; margin-bottom:10px;">
      <button class="ck-btn ck-btn--primary ck-btn--wide" @click="onHurdaEkle">Hurda Ekle</button>
    </div>

    <div v-if="(doc.hurdalar||[]).length===0" class="ck-muted">Hurda kaydı yok.</div>

    <div v-else class="ck-mini-list">
      <div v-for="(h, i) in doc.hurdalar" :key="h.name || i" class="ck-mini-item">
        <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start;">
          <div style="min-width:0;">
            <b style="display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              {{ h.parca_no || ('Hurda #' + (i+1)) }}
            </b>
            <div class="ck-muted">{{ h.hurda_nedeni || "-" }}</div>
            <div class="ck-muted">{{ h.miktar ?? "-" }} {{ h.birim || "" }}</div>
            <div v-if="h.depo" class="ck-muted">Depo: {{ h.depo }}</div>
          </div>

          <div style="display:flex; gap:6px; flex-shrink:0;">
            <button class="ck-btn ck-btn--ghost" style="padding:8px 10px;" @click="onHurdaDuzenle(h)">
              Düzenle
            </button>
            <button class="ck-btn ck-btn--danger" style="padding:8px 10px;" @click="onHurdaSil(h)">
              Sil
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>