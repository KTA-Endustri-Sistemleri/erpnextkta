<script setup lang="ts">
import { fmtDt, openActionSheet } from "../utils/kalite_ui";
import MeasureGauge from "./MeasureGauge.vue";

const props = defineProps<{
  doc: any;
  rows: any[];
  canEditQC: boolean;
  canEditData: boolean;
  onAdd: () => void;
  onEdit: (row: any) => void;
  onDelete: (row: any) => void;
  onClone: (row: any) => void;
  onPrint: () => void;
}>();

function actions(r: any) {
  const items = props.canEditData
    ? ["Düzenle", "Kopyala", "Sil"]
    : ["Kopyala"];
  openActionSheet("Krimp İşlemleri", items, (a) => {
    if (a === "Düzenle") props.onEdit(r);
    if (a === "Kopyala") props.onClone(r);
    if (a === "Sil") props.onDelete(r);
  });
}
</script>

<template>
  <div class="ck-qc-header">
    <b>{{ __('Krimp Ölçümleri') }}</b>
    <div style="display:flex; gap:6px;">
      <button
        v-if="(props.rows||[]).length > 0"
        class="ck-btn"
        style="padding: 8px 10px; font-size: 12px;"
        @click="props.onPrint"
      >
        {{ __('🖨️ Protokol') }}
      </button>
      <button v-if="props.canEditData" class="ck-btn ck-btn--primary" style="background: var(--btn-default-hover-bg);padding: 8px 10px;" @click="props.onAdd">
        {{ __('+ Ekle') }}
      </button>
    </div>
  </div>

  <div v-if="(props.rows||[]).length===0" class="ck-muted" style="margin-top: 14px;padding: 0px 6px;">
    Krimp ölçüm kaydı yok.
  </div>

  <div v-else class="ck-mini-list" style="margin-top:8px;">
    <div v-for="(r, i) in props.rows" :key="r.name || i" class="ck-mini-item">
      <div style="display:flex; flex-direction:column; gap:8px;">
        <div class="ck-krimp-header-info">
           <div class="ck-header-row">
             <span class="ck-label">{{ __('KABLO:') }}</span>
             <span class="ck-val">{{ r.kablo_no || '-' }}</span>
           </div>
           <div class="ck-header-row">
             <span class="ck-label">{{ __('KONTAK:') }}</span>
             <span class="ck-val">{{ r.kontak_no || '-' }}</span>
           </div>
           <div class="ck-header-row">
             <span class="ck-label">{{ __('KESİT:') }}</span>
             <span class="ck-val">{{ r.kablo_kesiti || '-' }}</span>
           </div>
        </div>

        <div class="ck-krimp-sub-info">
            <div><span class="ck-label">{{ __('MAKİNE:') }}</span> <b>{{ r.makine_pres_no || "-" }}</b></div>
            <div><span class="ck-label">{{ __('KALIP:') }}</span> <b>{{ r.kalip_no || "-" }}</b></div>
        </div>

        <div class="ck-krimp-grid">
          <div class="ck-krimp-box ck-krimp-box--wide">
             <span>{{ __('Kablo Boyu') }}</span>
             <MeasureGauge
               :measured="r.olculen_kablo_boyu"
               :target="r.hedef_kablo_boyu"
               :tolerance="3"
               :segment-step="1"
               unit="mm"
             />
          </div>
          <div class="ck-krimp-box ck-krimp-box--wide">
             <span>{{ __('Krimp Yük.') }}</span>
             <MeasureGauge
               :measured="r.olculen_iletken_krimp_yuksekliği"
               :target="r.hedef_iletken_krimp_yuksekliği"
               :tolerance="0.05"
               :segment-step="0.01"
               text-low="düşük"
               text-high="yüksek"
               unit="mm"
             />
          </div>
          <div class="ck-krimp-box">
             <span>{{ __('Çekme') }}</span>
             <div v-if="r.olculen_cekme_kuvveti_n > 0" class="ck-pull-force">
                <span
                  class="ck-pull-val"
                  :class="r.olculen_cekme_kuvveti_n >= r.hedef_cekme_kuvveti_n ? 'ck-pull--ok' : 'ck-pull--fail'"
                >
                  {{ r.olculen_cekme_kuvveti_n }}<small>N</small>
                </span>
                <span v-if="r.hedef_cekme_kuvveti_n > 0" class="ck-pull-target">
                  Hedef: {{ r.hedef_cekme_kuvveti_n }}N
                </span>
             </div>
             <div v-else class="ck-pull-na">—</div>
          </div>
          <div class="ck-krimp-box">
             <span>{{ __('İzokrimp') }}</span>
             <b>{{ r.izokrimp_yuksekligi }}</b>
          </div>
          <div class="ck-krimp-box">
             <span>{{ __('Sıyırma Boyu') }}</span>
             <b>{{ r.siyirma_boyu }}</b> <small>mm</small>
          </div>
          <div class="ck-krimp-box">
             <span>{{ __('Çapak Boyu') }}</span>
             <b>{{ r.capak_boyu }}</b> <small>mm</small>
          </div>
        </div>

        <div class="ck-status-grid">
            <div :class="['ck-status-box', r.radus_mevcut ? 'ck-status--success' : 'ck-status--danger']">
                {{ __('Radüs') }} {{ r.radus_mevcut ? '✓' : '✕' }}
            </div>
            <div :class="['ck-status-box', !r.tel_kesme_mevcut ? 'ck-status--success' : 'ck-status--danger']">
                {{ __('Tel Kesme') }} {{ !r.tel_kesme_mevcut ? __('Yok') + ' ✓' : __('Var') + ' ✕' }}
            </div>
        </div>

        <div
          v-if="r.olcum_tarihi || r.operator"
          class="ck-muted"
          style="border:1px dashed rgba(0,0,0,.12); border-radius:12px; padding:8px 10px;"
        >
          <div v-if="r.olcum_tarihi">Tarih: {{ fmtDt(r.olcum_tarihi) }}</div>
          <div v-if="r.operator">Giren: {{ r.operator }}</div>
        </div>

        <div style="display:flex; justify-content:flex-end;">
          <button class="ck-btn ck-btn--ghost" style="padding:8px 10px; width:100%;" @click="actions(r)">
            {{ __('İŞLEMLER') }} ▾
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
.ck-krimp-box--wide {
    grid-column: 1 / -1;
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
.ck-krimp-header-info {
    border-bottom: 1px solid var(--btn-default-hover-bg);
    padding-bottom: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.ck-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.ck-krimp-sub-info {
    display: flex;
    justify-content: space-between;
    background: rgba(0,0,0,0.03);
    padding: 6px 10px;
    border-radius: 8px;
    font-size: 11px;
}
.ck-label {
    font-size: 10px;
    font-weight: 700;
    opacity: 0.6;
    margin-right: 4px;
}
.ck-val {
    font-weight: 800;
    font-size: 13px;
    color: var(--text-color);
}
.ck-status-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}
.ck-status-box {
    text-align: center;
    padding: 6px;
    border-radius: 8px;
    font-size: 11px;
    font-weight: 700;
}
.ck-status--success {
    background: var(--ck-success-bg);
    color: var(--ck-success);
}
.ck-status--danger {
    background: #ffe6e6;
    color: #cc0000;
}
.ck-badge {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
}
.ck-pull-force {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-top: 4px;
}
.ck-pull-val {
    font-size: 15px;
    font-weight: 800;
    line-height: 1;
}
.ck-pull-val small {
    font-size: 10px;
    font-weight: 400;
    opacity: 0.7;
}
.ck-pull--ok {
    color: var(--ck-success, #1a7a1a);
}
.ck-pull--fail {
    color: #cc0000;
}
.ck-pull-target {
    font-size: 10px;
    opacity: 0.5;
}
.ck-pull-na {
    font-size: 13px;
    opacity: 0.4;
    padding: 4px 0;
}
</style>
