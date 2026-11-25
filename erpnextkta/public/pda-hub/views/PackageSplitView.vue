<script setup lang="ts">
import { computed, ref } from "vue";
import type { BoxScanResult, PackageSplitResponse } from "../types";
import BarcodeScannerBar from "../../line-replenishment-pda/components/BarcodeScannerBar.vue";
import { playBeep } from "../../line-replenishment-pda/utils/audio";

const __ = (...args: any[]) => (window as any).__(...args);

const EPSILON = 1e-6;
let nextRowId = 2;

const scannerBarRef = ref<InstanceType<typeof BarcodeScannerBar> | null>(null);
const scanning = ref(false);
const submitting = ref(false);
const scannedBox = ref<BoxScanResult | null>(null);
const selectedWarehouse = ref("");
const splitRows = ref<Array<{ id: number; qty: string }>>([{ id: 1, qty: "" }]);
const reprintSourceLabel = ref(true);
const splitResult = ref<PackageSplitResponse | null>(null);
const feedbackMsg = ref("");
const feedbackType = ref<"success" | "error" | "">("");

const balances = computed(() => scannedBox.value?.balances || []);
const availableQty = computed(() => {
  const row = balances.value.find((b) => b.warehouse === selectedWarehouse.value);
  return Number(row?.qty || 0);
});

const parsedQtys = computed(() =>
  splitRows.value.map((r) => {
    const raw = String(r.qty ?? "").trim().replace(",", ".");
    return raw === "" ? NaN : Number(raw);
  }),
);
const hasNonPositiveOrBlank = computed(
  () => parsedQtys.value.length === 0 || parsedQtys.value.some((q) => !Number.isFinite(q) || q <= EPSILON),
);
const hasExplicitZeroOrNegative = computed(() =>
  parsedQtys.value.some((q) => Number.isFinite(q) && q <= EPSILON),
);
const totalSplitQty = computed(() =>
  parsedQtys.value.reduce((acc, q) => (Number.isFinite(q) && q > 0 ? acc + q : acc), 0),
);
const remainingQty = computed(() =>
  Math.max(0, Number((availableQty.value - totalSplitQty.value).toFixed(6))),
);
const exceedsBalance = computed(() => totalSplitQty.value - availableQty.value > EPSILON);
const isFullSingleStandardSplit = computed(() =>
  Boolean(
    scannedBox.value?.is_standard_batch &&
      parsedQtys.value.length === 1 &&
      Number.isFinite(parsedQtys.value[0]) &&
      Math.abs(totalSplitQty.value - availableQty.value) <= EPSILON,
  ),
);

const validationWarning = computed(() => {
  if (hasExplicitZeroOrNegative.value) return __("Bölme miktarları sıfırdan büyük olmalıdır.");
  if (exceedsBalance.value) return __("Bölünecek toplam miktar mevcut bakiyeyi aşıyor.");
  if (isFullSingleStandardSplit.value) {
    return __("Standart KTA kolisinin tamamı tek bir yeni koliye bölünemez.");
  }
  return "";
});

const canSubmit = computed(() =>
  Boolean(
    scannedBox.value &&
      selectedWarehouse.value &&
      !submitting.value &&
      !hasNonPositiveOrBlank.value &&
      !exceedsBalance.value &&
      !isFullSingleStandardSplit.value,
  ),
);

function clearFeedback() {
  feedbackMsg.value = "";
  feedbackType.value = "";
}

async function onScanBarcode(code: string) {
  const cleanCode = code.trim();
  if (!cleanCode || scanning.value) return;

  scanning.value = true;
  clearFeedback();
  try {
    const res = await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_scan_box",
      type: "GET",
      args: { barcode: cleanCode },
      quiet: true,
    });
    const box = res?.message as BoxScanResult | undefined;
    if (!box || !box.balances?.length) {
      playBeep(false);
      feedbackMsg.value = __("Koli için kullanılabilir stok bakiyesi bulunamadı.");
      feedbackType.value = "error";
      return;
    }
    scannedBox.value = box;
    splitResult.value = null;
    selectedWarehouse.value = box.balances[0].warehouse;
    splitRows.value = [{ id: nextRowId++, qty: "" }];
    reprintSourceLabel.value = true;
    playBeep(true);
    feedbackMsg.value = __("Koli okutuldu ve bölme işlemi için hazır.");
    feedbackType.value = "success";
  } catch (err: any) {
    playBeep(false);
    feedbackMsg.value = err?.message || __("Koli barkodu çözümlenemedi.");
    feedbackType.value = "error";
  } finally {
    scanning.value = false;
    scannerBarRef.value?.focusInput?.(true);
  }
}

