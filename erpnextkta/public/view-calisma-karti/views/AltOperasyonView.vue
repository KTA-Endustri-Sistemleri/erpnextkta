<script setup lang="ts">
import { computed, ref, onMounted } from "vue";
import { altOperasyonFields } from "../composables/prompts";

const props = defineProps<{
  doc: any;
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

async function fetchAltOpOptions() {
  const r = await frappe.call({
    method: "erpnextkta.kta_calisma_karti.api.get_alt_operasyon_options",
    args: { parent_operation: props.doc.operasyon },
  });
  altOpOptions.value = r.message || [];
}

onMounted(() => {
  fetchAltOpOptions();
});

function onAltOperasyonEkle() {
  let d: any;
  const fields = altOperasyonFields(props.doc.operasyon, props.doc.name, {}, () => d?.get_value("alt_operasyon"), altOpOptions.value);
  d = frappe.prompt(
    fields,
    async (v: any) => {
      await props.onAdd({
        alt_operasyon: v.alt_operasyon,
        hammadde: v.hammadde || null,
        adet: v.adet || 0,
        uom: v.uom || null,
        note: v.note || null,
      });
      frappe.show_alert({ message: "Alt İşlem eklendi", indicator: "green" });
    },
    "Alt İşlem Ekle",
    "Kaydet"
  );
}

function onAltOperasyonDuzenle(h: any) {
  if (!h?.name) {
    frappe.msgprint("Satır kimliği (row name) bulunamadı.");
    return;
  }

  let d: any;
  const fields = altOperasyonFields(props.doc.operasyon, props.doc.name, h, () => d?.get_value("alt_operasyon"), altOpOptions.value);
  d = frappe.prompt(
    fields,
    async (v: any) => {
      await props.onUpdate({
        row_id: h.name,
        alt_operasyon: v.alt_operasyon,
        hammadde: v.hammadde || null,
        adet: v.adet || 0,
        uom: v.uom || null,
        note: v.note || null,
      });
      frappe.show_alert({ message: "Alt İşlem güncellendi", indicator: "green" });
    },
    "Alt İşlem Düzenle",
    "Kaydet"
  );
}

function onAltOperasyonSil(h: any) {
  if (!h?.name) {
    frappe.msgprint("Satır kimliği (row name) bulunamadı.");
    return;
  }

  frappe.confirm("Bu işlem satırı silinecek. Emin misiniz?", async () => {
    await props.onDelete(h.name);
    frappe.show_alert({ message: "Alt İşlem silindi", indicator: "green" });
  });
}
</script>

<template>
  <div class="ck-card">
    <div style="display: flex;gap: 8px;padding: 0px 10px 10px;" v-if="doc.durum !== 'Hazır' && doc.durum !== 'Bitmiş'">
      <button class="ck-btn ck-btn--ghost ck-btn--wide" @click="onAltOperasyonEkle">Alt İşlem Ekle</button>
    </div>

    <div v-if="sortedRows.length === 0" class="ck-muted" style="padding: 0px 10px;padding-top: 0px;">Kayıt yok.</div>

    <div v-else class="ck-mini-list">
      <div v-for="(h, i) in sortedRows" :key="h.name || i" class="ck-mini-item">
        <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start;">
          <div style="min-width:0;">
            <b style="display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              {{ h.alt_operasyon_title || h.alt_operasyon }}
            </b>
            <div class="ck-muted" v-if="h.hammadde">{{ h.hammadde }} ({{ h.adet || 0 }} {{ h.uom || '' }})</div>
            <div class="ck-muted" v-else-if="h.adet || h.uom">{{ h.adet || 0 }} {{ h.uom || '' }}</div>
            <div class="ck-muted" v-if="h.note">{{ h.note }}</div>
          </div>

          <div style="display:flex; gap:6px; flex-shrink:0;">
            <button class="ck-btn ck-btn--ghost" style="padding:8px 10px;" @click="onAltOperasyonDuzenle(h)">
              Düzenle
            </button>
            <button class="ck-btn ck-btn--danger" style="padding:8px 10px;" @click="onAltOperasyonSil(h)">
              Sil
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
