<script setup lang="ts">
import { computed, ref, onMounted } from "vue";
import { altOperasyonFieldsMulti, altOperasyonFieldsSingle } from "../composables/prompts";
import { isQcApproved, isQcRejected, extractAltOpCode, sortAltOperasyonRows } from "../utils/kalite_ui";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  doc: any;
  canEditData: boolean;
  onAdd: (payload: any) => Promise<void>;
  onUpdate: (payload: any) => Promise<void>;
  onDelete: (rowname: string) => Promise<void>;
}>();

function isQCLocked(h: any): boolean {
  if (!props.doc.alt_operasyon_bazli_kalite) return false;
  return !!(h.quality_inspection || "").trim();
}

function isApprovedEnjeksiyon(h: any): boolean {
  return Boolean(
    props.doc.has_enjeksiyon &&
    isQCLocked(h) &&
    !props.doc.is_qc_user &&
    isQcApproved(h.quality_inspection_status)
  );
}

function getIsTuketimHesaplanir(h: any) {
  const op = altOpOptions.value.find((o: any) => o.value === h.alt_operasyon || o.label === h.alt_operasyon);
  return op && op.is_tuketim_hesaplanir !== undefined ? op.is_tuketim_hesaplanir : 1;
}

function formatSingleQty(h: any) {
  if (props.doc.has_enjeksiyon) {
    const islem = (h.islem_adedi_1 !== undefined && h.islem_adedi_1 !== null && h.islem_adedi_1 > 0) ? h.islem_adedi_1 : (h.adet || 0);
    const uom = (h.uom || "").toLowerCase();
    if (uom && uom !== "adet" && h.adet) {
      return `${islem} ${__("Adet")} (${h.adet} ${h.uom})`;
    }
    return `${islem} ${__("Adet")}`;
  }
  const qty = getIsTuketimHesaplanir(h) ? (h.adet || 0) : (h.islem_adedi_1 !== undefined ? h.islem_adedi_1 : (h.adet || 0));
  const uom = getIsTuketimHesaplanir(h) ? (h.uom || "") : __("Adet");
  return `${qty} ${uom}`.trim();
}

// Sort rows by satir_no (natural), then kalip_no (natural), then sequence, then idx
const sortedRows = computed(() => {
  return sortAltOperasyonRows(props.doc?.alt_operasyon_kayitlari ?? []);
});

const altOpOptions = ref<any[]>([]);
const ekranTipi = ref<string>("Tekli Hammadde");

async function fetchAltOpOptions() {
  const r = await frappe.call({
    method: "erpnextkta.kta_calisma_karti.api.get_alt_operasyon_options",
    args: { parent_operation: props.doc.operasyon },
  });
  if (r.message && !Array.isArray(r.message)) {
    altOpOptions.value = r.message.options || [];
    ekranTipi.value = r.message.ekran_tipi || "Tekli Hammadde";
  } else {
    // Fallback for older api response format if needed
    altOpOptions.value = r.message || [];
    ekranTipi.value = "Tekli Hammadde";
  }
}

onMounted(() => {
  fetchAltOpOptions();
});