function addSplitRow() {
  splitRows.value.push({ id: nextRowId++, qty: "" });
}

function removeSplitRow(id: number) {
  if (splitRows.value.length <= 1) return;
  splitRows.value = splitRows.value.filter((r) => r.id !== id);
}

async function submitSplit() {
  if (!canSubmit.value || !scannedBox.value) return;
  submitting.value = true;
  clearFeedback();
  try {
    const res = await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_package_split",
      args: {
        item_code: scannedBox.value.item_code,
        source_warehouse: selectedWarehouse.value,
        source_batch: scannedBox.value.batch_no,
        split_qtys: parsedQtys.value,
        reprint_source_label: reprintSourceLabel.value ? 1 : 0,
      },
      freeze: true,
      freeze_message: __("Koli Bölünüyor ve Etiketler Hazırlanıyor..."),
      quiet: true,
    });
    splitResult.value = res?.message as PackageSplitResponse;
    scannedBox.value = null;
    playBeep(true);
    window.frappe.show_alert({ message: __("Koli bölme işlemi tamamlandı."), indicator: "green" });
  } catch (err: any) {
    playBeep(false);
    feedbackMsg.value = err?.message || __("Koli bölme işlemi başarısız oldu.");
    feedbackType.value = "error";
  } finally {
    submitting.value = false;
  }
}

function resetView() {
  scannedBox.value = null;
  splitResult.value = null;
  selectedWarehouse.value = "";
  splitRows.value = [{ id: nextRowId++, qty: "" }];
  reprintSourceLabel.value = true;
  clearFeedback();
  scannerBarRef.value?.focusInput?.(true);
}
</script>

