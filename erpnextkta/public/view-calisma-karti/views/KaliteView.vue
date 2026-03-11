<script setup lang="ts">
import { onMounted, computed, ref, watch } from "vue";
import QcToggle from "../components/QcToggle.vue";
import IdcSection from "../components/IdcSection.vue";
import BarkodSection from "../components/BarkodSection.vue";
import { idcOlcumFields, barkodKayitFields } from "../composables/prompts";

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

// --- Test Masası Doğrulama ---
const requiresBoardDogrulama = ref(false);

watch(() => props.doc?.operasyon, async (op) => {
  if (op) {
    try {
      const resp = await frappe.db.get_value("KTA Calisma Karti Operasyonlari", op, "board_dogrulamasi_gerektirir");
      requiresBoardDogrulama.value = resp.message?.board_dogrulamasi_gerektirir === 1;
    } catch (err) {
      console.error("Board dogrulama kontrol hatasi", err);
      requiresBoardDogrulama.value = false;
    }
  } else {
    requiresBoardDogrulama.value = false;
  }
}, { immediate: true });

const hasDogrulama = computed(() => {
  return !!props.doc?.test_masasi_dogrulama_kaydi;
});

function openDogrulama() {
  if (hasDogrulama.value) {
    frappe.set_route("Form", "Test Masasi Dogrulama Kaydi", props.doc.test_masasi_dogrulama_kaydi);
  } else {
    frappe.msgprint("Kayıtlı bir doğrulama bulunamadı.");
  }
}

function createDogrulama() {
  frappe.new_doc("Test Masasi Dogrulama Kaydi", {
    is_karti: props.doc.is_karti,
    urun_no: props.doc.urun_no,
    urun_siparis_no: props.doc.sales_order,
    calisma_karti_ref: props.doc.name
  });
}
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

    <div style="height: 1px;background: var(--fg-hover-color);margin-top: 10px;"></div>
    
    <!-- Test Masası Doğrulama -->
    <div v-if="requiresBoardDogrulama" style="display: flex; flex-direction: column;">
      <div class="ck-qc-header">
        <b>Test Masası Doğrulama</b>
        <button v-if="hasDogrulama" class="ck-btn ck-btn--primary" style="background: var(--btn-default-hover-bg);padding: 8px 10px;" @click="openDogrulama">
          Aç
        </button>
        <button v-else-if="props.canEditQC" class="ck-btn ck-btn--primary" style="background: var(--btn-default-hover-bg);padding: 8px 10px;" @click="createDogrulama">
          + Ekle
        </button>
      </div>
      
      <div v-if="hasDogrulama" class="ck-mini-list" style="margin-top:8px;">
        <div class="ck-mini-item">
          <div style="display:flex; flex-direction:column; gap:8px;">
            <div class="ck-row">
              <span style="font-size: 14px; font-weight: 500;">Kayıt No:</span>
              <b style="font-size: 14px;">{{ props.doc.test_masasi_dogrulama_kaydi }}</b>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="ck-muted" style="margin-top: 14px;padding: 0px 6px;">
        Henüz doğrulama kaydı yok.
      </div>
    </div>

  </div>
</template>