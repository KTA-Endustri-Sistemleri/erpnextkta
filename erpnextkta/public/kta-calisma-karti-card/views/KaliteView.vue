<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
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

const isNarrow = ref(false);

function updateIsNarrow() {
  isNarrow.value = window.innerWidth <= 360;
}

// --------------------
// CRUD actions
// --------------------
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
  if (!row?.name) {
    frappe.msgprint("IDC satır kimliği (row name) bulunamadı.");
    return;
  }

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
      await props.onAddBarkod({ barcode: v.barcode });
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
      await props.onUpdateBarkod({ rowname: row.name, barcode: v.barcode });
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

// --------------------
// Helpers
// --------------------
function fmtDt(val?: string) {
  if (!val) return "";
  try {
    const d = new Date(val);
    if (isNaN(d.getTime())) return val;
    return d.toLocaleString("tr-TR");
  } catch {
    return val;
  }
}

function copyToClipboard(text?: string) {
  const t = (text || "").trim();
  if (!t) return;
  navigator.clipboard?.writeText(t).then(
    () => frappe.show_alert({ message: "Kopyalandı", indicator: "green" }),
    () => frappe.msgprint("Kopyalama başarısız.")
  );
}

/** Visual-only deterministic bars (no real encoding). */
function barcodeBars(str?: string) {
  const s = (str || "").trim();
  if (!s) return [];
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const bars: number[] = [];
  let x = h >>> 0;
  for (let i = 0; i < 42; i++) {
    x = (x * 1103515245 + 12345) >>> 0;
    bars.push(1 + (x % 3));
  }
  return bars;
}

function barX(bars: number[], idx: number) {
  let sum = 0;
  for (let i = 0; i < idx; i++) sum += bars[i] || 0;
  return sum;
}

function barOpacity(idx: number) {
  return idx % 2 === 0 ? 1 : 0.15;
}

function openActionSheet(title: string, options: string[], onPick: (picked: string) => void) {
  frappe.prompt(
    [
      {
        fieldtype: "Select",
        label: title,
        fieldname: "action",
        reqd: 1,
        options: options.join("\n"),
      },
    ],
    (v: any) => onPick(v.action),
    title,
    "Seç"
  );
}

function idcActions(r: any) {
  openActionSheet("IDC İşlemleri", ["Düzenle", "Sil"], (a) => {
    if (a === "Düzenle") editIdc(r);
    if (a === "Sil") deleteIdc(r);
  });
}

function barkodActions(r: any) {
  const opts = ["Kopyala"];
  if (props.canEditQC) opts.push("Düzenle", "Sil");

  openActionSheet("Barkod İşlemleri", opts, (a) => {
    if (a === "Kopyala") copyToClipboard(r.barcode);
    if (a === "Düzenle") editBarkod(r);
    if (a === "Sil") deleteBarkod(r);
  });
}

onMounted(() => {
  updateIsNarrow();
  window.addEventListener("resize", updateIsNarrow, { passive: true });
});

