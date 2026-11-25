<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import type { BoxScanResult, MaterialTransferResponse } from "../types";
import BarcodeScannerBar from "../../line-replenishment-pda/components/BarcodeScannerBar.vue";
import { playBeep } from "../../line-replenishment-pda/utils/audio";

const __ = (...args: any[]) => (window as any).__(...args);

const scannerBarRef = ref<InstanceType<typeof BarcodeScannerBar> | null>(null);
const targetInputRef = ref<HTMLInputElement | null>(null);

const scanning = ref(false);
const submitting = ref(false);
const scannedBox = ref<BoxScanResult | null>(null);
const selectedWarehouse = ref("");
const targetWarehouseBarcode = ref("");
const lastTransfer = ref<MaterialTransferResponse | null>(null);
const feedbackMsg = ref("");
const feedbackType = ref<"success" | "error" | "">("");

const balances = computed(() => scannedBox.value?.balances || []);

const availableQty = computed(() => {
  const row = balances.value.find((b) => b.warehouse === selectedWarehouse.value);
  return Number(row?.qty || 0);
});

const canSubmit = computed(() =>
  Boolean(
    scannedBox.value &&
      selectedWarehouse.value &&
      availableQty.value > 0 &&
      targetWarehouseBarcode.value.trim() &&
      !submitting.value,
  ),
);

function clearFeedback() {
  feedbackMsg.value = "";
  feedbackType.value = "";
}

async function onScanBox(code: string) {
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
      scannerBarRef.value?.focusInput?.(true);
      return;
    }

    scannedBox.value = box;
    selectedWarehouse.value = box.balances[0].warehouse;
    targetWarehouseBarcode.value = "";
    playBeep(true);
    feedbackMsg.value = __("Koli doğrulandı. Şimdi hedef raf barkodunu okutun.");
    feedbackType.value = "success";

    await nextTick();
    targetInputRef.value?.focus();
  } catch (err: any) {
    playBeep(false);
    feedbackMsg.value = err?.message || __("Koli barkodu çözümlenemedi.");
    feedbackType.value = "error";
    scannerBarRef.value?.focusInput?.(true);
  } finally {
    scanning.value = false;
  }
}

async function submitTransfer() {
  if (!canSubmit.value || !scannedBox.value) return;

  submitting.value = true;
  clearFeedback();
  try {
    const res = await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_material_transfer",
      args: {
        item_code: scannedBox.value.item_code,
        batch_no: scannedBox.value.batch_no,
        source_warehouse: selectedWarehouse.value,
        target_warehouse_barcode: targetWarehouseBarcode.value.trim(),
        qty: availableQty.value,
      },
      freeze: true,
      freeze_message: __("Malzeme Transfer Ediliyor..."),
      quiet: true,
    });

    lastTransfer.value = res?.message as MaterialTransferResponse;
    scannedBox.value = null;
    selectedWarehouse.value = "";
    targetWarehouseBarcode.value = "";
    playBeep(true);
    feedbackMsg.value = __("Transfer tamamlandı. Sıradaki koliyi okutabilirsiniz.");
    feedbackType.value = "success";
    window.frappe.show_alert({
      message: __("Koli transferi başarıyla tamamlandı."),
      indicator: "green",
    });

    await nextTick();
    scannerBarRef.value?.focusInput?.(true);
  } catch (err: any) {
    playBeep(false);
    feedbackMsg.value = err?.message || __("Transfer işlemi tamamlanamadı.");
    feedbackType.value = "error";
    await nextTick();
    targetInputRef.value?.focus();
  } finally {
    submitting.value = false;
  }
}

function resetBox() {
  scannedBox.value = null;
  selectedWarehouse.value = "";
  targetWarehouseBarcode.value = "";
  clearFeedback();
  scannerBarRef.value?.focusInput?.(true);
}
</script>

