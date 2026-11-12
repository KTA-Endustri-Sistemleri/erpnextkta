<script setup lang="ts">
import { ref, computed } from "vue";
import { fmtDt, getQcBadgeClass, isQcPending, isQcRejected, openActionSheet, sortAltOperasyonRows } from "../utils/kalite_ui";

const props = defineProps<{
  doc: any;
  rows: any[];
  canEditQC: boolean;
  canEditData: boolean;
  onAdd: (kalipNo?: string, hammadde?: string, altOpKaydiName?: string) => void;
  onEdit: (row: any) => void;
  onDelete: (row: any) => void;
  onClone: (row: any) => void;
  onPrint: () => void;
  onSubmitQC?: (rowname: string, item_code: string, intent?: "approve" | "reject") => void;
}>();

const __ = (...args: any[]) => (window as any).__(...args);
const frappe = (window as any).frappe;

const openedRowIds = ref(new Set<string>());

function toggleAccordion(id: string) {
  const isOpened = openedRowIds.value.has(id);
  const newSet = new Set<string>();
  if (!isOpened) {
    newSet.add(id);
  }
  openedRowIds.value = newSet;
}

const altOpList = computed(() => {
  return sortAltOperasyonRows(props.doc?.alt_operasyon_kayitlari || []);
});

function getMeasurementsForAltOp(ao: any) {
  const all = props.rows || [];
  if (all.length === 0) return [];

  // 1. Direct match by alt_operasyon_kaydi if available
  const directMatches = all.filter((m: any) => m.alt_operasyon_kaydi && m.alt_operasyon_kaydi === ao.name);

  // 2. Disambiguate legacy records without alt_operasyon_kaydi:
  const unassigned = all.filter((m: any) => !m.alt_operasyon_kaydi);
  if (unassigned.length === 0) return directMatches;

  let legacyMatches: any[] = [];

  // Check if multiple alt ops share the same kalip_no
  const sameKalipAltOps = altOpList.value.filter((x: any) => 
    x.kalip_no && ao.kalip_no && String(x.kalip_no).trim().toLowerCase() === String(ao.kalip_no).trim().toLowerCase()
  );

  // If this kalip_no is unique to this alt_op (unambiguous legacy match)
  if (sameKalipAltOps.length === 1 && ao.kalip_no) {
    legacyMatches = unassigned.filter((m: any) => 
      String(m.kalip_no || "").trim().toLowerCase() === String(ao.kalip_no).trim().toLowerCase()
    );
  } else if (sameKalipAltOps.length > 1 && ao.kalip_no && ao.hammadde) {
    // If multiple alt ops share mold, match by BOTH kalip_no AND hammadde_no
    const sameKalipAndHammaddeAltOps = altOpList.value.filter((x: any) =>
      x.kalip_no && ao.kalip_no && String(x.kalip_no).trim().toLowerCase() === String(ao.kalip_no).trim().toLowerCase() &&
      x.hammadde && ao.hammadde && String(x.hammadde).trim().toLowerCase() === String(ao.hammadde).trim().toLowerCase()
    );
    if (sameKalipAndHammaddeAltOps.length === 1) {
      legacyMatches = unassigned.filter((m: any) =>
        String(m.kalip_no || "").trim().toLowerCase() === String(ao.kalip_no).trim().toLowerCase() &&
        String(m.hammadde_no || "").trim().toLowerCase() === String(ao.hammadde).trim().toLowerCase()
      );
    }
  } else if (altOpList.value.length === 1) {
    // Single alt op fallback
    legacyMatches = unassigned;
  }

  // Merge direct matches with unambiguously matched legacy records
  const combined = [...directMatches];
  for (const leg of legacyMatches) {
    if (!combined.some((x: any) => x.name && x.name === leg.name)) {
      combined.push(leg);
    }
  }
  return combined;
}

const unassignedMeasurements = computed(() => {
  const all = props.rows || [];
  if (all.length === 0) return [];
  const assignedNames = new Set<string>();
  for (const ao of altOpList.value) {
    const list = getMeasurementsForAltOp(ao);
    for (const m of list) {
      if (m.name) assignedNames.add(m.name);
    }
  }
  return all.filter((m: any) => m.name && !assignedNames.has(m.name));
});

function getLatestMeasurement(ao: any) {
  const list = getMeasurementsForAltOp(ao);
  if (list.length === 0) return null;
  return list[list.length - 1];
}

const getThemeClass = getQcBadgeClass;