<template>
  <div class="pda-module-page">
    <BarcodeScannerBar
      ref="scannerBarRef"
      :disabled="scanning || submitting"
      :feedback-msg="feedbackMsg"
      :feedback-type="feedbackType"
      @scan="onScanBarcode"
      @clear="clearFeedback"
    />

    <section
      v-if="splitResult"
      class="pda-module-card split-success-card"
      data-testid="split-success-card"
    >
      <div class="success-head">
        <span class="success-icon">✅</span>
        <div>
          <h3 class="pda-empty-title">{{ __("Koli Bölme Tamamlandı") }}</h3>
          <p class="pda-empty-desc">
            {{ __("Belge No") }}: <strong>{{ splitResult.stock_entry }}</strong>
          </p>
        </div>
      </div>
      <div class="pda-meta-grid">
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Kaynak Parti") }}</span>
          <strong class="pda-meta-value">{{ splitResult.source_batch }}</strong>
        </div>
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Kalan Kaynak Miktar") }}</span>
          <strong class="pda-meta-value">{{ splitResult.remaining_qty }}</strong>
        </div>
      </div>
      <div class="created-list">
        <div class="pda-meta-label">{{ __("Oluşturulan Yeni Partiler") }}</div>
        <div v-for="batch in splitResult.created_batches" :key="batch.batch_no" class="created-row">
          <span>{{ batch.batch_no }}</span>
          <strong>{{ batch.qty }}</strong>
        </div>
      </div>
      <div v-if="splitResult.source_label_reprinted" class="reprint-note">
        🖨️ {{ __("Kalan kaynak koli etiketi yazdırma kuyruğuna eklendi.") }}
      </div>
      <button type="button" class="pda-btn-primary-lg" data-testid="split-reset-btn" @click="resetView">
        {{ __("Yeni Koli Okut") }}
      </button>
    </section>

    <section v-else-if="scannedBox" class="pda-module-card" data-testid="split-box-card">
      <div class="pda-box-header">
        <div>
          <div class="pda-item-code">{{ scannedBox.item_code }}</div>
          <div class="pda-item-name">{{ scannedBox.item_name || scannedBox.item_code }}</div>
        </div>
        <span class="batch-badge">{{ scannedBox.batch_no }}</span>
      </div>

      <div v-if="balances.length > 1" class="pda-field-group">
        <label class="pda-field-label" for="split-source-wh">{{ __("Kaynak Depo") }}</label>
        <select
          id="split-source-wh"
          v-model="selectedWarehouse"
          class="pda-control-input"
          data-testid="split-source-select"
        >
          <option v-for="b in balances" :key="b.warehouse" :value="b.warehouse">
            {{ b.warehouse }} ({{ b.qty }} {{ scannedBox.stock_uom || "" }})
          </option>
        </select>
      </div>

      <div class="pda-meta-grid">
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Kaynak Depo") }}</span>
          <strong class="pda-meta-value">{{ selectedWarehouse }}</strong>
        </div>
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Mevcut Bakiye") }}</span>
          <strong class="pda-meta-value">{{ availableQty }} {{ scannedBox.stock_uom || "" }}</strong>
        </div>
      </div>

      <div class="pda-field-group">
        <div class="rows-head">
          <span class="pda-field-label">{{ __("Bölünecek Koli Adetleri") }}</span>
          <button type="button" class="btn-add-row" data-testid="split-add-row-btn" @click="addSplitRow">
            + {{ __("Kutu Ekle") }}
          </button>
        </div>
        <div v-for="(row, idx) in splitRows" :key="row.id" class="split-qty-row">
          <span class="row-index">#{{ idx + 1 }}</span>
          <input
            v-model="row.qty"
            type="number"
            inputmode="decimal"
            step="any"
            min="0"
            class="pda-control-input"
            :data-testid="`split-qty-input-${idx}`"
            :placeholder="__('Bölünecek Miktar Girin...')"
          />
          <button v-if="splitRows.length > 1" type="button" class="pda-btn-outline" @click="removeSplitRow(row.id)">
            ✕
          </button>
        </div>
      </div>

      <div class="remaining-banner" data-testid="split-remaining-qty">
        <span>{{ __("Kalan Kaynak Miktar") }}:</span>
        <strong>{{ remainingQty }} {{ scannedBox.stock_uom || "" }}</strong>
      </div>

      <label class="checkbox-row">
        <input v-model="reprintSourceLabel" type="checkbox" />
        <span>{{ __("Kalan kaynak etiketini de yeniden bas") }}</span>
      </label>

      <div v-if="validationWarning" class="inline-warning">{{ validationWarning }}</div>

      <div class="pda-actions-row">
        <button type="button" class="pda-btn-outline" @click="resetView">{{ __("Temizle") }}</button>
        <button
          type="button"
          class="pda-btn-primary-lg"
          data-testid="split-submit-btn"
          :disabled="!canSubmit"
          @click="submitSplit"
        >
          ✂️ {{ __("Koli Böl ve Etiket Bas") }}
        </button>
      </div>
    </section>

    <div v-else class="pda-empty-hint-card">
      <div class="pda-empty-icon">✂️</div>
      <div class="pda-empty-title">{{ __("Koli Barkodu Okutun") }}</div>
      <p class="pda-empty-desc">
        {{ __("Bölmek istediğiniz kolinin etiketini veya parti numarasını okutun.") }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.split-success-card { border-color: rgba(22, 163, 74, 0.45); }
.success-head { display: flex; align-items: center; gap: 10px; }
.success-icon { font-size: 1.8rem; }
.batch-badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.14);
  color: var(--pda-primary);
  font-size: 0.8rem;
  font-weight: 800;
  white-space: nowrap;
}
.rows-head, .split-qty-row, .remaining-banner, .checkbox-row { display: flex; align-items: center; gap: 8px; }
.rows-head, .remaining-banner { justify-content: space-between; }
.row-index { font-size: 0.82rem; font-weight: 700; color: var(--text-muted); min-width: 24px; }
.btn-add-row {
  min-height: 38px;
  padding: 6px 12px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--pda-surface-alt);
  color: var(--text-color);
  font-weight: 700;
  cursor: pointer;
}
.remaining-banner {
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--pda-surface-alt);
  border: 1px solid var(--border-color);
  font-size: 0.92rem;
}
.checkbox-row { font-size: 0.88rem; font-weight: 600; cursor: pointer; }
.inline-warning {
  padding: 9px 12px;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.12);
  color: var(--pda-danger);
  font-size: 0.85rem;
  font-weight: 700;
}
.created-list { display: flex; flex-direction: column; gap: 6px; }
.created-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--pda-surface-alt);
  font-weight: 700;
}
.reprint-note { font-size: 0.84rem; font-weight: 600; color: var(--pda-success); }
</style>