function onAltOperasyonEkle() {
  let d: any;
  const fieldsFn = ekranTipi.value === "Çoklu Hammadde" ? altOperasyonFieldsMulti : altOperasyonFieldsSingle;
  const defaults = {
    alt_operasyon_bazli_kalite: props.doc.alt_operasyon_bazli_kalite,
    has_enjeksiyon: props.doc.has_enjeksiyon,
    has_krimp: props.doc.has_krimp,
  };
  const fields = fieldsFn(props.doc.operasyon, props.doc.name, defaults, () => d?.get_value("alt_operasyon"), altOpOptions.value);
  d = new frappe.ui.Dialog({
    title: __("Alt İşlem Ekle"),
    fields: fields,
    primary_action_label: __("Kaydet"),
    primary_action: async (v: any) => {
      if (ekranTipi.value === "Tekli Hammadde") {
        const uom = (v.uom || "").toLowerCase();
        const selectedOp = altOpOptions.value.find((o: any) => o.value === v.alt_operasyon || o.label === v.alt_operasyon);
        const isTuketim = selectedOp && selectedOp.is_tuketim_hesaplanir !== undefined ? selectedOp.is_tuketim_hesaplanir : 1;

        if (isTuketim && (uom === "metre" || uom === "m" || uom === "meter")) {
          if (!v.boyut_1_mm || v.boyut_1_mm <= 0) {
            frappe.msgprint(__("Birim 'Metre' seçildiğinde tüketimin hesaplanabilmesi için 'Parça Boyu (mm)' alanı doldurulmalıdır."));
            return;
          }
        }
      }

      if (props.doc.has_enjeksiyon && v.kalip_no) {
        const kalip = String(v.kalip_no).trim().toLowerCase();
        const mat = String(v.hammadde || "").trim().toLowerCase();
        const existing = (props.doc.alt_operasyon_kayitlari || []).find((r: any) => {
          const rKalip = String(r.kalip_no || "").trim().toLowerCase();
          const rMat = String(r.hammadde || "").trim().toLowerCase();
          return rKalip === kalip && rMat === mat && !isQcRejected(r.quality_inspection_status);
        });
        if (existing) {
          frappe.msgprint({
            title: __("Mükerrer Alt İşlem"),
            message: __("Bu çalışma kartında '{0}' kalıbı ve '{1}' hammaddesi için zaten aktif bir alt işlem kaydı bulunmaktadır.", [v.kalip_no, v.hammadde || "-"]),
            indicator: "orange"
          });
          return;
        }
      }

      let islem_1 = typeof v.islem_adedi_1 !== 'undefined' ? v.islem_adedi_1 : (v.adet || 1);
      let islem_3 = v.islem_adedi_3 || 1;
      const cleanAltOp = extractAltOpCode(v.alt_operasyon);

      await props.onAdd({
        alt_operasyon: cleanAltOp,
        satir_no: v.satir_no || "",
        kalip_no: v.kalip_no || "",
        hammadde: v.hammadde || null,
        boyut_1_mm: v.boyut_1_mm || 0,
        islem_adedi_1: islem_1, // fallback to adet for single mode handled above
        hammadde_2: v.hammadde_2 || null,
        boyut_2_mm: v.boyut_2_mm || 0,
        islem_adedi_2: v.islem_adedi_2 || 1,
        hammadde_3: v.hammadde_3 || null,
        boyut_3_mm: v.boyut_3_mm || 0,
        islem_adedi_3: islem_3,
        note: v.note || null,
        uom: props.doc.has_enjeksiyon ? "Adet" : (v.uom || null), // For injection always use Adet
      });
      d.hide();
      frappe.show_alert({ message: __("Alt İşlem eklendi"), indicator: "green" });
    }
  });
  d.show();
}

function onAltOperasyonDuzenle(h: any) {
  if (!h?.name) {
    frappe.msgprint(__("Satır kimliği (row name) bulunamadı."));
    return;
  }

  const isEnjApproved = isApprovedEnjeksiyon(h);
  let d: any;
  const fieldsFn = ekranTipi.value === "Çoklu Hammadde" ? altOperasyonFieldsMulti : altOperasyonFieldsSingle;
  const defaults = {
    ...h,
    alt_operasyon_bazli_kalite: props.doc.alt_operasyon_bazli_kalite,
    has_enjeksiyon: props.doc.has_enjeksiyon,
    has_krimp: props.doc.has_krimp,
    is_qc_locked_enjeksiyon: isEnjApproved,
  };
  const fields = fieldsFn(props.doc.operasyon, props.doc.name, defaults, () => d?.get_value("alt_operasyon"), altOpOptions.value);
  d = new frappe.ui.Dialog({
    title: isEnjApproved ? __("İşlem Adedi Güncelle") : __("Alt İşlem Düzenle"),
    fields: fields,
    primary_action_label: __("Kaydet"),
    primary_action: async (v: any) => {
      const rawAltOp = isEnjApproved ? h.alt_operasyon : (v.alt_operasyon || h.alt_operasyon);
      const finalAltOp = extractAltOpCode(rawAltOp);
      const finalKalip = v.kalip_no || h.kalip_no || "";
      const finalHammadde = v.hammadde || h.hammadde || null;
      const finalSatir = v.satir_no || h.satir_no || "";
      const finalUom = v.uom || h.uom || null;

      if (ekranTipi.value === "Tekli Hammadde") {
        const uom = (finalUom || "").toLowerCase();
        const selectedOp = altOpOptions.value.find((o: any) => o.value === finalAltOp || o.label === finalAltOp || o.value === rawAltOp || o.label === rawAltOp);
        const isTuketim = selectedOp && selectedOp.is_tuketim_hesaplanir !== undefined ? selectedOp.is_tuketim_hesaplanir : 1;

        if (isTuketim && (uom === "metre" || uom === "m" || uom === "meter")) {
          if (!v.boyut_1_mm || v.boyut_1_mm <= 0) {
            frappe.msgprint(__("Birim 'Metre' seçildiğinde tüketimin hesaplanabilmesi için 'Parça Boyu (mm)' alanı doldurulmalıdır."));
            return;
          }
        }
      }

      if (props.doc.has_enjeksiyon && finalKalip) {
        const kalip = String(finalKalip).trim().toLowerCase();
        const mat = String(finalHammadde || "").trim().toLowerCase();
        const existing = (props.doc.alt_operasyon_kayitlari || []).find((r: any) => {
          if (r.name === h.name) return false;
          const rKalip = String(r.kalip_no || "").trim().toLowerCase();
          const rMat = String(r.hammadde || "").trim().toLowerCase();
          return rKalip === kalip && rMat === mat && !isQcRejected(r.quality_inspection_status);
        });
        if (existing) {
          frappe.msgprint({
            title: __("Mükerrer Alt İşlem"),
            message: __("Bu çalışma kartında '{0}' kalıbı ve '{1}' hammaddesi için zaten aktif bir alt işlem kaydı bulunmaktadır.", [finalKalip, finalHammadde || "-"]),
            indicator: "orange"
          });
          return;
        }
      }

      let islem_1 = typeof v.islem_adedi_1 !== 'undefined' ? v.islem_adedi_1 : (v.adet || 1);
      let islem_3 = v.islem_adedi_3 || 1;

      await props.onUpdate({
        row_id: h.name,
        alt_operasyon: finalAltOp,
        satir_no: finalSatir,
        kalip_no: finalKalip,
        hammadde: finalHammadde,
        boyut_1_mm: v.boyut_1_mm || h.boyut_1_mm || 0,
        islem_adedi_1: islem_1,
        hammadde_2: v.hammadde_2 || null,
        boyut_2_mm: v.boyut_2_mm || 0,
        islem_adedi_2: v.islem_adedi_2 || 1,
        hammadde_3: v.hammadde_3 || null,
        boyut_3_mm: v.boyut_3_mm || 0,
        islem_adedi_3: islem_3,
        note: v.note || null,
        uom: props.doc.has_enjeksiyon ? "Adet" : (finalUom || null),
      });
      d.hide();
      frappe.show_alert({ message: __("Alt İşlem güncellendi"), indicator: "green" });
    }
  });
  d.show();
}