function getOperatorName(r: any) {
  const op = r?.operator;
  if (!op) return "";

  // Email veya kullanıcı adı ise tam ada çevir
  if (frappe?.user_info?.[op]?.fullname) {
    return frappe.user_info[op].fullname;
  }

  if (op === props.doc?.operator && props.doc?.operator_name) {
    return props.doc.operator_name;
  }

  if (typeof op === "string" && op.includes("@")) {
    if (frappe?.boot?.user_info?.[op]?.fullname) {
      return frappe.boot.user_info[op].fullname;
    }
    if (frappe?.session?.user === op && frappe?.session?.user_fullname) {
      return frappe.session.user_fullname;
    }
    return props.doc?.operator_name || op.split("@")[0].toUpperCase();
  }

  return op;
}

function isRejected(ao: any): boolean {
  return isQcRejected(ao?.quality_inspection_status);
}

function canAddMeasurement(ao: any): boolean {
  if (!props.canEditData) return false;
  if (isRejected(ao)) return false;
  const measurements = getMeasurementsForAltOp(ao);
  if (measurements.length >= 3) return false;
  const used = new Set(measurements.map((m: any) => m.kontrol_periyodu).filter(Boolean));
  if (used.has("Başlangıç") && used.has("Ara") && used.has("Bitiş")) return false;
  return true;
}

function isQCLocked(ao: any): boolean {
  if (!props.doc?.alt_operasyon_bazli_kalite) return false;
  if (!ao) return false;
  return !!(ao.quality_inspection || "").trim();
}

