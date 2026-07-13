<script setup lang="ts">
import { ref } from "vue";
import { fmtDt, openActionSheet } from "../utils/kalite_ui";
import MeasureGauge from "./MeasureGauge.vue";

const props = defineProps<{
  doc: any;
  rows: any[];
  canEditQC: boolean;
  canEditData: boolean;
  onAdd: (altOpKaydiName?: string) => void;
  onEdit: (row: any) => void;
  onDelete: (row: any) => void;
  onClone: (row: any) => void;
  onPrint: () => void;
  onSubmitQC?: (rowname: string, item_code: string) => void;
}>();

const openedRowIds = ref(new Set<string>());

function toggleAccordion(rowName: string) {
  const isOpened = openedRowIds.value.has(rowName);
  const newSet = new Set<string>();
  if (!isOpened) {
    newSet.add(rowName);
  }
  openedRowIds.value = newSet;
}

const __ = (...args: any[]) => window.__(...args);

function getAltOpRow(r: any) {
  if (!props.doc.alt_operasyon_bazli_kalite) return null;
  const aoId = r.alt_operasyon_kaydi;
  if (!aoId) return null;
  return (props.doc.alt_operasyon_kayitlari || []).find((x: any) => x.name === aoId);
}

function getThemeClass(status: string) {
  const val = (status || '').toLowerCase();
  if (val === 'accepted' || val === 'onaylandı') return 'ck-badge--success';
  if (val === 'rejected' || val === 'reddedildi' || val === 'red') return 'ck-badge--danger';
  return 'ck-badge--info';
}

function isQCLocked(r: any): boolean {
  if (!props.doc.alt_operasyon_bazli_kalite) return false;
  const aoId = r.alt_operasyon_kaydi;
  if (!aoId) return false;
  
  const ao = (props.doc.alt_operasyon_kayitlari || []).find((x: any) => x.name === aoId);
  if (!ao) return false;
  
  return (ao.quality_inspection_status || "").trim() === "Onaylandı" && !!(ao.quality_inspection || "").trim();
}

function actions(r: any) {
  const locked = isQCLocked(r);
  const isQcUser = props.doc.is_qc_user;

  let items: string[] = [];
  
  if (locked) {
    if (isQcUser) {
      items = [__("Düzenle"), __("Kopyala"), __("Sil")];
    } else {
      items = [__("Kopyala")];
    }
  } else {
    items = props.canEditData ? [__("Düzenle"), __("Kopyala"), __("Sil")] : [__("Kopyala")];
  }

  openActionSheet(__("Krimp İşlemleri"), items, (a) => {
    if (a === __("Düzenle")) props.onEdit(r);
    if (a === __("Kopyala")) props.onClone(r);
    if (a === __("Sil")) {
      if (locked && isQcUser) {
        frappe.confirm(
          __("Bu kayda bağlı kalite kontrol belgesi de iptal edilecektir. Devam etmek istiyor musunuz?"),
          () => props.onDelete(r)
        );
      } else {
        props.onDelete(r);
      }
    }
  });
}
</script>