function onAltOperasyonSil(h: any) {
  if (!h?.name) {
    frappe.msgprint(__("Satır kimliği (row name) bulunamadı."));
    return;
  }

  const locked = isQCLocked(h);
  const isQcUser = props.doc.is_qc_user;

  let msg = __("Bu işlem satırı silinecek. Emin misiniz?");
  if (locked && isQcUser) {
    msg = __("Bu kayda bağlı kalite kontrol belgesi de iptal edilecektir. Devam etmek istiyor musunuz?");
  }

  frappe.confirm(msg, async () => {
    await props.onDelete(h.name);
    frappe.show_alert({ message: __("Alt İşlem silindi"), indicator: "green" });
  });
}
</script>

<template>
  <div class="ck-card">
    <div class="ck-view-action" v-if="props.canEditData">
      <button class="ck-btn ck-btn--ghost ck-btn--wide" @click="onAltOperasyonEkle">{{ __("Alt İşlem Ekle") }}</button>
    </div>

    <div v-if="sortedRows.length === 0" class="ck-empty-state">{{ __("Kayıt yok.") }}</div>

    <div v-else class="ck-mini-list">
      <div v-for="(h, i) in sortedRows" :key="h.name || i" class="ck-mini-item">
        <div style="display: flex; gap: 12px; align-items: stretch; flex: 1; min-width: 0;">
            <div v-if="h.satir_no" class="ck-satir-badge">
                <span>{{ h.satir_no }}</span>
            </div>
            <div class="ck-mini-content">
                <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                    <b class="ck-mini-title">{{ __(h.alt_operasyon_title || h.alt_operasyon) }}</b>
                    <span v-if="h.kalip_no" class="ck-mold-pill">🏷️ {{ h.kalip_no }}</span>
                </div>

            <template v-if="ekranTipi === 'Çoklu Hammadde'">
              <div class="ck-muted ck-mini-sub" v-if="h.hammadde_2 || h.boyut_2_mm || h.hammadde_3">
                <b>{{ __("T1") }}:</b> 
                <template v-if="h.hammadde_2">
                    {{ h.hammadde_2 }}
                    <template v-if="h.boyut_2_mm > 0"> ({{ __("Sıyırma") }}: {{ h.boyut_2_mm }}mm)</template>
                    <span v-if="h.uom_2"> [{{ h.adet_2 || 0 }} {{ h.uom_2 }}]</span>
                </template>
                <template v-else>
                    <template v-if="h.boyut_2_mm > 0">{{ __("Sıyırma") }}: {{ h.boyut_2_mm }}mm</template>
                    <template v-else>{{ __("Sıyırmasız") }}</template>
                </template>
              </div>

              <div class="ck-muted ck-mini-sub" v-if="h.hammadde || h.boyut_1_mm">
                <b>{{ __("C") }}:</b> 
                <template v-if="h.hammadde">{{ h.hammadde }}</template>
                <template v-if="h.hammadde && h.boyut_1_mm"> ({{ __("Boy") }}: {{ h.boyut_1_mm }}mm)</template>
                <template v-if="!h.hammadde && h.boyut_1_mm">{{ __("Boy") }}: {{ h.boyut_1_mm }}mm</template>
                <span v-if="h.uom"> [{{ h.adet || 0 }} {{ h.uom }}]</span>
              </div>
              
              <div class="ck-muted ck-mini-sub" v-if="h.hammadde_3 || h.boyut_3_mm || h.hammadde_2">
                <b>{{ __("T2") }}:</b> 
                <template v-if="h.hammadde_3">
                    {{ h.hammadde_3 }}
                    <template v-if="h.boyut_3_mm > 0"> ({{ __("Sıyırma") }}: {{ h.boyut_3_mm }}mm)</template>
                    <span v-if="h.uom_3"> [{{ h.adet_3 || 0 }} {{ h.uom_3 }}]</span>
                </template>
                <template v-else>
                    <template v-if="h.boyut_3_mm > 0">{{ __("Sıyırma") }}: {{ h.boyut_3_mm }}mm</template>
                    <template v-else>{{ __("Sıyırmasız") }}</template>
                </template>
              </div>
            </template>
            <template v-else>
              <div class="ck-muted ck-mini-sub" v-if="h.hammadde">
                {{ h.hammadde }} 
                <template v-if="h.boyut_1_mm">({{ __("Boy") }}: {{ h.boyut_1_mm }}mm) </template>
                [{{ formatSingleQty(h) }}]
              </div>
              <div class="ck-muted ck-mini-sub" v-else-if="h.islem_adedi_1 !== undefined || h.adet || h.uom">
                <template v-if="h.boyut_1_mm">{{ __("Boy") }}: {{ h.boyut_1_mm }}mm </template>
                [{{ formatSingleQty(h) }}]
              </div>
            </template>
            
            <div class="ck-muted ck-mini-sub" v-if="h.note">{{ h.note }}</div>
            </div>
        </div>

        <div class="ck-mini-actions" v-if="props.canEditData">
          <template v-if="!isQCLocked(h) || props.doc.is_qc_user">
            <button class="ck-btn ck-btn--ghost ck-btn-small" @click="onAltOperasyonDuzenle(h)">{{ __("Düzenle") }}</button>
            <button class="ck-btn ck-btn--danger ck-btn-small" @click="onAltOperasyonSil(h)">{{ __("Sil") }}</button>
          </template>
          <template v-else-if="isApprovedEnjeksiyon(h)">
            <button class="ck-btn ck-btn--ghost ck-btn-small" @click="onAltOperasyonDuzenle(h)">{{ __("Düzenle") }}</button>
            <span class="ck-badge ck-badge--success ck-badge--small" style="font-size: 10px; padding: 2px 6px;">
              🔒 {{ __("Kalite Onaylı") }}
            </span>
          </template>
          <template v-else>
            <span v-if="isQcRejected(h.quality_inspection_status)" class="ck-badge ck-badge--danger ck-badge--small" style="font-size: 10px; padding: 2px 6px;">
              🔒 {{ __("Kalite Reddi") }}
            </span>
            <span v-else class="ck-badge ck-badge--success ck-badge--small" style="font-size: 10px; padding: 2px 6px;">
              🔒 {{ __("Kalite Onaylı") }}
            </span>
          </template>
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
@media (max-width: 480px) {
  .ck-mini-item {
    flex-direction: column;
    align-items: stretch;
    padding: 12px 10px;
    gap: 10px;
  }
  .ck-mini-actions {
    width: 100%;
    display: flex;
    gap: 6px;
  }
  .ck-mini-actions > * {
    flex: 1;
    text-align: center;
    justify-content: center;
  }
}
@media (max-width: 340px) {
  .ck-mini-item {
    padding: 10px 8px;
  }
  .ck-btn-small {
    padding: 6px 8px;
    font-size: 12px;
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
  word-break: break-word;
}
.ck-mini-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}
.ck-btn-small {
  padding: 8px 14px;
  font-size: 13px;
  border-radius: 8px;
  font-weight: 700;
}
</style>

