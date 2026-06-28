<script setup lang="ts">
import { fmtDt, openActionSheet } from "../utils/kalite_ui";

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

const __ = (...args: any[]) => window.__(...args);

function actions(r: any) {
  const items = props.canEditData
    ? [__("Düzenle"), __("Kopyala"), __("Sil")]
    : [__("Kopyala")];
  openActionSheet(__("Enjeksiyon İşlemleri"), items, (a) => {
    if (a === __("Düzenle")) props.onEdit(r);
    if (a === __("Kopyala")) props.onClone(r);
    if (a === __("Sil")) props.onDelete(r);
  });
}

function sapmaClass(val: number, merkez: number, tolerans: number) {
    if (!val || !merkez) return "";
    const diff = Math.abs(val - merkez);
    return diff <= tolerans ? "ck-box-ok" : "ck-box-err";
}

function minMaxClass(val: number, min: number, max: number) {
    if (!val || (!min && !max)) return "";
    if (min && val < min) return "ck-box-err";
    if (max && val > max) return "ck-box-err";
    return "ck-box-ok";
}
</script>

<template>
  <div class="ck-qc-header">
    <b>{{ __('Enjeksiyon Ölçümleri') }}</b>
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
    Enjeksiyon ölçüm kaydı yok.
  </div>

  <div v-else class="ck-mini-list" style="margin-top:8px;">
    <div v-for="(r, i) in props.rows" :key="r.name || i" class="ck-mini-item">
      <div style="display:flex; flex-direction:column; gap:8px;">
        <div class="ck-enjeksiyon-header-info">
           <div class="ck-header-row">
             <span class="ck-label">{{ __("PERİYOT:") }}</span>
             <span class="ck-val">{{ r.kontrol_periyodu || '-' }}</span>
           </div>
           <div class="ck-header-row">
             <span class="ck-label">{{ __("HAMMADDE:") }}</span>
             <span class="ck-val">{{ r.hammadde_no || '-' }}</span>
           </div>
        </div>

        <div class="ck-enjeksiyon-grid">
          <div :class="['ck-enjeksiyon-box', sapmaClass(r.hammadde_kazan_isisi, r.hedef_hammadde_kazan_isisi_merkez, r.hedef_hammadde_kazan_isisi_tolerans)]">
             <span>{{ __('Hammadde Kazan Isısı') }}</span>
             <div><b>{{ r.hammadde_kazan_isisi }}</b> <small>°C</small></div>
             <span v-if="r.hedef_hammadde_kazan_isisi_merkez > 0" class="ck-target-val">Hedef: {{ r.hedef_hammadde_kazan_isisi_merkez }}±{{ r.hedef_hammadde_kazan_isisi_tolerans }}</span>
          </div>
          <div :class="['ck-enjeksiyon-box', sapmaClass(r.ara_hortum_isisi, r.hedef_ara_hortum_isisi_merkez, r.hedef_ara_hortum_isisi_tolerans)]">
             <span>{{ __('Ara Hortum Isısı') }}</span>
             <div><b>{{ r.ara_hortum_isisi }}</b> <small>°C</small></div>
             <span v-if="r.hedef_ara_hortum_isisi_merkez > 0" class="ck-target-val">Hedef: {{ r.hedef_ara_hortum_isisi_merkez }}±{{ r.hedef_ara_hortum_isisi_tolerans }}</span>
          </div>
          <div :class="['ck-enjeksiyon-box', sapmaClass(r.kafa_meme_isisi, r.hedef_kafa_meme_isisi_merkez, r.hedef_kafa_meme_isisi_tolerans)]">
             <span>{{ __('Kafa (Meme) Isısı') }}</span>
             <div><b>{{ r.kafa_meme_isisi }}</b> <small>°C</small></div>
             <span v-if="r.hedef_kafa_meme_isisi_merkez > 0" class="ck-target-val">Hedef: {{ r.hedef_kafa_meme_isisi_merkez }}±{{ r.hedef_kafa_meme_isisi_tolerans }}</span>
          </div>
          <div :class="['ck-enjeksiyon-box', minMaxClass(r.soguk_su_isisi, r.hedef_soguk_su_isisi_min, r.hedef_soguk_su_isisi_maks)]">
             <span>{{ __('Soğuk Su Isısı') }}</span>
             <div><b>{{ r.soguk_su_isisi }}</b> <small>°C</small></div>
             <span v-if="r.hedef_soguk_su_isisi_min > 0 || r.hedef_soguk_su_isisi_maks > 0" class="ck-target-val">Hedef: {{ r.hedef_soguk_su_isisi_min||'' }}-{{ r.hedef_soguk_su_isisi_maks||'' }}</span>
          </div>
          <div :class="['ck-enjeksiyon-box', minMaxClass(r.motor_devir, r.hedef_motor_devir_min, r.hedef_motor_devir_maks)]">
             <span>{{ __('Motor Devir') }}</span>
             <div><b>{{ r.motor_devir }}</b></div>
             <span v-if="r.hedef_motor_devir_min > 0 || r.hedef_motor_devir_maks > 0" class="ck-target-val">Hedef: {{ r.hedef_motor_devir_min||'' }}-{{ r.hedef_motor_devir_maks||'' }}</span>
          </div>
          <div :class="['ck-enjeksiyon-box', minMaxClass(r.hammadde_enjeksiyon_zamani, r.hedef_enjeksiyon_zamani_min, r.hedef_enjeksiyon_zamani_maks)]">
             <span>{{ __('Enjeksiyon Zamanı') }}</span>
             <div><b>{{ r.hammadde_enjeksiyon_zamani }}</b> <small>sn</small></div>
             <span v-if="r.hedef_enjeksiyon_zamani_min > 0 || r.hedef_enjeksiyon_zamani_maks > 0" class="ck-target-val">Hedef: {{ r.hedef_enjeksiyon_zamani_min||'' }}-{{ r.hedef_enjeksiyon_zamani_maks||'' }}</span>
          </div>
          <div :class="['ck-enjeksiyon-box', minMaxClass(r.sogutma_zamani, r.hedef_sogutma_zamani_min, r.hedef_sogutma_zamani_maks)]">
             <span>{{ __('Soğutma Zamanı') }}</span>
             <div><b>{{ r.sogutma_zamani }}</b> <small>sn</small></div>
             <span v-if="r.hedef_sogutma_zamani_min > 0 || r.hedef_sogutma_zamani_maks > 0" class="ck-target-val">Hedef: {{ r.hedef_sogutma_zamani_min||'' }}-{{ r.hedef_sogutma_zamani_maks||'' }}</span>
          </div>
          <div :class="['ck-enjeksiyon-box', minMaxClass(r.cekme_kuvveti_olculen, r.hedef_cekme_kuvveti_min, 0)]">
             <span>{{ __('Çekme Kuvveti') }}</span>
             <div><b>{{ r.cekme_kuvveti_olculen }}</b> <small>N</small></div>
             <span v-if="r.hedef_cekme_kuvveti_min > 0" class="ck-target-val">Min: {{ r.hedef_cekme_kuvveti_min }}</span>
          </div>
        </div>

        <div class="ck-status-grid">
            <div :class="['ck-status-box', r.goz_kontrol ? 'ck-status--success' : 'ck-status--danger']">
                Göz Kontrol {{ r.goz_kontrol ? '✓' : '✕' }}
            </div>
        </div>

        <div
          v-if="r.olcum_tarihi || r.operator"
          class="ck-muted"
          style="border:1px dashed rgba(0,0,0,.12); border-radius:12px; padding:8px 10px;"
        >
          <div v-if="r.olcum_tarihi">{{ __('Tarih') }}: {{ fmtDt(r.olcum_tarihi) }}</div>
          <div v-if="r.operator">{{ __('Giren') }}: {{ r.operator }}</div>
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
.ck-enjeksiyon-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}
.ck-enjeksiyon-box {
    border: 1px solid var(--btn-default-hover-bg);
    border-radius: 10px;
    padding: 6px 10px;
    display: flex;
    flex-direction: column;
    font-size: 11px;
}
.ck-enjeksiyon-box span {
    font-size: 10px;
    opacity: 0.7;
    text-transform: uppercase;
}
.ck-enjeksiyon-box b {
    font-size: 14px;
    font-weight: 800;
}
.ck-enjeksiyon-box small {
    font-size: 10px;
    opacity: 0.6;
}
.ck-enjeksiyon-header-info {
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
.ck-enjeksiyon-sub-info {
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
    grid-template-columns: 1fr;
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
.ck-box-ok {
    border-color: #166534;
    background: #f0fdf4;
}
.ck-box-err {
    border-color: #991b1b;
    background: #fef2f2;
}
.ck-target-val {
    font-size: 9px !important;
    color: #666;
    margin-top: 2px;
}
[data-theme="dark"] .ck-box-ok {
    border-color: var(--ck-success, #22c55e);
    background: var(--ck-success-bg, rgba(34, 197, 94, 0.18));
}
[data-theme="dark"] .ck-box-err {
    border-color: var(--ck-danger, #ef4444);
    background: var(--ck-danger-bg, rgba(239, 68, 68, 0.18));
}
[data-theme="dark"] .ck-target-val {
    color: #a1a1aa;
}
</style>
