<script setup lang="ts">
import { computed, ref, onMounted } from "vue";
import { altOperasyonFields } from "../composables/prompts";

declare const __: any;

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
            <div class="ck-muted ck-mini-sub" v-if="h.hammadde">{{ h.hammadde }} ({{ h.adet || 0 }} {{ h.uom || '' }})</div>
            <div class="ck-muted ck-mini-sub" v-else-if="h.adet || h.uom">{{ h.adet || 0 }} {{ h.uom || '' }}</div>
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
