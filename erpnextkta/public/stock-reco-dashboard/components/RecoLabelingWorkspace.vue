<script setup lang="ts">
import { ref, computed, watch } from "vue";
import type {
  RecoRelabelMode,
  StockRecoPreviewResponse,
  StockRecoPreviewRow,
  StockRecoRelabelSelection,
} from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

interface RowDraft {
  selected: boolean;
  convertLegacy: boolean;
  boxSplits: number[];
}

const props = defineProps<{
  preview: StockRecoPreviewResponse | null;
  loading: boolean;
  submitting: boolean;
}>();

const emit = defineEmits<{
  (e: "refresh"): void;
  (
    e: "execute",
    payload: {
      mode: RecoRelabelMode;
      selectedItems: StockRecoRelabelSelection[];
      isDraftSubmit: boolean;
      printLabels: boolean;
      submitDoc: boolean;
    }
  ): void;
}>();

const activeMode = ref<RecoRelabelMode>("mode1_changed");
const printLabels = ref<boolean>(true);
const rowDrafts = ref<Record<string, RowDraft>>({});

function getRowKey(row: StockRecoPreviewRow, idx: number): string {
  return `${row.row_name}::${row.batch_no || idx}`;
}

function initRowDrafts(mode: RecoRelabelMode) {
  const next: Record<string, RowDraft> = {};
  const list = props.preview?.rows || [];
  list.forEach((row, idx) => {
    const key = getRowKey(row, idx);
    const isSelected = mode === "mode2_all" ? true : Boolean(row.suggested_mode1_selected);
    const isNonStd = !row.is_standard_batch || row.is_legacy;
    next[key] = {
      selected: isSelected,
      convertLegacy: Boolean(isSelected && isNonStd),
      boxSplits: [Number(row.qty) || 0],
    };
  });
  rowDrafts.value = next;
}

watch(
  () => props.preview,
  () => initRowDrafts(activeMode.value),
  { immediate: true }
);

function getDraft(row: StockRecoPreviewRow, idx: number): RowDraft {
  const key = getRowKey(row, idx);
  if (!rowDrafts.value[key]) {
    const isSelected = activeMode.value === "mode2_all" ? true : Boolean(row.suggested_mode1_selected);
    rowDrafts.value[key] = {
      selected: isSelected,
      convertLegacy: Boolean(isSelected && (!row.is_standard_batch || row.is_legacy)),
      boxSplits: [Number(row.qty) || 0],
    };
  }
  return rowDrafts.value[key];
}

function setMode(mode: RecoRelabelMode) {
  if (activeMode.value === mode) return;
  activeMode.value = mode;
  initRowDrafts(mode);
}

function onRowSelectionChange(row: StockRecoPreviewRow, idx: number, event: Event) {
  const target = event.target as HTMLInputElement | null;
  const checked = Boolean(target?.checked);
  const draft = getDraft(row, idx);
  draft.selected = checked;
  if (checked && (!row.is_standard_batch || row.is_legacy)) {
    draft.convertLegacy = true;
  }
}

const rows = computed(() => props.preview?.rows || []);
const selectedEntries = computed(() =>
  rows.value
    .map((row, idx) => ({ row, idx, draft: getDraft(row, idx) }))
    .filter((entry) => entry.draft.selected)
);

const isAllSelected = computed(
  () => rows.value.length > 0 && selectedEntries.value.length === rows.value.length
);

const isIndeterminate = computed(
  () => selectedEntries.value.length > 0 && selectedEntries.value.length < rows.value.length
);

function toggleSelectAll(event: Event) {
  const target = event.target as HTMLInputElement | null;
  const checked = Boolean(target?.checked);
  rows.value.forEach((row, idx) => {
    const draft = getDraft(row, idx);
    draft.selected = checked;
    if (checked && (!row.is_standard_batch || row.is_legacy)) {
      draft.convertLegacy = true;
    }
  });
}

