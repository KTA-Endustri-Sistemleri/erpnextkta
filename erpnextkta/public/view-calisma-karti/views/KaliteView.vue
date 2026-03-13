<script setup lang="ts">
import { onMounted, computed, ref, watch } from "vue";
import QcToggle from "../components/QcToggle.vue";
import IdcSection from "../components/IdcSection.vue";
import BarkodSection from "../components/BarkodSection.vue";
import { idcOlcumFields, barkodKayitFields } from "../composables/prompts";

function openQualityInspection(name: string) {
  frappe.set_route("Form", "Quality Inspection", name);
}

const props = defineProps<{
  doc: any;

  qcLabel: string;
  qcOptions: string[];
  qcFormValue: string;
  canEditQC: boolean;
  qcSaving: boolean;
  onSetQC: (next: string) => void;

  // IDC CRUD
  onAddIdc: (payload: any) => Promise<void>;
  onUpdateIdc: (payload: any) => Promise<void>;
  onDeleteIdc: (rowname: string) => Promise<void>;

  // Barkod CRUD
  onAddBarkod: (payload: any) => Promise<void>;
  onUpdateBarkod: (payload: any) => Promise<void>;
  onDeleteBarkod: (rowname: string) => Promise<void>;
}>();

function addIdc() {
  frappe.prompt(
    idcOlcumFields(props.doc.name),
    async (v: any) => {
      await props.onAddIdc({
        item_code: v.item_code,
        yukseklik_mm: v.yukseklik_mm,
        cekme_n: v.cekme_n,
      });
      frappe.show_alert({ message: "IDC ölçümü eklendi", indicator: "green" });
    },
    "IDC Ölçümü Ekle",
    "Kaydet"
  );
}

function editIdc(row: any) {
  if (!row?.name) return frappe.msgprint("IDC satır kimliği (row name) bulunamadı.");
  frappe.prompt(
    idcOlcumFields(props.doc.name, row),
    async (v: any) => {
      await props.onUpdateIdc({
        rowname: row.name,
        item_code: v.item_code,
        yukseklik_mm: v.yukseklik_mm,
        cekme_n: v.cekme_n,
      });
      frappe.show_alert({ message: "IDC ölçümü güncellendi", indicator: "green" });
    },
    "IDC Ölçümü Düzenle",
    "Kaydet"
  );
}

function deleteIdc(row: any) {
  if (!row?.name) return frappe.msgprint("IDC satır kimliği (row name) bulunamadı.");
  frappe.confirm("Bu IDC ölçüm satırı silinecek. Emin misiniz?", async () => {
    await props.onDeleteIdc(row.name);
    frappe.show_alert({ message: "IDC ölçümü silindi", indicator: "green" });
  });
}

function addBarkod() {
  frappe.prompt(
    barkodKayitFields(),
    async (v: any) => {
      await props.onAddBarkod({ barcode: v.barcode });
      frappe.show_alert({ message: "Barkod kaydı eklendi", indicator: "green" });
    },
    "Barkod Kaydı Ekle",
    "Kaydet"
  );
}

function editBarkod(row: any) {
  if (!row?.name) return frappe.msgprint("Barkod satır kimliği (row name) bulunamadı.");
  frappe.prompt(
    barkodKayitFields(row),
    async (v: any) => {
      await props.onUpdateBarkod({ rowname: row.name, barcode: v.barcode });
      frappe.show_alert({ message: "Barkod kaydı güncellendi", indicator: "green" });
    },
    "Barkod Kaydı Düzenle",
    "Kaydet"
  );
}

function deleteBarkod(row: any) {
  if (!row?.name) return frappe.msgprint("Barkod satır kimliği (row name) bulunamadı.");
  frappe.confirm("Bu barkod satırı silinecek. Emin misiniz?", async () => {
    await props.onDeleteBarkod(row.name);
    frappe.show_alert({ message: "Barkod kaydı silindi", indicator: "green" });
  });
}

// (Opsiyonel) burada bir şey yapmayacağız; sadece Vue shim uyumu için bırakıyorum
onMounted(() => {});
</script>

<template>
  <div class="ck-card">
    <QcToggle
      :qcLabel="props.qcLabel"
      :qcOptions="props.qcOptions"
      :qcFormValue="props.qcFormValue"
      :canEditQC="props.canEditQC"
      :qcSaving="props.qcSaving"
      :onSetQC="props.onSetQC"
    />

    <!-- Bağlı Kalite Belgesi linki: QcToggle hemen altında -->
    <div v-if="props.doc.quality_inspection" class="ck-qi-link">
      <div class="ck-qi-link__info">
        <span class="ck-qi-link__label">Kalite Belgesi</span>
        <b class="ck-qi-link__name">{{ props.doc.quality_inspection }}</b>
      </div>
      <button
        class="ck-btn ck-btn--ghost ck-qi-link__btn"
        @click="openQualityInspection(props.doc.quality_inspection)"
      >
        Görüntüle ↗
      </button>
    </div>

    <div style="height: 1px;background: var(--fg-hover-color);margin-top: 10px;"></div>

    <IdcSection
      :rows="props.doc.idc_olcumleri || []"
      :canEditQC="props.canEditQC"
      :onAdd="addIdc"
      :onEdit="editIdc"
      :onDelete="deleteIdc"
    />

    <div style="height: 1px;background: var(--fg-hover-color);margin-top: 10px;"></div>

    <BarkodSection
      :rows="props.doc.barkod_kayitlari || []"
      :canEditQC="props.canEditQC"
      :onAdd="addBarkod"
      :onEdit="editBarkod"
      :onDelete="deleteBarkod"
    />

  </div>
</template>

<style scoped>
.ck-qi-link {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin: 8px 6px 0;
  padding: 10px 12px;
  background: var(--ck-info-bg);
  border: 1px solid color-mix(in srgb, var(--ck-info) 25%, transparent);
  border-radius: 10px;
}

.ck-qi-link__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ck-qi-link__label {
  font-size: 11px;
  color: var(--ck-info);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.ck-qi-link__name {
  font-size: 14px;
  color: var(--ck-info);
}

.ck-qi-link__btn {
  padding: 7px 12px;
  font-size: 12px;
  white-space: nowrap;
}
</style>