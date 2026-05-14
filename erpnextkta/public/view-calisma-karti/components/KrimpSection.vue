<script setup lang="ts">
import { fmtDt, openActionSheet } from "../utils/kalite_ui";

const props = defineProps<{
  rows: any[];
  canEditQC: boolean;
  canEditData: boolean;
  onAdd: () => void;
  onEdit: (row: any) => void;
  onDelete: (row: any) => void;
}>();

function actions(r: any) {
  openActionSheet("Krimp İşlemleri", ["Düzenle", "Sil"], (a) => {
    if (a === "Düzenle") props.onEdit(r);
    if (a === "Sil") props.onDelete(r);
  });
}
</script>

<template>
  <div class="ck-qc-header">
    <b>Krimp Ölçümleri</b>
    <button v-if="props.canEditData" class="ck-btn ck-btn--primary" style="background: var(--btn-default-hover-bg);padding: 8px 10px;" @click="props.onAdd">
      + Ekle
    </button>
  </div>

  <div v-if="(props.rows||[]).length===0" class="ck-muted" style="margin-top: 14px;padding: 0px 6px;">
    Krimp ölçüm kaydı yok.
  </div>

  <div v-else class="ck-mini-list" style="margin-top:8px;">
    <div v-for="(r, i) in props.rows" :key="r.name || i" class="ck-mini-item">
      <div style="display:flex; flex-direction:column; gap:8px;">
        <b style="padding: 4px 4px;display: block;overflow: hidden;text-overflow: ellipsis;white-space: nowrap;border-bottom: 1px solid var(--btn-default-hover-bg);">
          {{ r.kablo_no || ('Krimp #' + (i+1)) }} / {{ r.kontak_no || "-" }}
        </b>

        <div class="ck-krimp-grid">
          <div class="ck-krimp-box">
             <span>Kablo Boyu</span>
             <b>{{ r.olculen_kablo_boyu }}</b> <small>/ {{ r.hedef_kablo_boyu }}</small>
          </div>
          <div class="ck-krimp-box">
             <span>Krimp Yük.</span>
             <b>{{ r.olculen_iletken_krimp_yuksekliği }}</b> <small>/ {{ r.hedef_iletken_krimp_yuksekliği }}</small>
          </div>
          <div class="ck-krimp-box">
             <span>Çekme</span>
             <b>{{ r.cekme_kuvveti_n }}</b> <small>N</small>
          </div>
          <div class="ck-krimp-box">
             <span>İzokrimp</span>
             <b>{{ r.izokrimp_yuksekligi }}</b>
          </div>
        </div>

        <div style="display:flex; gap:8px; flex-wrap:wrap;">
            <div v-if="r.radus_mevcut" class="ck-badge ck-badge--success">Radüs ✓</div>
            <div v-else class="ck-badge ck-badge--danger">Radüs ✕</div>

            <div v-if="r.tel_kesme_mevcut" class="ck-badge ck-badge--success">Tel Kesme ✓</div>
            <div v-else class="ck-badge ck-badge--danger">Tel Kesme ✕</div>

            <div class="ck-badge ck-badge--info">Kalıp: {{ r.kalip_no || "-" }}</div>
            <div class="ck-badge ck-badge--info">Makine: {{ r.makine_pres_no || "-" }}</div>
        </div>

        <div
          v-if="r.olcum_tarihi || r.operator"
          class="ck-muted"
          style="border:1px dashed rgba(0,0,0,.12); border-radius:12px; padding:8px 10px;"
        >
          <div v-if="r.olcum_tarihi">Tarih: {{ fmtDt(r.olcum_tarihi) }}</div>
          <div v-if="r.operator">Giren: {{ r.operator }}</div>
        </div>

        <div v-if="props.canEditData" style="display:flex; justify-content:flex-end;">
          <button class="ck-btn ck-btn--ghost" style="padding:8px 10px; width:100%;" @click="actions(r)">
            DETAY ▾
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ck-krimp-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}
.ck-krimp-box {
    border: 1px solid var(--btn-default-hover-bg);
    border-radius: 10px;
    padding: 6px 10px;
    display: flex;
    flex-direction: column;
    font-size: 11px;
}
.ck-krimp-box span {
    font-size: 10px;
    opacity: 0.7;
    text-transform: uppercase;
}
.ck-krimp-box b {
    font-size: 14px;
    font-weight: 800;
}
.ck-krimp-box small {
    font-size: 10px;
    opacity: 0.6;
}
.ck-badge {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
}
.ck-badge--success {
    background: var(--ck-success-bg);
    color: var(--ck-success);
}
.ck-badge--danger {
    background: #ffe6e6;
    color: #cc0000;
}
.ck-badge--info {
    background: var(--ck-info-bg);
    color: var(--ck-info);
}
</style>
