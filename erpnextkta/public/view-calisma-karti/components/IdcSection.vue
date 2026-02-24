<script setup lang="ts">
import { fmtDt, openActionSheet } from "../utils/kalite_ui";

const props = defineProps<{
  rows: any[];
  canEditQC: boolean;
  onAdd: () => void;
  onEdit: (row: any) => void;
  onDelete: (row: any) => void;
}>();

function actions(r: any) {
  openActionSheet("IDC İşlemleri", ["Düzenle", "Sil"], (a) => {
    if (a === "Düzenle") props.onEdit(r);
    if (a === "Sil") props.onDelete(r);
  });
}
</script>

<template>
  <div class="ck-qc-header">
    <b>IDC Ölçümleri</b>
    <button v-if="props.canEditQC" class="ck-btn ck-btn--primary" style="background: var(--btn-default-hover-bg);padding: 8px 10px;" @click="props.onAdd">
      + Ekle
    </button>
  </div>

  <div v-if="(props.rows||[]).length===0" class="ck-muted" style="margin-top: 14px;padding: 0px 6px;">
    IDC ölçüm kaydı yok.
  </div>

  <div v-else class="ck-mini-list" style="margin-top:8px;">
    <div v-for="(r, i) in props.rows" :key="r.name || i" class="ck-mini-item">
      <!-- Everything stacked -->
      <div style="display:flex; flex-direction:column; gap:8px;">
        <b style="padding: 4px 4px;display: block;overflow: hidden;text-overflow: ellipsis;white-space: nowrap;border-bottom: 1px solid var(--btn-default-hover-bg);">
          {{ r.item_code || ('IDC #' + (i+1)) }}
        </b>

        <div style="display:flex; flex-direction:column; gap:6px;">
          <div class="ck-muted" style="border: 1px solid var(--btn-default-hover-bg);border-radius: 10px;padding: 6px 10px;">
            Yükseklik: <b style="font-weight:800;">{{ r.yukseklik_mm ?? "-" }}</b> mm
          </div>
          <div class="ck-muted" style="border: 1px solid var(--btn-default-hover-bg);border-radius: 10px;padding: 6px 10px;">
            Çekme: <b style="font-weight:800;">{{ r.cekme_n ?? "-" }}</b> N
          </div>
        </div>

        <div
          v-if="r.olcum_tarihi || r.olcumu_giren"
          class="ck-muted"
          style="border:1px dashed rgba(0,0,0,.12); border-radius:12px; padding:8px 10px;"
        >
          <div v-if="r.olcum_tarihi">Tarih: {{ fmtDt(r.olcum_tarihi) }}</div>
          <div v-if="r.olcumu_giren">Giren: {{ r.olcumu_giren }}</div>
        </div>

        <div v-if="props.canEditQC" style="display:flex; justify-content:flex-end;">
          <button class="ck-btn ck-btn--ghost" style="padding:8px 10px; width:100%;" @click="actions(r)">
            DETAY ▾
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
