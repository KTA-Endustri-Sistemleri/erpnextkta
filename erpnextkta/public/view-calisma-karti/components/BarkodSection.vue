<script setup lang="ts">
import BarcodeVisual from "./BarcodeVisual.vue";
import { copyToClipboard, fmtDt, openActionSheet } from "../utils/kalite_ui";

const props = defineProps<{
  rows: any[];
  canEditQC: boolean;
  canEditData: boolean;
  onAdd: () => void;
  onEdit: (row: any) => void;
  onDelete: (row: any) => void;
}>();

function actions(r: any) {
  const opts = ["Kopyala"];
  if (props.canEditData) opts.push("Düzenle", "Sil");

  openActionSheet("Barkod İşlemleri", opts, (a) => {
    if (a === "Kopyala") copyToClipboard(r.barcode);
    if (a === "Düzenle") props.onEdit(r);
    if (a === "Sil") props.onDelete(r);
  });
}
</script>

<template>
  <div class="ck-qc-header">
    <b>Barkod Kayıtları</b>
    <button v-if="props.canEditData" class="ck-btn ck-btn--primary" style="background: var(--btn-default-hover-bg);padding: 8px 10px;" @click="props.onAdd">
      + Ekle
    </button>
  </div>

  <div v-if="(props.rows||[]).length===0" class="ck-muted" style="margin-top: 14px;padding: 0px 6px;">
    Barkod kaydı yok.
  </div>

  <div v-else class="ck-mini-list" style="margin-top:8px;">
    <div v-for="(r, i) in props.rows" :key="r.name || i" class="ck-mini-item">
      <div style="display:flex; flex-direction:column; gap:8px;">

        <template v-if="r.barcode">
          <BarcodeVisual :value="r.barcode" :width="120" />
          <div
            class="ck-muted"
            style="border: 1px solid var(--btn-default-hover-bg);border-radius: 10px;padding: 6px 10px;background: rgba(0, 0, 0, 0.03);overflow: hidden;text-overflow: ellipsis;white-space: nowrap;"
            :title="r.barcode"
          >
            {{ r.barcode }}
          </div>
        </template>

        <div
          v-if="r.olcum_tarihi || r.olcumu_giren"
          class="ck-muted"
          style="border: 1px dashed var(--btn-default-hover-bg);border-radius: 8px;padding: 8px 10px;"
        >
          <div v-if="r.olcum_tarihi">Tarih: {{ fmtDt(r.olcum_tarihi) }}</div>
          <div v-if="r.olcumu_giren">Giren: {{ r.olcumu_giren }}</div>
        </div>

        <div style="display:flex; justify-content:flex-end;">
          <button v-if="props.canEditData" class="ck-btn ck-btn--ghost" style="padding:8px 10px; width:100%;" @click="actions(r)">
            DETAY ▾
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