<template>
  <div class="pda-module-page">
    <div
      v-if="lastTransfer"
      class="transfer-success-banner"
      data-testid="transfer-success-banner"
    >
      <div class="banner-title">✅ {{ __("Son Transfer Tamamlandı") }}</div>
      <div class="banner-meta">
        <span>{{ lastTransfer.stock_entry }}</span>
        <span>→ {{ lastTransfer.target_warehouse }}</span>
        <span>({{ lastTransfer.qty }})</span>
      </div>
    </div>

    <BarcodeScannerBar
      ref="scannerBarRef"
      :disabled="scanning || submitting"
      :feedback-msg="feedbackMsg"
      :feedback-type="feedbackType"
      @scan="onScanBox"
      @clear="clearFeedback"
    />

    <section v-if="scannedBox" class="pda-module-card" data-testid="transfer-box-card">
      <div class="pda-box-header">
        <div>
          <div class="pda-item-code">{{ scannedBox.item_code }}</div>
          <div class="pda-item-name">{{ scannedBox.item_name || scannedBox.item_code }}</div>
        </div>
        <span class="rule-badge" data-testid="one-box-one-batch-badge">
          {{ __("1 Kutu = 1 Parti") }}
        </span>
      </div>

      <div v-if="balances.length > 1" class="pda-field-group">
        <label class="pda-field-label" for="transfer-source-wh">{{ __("Kaynak Depo") }}</label>
        <select
          id="transfer-source-wh"
          v-model="selectedWarehouse"
          class="pda-control-input"
          data-testid="transfer-source-select"
        >
          <option v-for="b in balances" :key="b.warehouse" :value="b.warehouse">
            {{ b.warehouse }} ({{ b.qty }} {{ scannedBox.stock_uom || "" }})
          </option>
        </select>
      </div>

      <div class="pda-meta-grid">
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Parti Numarası") }}</span>
          <strong class="pda-meta-value">{{ scannedBox.batch_no }}</strong>
        </div>
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Kaynak Raf") }}</span>
          <strong class="pda-meta-value">{{ selectedWarehouse }}</strong>
        </div>
        <div class="pda-meta-box meta-box-wide">
          <span class="pda-meta-label">{{ __("Transfer Edilecek Tam Kutu Miktarı") }}</span>
          <strong class="meta-qty-readonly">{{ availableQty }} {{ scannedBox.stock_uom || "" }}</strong>
        </div>
      </div>

      <div class="pda-field-group">
        <label class="pda-field-label" for="transfer-target-input">
          {{ __("Adım 2: Hedef Raf Barkodu") }}
        </label>
        <input
          id="transfer-target-input"
          ref="targetInputRef"
          v-model="targetWarehouseBarcode"
          type="text"
          class="pda-control-input target-input"
          data-testid="transfer-target-input"
          :placeholder="__('Hedef Raf Barkodu Okutun (Örn: 170-W1F-02-04)...')"
          :disabled="submitting"
          autocomplete="off"
          autocapitalize="off"
          autocorrect="off"
          spellcheck="false"
          @keydown.enter.prevent="submitTransfer"
        />
      </div>

      <div class="pda-actions-row">
        <button type="button" class="pda-btn-outline" :disabled="submitting" @click="resetBox">
          {{ __("Vazgeç") }}
        </button>
        <button
          type="button"
          class="pda-btn-primary-lg btn-transfer-submit"
          data-testid="transfer-submit-btn"
          :disabled="!canSubmit"
          @click="submitTransfer"
        >
          🔄 {{ __("Transferi Tamamla") }}
        </button>
      </div>
    </section>

    <div v-else class="pda-empty-hint-card">
      <div class="pda-empty-icon">🔄</div>
      <div class="pda-empty-title">{{ __("Adım 1: Koli Barkodu Okutun") }}</div>
      <p class="pda-empty-desc">
        {{ __("Tam kutu raf transferi için önce taşımak istediğiniz koliyi okutun.") }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.transfer-success-banner {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(22, 163, 74, 0.14);
  border: 1px solid rgba(22, 163, 74, 0.35);
  color: var(--pda-success);
}
.banner-title { font-size: 0.9rem; font-weight: 800; }
.banner-meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 2px; font-size: 0.82rem; font-weight: 700; }
.rule-badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(217, 119, 6, 0.14);
  color: #d97706;
  font-size: 0.76rem;
  font-weight: 800;
  white-space: nowrap;
}
[data-theme="dark"] .rule-badge { color: #fbbf24; }
.meta-box-wide { grid-column: 1 / -1; }
.meta-qty-readonly { font-size: 1.12rem; font-weight: 800; color: var(--pda-primary); }
.target-input:focus { outline: none; border-color: var(--pda-primary); }
.btn-transfer-submit { background: var(--pda-success); }
</style>