function addBoxSplit(row: StockRecoPreviewRow, idx: number) {
  const draft = getDraft(row, idx);
  const currentSum = draft.boxSplits.reduce((s, v) => s + (Number(v) || 0), 0);
  const rem = Number((Number(row.qty) - currentSum).toFixed(4));
  draft.boxSplits.push(rem > 0.0001 ? rem : 0);
}

function removeBoxSplit(row: StockRecoPreviewRow, idx: number, splitIdx: number) {
  const draft = getDraft(row, idx);
  if (draft.boxSplits.length <= 1) return;
  draft.boxSplits.splice(splitIdx, 1);
}

function getSplitDelta(row: StockRecoPreviewRow, idx: number): number {
  const draft = getDraft(row, idx);
  const sum = draft.boxSplits.reduce((s, v) => s + (Number(v) || 0), 0);
  return Number((Number(row.qty) - sum).toFixed(4));
}

function isSplitValid(row: StockRecoPreviewRow, idx: number): boolean {
  const draft = getDraft(row, idx);
  if (!draft.boxSplits.length) return false;
  if (draft.boxSplits.some((v) => Number.isNaN(Number(v)) || Number(v) <= 0)) return false;
  return Math.abs(getSplitDelta(row, idx)) <= 0.0001;
}

const hasInvalidSplit = computed(() =>
  selectedEntries.value.some(({ row, idx }) => !isSplitValid(row, idx))
);

const totalLabelsCount = computed(() =>
  selectedEntries.value.reduce((acc, { draft }) => acc + draft.boxSplits.length, 0)
);

function statusLabel(status: StockRecoPreviewRow["status"]): string {
  if (status === "valid") return __("Uyumlu");
  if (status === "qty_changed") return __("Miktar Değişti");
  if (status === "missing_label") return __("Etiket Eksik");
  return __("LEGACY / Partisiz");
}

function statusClass(status: StockRecoPreviewRow["status"]): string {
  if (status === "valid") return "st-valid";
  if (status === "qty_changed") return "st-changed";
  if (status === "missing_label") return "st-missing";
  return "st-legacy";
}

function getLabelTypeDisplay(type: string | null | undefined): string {
  if (!type) return "";
  if (type === "İş Emri Etiketi") return `🏭 ${__("İş Emri")}`;
  if (type === "Depo Giriş Etiketi") return `📦 ${__("Depo")}`;
  return `🏷️ ${__(type)}`;
}

function getLabelTypeClass(type: string | null | undefined): string {
  if (!type) return "";
  if (type === "İş Emri Etiketi") return "lt-work-order";
  if (type === "Depo Giriş Etiketi") return "lt-warehouse";
  return "lt-default";
}

function formatQty(val: number | null | undefined): string {
  if (val === null || val === undefined) return "—";
  return new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 4 }).format(Number(val));
}

function openDocInDesk(name: string) {
  if (typeof frappe !== "undefined" && frappe.set_route) {
    frappe.set_route("Form", "Stock Reconciliation", name);
  }
}

function handleExecute(submitDoc: boolean = true) {
  if (!props.preview || props.submitting || selectedEntries.value.length === 0 || hasInvalidSplit.value) {
    return;
  }
  const selectedItems: StockRecoRelabelSelection[] = selectedEntries.value.map(({ row, draft }) => ({
    row_name: row.row_name,
    item_code: row.item_code,
    warehouse: row.warehouse,
    source_batch: row.batch_no || null,
    qty: Number(row.qty),
    convert_legacy: (!row.is_standard_batch || row.is_legacy) && draft.convertLegacy ? 1 : 0,
    box_splits: draft.boxSplits.map((v) => Number(v)),
  }));
  emit("execute", {
    mode: activeMode.value,
    selectedItems,
    isDraftSubmit: props.preview.doc.docstatus === 0,
    printLabels: printLabels.value,
    submitDoc,
  });
}
</script>