<template>
  <div class="ck-qc-header">
    <b>{{ __('Krimp Ölçümleri') }}</b>
    <div style="display:flex; gap:6px;">
      <button
        v-if="props.canEditData && props.doc.has_krimp && !props.doc.alt_operasyon_bazli_kalite"
        class="ck-btn ck-btn--primary"
        style="padding: 8px 10px; font-size: 12px;"
        @click="props.onAdd()"
      >
        {{ __('Ekle') }}
      </button>
      <button
        v-if="(props.rows||[]).length > 0"
        class="ck-btn"
        style="padding: 8px 10px; font-size: 12px;"
        @click="props.onPrint"
      >
        {{ __('🖨️ Protokol') }}
      </button>
    </div>
  </div>

  <div v-if="(props.rows||[]).length===0" class="ck-muted" style="margin-top: 14px;padding: 0px 6px;">
    Krimp ölçüm kaydı yok.
  </div>

  <div v-else class="ck-mini-list" style="margin-top:8px;">
    <div v-for="(r, i) in props.rows" :key="r.name || i" class="ck-mini-item ck-accordion" :class="{'is-open': openedRowIds.has(r.name)}">
      <div class="ck-accordion-header" @click="toggleAccordion(r.name)">
        <div style="display: flex; gap: 12px; align-items: stretch; flex: 1; min-width: 0;">
            <div v-if="getAltOpRow(r) && getAltOpRow(r).satir_no" style="display: flex; align-items: center; justify-content: center; padding-right: 12px; border-right: 2px solid var(--ck-glass-border-soft); margin-right: 4px;">
                <span style="font-size: 22px; font-weight: 900; color: var(--ck-text); opacity: 0.9;">{{ getAltOpRow(r).satir_no }}</span>
            </div>
            <div style="display:flex; flex-direction:column; gap:4px; flex:1; min-width: 0;">
               <div v-if="getAltOpRow(r)" style="font-size:13px; font-weight:800; color:var(--ck-text); margin-bottom: 2px;">
                 {{ getAltOpRow(r).alt_operasyon_title || getAltOpRow(r).alt_operasyon }}
               </div>
               <div style="display:flex; align-items:center; gap:8px;">
                 <span class="ck-label">{{ __('KABLO:') }}</span>
                 <span class="ck-val" style="font-size:14px;">{{ r.kablo_no || '-' }}</span>
               </div>
               <div style="display:flex; align-items:center; gap:8px; opacity:0.8; flex-wrap:wrap;">
                 <span class="ck-label" style="margin-right:2px;">{{ __('T1 TERMİNAL:') }}</span>
                 <span class="ck-val" style="font-size:11px;">{{ r.kontak_no || '-' }}</span>
                 <template v-if="r.is_cift_tarafli">
                     <span class="ck-label" style="margin-right:2px; margin-left:6px;">{{ __('T2 TERMİNAL:') }}</span>
                     <span class="ck-val" style="font-size:11px;">{{ r.yon_2_kontak_no || '-' }}</span>
                 </template>
               </div>
            </div>
        </div>
        <div class="ck-accordion-right" style="display:flex; align-items:center; gap:8px; opacity:1; font-size:11px;">
           <template v-if="getAltOpRow(r)">
             <button 
               v-if="props.canEditQC && getAltOpRow(r).quality_inspection_status !== 'Onaylandı' && props.onSubmitQC" 
               class="ck-btn ck-btn--success ck-btn-small" 
               style="font-size:10px; padding:4px 8px; margin-right: 6px; border-radius: 6px;"
               @click.stop="props.onSubmitQC(getAltOpRow(r).name, getAltOpRow(r).hammadde || '')"
             >
               {{ __("KALİTE ONAYI VER") }}
             </button>
             <span v-else :class="['ck-badge', getThemeClass(getAltOpRow(r).quality_inspection_status)]" style="font-size:10px; padding:4px 8px; margin-right: 6px; border-radius: 6px; font-weight: bold; opacity: 1; text-transform: uppercase;">
               {{ getAltOpRow(r).quality_inspection_status || "Onay Bekliyor" }}
             </span>
           </template>
           <span v-if="r.olcum_tarihi" style="text-align:right; opacity:0.6;">{{ fmtDt(r.olcum_tarihi) }}<br><span style="font-size:9px;">{{ r.operator }}</span></span>
           <span class="ck-chevron" style="opacity:0.6;">▼</span>
        </div>
      </div>

      <div class="ck-accordion-body-wrapper">
        <div class="ck-accordion-body-inner">
          <div class="ck-accordion-body" style="display:flex; flex-direction:column; gap:8px; margin-top:12px; padding-top:12px; border-top:1px solid var(--btn-default-hover-bg);">
            <div class="ck-krimp-header-info" style="border-bottom:none; padding-bottom:0;">
            <div class="ck-term-header" style="border-top:none; margin-top:0; padding-top:0;" v-if="r.kontak_no">
              <span class="ck-badge" style="background:#eee;color:#333;" v-if="r.is_cift_tarafli">T1</span>
              <div style="flex:1; display:flex; flex-direction:column; gap:4px;" :style="r.is_cift_tarafli ? 'margin-left:6px;' : ''">
                <div class="ck-header-row" style="opacity:0.8;">
                  <span class="ck-label">{{ __('KESİT:') }} <span style="color:var(--text-color);">{{ r.kablo_kesiti || '-' }}</span></span>
                  <span class="ck-label">{{ __('MK/KL:') }} <span style="color:var(--text-color);">{{ r.makine_pres_no || '-' }} / {{ r.kalip_no || '-' }}</span></span>
                </div>
              </div>
            </div>

           <div v-if="r.yon_2_kontak_no" class="ck-term-header" style="margin-top:4px; padding-top:6px; border-top:1px dashed var(--btn-default-hover-bg);">
             <span class="ck-badge" style="background:#eee;color:#333;">T2</span>
             <div style="flex:1; display:flex; flex-direction:column; gap:4px; margin-left:6px;">
               <div class="ck-header-row" style="opacity:0.8;">
                 <span class="ck-label">{{ __('KESİT:') }} <span style="color:var(--text-color);">{{ r.yon_2_kablo_kesiti || '-' }}</span></span>
                 <span class="ck-label">{{ __('MK/KL:') }} <span style="color:var(--text-color);">{{ r.yon_2_makine_pres_no || '-' }} / {{ r.yon_2_kalip_no || '-' }}</span></span>
               </div>
             </div>
           </div>
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
        </div>

        <div class="ck-term-divider" style="margin-top:8px;">
           <span>{{ __('Kablo Uç İşlemleri') }}</span>
        </div>
        <div class="ck-krimp-grid" style="margin-top:8px;">
          <div class="ck-krimp-box">
             <span>{{ __('Sıyırma Boyu') }} (T1)</span>
             <b>{{ r.siyirma_boyu }}</b> <small>mm</small>
          </div>
          <div class="ck-krimp-box">
             <span>{{ __('Sıyırma Boyu') }} (T2)</span>
             <b>{{ r.yon_2_siyirma_boyu }}</b> <small>mm</small>
          </div>
          <div class="ck-krimp-box">
             <span>{{ __('Çapak Boyu') }} (T1)</span>
             <b>{{ r.capak_boyu }}</b> <small>mm</small>
          </div>
          <div class="ck-krimp-box">
             <span>{{ __('Çapak Boyu') }} (T2)</span>
             <b>{{ r.yon_2_capak_boyu }}</b> <small>mm</small>
          </div>
        </div>

        <template v-if="r.kontak_no">
          <div class="ck-term-divider" v-if="r.is_cift_tarafli || r.yon_2_kontak_no">
             <span>{{ __('T1 Ölçümleri') }}</span>
          </div>
          
          <div class="ck-krimp-grid" :style="r.is_cift_tarafli ? 'margin-top:8px;' : 'margin-top:8px;'">
            <div class="ck-krimp-box ck-krimp-box--wide">
               <span>{{ __('Krimp Yük.') }} <span v-if="r.is_cift_tarafli">(T1)</span></span>
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
               <span>{{ __('Çekme') }} <span v-if="r.is_cift_tarafli">(T1)</span></span>
               <div v-if="r.olculen_cekme_kuvveti_n > 0" class="ck-pull-force">
                  <span
                    class="ck-pull-val"
                    :class="r.olculen_cekme_kuvveti_n >= r.hedef_cekme_kuvveti_n ? 'ck-pull--ok' : 'ck-pull--fail'"
                  >
                    {{ r.olculen_cekme_kuvveti_n }}<small>N</small>
                  </span>
                  <span v-if="r.hedef_cekme_kuvveti_n > 0" class="ck-pull-target">
                    {{ __('Hedef') }}: {{ r.hedef_cekme_kuvveti_n }}N
                  </span>
               </div>
               <div v-else class="ck-pull-na">—</div>
            </div>
            <div class="ck-krimp-box">
               <span>{{ __('İzokrimp') }} <span v-if="r.is_cift_tarafli">(T1)</span></span>
               <b>{{ r.izokrimp_yuksekligi }}</b>
            </div>
          </div>

          <div class="ck-status-grid" style="margin-top:8px;">
              <div :class="['ck-status-box', r.radus_mevcut ? 'ck-status--success' : 'ck-status--danger']">
                  {{ __('Radüs') }} <span v-if="r.is_cift_tarafli">(T1)</span> {{ r.radus_mevcut ? '✓' : '✕' }}
              </div>
              <div :class="['ck-status-box', !r.tel_kesme_mevcut ? 'ck-status--success' : 'ck-status--danger']">
                  {{ __('Tel Kesme') }} <span v-if="r.is_cift_tarafli">(T1)</span> {{ !r.tel_kesme_mevcut ? __('Yok') + ' ✓' : __('Var') + ' ✕' }}
              </div>
          </div>
        </template>

        <template v-if="r.yon_2_kontak_no">
            <div class="ck-term-divider">
               <span>{{ __('T2 Ölçümleri') }}</span>
            </div>
            <div class="ck-krimp-grid" style="margin-top:8px;">
              <div class="ck-krimp-box ck-krimp-box--wide">
                 <span>{{ __('Krimp Yük.') }} (T2)</span>
                 <MeasureGauge
                   :measured="r.yon_2_olculen_iletken_krimp_yuksekligi"
                   :target="r.yon_2_hedef_iletken_krimp_yuksekligi"
                   :tolerance="0.05"
                   :segment-step="0.01"
                   text-low="düşük"
                   text-high="yüksek"
                   unit="mm"
                 />
              </div>
              <div class="ck-krimp-box">
                 <span>{{ __('Çekme') }} (T2)</span>
                 <div v-if="r.yon_2_olculen_cekme_kuvveti_n > 0" class="ck-pull-force">
                    <span
                      class="ck-pull-val"
                      :class="r.yon_2_olculen_cekme_kuvveti_n >= r.yon_2_hedef_cekme_kuvveti_n ? 'ck-pull--ok' : 'ck-pull--fail'"
                    >
                      {{ r.yon_2_olculen_cekme_kuvveti_n }}<small>N</small>
                    </span>
                    <span v-if="r.yon_2_hedef_cekme_kuvveti_n > 0" class="ck-pull-target">
                      {{ __('Hedef') }}: {{ r.yon_2_hedef_cekme_kuvveti_n }}N
                    </span>
                 </div>
                 <div v-else class="ck-pull-na">—</div>
              </div>
              <div class="ck-krimp-box">
                 <span>{{ __('İzokrimp') }} (T2)</span>
                 <b>{{ r.yon_2_izokrimp_yuksekligi }}</b>
              </div>

            </div>
            
            <div class="ck-status-grid" style="margin-top:8px;">
                <div :class="['ck-status-box', r.yon_2_radus_mevcut ? 'ck-status--success' : 'ck-status--danger']">
                    {{ __('Radüs') }} (T2) {{ r.yon_2_radus_mevcut ? '✓' : '✕' }}
                </div>
                <div :class="['ck-status-box', !r.yon_2_tel_kesme_mevcut ? 'ck-status--success' : 'ck-status--danger']">
                    {{ __('Tel Kesme') }} (T2) {{ !r.yon_2_tel_kesme_mevcut ? __('Yok') + ' ✓' : __('Var') + ' ✕' }}
                </div>
            </div>
        </template>

        <div style="display:flex; justify-content:flex-end;">
          <button class="ck-btn ck-btn--ghost" style="padding:8px 10px; width:100%;" @click="actions(r)">
            {{ __('İŞLEMLER') }} ▾
          </button>
        </div>
      </div>
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
    padding: 4px 8px;
    border-radius: 6px;
    display: inline-block;
}
.ck-badge--success {
    background: var(--ck-success-bg, #dcfce7);
    color: var(--ck-success, #166534);
    border: 1px solid rgba(34, 197, 94, 0.2);
}
.ck-badge--info {
    background: var(--ck-info-bg, #dbeafe);
    color: var(--ck-info, #1e40af);
    border: 1px solid rgba(59, 130, 246, 0.2);
}
.ck-badge--danger {
    background: var(--ck-danger-bg, #fee2e2);
    color: var(--ck-danger, #991b1b);
    border: 1px solid rgba(239, 68, 68, 0.2);
}

.ck-accordion {
    transition: all 0.3s ease;
}
.ck-accordion.is-open .ck-chevron {
    transform: rotate(180deg);
}
.ck-chevron {
    transition: transform 0.3s ease;
    display: inline-block;
}
.ck-accordion-header {
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.ck-accordion-body-wrapper {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
}
.ck-accordion.is-open .ck-accordion-body-wrapper {
    grid-template-rows: 1fr;
}
.ck-accordion-body-inner {
    overflow: hidden;
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
.ck-term-divider {
    display: flex;
    align-items: center;
    text-align: center;
    margin: 12px 0 4px 0;
    font-size: 10px;
    font-weight: 800;
    color: var(--text-muted, #666);
    text-transform: uppercase;
}
.ck-term-divider::before,
.ck-term-divider::after {
    content: '';
    flex: 1;
    border-bottom: 1px dashed var(--btn-default-hover-bg, #e2e8f0);
}
.ck-term-divider:not(:empty)::before {
    margin-right: 8px;
}
.ck-term-divider:not(:empty)::after {
    margin-left: 8px;
}
.ck-term-header {
    display: flex;
    align-items: center;
    padding-top: 6px;
    border-top: 1px dashed var(--btn-default-hover-bg);
    margin-top: 6px;
}
details.ck-accordion summary {
    list-style: none;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    outline: none;
}
details.ck-accordion summary::-webkit-details-marker {
    display: none;
}
details.ck-accordion[open] summary .ck-chevron {
    transform: rotate(180deg);
}
.ck-chevron {
    transition: transform 0.2s ease;
}
</style>