function actions(r: any, ao?: any) {
  const locked = ao ? isQCLocked(ao) : false;
  const isQcUser = props.doc?.is_qc_user;

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

  openActionSheet(__("Enjeksiyon İşlemleri"), items, (a) => {
    if (a === __("Düzenle")) props.onEdit(r);
    if (a === __("Kopyala")) {
      props.onClone({
        ...r,
        alt_operasyon_kaydi: r.alt_operasyon_kaydi || ao?.name || ""
      });
    }
    if (a === __("Sil")) {
      frappe.confirm(
        __("Bu ölçüm kaydı silinecek. Emin misiniz?"),
        () => props.onDelete(r)
      );
    }
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
        v-if="props.canEditData && !props.doc?.alt_operasyon_bazli_kalite"
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

  <!-- CASE 1: Alt Operasyon Bazlı Kalite (Her alt operasyon listelenir) -->
  <template v-if="props.doc?.alt_operasyon_bazli_kalite">
    <div v-if="altOpList.length === 0" class="ck-muted" style="margin-top: 14px;padding: 0px 6px;">
      {{ __('Alt operasyon kaydı bulunamadı.') }}
    </div>

    <div v-else class="ck-mini-list" style="margin-top:8px;">
      <div
        v-for="(ao, i) in altOpList"
        :key="ao.name || i"
        class="ck-mini-item ck-accordion"
        :class="{'is-open': openedRowIds.has(ao.name)}"
      >
        <div
          class="ck-accordion-header"
          role="button"
          tabindex="0"
          :aria-expanded="openedRowIds.has(ao.name)"
          :aria-controls="'ck-accordion-body-enj-' + (ao.name || i)"
          @click="toggleAccordion(ao.name)"
          @keydown.enter.self.prevent="toggleAccordion(ao.name)"
          @keydown.space.self.prevent="toggleAccordion(ao.name)"
        >
          <div style="display: flex; gap: 12px; align-items: stretch; flex: 1; min-width: 0;">
            <!-- Büyük Satır No kutusu (Varsa) -->
            <div
              v-if="ao.satir_no"
              class="ck-satir-badge"
            >
              <span>{{ ao.satir_no }}</span>
            </div>

            <div style="display:flex; flex-direction:column; gap:4px; flex:1; min-width: 0;">
              <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-bottom: 2px;">
                <span style="font-size:13px; font-weight:800; color:var(--ck-text);">
                  {{ __(ao.title || ao.alt_operasyon_title || ao.alt_operasyon) }}
                </span>
                <span v-if="ao.kalip_no" class="ck-mold-pill">🏷️ {{ ao.kalip_no }}</span>
              </div>
              <div v-if="getLatestMeasurement(ao)?.kontrol_periyodu" style="display:flex; align-items:center; gap:8px;">
                <span class="ck-label">{{ __('Periyot') }}:</span>
                <span class="ck-val" style="font-size:14px;">{{ __(getLatestMeasurement(ao).kontrol_periyodu) }}</span>
              </div>
              <div style="display:flex; align-items:center; gap:8px; opacity:0.8; flex-wrap:wrap;">
                <span class="ck-label" style="margin-right:2px;">{{ __('Hammadde') }}:</span>
                <span class="ck-val" style="font-size:11px;">{{ ao.hammadde || getLatestMeasurement(ao)?.hammadde_no || '-' }}</span>
                <template v-if="ao.satir_no">
                  <span class="ck-label" style="margin-right:2px; margin-left:6px;">{{ __('Satır No') }}:</span>
                  <span class="ck-val" style="font-size:11px;">{{ ao.satir_no }}</span>
                </template>
              </div>
            </div>
          </div>

          <!-- Sağ Taraf (Krimp ile birebir aynı: Onay Butonları, Rozet, Tarih/Kullanıcı Adı, Chevron) -->
          <div class="ck-accordion-right" style="display:flex; align-items:center; gap:8px; opacity:1; font-size:11px;">
            <template v-if="props.canEditQC && isQcPending(ao.quality_inspection_status) && props.onSubmitQC">
              <button
                class="ck-btn ck-btn--success ck-btn-small"
                style="font-size:10px; padding:4px 8px; margin-right: 4px; border-radius: 6px;"
                @click.stop="props.onSubmitQC(ao.name, ao.hammadde || '', 'approve')"
              >
                {{ __("Kalite Onayı Ver") }}
              </button>
              <button
                class="ck-btn ck-btn--danger ck-btn-small"
                style="font-size:10px; padding:4px 8px; margin-right: 6px; border-radius: 6px;"
                @click.stop="props.onSubmitQC(ao.name, ao.hammadde || '', 'reject')"
              >
                {{ __("Reddet") }}
              </button>
            </template>
            <span v-else :class="['ck-badge', getThemeClass(ao.quality_inspection_status)]" style="font-size:10px; padding:4px 8px; margin-right: 6px; border-radius: 6px; font-weight: bold; opacity: 1; text-transform: uppercase;">
              {{ ao.quality_inspection_status ? __(ao.quality_inspection_status) : __("Onay Bekliyor") }}
            </span>
            <span v-if="getLatestMeasurement(ao)?.olcum_tarihi" style="text-align:right; opacity:0.6;">
              {{ fmtDt(getLatestMeasurement(ao).olcum_tarihi) }}<br><span style="font-size:9px;">{{ getOperatorName(getLatestMeasurement(ao)) }}</span>
            </span>
            <button
              type="button"
              class="ck-accordion-toggle-btn"
              :aria-expanded="openedRowIds.has(ao.name)"
              :aria-controls="'ck-accordion-body-enj-' + (ao.name || i)"
              :aria-label="__('Detayları Göster/Gizle')"
              tabindex="-1"
              @click.stop="toggleAccordion(ao.name)"
            >
              <span class="ck-chevron" style="opacity:0.6;">▼</span>
            </button>
          </div>
        </div>

        <!-- Akordiyon Gövdesi: Ölçüm Parametreleri ve İşlemler Butonu (Krimp ile birebir aynı) -->
        <div
          :id="'ck-accordion-body-enj-' + (ao.name || i)"
          class="ck-accordion-body-wrapper"
        >
          <div class="ck-accordion-body-inner">
            <div class="ck-accordion-body" style="display:flex; flex-direction:column; gap:8px; margin-top:12px; padding-top:12px; border-top:1px solid var(--btn-default-hover-bg);">
              <template v-if="getMeasurementsForAltOp(ao).length === 0">
                <div class="ck-muted" style="text-align: center; padding: 12px 0;">
                  {{ __('Bu alt operasyon için henüz ölçüm girilmedi.') }}
                </div>
                <button
                  v-if="canAddMeasurement(ao)"
                  class="ck-btn ck-btn--primary"
                  style="width: 100%; padding: 8px 10px; font-size: 12px;"
                  @click="props.onAdd(ao.kalip_no, ao.hammadde, ao.name)"
                >
                  + {{ __('Ölçüm Ekle') }}
                </button>
                <div
                  v-else-if="isRejected(ao)"
                  class="ck-badge ck-badge--danger"
                  style="padding: 6px 12px; font-size: 11px; text-align: center; border-radius: 6px; font-weight: 700; width: 100%; display: block;"
                >
                  ✕ {{ __('Alt Operasyon Kalite Tarafından Reddedildi') }}
                </div>
              </template>

              <template v-else>
                <div v-for="(m, mIdx) in getMeasurementsForAltOp(ao)" :key="m.name || mIdx" style="display:flex; flex-direction:column; gap:8px;">
                  <div v-if="getMeasurementsForAltOp(ao).length > 1" class="ck-header-row" style="font-weight:700; font-size:12px; opacity:0.8;">
                    <span>{{ __('Periyot') }}: {{ m.kontrol_periyodu ? __(m.kontrol_periyodu) : '-' }}</span>
                    <span v-if="m.olcum_tarihi">{{ fmtDt(m.olcum_tarihi) }}</span>
                  </div>

                  <div class="ck-enjeksiyon-grid">
                    <div :class="['ck-enjeksiyon-box', sapmaClass(m.hammadde_kazan_isisi, m.hedef_hammadde_kazan_isisi_merkez, m.hedef_hammadde_kazan_isisi_tolerans)]">
                      <span>{{ __('Hammadde Kazan Isısı') }}</span>
                      <div><b>{{ m.hammadde_kazan_isisi }}</b> <small>°C</small></div>
                      <span v-if="m.hedef_hammadde_kazan_isisi_merkez > 0" class="ck-target-val">{{ __('Hedef') }}: {{ m.hedef_hammadde_kazan_isisi_merkez }}±{{ m.hedef_hammadde_kazan_isisi_tolerans }}</span>
                    </div>
                    <div :class="['ck-enjeksiyon-box', sapmaClass(m.ara_hortum_isisi, m.hedef_ara_hortum_isisi_merkez, m.hedef_ara_hortum_isisi_tolerans)]">
                      <span>{{ __('Ara Hortum Isısı') }}</span>
                      <div><b>{{ m.ara_hortum_isisi }}</b> <small>°C</small></div>
                      <span v-if="m.hedef_ara_hortum_isisi_merkez > 0" class="ck-target-val">{{ __('Hedef') }}: {{ m.hedef_ara_hortum_isisi_merkez }}±{{ m.hedef_ara_hortum_isisi_tolerans }}</span>
                    </div>
                    <div :class="['ck-enjeksiyon-box', sapmaClass(m.kafa_meme_isisi, m.hedef_kafa_meme_isisi_merkez, m.hedef_kafa_meme_isisi_tolerans)]">
                      <span>{{ __('Kafa (Meme) Isısı') }}</span>
                      <div><b>{{ m.kafa_meme_isisi }}</b> <small>°C</small></div>
                      <span v-if="m.hedef_kafa_meme_isisi_merkez > 0" class="ck-target-val">{{ __('Hedef') }}: {{ m.hedef_kafa_meme_isisi_merkez }}±{{ m.hedef_kafa_meme_isisi_tolerans }}</span>
                    </div>
                    <div :class="['ck-enjeksiyon-box', minMaxClass(m.soguk_su_isisi, m.hedef_soguk_su_isisi_min, m.hedef_soguk_su_isisi_maks)]">
                      <span>{{ __('Soğuk Su Isısı') }}</span>
                      <div><b>{{ m.soguk_su_isisi }}</b> <small>°C</small></div>
                      <span v-if="m.hedef_soguk_su_isisi_min > 0 || m.hedef_soguk_su_isisi_maks > 0" class="ck-target-val">{{ __('Hedef') }}: {{ m.hedef_soguk_su_isisi_min||'' }}-{{ m.hedef_soguk_su_isisi_maks||'' }}</span>
                    </div>
                    <div :class="['ck-enjeksiyon-box', minMaxClass(m.motor_devir, m.hedef_motor_devir_min, m.hedef_motor_devir_maks)]">
                      <span>{{ __('Motor Devir') }}</span>
                      <div><b>{{ m.motor_devir }}</b></div>
                      <span v-if="m.hedef_motor_devir_min > 0 || m.hedef_motor_devir_maks > 0" class="ck-target-val">{{ __('Hedef') }}: {{ m.hedef_motor_devir_min||'' }}-{{ m.hedef_motor_devir_maks||'' }}</span>
                    </div>
                    <div :class="['ck-enjeksiyon-box', minMaxClass(m.hammadde_enjeksiyon_zamani, m.hedef_enjeksiyon_zamani_min, m.hedef_enjeksiyon_zamani_maks)]">
                      <span>{{ __('Enjeksiyon Zamanı') }}</span>
                      <div><b>{{ m.hammadde_enjeksiyon_zamani }}</b> <small>sn</small></div>
                      <span v-if="m.hedef_enjeksiyon_zamani_min > 0 || m.hedef_enjeksiyon_zamani_maks > 0" class="ck-target-val">{{ __('Hedef') }}: {{ m.hedef_enjeksiyon_zamani_min||'' }}-{{ m.hedef_enjeksiyon_zamani_maks||'' }}</span>
                    </div>
                    <div :class="['ck-enjeksiyon-box', minMaxClass(m.sogutma_zamani, m.hedef_sogutma_zamani_min, m.hedef_sogutma_zamani_maks)]">
                      <span>{{ __('Soğutma Zamanı') }}</span>
                      <div><b>{{ m.sogutma_zamani }}</b> <small>sn</small></div>
                      <span v-if="m.hedef_sogutma_zamani_min > 0 || m.hedef_sogutma_zamani_maks > 0" class="ck-target-val">{{ __('Hedef') }}: {{ m.hedef_sogutma_zamani_min||'' }}-{{ m.hedef_sogutma_zamani_maks||'' }}</span>
                    </div>
                    <div :class="['ck-enjeksiyon-box', minMaxClass(m.cekme_kuvveti_olculen, m.hedef_cekme_kuvveti_min, 0)]">
                      <span>{{ __('Çekme Kuvveti') }}</span>
                      <div><b>{{ m.cekme_kuvveti_olculen }}</b> <small>N</small></div>
                      <span v-if="m.hedef_cekme_kuvveti_min > 0" class="ck-target-val">{{ __('Min') }}: {{ m.hedef_cekme_kuvveti_min }}</span>
                    </div>
                  </div>

                  <div class="ck-status-grid" style="margin-top:4px;">
                    <div :class="['ck-status-box', m.goz_kontrol ? 'ck-status--success' : 'ck-status--danger']">
                      {{ __('Göz Kontrol') }} {{ m.goz_kontrol ? '✓' : '✕' }}
                    </div>
                  </div>

                  <div style="display:flex; justify-content:flex-end; margin-top:4px;">
                    <button class="ck-btn ck-btn--ghost" style="padding:8px 10px; width:100%;" @click="actions(m, ao)">
                      {{ __('İşlemler') }} ▾
                    </button>
                  </div>
                </div>

                <button
                  v-if="canAddMeasurement(ao)"
                  class="ck-btn ck-btn--primary"
                  style="width: 100%; padding: 8px 10px; font-size: 12px; margin-top: 4px;"
                  @click="props.onAdd(ao.kalip_no, ao.hammadde, ao.name)"
                >
                  + {{ __('Ölçüm Ekle') }}
                </button>
                <div
                  v-else-if="getMeasurementsForAltOp(ao).length >= 3"
                  class="ck-badge ck-badge--success"
                  style="padding: 6px 12px; font-size: 11px; text-align: center; border-radius: 6px; font-weight: 700; width: 100%; display: block; margin-top: 4px;"
                >
                  ✓ {{ __('Tüm Periyot Ölçümleri Tamamlandı (3/3)') }}
                </div>
                <div
                  v-else-if="isRejected(ao)"
                  class="ck-badge ck-badge--danger"
                  style="padding: 6px 12px; font-size: 11px; text-align: center; border-radius: 6px; font-weight: 700; width: 100%; display: block; margin-top: 4px;"
                >
                  ✕ {{ __('Alt Operasyon Kalite Tarafından Reddedildi') }}
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Fallback: Atanmamış / Geçmiş Ölçümler (Legacy Unassigned Measurements) -->
      <div v-if="unassignedMeasurements.length > 0" class="ck-unassigned-section" style="margin-top:16px;">
        <div style="font-size:12px; font-weight:800; color:var(--ck-text); opacity:0.85; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
          <span>📦</span>
          <span>{{ __('Atanmamış / Geçmiş Ölçümler') }}</span>
          <span class="ck-badge" style="font-size:10px; padding:2px 6px;">{{ unassignedMeasurements.length }}</span>
        </div>
        <div class="ck-mini-list">
          <div v-for="(r, i) in unassignedMeasurements" :key="r.name || i" class="ck-mini-item">
            <div style="display:flex; flex-direction:column; gap:8px;">
              <div class="ck-enjeksiyon-header-info">
                <div class="ck-header-row">
                  <span class="ck-label">{{ __("Periyot") }}:</span>
                  <span class="ck-val">{{ r.kontrol_periyodu ? __(r.kontrol_periyodu) : '-' }}</span>
                </div>
                <div class="ck-header-row">
                  <span class="ck-label">{{ __("Kalıp No") }}:</span>
                  <span class="ck-val">{{ r.kalip_no || '-' }}</span>
                </div>
                <div class="ck-header-row">
                  <span class="ck-label">{{ __("Hammadde") }}:</span>
                  <span class="ck-val">{{ r.hammadde_no || '-' }}</span>
                </div>
              </div>

              <div class="ck-enjeksiyon-grid">
                <div :class="['ck-enjeksiyon-box', sapmaClass(r.hammadde_kazan_isisi, r.hedef_hammadde_kazan_isisi_merkez, r.hedef_hammadde_kazan_isisi_tolerans)]">
                  <span>{{ __('Hammadde Kazan Isısı') }}</span>
                  <div><b>{{ r.hammadde_kazan_isisi }}</b> <small>°C</small></div>
                </div>
                <div :class="['ck-enjeksiyon-box', sapmaClass(r.ara_hortum_isisi, r.hedef_ara_hortum_isisi_merkez, r.hedef_ara_hortum_isisi_tolerans)]">
                  <span>{{ __('Ara Hortum Isısı') }}</span>
                  <div><b>{{ r.ara_hortum_isisi }}</b> <small>°C</small></div>
                </div>
                <div :class="['ck-enjeksiyon-box', sapmaClass(r.kafa_meme_isisi, r.hedef_kafa_meme_isisi_merkez, r.hedef_kafa_meme_isisi_tolerans)]">
                  <span>{{ __('Kafa (Meme) Isısı') }}</span>
                  <div><b>{{ r.kafa_meme_isisi }}</b> <small>°C</small></div>
                </div>
                <div :class="['ck-enjeksiyon-box', minMaxClass(r.soguk_su_isisi, r.hedef_soguk_su_isisi_min, r.hedef_soguk_su_isisi_maks)]">
                  <span>{{ __('Soğuk Su Isısı') }}</span>
                  <div><b>{{ r.soguk_su_isisi }}</b> <small>°C</small></div>
                </div>
              </div>

              <div class="ck-status-grid" style="margin-top:4px;">
                <div :class="['ck-status-box', r.goz_kontrol ? 'ck-status--success' : 'ck-status--danger']">
                  {{ __('Göz Kontrol') }} {{ r.goz_kontrol ? '✓' : '✕' }}
                </div>
              </div>

              <div
                v-if="r.olcum_tarihi || r.operator"
                class="ck-muted"
                style="border:1px dashed rgba(0,0,0,.12); border-radius:12px; padding:8px 10px;"
              >
                <div v-if="r.olcum_tarihi">{{ __('Tarih') }}: {{ fmtDt(r.olcum_tarihi) }}</div>
                <div v-if="r.operator">{{ __('Giren') }}: {{ getOperatorName(r) }}</div>
              </div>

              <div v-if="props.canEditData" style="display:flex; justify-content:flex-end;">
                <button class="ck-btn ck-btn--ghost" style="padding:8px 10px; width:100%;" @click="actions(r)">
                  {{ __('İşlemler') }} ▾
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </template>

  <!-- CASE 2: Standart Kalite (Alt operasyon bazlı olmayan kartlar) -->
  <template v-else>
    <div v-if="(props.rows||[]).length===0" class="ck-muted" style="margin-top: 14px;padding: 0px 6px;">
      {{ __('Enjeksiyon ölçüm kaydı yok.') }}
    </div>

    <div v-else class="ck-mini-list" style="margin-top:8px;">
      <div v-for="(r, i) in props.rows" :key="r.name || i" class="ck-mini-item">
        <div style="display:flex; flex-direction:column; gap:8px;">
          <div class="ck-enjeksiyon-header-info">
            <div class="ck-header-row">
              <span class="ck-label">{{ __("Periyot") }}:</span>
              <span class="ck-val">{{ r.kontrol_periyodu ? __(r.kontrol_periyodu) : '-' }}</span>
            </div>
            <div class="ck-header-row">
              <span class="ck-label">{{ __("Kalıp No") }}:</span>
              <span class="ck-val">{{ r.kalip_no || '-' }}</span>
            </div>
            <div class="ck-header-row">
              <span class="ck-label">{{ __("Hammadde") }}:</span>
              <span class="ck-val">{{ r.hammadde_no || '-' }}</span>
            </div>
          </div>

          <div class="ck-enjeksiyon-grid">
            <div :class="['ck-enjeksiyon-box', sapmaClass(r.hammadde_kazan_isisi, r.hedef_hammadde_kazan_isisi_merkez, r.hedef_hammadde_kazan_isisi_tolerans)]">
              <span>{{ __('Hammadde Kazan Isısı') }}</span>
              <div><b>{{ r.hammadde_kazan_isisi }}</b> <small>°C</small></div>
              <span v-if="r.hedef_hammadde_kazan_isisi_merkez > 0" class="ck-target-val">{{ __('Hedef') }}: {{ r.hedef_hammadde_kazan_isisi_merkez }}±{{ r.hedef_hammadde_kazan_isisi_tolerans }}</span>
            </div>
            <div :class="['ck-enjeksiyon-box', sapmaClass(r.ara_hortum_isisi, r.hedef_ara_hortum_isisi_merkez, r.hedef_ara_hortum_isisi_tolerans)]">
              <span>{{ __('Ara Hortum Isısı') }}</span>
              <div><b>{{ r.ara_hortum_isisi }}</b> <small>°C</small></div>
              <span v-if="r.hedef_ara_hortum_isisi_merkez > 0" class="ck-target-val">{{ __('Hedef') }}: {{ r.hedef_ara_hortum_isisi_merkez }}±{{ r.hedef_ara_hortum_isisi_tolerans }}</span>
            </div>
            <div :class="['ck-enjeksiyon-box', sapmaClass(r.kafa_meme_isisi, r.hedef_kafa_meme_isisi_merkez, r.hedef_kafa_meme_isisi_tolerans)]">
              <span>{{ __('Kafa (Meme) Isısı') }}</span>
              <div><b>{{ r.kafa_meme_isisi }}</b> <small>°C</small></div>
              <span v-if="r.hedef_kafa_meme_isisi_merkez > 0" class="ck-target-val">{{ __('Hedef') }}: {{ r.hedef_kafa_meme_isisi_merkez }}±{{ r.hedef_kafa_meme_isisi_tolerans }}</span>
            </div>
            <div :class="['ck-enjeksiyon-box', minMaxClass(r.soguk_su_isisi, r.hedef_soguk_su_isisi_min, r.hedef_soguk_su_isisi_maks)]">
              <span>{{ __('Soğuk Su Isısı') }}</span>
              <div><b>{{ r.soguk_su_isisi }}</b> <small>°C</small></div>
              <span v-if="r.hedef_soguk_su_isisi_min > 0 || r.hedef_soguk_su_isisi_maks > 0" class="ck-target-val">{{ __('Hedef') }}: {{ r.hedef_soguk_su_isisi_min||'' }}-{{ r.hedef_soguk_su_isisi_maks||'' }}</span>
            </div>
            <div :class="['ck-enjeksiyon-box', minMaxClass(r.motor_devir, r.hedef_motor_devir_min, r.hedef_motor_devir_maks)]">
              <span>{{ __('Motor Devir') }}</span>
              <div><b>{{ r.motor_devir }}</b></div>
              <span v-if="r.hedef_motor_devir_min > 0 || r.hedef_motor_devir_maks > 0" class="ck-target-val">{{ __('Hedef') }}: {{ r.hedef_motor_devir_min||'' }}-{{ r.hedef_motor_devir_maks||'' }}</span>
            </div>
            <div :class="['ck-enjeksiyon-box', minMaxClass(r.hammadde_enjeksiyon_zamani, r.hedef_enjeksiyon_zamani_min, r.hedef_enjeksiyon_zamani_maks)]">
              <span>{{ __('Enjeksiyon Zamanı') }}</span>
              <div><b>{{ r.hammadde_enjeksiyon_zamani }}</b> <small>sn</small></div>
              <span v-if="r.hedef_enjeksiyon_zamani_min > 0 || r.hedef_enjeksiyon_zamani_maks > 0" class="ck-target-val">{{ __('Hedef') }}: {{ r.hedef_enjeksiyon_zamani_min||'' }}-{{ r.hedef_enjeksiyon_zamani_maks||'' }}</span>
            </div>
            <div :class="['ck-enjeksiyon-box', minMaxClass(r.sogutma_zamani, r.hedef_sogutma_zamani_min, r.hedef_sogutma_zamani_maks)]">
              <span>{{ __('Soğutma Zamanı') }}</span>
              <div><b>{{ r.sogutma_zamani }}</b> <small>sn</small></div>
              <span v-if="r.hedef_sogutma_zamani_min > 0 || r.hedef_sogutma_zamani_maks > 0" class="ck-target-val">{{ __('Hedef') }}: {{ r.hedef_sogutma_zamani_min||'' }}-{{ r.hedef_sogutma_zamani_maks||'' }}</span>
            </div>
            <div :class="['ck-enjeksiyon-box', minMaxClass(r.cekme_kuvveti_olculen, r.hedef_cekme_kuvveti_min, 0)]">
              <span>{{ __('Çekme Kuvveti') }}</span>
              <div><b>{{ r.cekme_kuvveti_olculen }}</b> <small>N</small></div>
              <span v-if="r.hedef_cekme_kuvveti_min > 0" class="ck-target-val">{{ __('Min') }}: {{ r.hedef_cekme_kuvveti_min }}</span>
            </div>
          </div>

          <div class="ck-status-grid" style="margin-top:4px;">
            <div :class="['ck-status-box', r.goz_kontrol ? 'ck-status--success' : 'ck-status--danger']">
              {{ __('Göz Kontrol') }} {{ r.goz_kontrol ? '✓' : '✕' }}
            </div>
          </div>

          <div
            v-if="r.olcum_tarihi || r.operator"
            class="ck-muted"
            style="border:1px dashed rgba(0,0,0,.12); border-radius:12px; padding:8px 10px;"
          >
            <div v-if="r.olcum_tarihi">{{ __('Tarih') }}: {{ fmtDt(r.olcum_tarihi) }}</div>
            <div v-if="r.operator">{{ __('Giren') }}: {{ getOperatorName(r) }}</div>
          </div>

          <div style="display:flex; justify-content:flex-end;">
            <button class="ck-btn ck-btn--ghost" style="padding:8px 10px; width:100%;" @click="actions(r)">
              {{ __('İşlemler') }} ▾
            </button>
          </div>
        </div>
      </div>
    </div>
  </template>
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

/* Krimp ile birebir aynı akordiyon ve rozet stilleri */
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
.ck-badge--partial {
    background: rgba(124, 58, 237, 0.15);
    color: #7c3aed;
    border: 1px solid rgba(124, 58, 237, 0.3);
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
.ck-satir-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    padding-right: 12px;
    border-right: 2px solid var(--ck-glass-border-soft);
    margin-right: 4px;
    font-size: 22px;
    font-weight: 900;
    color: var(--ck-text);
    opacity: 0.9;
    flex-shrink: 0;
}
.ck-mold-pill {
    font-size: 11px;
    font-weight: 700;
    background: var(--ck-glass-bg);
    border: 1px solid var(--ck-glass-border-soft);
    padding: 1px 6px;
    border-radius: 6px;
    color: var(--ck-text);
    display: inline-flex;
    align-items: center;
    gap: 4px;
}
.ck-accordion-header {
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.ck-accordion-header:focus-visible {
    outline: 2px solid var(--ck-primary, #2563eb);
    outline-offset: -2px;
}
.ck-accordion-toggle-btn {
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: inherit;
}
@media (max-width: 480px) {
    .ck-accordion-header {
        flex-direction: column !important;
        align-items: stretch !important;
        position: relative !important;
        padding-right: 28px !important;
        gap: 8px !important;
    }
    .ck-accordion-toggle-btn {
        position: absolute !important;
        right: 0 !important;
        top: 0 !important;
        padding: 6px !important;
    }
    .ck-accordion-right {
        width: 100% !important;
        display: flex !important;
        flex-wrap: wrap !important;
        justify-content: flex-start !important;
        align-items: center !important;
        gap: 6px !important;
        margin-top: 4px !important;
        border-top: 1px dashed var(--ck-glass-border-soft) !important;
        padding-top: 8px !important;
    }
    .ck-accordion-right .ck-btn {
        flex: 1 1 calc(50% - 6px) !important;
        text-align: center !important;
        justify-content: center !important;
    }
    .ck-accordion-right .ck-badge {
        flex: 1 1 100% !important;
        text-align: center !important;
        box-sizing: border-box !important;
        margin-right: 0 !important;
    }
}
@media (max-width: 340px) {
    .ck-enjeksiyon-grid {
        gap: 6px;
    }
    .ck-enjeksiyon-box {
        padding: 4px 6px;
        min-width: 0;
    }
    .ck-enjeksiyon-box span {
        font-size: 9px;
        word-break: break-word;
    }
    .ck-enjeksiyon-box b {
        font-size: 13px;
    }
    .ck-target-val {
        font-size: 8.5px !important;
    }
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
</style>

