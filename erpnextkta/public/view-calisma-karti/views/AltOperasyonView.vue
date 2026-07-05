<script setup lang="ts">
import { computed, ref, onMounted } from "vue";
import { altOperasyonFieldsMulti, altOperasyonFieldsSingle } from "../composables/prompts";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  doc: any;
  canEditData: boolean;
  onAdd: (payload: any) => Promise<void>;
  onUpdate: (payload: any) => Promise<void>;
  onDelete: (rowname: string) => Promise<void>;
}>();

// Sort rows by sequence from master doctype (populated by backend), then by idx
const sortedRows = computed(() => {
  const rows: any[] = props.doc?.alt_operasyon_kayitlari ?? [];
  return [...rows].sort((a, b) => {
    const seqDiff = (a.alt_operasyon_sequence ?? 0) - (b.alt_operasyon_sequence ?? 0);
    if (seqDiff !== 0) return seqDiff;
    return (a.idx ?? 0) - (b.idx ?? 0);
  });
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
  const fields = fieldsFn(props.doc.operasyon, props.doc.name, {}, () => d?.get_value("alt_operasyon"), altOpOptions.value);
  d = frappe.prompt(
    fields,
    async (v: any) => {
      let islem_1 = typeof v.islem_adedi_1 !== 'undefined' ? v.islem_adedi_1 : (v.adet || 1);
      let islem_3 = v.islem_adedi_3 || 1;

      await props.onAdd({
        alt_operasyon: v.alt_operasyon,
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
        uom: v.uom || null, // Capture UOM from old mode
      });
      frappe.show_alert({ message: __("Alt İşlem eklendi"), indicator: "green" });
    },
    __("Alt İşlem Ekle"),
    __("Kaydet")
  );
}

function onAltOperasyonDuzenle(h: any) {
  if (!h?.name) {
    frappe.msgprint("Satır kimliği (row name) bulunamadı.");
    return;
  }

  let d: any;
  const fieldsFn = ekranTipi.value === "Çoklu Hammadde" ? altOperasyonFieldsMulti : altOperasyonFieldsSingle;
  const defaults = {
    ...h,
    adet: h.adet || h.islem_adedi_1 // map islem_adedi_1 to adet for single mode edit
  };
  const fields = fieldsFn(props.doc.operasyon, props.doc.name, defaults, () => d?.get_value("alt_operasyon"), altOpOptions.value);
  d = frappe.prompt(
    fields,
    async (v: any) => {
      let islem_1 = typeof v.islem_adedi_1 !== 'undefined' ? v.islem_adedi_1 : (v.adet || 1);
      let islem_3 = v.islem_adedi_3 || 1;

      await props.onUpdate({
        row_id: h.name,
        alt_operasyon: v.alt_operasyon,
        hammadde: v.hammadde || null,
        boyut_1_mm: v.boyut_1_mm || 0,
        islem_adedi_1: islem_1,
        hammadde_2: v.hammadde_2 || null,
        boyut_2_mm: v.boyut_2_mm || 0,
        islem_adedi_2: v.islem_adedi_2 || 1,
        hammadde_3: v.hammadde_3 || null,
        boyut_3_mm: v.boyut_3_mm || 0,
        islem_adedi_3: islem_3,
        note: v.note || null,
        uom: v.uom || null,
      });
      frappe.show_alert({ message: __("Alt İşlem güncellendi"), indicator: "green" });
    },
    __("Alt İşlem Düzenle"),
    __("Kaydet")
  );
}

function onAltOperasyonSil(h: any) {
  if (!h?.name) {
    frappe.msgprint("Satır kimliği (row name) bulunamadı.");
    return;
  }

  frappe.confirm(__("Bu işlem satırı silinecek. Emin misiniz?"), async () => {
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
        <div class="ck-mini-content">
            <b class="ck-mini-title">{{ h.alt_operasyon_title || h.alt_operasyon }}</b>
            
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
                    <template v-else>{{ __("SIYIRMASIZ") }}</template>
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
                    <template v-else>{{ __("SIYIRMASIZ") }}</template>
                </template>
              </div>
            </template>
            <template v-else>
              <div class="ck-muted ck-mini-sub" v-if="h.hammadde">{{ h.hammadde }} ({{ h.adet || 0 }} {{ h.uom || '' }})</div>
              <div class="ck-muted ck-mini-sub" v-else-if="h.adet || h.uom">{{ h.adet || 0 }} {{ h.uom || '' }}</div>
            </template>
            
            <div class="ck-muted ck-mini-sub" v-if="h.note">{{ h.note }}</div>
        </div>

        <div class="ck-mini-actions" v-if="props.canEditData">
          <button class="ck-btn ck-btn--ghost ck-btn-small" @click="onAltOperasyonDuzenle(h)">{{ __("Düzenle") }}</button>
          <button class="ck-btn ck-btn--danger ck-btn-small" @click="onAltOperasyonSil(h)">{{ __("Sil") }}</button>
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