<template>
  <section class="rlw-wrap">
    <div v-if="!preview && !loading" class="rlw-empty">
      <div class="rlw-empty-icon">🏷️</div>
      <h3>{{ __("Sayım Belgesi Seçin") }}</h3>
      <p>{{ __("Etiket sağlığını incelemek ve toplu barkod basımı yapmak için soldaki listeden bir sayım belgesi seçin.") }}</p>
    </div>

    <div v-else-if="loading && !preview" class="rlw-empty">
      <div class="rlw-empty-icon">⏳</div>
      <h3>{{ __("Etiket Önizlemesi Yükleniyor...") }}</h3>
    </div>

    <template v-else-if="preview">
      <header class="rlw-header">
        <div class="rlw-doc-meta">
          <div class="rlw-doc-row">
            <button type="button" class="rlw-doc-link" @click="openDocInDesk(preview.doc.name)">
              {{ preview.doc.name }} ↗
            </button>
            <span class="rlw-doc-status" :class="preview.doc.docstatus === 0 ? 'st-changed' : 'st-valid'">
              {{ preview.doc.docstatus === 0 ? __("Taslak") : __("Onaylı") }}
            </span>
            <span class="rlw-meta-chip">🏢 {{ preview.doc.set_warehouse || __("Çoklu Depo") }}</span>
            <span v-if="preview.doc.posting_date" class="rlw-meta-chip">📅 {{ preview.doc.posting_date }}</span>
          </div>

          <div class="rlw-summary-chips">
            <span class="rlw-chip">{{ __("Toplam") }}: {{ preview.summary.total_positive }}</span>
            <span class="rlw-chip st-valid">{{ __("Uyumlu") }}: {{ preview.summary.valid }}</span>
            <span class="rlw-chip st-changed">{{ __("Değişen") }}: {{ preview.summary.qty_changed }}</span>
            <span class="rlw-chip st-missing">{{ __("Eksik") }}: {{ preview.summary.missing_label }}</span>
            <span class="rlw-chip st-legacy">LEGACY: {{ preview.summary.legacy_batch }}</span>
          </div>
        </div>

        <div class="rlw-controls">
          <div class="rlw-mode-switch" role="tablist">
            <button type="button" class="rlw-mode-btn" :class="{ active: activeMode === 'mode1_changed' }" :disabled="submitting" @click="setMode('mode1_changed')">
              {{ __("Fiziksel Kutu Esas") }}
            </button>
            <button type="button" class="rlw-mode-btn" :class="{ active: activeMode === 'mode2_all' }" :disabled="submitting" @click="setMode('mode2_all')">
              {{ __("Sistem Partisi Esas") }}
            </button>
          </div>

          <button type="button" class="rlw-refresh-btn" :disabled="loading || submitting" @click="emit('refresh')">
            🔄 {{ __("Yenile") }}
          </button>
        </div>
      </header>

      <div v-if="rows.length === 0" class="rlw-empty">
        <div class="rlw-empty-icon">📦</div>
        <h3>{{ __("Pozitif Stok Kalemi Bulunamadı") }}</h3>
        <p>{{ __("Bu sayım belgesinde miktarı sıfırdan büyük kalem yer almıyor.") }}</p>
      </div>

      <div v-else class="rlw-table-scroll">
        <table class="rlw-table">
          <thead>
            <tr>
              <th class="col-check">
                <input type="checkbox" class="rlw-check" :checked="isAllSelected" :indeterminate="isIndeterminate" :disabled="submitting" @change="toggleSelectAll" />
              </th>
              <th>{{ __("Malzeme & Depo") }}</th>
              <th>{{ __("Parti & Etiket Durumu") }}</th>
              <th class="text-right">{{ __("Sistem / Etiket Miktarı") }}</th>
              <th>{{ __("Kutu Kırılımı") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in rows" :key="getRowKey(row, idx)" :class="{ 'row-selected': getDraft(row, idx).selected }">
              <td class="col-check">
                <input type="checkbox" class="rlw-check" :checked="getDraft(row, idx).selected" :disabled="submitting" @change="onRowSelectionChange(row, idx, $event)" />
              </td>
              <td>
                <div class="rlw-item-col">
                  <strong>{{ row.item_code }}</strong>
                  <span v-if="row.item_name && row.item_name !== row.item_code" class="rlw-muted">{{ row.item_name }}</span>
                  <span class="rlw-wh">🏢 {{ row.warehouse }}</span>
                </div>
              </td>
              <td>
                <div class="rlw-batch-col">
                  <div class="rlw-batch-top">
                    <span class="rlw-batch-code">{{ row.batch_no || __("Partisiz") }}</span>
                    <span
                      v-if="row.label_type"
                      class="rlw-badge-type"
                      :class="getLabelTypeClass(row.label_type)"
                      :title="row.label_type"
                    >
                      {{ getLabelTypeDisplay(row.label_type) }}
                    </span>
                    <span class="rlw-badge" :class="statusClass(row.status)">{{ statusLabel(row.status) }}</span>
                  </div>
                  <label v-if="!row.is_standard_batch || row.is_legacy" class="rlw-legacy-toggle">
                    <input v-model="getDraft(row, idx).convertLegacy" type="checkbox" class="rlw-check-sm" :disabled="submitting" />
                    <span>{{ __("Standart Koliye Çevir") }}</span>
                  </label>
                </div>
              </td>
              <td class="text-right">
                <div class="rlw-qty-col">
                  <span class="rlw-sys-qty">{{ formatQty(row.qty) }} {{ row.uom || "" }}</span>
                  <span class="rlw-lbl-qty">
                    {{ __("Etiket Miktarı") }}: {{ formatQty(row.label_qty) }}
                    <span
                      v-if="row.label_qty !== null && Math.abs(row.qty - row.label_qty) > 0.0001"
                      class="rlw-diff-tag"
                    >
                      ({{ row.qty - row.label_qty > 0 ? "+" : "" }}{{ formatQty(row.qty - row.label_qty) }})
                    </span>
                  </span>
                </div>
              </td>
              <td>
                <div class="rlw-splits-col">
                  <div class="rlw-splits-list">
                    <div v-for="(_, sIdx) in getDraft(row, idx).boxSplits" :key="sIdx" class="rlw-split-chip">
                      <input v-model.number="getDraft(row, idx).boxSplits[sIdx]" type="number" step="any" min="0.0001" class="rlw-split-input" :class="{ 'is-error': !isSplitValid(row, idx) }" :disabled="submitting" />
                      <button v-if="getDraft(row, idx).boxSplits.length > 1" type="button" class="rlw-split-del" :disabled="submitting" @click="removeBoxSplit(row, idx, sIdx)">✕</button>
                    </div>
                    <button type="button" class="rlw-split-add" :disabled="submitting" @click="addBoxSplit(row, idx)">+ {{ __("Kutu Böl") }}</button>
                  </div>
                  <span v-if="!isSplitValid(row, idx)" class="rlw-split-err">
                    ⚠️ {{ __("Kalan Fark") }}: {{ formatQty(getSplitDelta(row, idx)) }}
                  </span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer class="rlw-action-bar">
        <div class="rlw-action-left">
          <label class="rlw-print-toggle">
            <input v-model="printLabels" type="checkbox" class="rlw-check" :disabled="submitting" />
            <span>🖨️ {{ __("Etiketleri Zebra Yazıcıya Gönder") }}</span>
          </label>
          <div class="rlw-counters">
            <strong>{{ __("{0} satır seçili · {1} etiket üretilecek", [selectedEntries.length, totalLabelsCount]) }}</strong>
            <span v-if="hasInvalidSplit" class="rlw-split-err">
              ⚠️ {{ __("Seçili satırlarda kutu kırılım toplamı sistem miktarıyla eşleşmiyor") }}
            </span>
          </div>
        </div>

        <div class="rlw-action-buttons">
          <template v-if="preview.doc.docstatus === 0">
            <button
              type="button"
              class="rlw-save-draft-btn"
              :disabled="submitting || selectedEntries.length === 0 || hasInvalidSplit"
              :title="__('Taslak sayımı onaylamadan sadece seçili satırları kaydeder ve etiket basar.')"
              @click="handleExecute(false)"
            >
              🖨️ {{ submitting ? __("İşleniyor...") : __("Taslakta Kaydet & Etiket Bas") }}
            </button>
            <button
              type="button"
              class="rlw-submit-btn"
              :disabled="submitting || selectedEntries.length === 0 || hasInvalidSplit"
              @click="handleExecute(true)"
            >
              ✅ {{ submitting ? __("İşleniyor...") : __("Sayımı Onayla ve Tamamla") }}
            </button>
          </template>
          <template v-else>
            <button
              type="button"
              class="rlw-submit-btn"
              :disabled="submitting || selectedEntries.length === 0 || hasInvalidSplit"
              @click="handleExecute(false)"
            >
              🏷️ {{ submitting ? __("İşleniyor...") : __("Etiketleri Güncelle ve Bas") }}
            </button>
          </template>
        </div>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.rlw-wrap { display: flex; flex-direction: column; gap: 0.9rem; min-width: 0; }
.rlw-empty { padding: 3.5rem 1.5rem; text-align: center; background: var(--card-bg, #ffffff); border: 1px dashed var(--border-color, #cbd5e1); border-radius: 0.75rem; display: flex; flex-direction: column; align-items: center; gap: 0.4rem; }
[data-theme="dark"] .rlw-empty { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); }
.rlw-empty-icon { font-size: 2.5rem; }
.rlw-empty h3 { margin: 0; font-size: 1.08rem; font-weight: 800; }
.rlw-empty p { margin: 0; font-size: 0.85rem; color: var(--text-muted, #64748b); max-width: 460px; }
.rlw-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; flex-wrap: wrap; padding: 1rem 1.15rem; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; }
[data-theme="dark"] .rlw-header { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12)); }
.rlw-doc-meta { display: flex; flex-direction: column; gap: 0.55rem; }
.rlw-doc-row { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.rlw-doc-link { background: transparent; border: none; padding: 0; font-family: monospace; font-size: 1rem; font-weight: 800; color: #2563eb; cursor: pointer; text-decoration: underline; }
[data-theme="dark"] .rlw-doc-link { color: #60a5fa; }
.rlw-doc-status, .rlw-badge, .rlw-chip { display: inline-flex; align-items: center; padding: 0.18rem 0.55rem; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; white-space: nowrap; }
.rlw-meta-chip { font-size: 0.78rem; color: var(--text-muted, #64748b); font-weight: 600; }
.rlw-summary-chips { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.rlw-chip { background: var(--bg-color, #f1f5f9); color: var(--text-color, #334155); border: 1px solid var(--border-color, #cbd5e1); }
[data-theme="dark"] .rlw-chip { background: rgba(255, 255, 255, 0.06); border-color: rgba(255, 255, 255, 0.14); color: #e2e8f0; }
.st-valid { background: #dcfce7 !important; color: #15803d !important; border: 1px solid #86efac !important; }
.st-changed { background: #fef3c7 !important; color: #b45309 !important; border: 1px solid #fde68a !important; }
.st-missing { background: #ffedd5 !important; color: #c2410c !important; border: 1px solid #fdba74 !important; }
.st-legacy { background: #fee2e2 !important; color: #b91c1c !important; border: 1px solid #fca5a5 !important; }
[data-theme="dark"] .st-valid { background: rgba(34, 197, 94, 0.2) !important; color: #86efac !important; border-color: rgba(74, 222, 128, 0.35) !important; }
[data-theme="dark"] .st-changed { background: rgba(245, 158, 11, 0.2) !important; color: #fcd34d !important; border-color: rgba(251, 191, 36, 0.35) !important; }
[data-theme="dark"] .st-missing { background: rgba(249, 115, 22, 0.2) !important; color: #fdba74 !important; border-color: rgba(251, 146, 60, 0.35) !important; }
[data-theme="dark"] .st-legacy { background: rgba(239, 68, 68, 0.2) !important; color: #fca5a5 !important; border-color: rgba(248, 113, 113, 0.35) !important; }
.rlw-controls { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
.rlw-mode-switch { display: inline-flex; padding: 0.2rem; background: var(--bg-color, #f1f5f9); border: 1px solid var(--border-color, #cbd5e1); border-radius: 0.5rem; gap: 0.2rem; }
[data-theme="dark"] .rlw-mode-switch { background: rgba(15, 23, 42, 0.55); border-color: rgba(255, 255, 255, 0.14); }
.rlw-mode-btn { border: none; background: transparent; padding: 0.38rem 0.72rem; border-radius: 0.38rem; font-size: 0.78rem; font-weight: 700; color: var(--text-muted, #64748b); cursor: pointer; }
.rlw-mode-btn.active { background: #2563eb; color: #ffffff; }
.rlw-refresh-btn { padding: 0.4rem 0.78rem; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--bg-color, #f8fafc); color: var(--text-color, #0f172a); font-size: 0.79rem; font-weight: 700; cursor: pointer; }
[data-theme="dark"] .rlw-refresh-btn { background: rgba(255, 255, 255, 0.06); border-color: rgba(255, 255, 255, 0.16); color: #f8fafc; }
.rlw-table-scroll { overflow-x: auto; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; }
[data-theme="dark"] .rlw-table-scroll { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12)); }
.rlw-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; text-align: left; }
.rlw-table th { padding: 0.68rem 0.85rem; background: var(--bg-color, #f8fafc); color: var(--text-muted, #475569); font-size: 0.74rem; font-weight: 700; text-transform: uppercase; border-bottom: 1.5px solid var(--border-color, #cbd5e1); white-space: nowrap; }
[data-theme="dark"] .rlw-table th { background: rgba(255, 255, 255, 0.04); color: #cbd5e1; }
.rlw-table td { padding: 0.65rem 0.85rem; border-bottom: 1px solid var(--border-color, #e2e8f0); vertical-align: middle; }
.rlw-table tbody tr.row-selected { background: rgba(37, 99, 235, 0.05); }
.col-check { width: 38px; text-align: center; }
.rlw-check, .rlw-check-sm { accent-color: #2563eb; cursor: pointer; }
.rlw-check { width: 16px; height: 16px; }
.text-right { text-align: right !important; }
.rlw-item-col, .rlw-batch-col, .rlw-qty-col, .rlw-splits-col { display: flex; flex-direction: column; gap: 0.2rem; }
.rlw-muted, .rlw-wh { font-size: 0.74rem; color: var(--text-muted, #64748b); }
.rlw-batch-top { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; }
.rlw-batch-code { font-family: monospace; font-weight: 700; font-size: 0.8rem; }
.rlw-legacy-toggle { display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.73rem; font-weight: 700; color: #b45309; cursor: pointer; margin: 0; }
[data-theme="dark"] .rlw-legacy-toggle { color: #fcd34d; }
.rlw-qty-col { align-items: flex-end; white-space: nowrap; }
.rlw-sys-qty { font-weight: 800; }
.rlw-lbl-qty { font-size: 0.73rem; color: var(--text-muted, #64748b); }
.rlw-diff-tag { font-weight: 800; color: #d97706; }
.rlw-splits-list { display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap; }
.rlw-split-chip { display: inline-flex; align-items: center; gap: 0.2rem; }
.rlw-split-input { width: 74px; padding: 0.28rem 0.4rem; text-align: right; border-radius: 0.38rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-weight: 700; font-size: 0.79rem; }
[data-theme="dark"] .rlw-split-input { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #f8fafc; }
.rlw-split-input.is-error { border-color: #dc2626; background: rgba(239, 68, 68, 0.08); }
.rlw-split-del { border: none; background: transparent; color: #dc2626; font-weight: 800; cursor: pointer; font-size: 0.78rem; padding: 0 0.2rem; }
.rlw-split-add { padding: 0.26rem 0.55rem; border-radius: 0.38rem; border: 1px dashed #2563eb; background: rgba(37, 99, 235, 0.06); color: #2563eb; font-size: 0.73rem; font-weight: 700; cursor: pointer; white-space: nowrap; }
[data-theme="dark"] .rlw-split-add { color: #60a5fa; border-color: #60a5fa; }
.rlw-split-err { font-size: 0.73rem; font-weight: 700; color: #dc2626; }
[data-theme="dark"] .rlw-split-err { color: #f87171; }
.rlw-action-bar { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; padding: 0.9rem 1.15rem; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; }
[data-theme="dark"] .rlw-action-bar { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12)); }
.rlw-action-left { display: flex; flex-direction: column; gap: 0.35rem; }
.rlw-action-buttons { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
.rlw-print-toggle { display: inline-flex; align-items: center; gap: 0.45rem; font-size: 0.82rem; font-weight: 700; cursor: pointer; margin: 0; }
.rlw-counters { display: flex; flex-direction: column; gap: 0.15rem; font-size: 0.84rem; }
.rlw-badge-type { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.12rem 0.45rem; border-radius: 0.35rem; font-size: 0.7rem; font-weight: 700; white-space: nowrap; border: 1px solid var(--border-color, #cbd5e1); }
.rlw-badge-type.lt-work-order { background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }
.rlw-badge-type.lt-warehouse { background: #f0fdf4; color: #166534; border-color: #bbf7d0; }
.rlw-badge-type.lt-default { background: var(--bg-color, #f1f5f9); color: var(--text-muted, #475569); }
[data-theme="dark"] .rlw-badge-type.lt-work-order { background: rgba(59, 130, 246, 0.18); color: #93c5fd; border-color: rgba(96, 165, 250, 0.35); }
[data-theme="dark"] .rlw-badge-type.lt-warehouse { background: rgba(34, 197, 94, 0.18); color: #86efac; border-color: rgba(74, 222, 128, 0.35); }
[data-theme="dark"] .rlw-badge-type.lt-default { background: rgba(255, 255, 255, 0.08); color: #cbd5e1; border-color: rgba(255, 255, 255, 0.16); }
.rlw-save-draft-btn { padding: 0.58rem 1.15rem; border-radius: 0.5rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--bg-color, #f8fafc); color: var(--text-color, #0f172a); font-size: 0.86rem; font-weight: 700; cursor: pointer; transition: all 0.15s ease; }
.rlw-save-draft-btn:hover:not(:disabled) { background: #f1f5f9; border-color: #94a3b8; }
.rlw-save-draft-btn:disabled { opacity: 0.5; cursor: not-allowed; }
[data-theme="dark"] .rlw-save-draft-btn { background: rgba(255, 255, 255, 0.06); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.18)); color: #f8fafc; }
[data-theme="dark"] .rlw-save-draft-btn:hover:not(:disabled) { background: rgba(255, 255, 255, 0.12); border-color: rgba(255, 255, 255, 0.28); }
.rlw-submit-btn { padding: 0.58rem 1.25rem; border: none; border-radius: 0.5rem; background: #2563eb; color: #ffffff; font-size: 0.86rem; font-weight: 700; cursor: pointer; }
.rlw-submit-btn:hover:not(:disabled) { background: #1d4ed8; }
.rlw-submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