onUnmounted(() => {
  window.removeEventListener("resize", updateIsNarrow);
});
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

    <div style="height:1px; background:rgba(0,0,0,.06); margin:14px 0;"></div>

    <!-- IDC Ölçümleri -->
    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
      <b>IDC Ölçümleri</b>
      <button v-if="props.canEditQC" class="ck-btn ck-btn--primary" style="padding:8px 10px;" @click="addIdc">
        + Ekle
      </button>
    </div>

    <div v-if="(props.doc.idc_olcumleri||[]).length===0" class="ck-muted" style="margin-top:8px;">
      IDC ölçüm kaydı yok.
    </div>

    <div v-else class="ck-mini-list" style="margin-top:8px;">
      <div v-for="(r, i) in props.doc.idc_olcumleri" :key="r.name || i" class="ck-mini-item">
        <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start;">
          <div style="min-width:0; flex:1;">
            <b style="display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              {{ r.item_code || ('IDC #' + (i+1)) }}
            </b>

            <div style="margin-top:6px; display:flex; gap:10px; flex-wrap:wrap;">
              <span class="ck-muted" style="border:1px solid rgba(0,0,0,.08); border-radius:10px; padding:4px 8px;">
                Yükseklik: <b style="font-weight:800;">{{ r.yukseklik_mm ?? "-" }}</b> mm
              </span>
              <span class="ck-muted" style="border:1px solid rgba(0,0,0,.08); border-radius:10px; padding:4px 8px;">
                Çekme: <b style="font-weight:800;">{{ r.cekme_n ?? "-" }}</b> N
              </span>
            </div>

            <div
              v-if="r.olcum_tarihi || r.olcumu_giren"
              class="ck-muted"
              style="margin-top:8px; border:1px dashed rgba(0,0,0,.12); border-radius:999px; padding:6px 10px; width:fit-content; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"
            >
              <span v-if="r.olcum_tarihi">Tarih: {{ fmtDt(r.olcum_tarihi) }}</span>
              <span v-if="r.olcum_tarihi && r.olcumu_giren"> · </span>
              <span v-if="r.olcumu_giren">Giren: {{ r.olcumu_giren }}</span>
            </div>
          </div>

          <div style="display:flex; gap:6px; flex-shrink:0;">
            <button
              v-if="props.canEditQC && isNarrow"
              class="ck-btn ck-btn--ghost"
              style="padding:8px 10px; min-width:44px;"
              @click="idcActions(r)"
              title="İşlemler"
            >
              ⋯
            </button>

            <template v-else>
              <div v-if="props.canEditQC" style="display:flex; gap:6px;">
                <button class="ck-btn ck-btn--ghost" style="padding:8px 10px;" @click="editIdc(r)">
                  Düzenle
                </button>
                <button class="ck-btn ck-btn--danger" style="padding:8px 10px;" @click="deleteIdc(r)">
                  Sil
                </button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <div style="height:1px; background:rgba(0,0,0,.06); margin:14px 0;"></div>

    <!-- Barkod Kayıtları -->
    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
      <b>Barkod Kayıtları</b>
      <button v-if="props.canEditQC" class="ck-btn ck-btn--primary" style="padding:8px 10px;" @click="addBarkod">
        + Ekle
      </button>
    </div>

    <div v-if="(props.doc.barkod_kayitlari||[]).length===0" class="ck-muted" style="margin-top:8px;">
      Barkod kaydı yok.
    </div>

    <div v-else class="ck-mini-list" style="margin-top:8px;">
      <div v-for="(r, i) in props.doc.barkod_kayitlari" :key="r.name || i" class="ck-mini-item">
        <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start;">
          <div style="min-width:0; flex:1;">
            <b style="display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              {{ r.barcode || ('Barkod #' + (i+1)) }}
            </b>

            <div v-if="r.barcode" style="margin-top:8px; display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
              <div
                aria-label="Barkod görseli"
                style="height:34px; border:1px solid rgba(0,0,0,.08); border-radius:10px; padding:6px 10px; background:#fff; display:flex; align-items:center;"
              >
                <svg
                  :width="isNarrow ? 120 : 160"
                  :height="22"
                  :viewBox="`0 0 ${isNarrow ? 120 : 160} 22`"
                  role="img"
                  aria-hidden="true"
                >
                  <g>
                    <template v-for="(w, idx) in barcodeBars(r.barcode)" :key="idx">
                      <rect
                        :x="barX(barcodeBars(r.barcode), idx)"
                        y="0"
                        :width="w"
                        height="22"
                        fill="#111"
                        :opacity="barOpacity(idx)"
                      />
                    </template>
                  </g>
                </svg>
              </div>

              <div
                class="ck-muted"
                style="border:1px solid rgba(0,0,0,.08); border-radius:10px; padding:6px 10px; background:rgba(0,0,0,.03); max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"
                title="Barkod değeri"
              >
                {{ r.barcode }}
              </div>
            </div>

            <div
              v-if="r.olcum_tarihi || r.olcumu_giren"
              class="ck-muted"
              style="margin-top:8px; border:1px dashed rgba(0,0,0,.12); border-radius:999px; padding:6px 10px; width:fit-content; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"
            >
              <span v-if="r.olcum_tarihi">Tarih: {{ fmtDt(r.olcum_tarihi) }}</span>
              <span v-if="r.olcum_tarihi && r.olcumu_giren"> · </span>
              <span v-if="r.olcumu_giren">Giren: {{ r.olcumu_giren }}</span>
            </div>
          </div>

          <div style="display:flex; gap:6px; flex-shrink:0;">
            <button
              v-if="isNarrow"
              class="ck-btn ck-btn--ghost"
              style="padding:8px 10px; min-width:44px;"
              @click="barkodActions(r)"
              title="İşlemler"
            >
              ⋯
            </button>

            <template v-else>
              <button
                v-if="r.barcode"
                class="ck-btn ck-btn--ghost"
                style="padding:8px 10px;"
                @click="copyToClipboard(r.barcode)"
              >
                Kopyala
              </button>

              <div v-if="props.canEditQC" style="display:flex; gap:6px;">
                <button class="ck-btn ck-btn--ghost" style="padding:8px 10px;" @click="editBarkod(r)">
                  Düzenle
                </button>
                <button class="ck-btn ck-btn--danger" style="padding:8px 10px;" @click="deleteBarkod(r)">
                  Sil
                </button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
