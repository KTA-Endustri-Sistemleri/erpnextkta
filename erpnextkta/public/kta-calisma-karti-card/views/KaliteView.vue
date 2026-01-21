<script setup lang="ts">
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
    idcOlcumFields(),
    async (v: any) => {
      await props.onAddIdc({
        item_code: v.item_code,
        yukseklik_mm: v.yukseklik_mm,
        cekme_n: v.cekme_n,
        olcum_tarihi: v.olcum_tarihi || null,
        olcumu_giren: v.olcumu_giren || null,
      });
      frappe.show_alert({ message: "IDC ölçümü eklendi", indicator: "green" });
    },
    "IDC Ölçümü Ekle",
    "Kaydet"
  );
}

function editIdc(row: any) {
  if (!row?.name) {
    frappe.msgprint("IDC satır kimliği (row name) bulunamadı.");
    return;
  }

  frappe.prompt(
    idcOlcumFields(row),
    async (v: any) => {
      await props.onUpdateIdc({
        rowname: row.name,
        item_code: v.item_code,
        yukseklik_mm: v.yukseklik_mm,
        cekme_n: v.cekme_n,
        olcum_tarihi: v.olcum_tarihi || null,
        olcumu_giren: v.olcumu_giren || null,
      });
      frappe.show_alert({ message: "IDC ölçümü güncellendi", indicator: "green" });
    },
    "IDC Ölçümü Düzenle",
    "Kaydet"
  );
}

function deleteIdc(row: any) {
  if (!row?.name) {
    frappe.msgprint("IDC satır kimliği (row name) bulunamadı.");
    return;
  }
  frappe.confirm("Bu IDC ölçüm satırı silinecek. Emin misiniz?", async () => {
    await props.onDeleteIdc(row.name);
    frappe.show_alert({ message: "IDC ölçümü silindi", indicator: "green" });
  });
}

function addBarkod() {
  frappe.prompt(
    barkodKayitFields(),
    async (v: any) => {
      await props.onAddBarkod({
        barcode: v.barcode,
        olcum_tarihi: v.olcum_tarihi || null,
        olcumu_giren: v.olcumu_giren || null,
      });
      frappe.show_alert({ message: "Barkod kaydı eklendi", indicator: "green" });
    },
    "Barkod Kaydı Ekle",
    "Kaydet"
  );
}

function editBarkod(row: any) {
  if (!row?.name) {
    frappe.msgprint("Barkod satır kimliği (row name) bulunamadı.");
    return;
  }

  frappe.prompt(
    barkodKayitFields(row),
    async (v: any) => {
      await props.onUpdateBarkod({
        rowname: row.name,
        barcode: v.barcode,
        olcum_tarihi: v.olcum_tarihi || null,
        olcumu_giren: v.olcumu_giren || null,
      });
      frappe.show_alert({ message: "Barkod kaydı güncellendi", indicator: "green" });
    },
    "Barkod Kaydı Düzenle",
    "Kaydet"
  );
}

function deleteBarkod(row: any) {
  if (!row?.name) {
    frappe.msgprint("Barkod satır kimliği (row name) bulunamadı.");
    return;
  }
  frappe.confirm("Bu barkod satırı silinecek. Emin misiniz?", async () => {
    await props.onDeleteBarkod(row.name);
    frappe.show_alert({ message: "Barkod kaydı silindi", indicator: "green" });
  });
}
</script>

<template>
  <div class="ck-card">
    <!-- QC header -->
    <div class="ck-row" style="justify-content:space-between; align-items:center;">
      <span>Kalite Kontrol</span>
      <b>{{ props.qcLabel }}</b>
    </div>

    <div v-if="!props.canEditQC" class="ck-muted" style="margin-top:10px;">
      Bu sekmeyi görüntüleyebilirsiniz ancak güncelleme yetkiniz yok.
    </div>

    <div v-else style="margin-top:10px;">
      <div class="ck-qc-toggle" role="group" aria-label="Kalite durumu">
        <button
          v-for="o in props.qcOptions"
          :key="o"
          type="button"
          class="ck-qc-toggle__btn"
          :class="[
            props.qcFormValue === o && 'is-active',
            o === 'Onay Bekliyor' && 'is-pending',
            o === 'Onaylandı' && 'is-ok',
            o === 'Reddedildi' && 'is-reject',
          ]"
          :disabled="props.qcSaving"
          @click="props.onSetQC(o)"
        >
          {{ o }}
        </button>
      </div>
    </div>

    <!-- Divider -->
    <div style="height:1px; background:rgba(0,0,0,.06); margin:14px 0;"></div>

    <!-- IDC Ölçümleri -->
    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
      <b>IDC Ölçümleri</b>
      <button class="ck-btn ck-btn--primary" style="padding:8px 10px;" @click="addIdc">
        + Ekle
      </button>
    </div>

    <div v-if="(props.doc.idc_olcumleri||[]).length===0" class="ck-muted" style="margin-top:8px;">
      IDC ölçüm kaydı yok.
    </div>

    <div v-else class="ck-mini-list" style="margin-top:8px;">
      <div
        v-for="(r, i) in props.doc.idc_olcumleri"
        :key="r.name || i"
        class="ck-mini-item"
      >
        <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start;">
          <div style="min-width:0;">
            <b style="display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              {{ r.item_code || ('IDC #' + (i+1)) }}
            </b>
            <div class="ck-muted">Yükseklik: {{ r.yukseklik_mm ?? "-" }} mm</div>
            <div class="ck-muted">Çekme: {{ r.cekme_n ?? "-" }} N</div>
            <div class="ck-muted" v-if="r.olcum_tarihi">Tarih: {{ r.olcum_tarihi }}</div>
            <div class="ck-muted" v-if="r.olcumu_giren">Giren: {{ r.olcumu_giren }}</div>
          </div>

          <div style="display:flex; gap:6px; flex-shrink:0;">
            <button class="ck-btn ck-btn--ghost" style="padding:8px 10px;" @click="editIdc(r)">
              Düzenle
            </button>
            <button class="ck-btn ck-btn--danger" style="padding:8px 10px;" @click="deleteIdc(r)">
              Sil
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Divider -->
    <div style="height:1px; background:rgba(0,0,0,.06); margin:14px 0;"></div>

    <!-- Barkod Kayıtları -->
    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
      <b>Barkod Kayıtları</b>
      <button class="ck-btn ck-btn--primary" style="padding:8px 10px;" @click="addBarkod">
        + Ekle
      </button>
    </div>

    <div v-if="(props.doc.barkod_kayitlari||[]).length===0" class="ck-muted" style="margin-top:8px;">
      Barkod kaydı yok.
    </div>

    <div v-else class="ck-mini-list" style="margin-top:8px;">
      <div
        v-for="(r, i) in props.doc.barkod_kayitlari"
        :key="r.name || i"
        class="ck-mini-item"
      >
        <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start;">
          <div style="min-width:0;">
            <b style="display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              {{ r.barcode || ('Barkod #' + (i+1)) }}
            </b>
            <div class="ck-muted" v-if="r.olcum_tarihi">Tarih: {{ r.olcum_tarihi }}</div>
            <div class="ck-muted" v-if="r.olcumu_giren">Giren: {{ r.olcumu_giren }}</div>
          </div>

          <div style="display:flex; gap:6px; flex-shrink:0;">
            <button class="ck-btn ck-btn--ghost" style="padding:8px 10px;" @click="editBarkod(r)">
              Düzenle
            </button>
            <button class="ck-btn ck-btn--danger" style="padding:8px 10px;" @click="deleteBarkod(r)">
              Sil
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>