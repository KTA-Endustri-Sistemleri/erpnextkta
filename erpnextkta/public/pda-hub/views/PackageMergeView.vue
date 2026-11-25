<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import type { BoxScanResult, PackageMergeResponse, PackageMergeSourceInput } from "../types";
import BarcodeScannerBar from "../../line-replenishment-pda/components/BarcodeScannerBar.vue";
import { playBeep } from "../../line-replenishment-pda/utils/audio";

const __ = (...args: any[]) => (window as any).__(...args);

interface ScannedMergeEntry {
  id: number;
  box: BoxScanResult;
  selectedWarehouse: string;
}

let nextEntryId = 1;

const scannerBarRef = ref<InstanceType<typeof BarcodeScannerBar> | null>(null);
const scanning = ref(false);
const submitting = ref(false);
const scannedBoxes = ref<ScannedMergeEntry[]>([]);
const targetWarehouseBarcode = ref("");
const showMixedLotModal = ref(false);
const lastResult = ref<PackageMergeResponse | null>(null);
const feedbackMsg = ref("");
const feedbackType = ref<"success" | "error" | "">("");

function selectedQty(entry: ScannedMergeEntry): number {
  const match = entry.box.balances.find((b) => b.warehouse === entry.selectedWarehouse);
  return Number(match?.qty || 0);
}

const firstItemCode = computed(() => scannedBoxes.value[0]?.box.item_code || "");
const firstItemName = computed(() => scannedBoxes.value[0]?.box.item_name || firstItemCode.value);
const firstStockUom = computed(() => scannedBoxes.value[0]?.box.stock_uom || "");
const defaultTargetWarehouse = computed(() => scannedBoxes.value[0]?.selectedWarehouse || "");

const totalMergeQty = computed(() => {
  const sum = scannedBoxes.value.reduce((acc, e) => acc + selectedQty(e), 0);
  return Number(sum.toFixed(6));
});

const distinctBaseLots = computed(() => {
  const seen = new Set<string>();
  for (const entry of scannedBoxes.value) {
    seen.add(entry.box.base_lot || entry.box.batch_no);
  }
  return Array.from(seen);
});

const hasNonStandardBatch = computed(() =>
  scannedBoxes.value.some((entry) => !entry.box.is_standard_batch),
);

const isMixedLot = computed(() => hasNonStandardBatch.value || distinctBaseLots.value.length > 1);

const hasDuplicatePair = computed(() => {
  const pairs = new Set<string>();
  for (const entry of scannedBoxes.value) {
    const key = `${entry.box.batch_no}::${entry.selectedWarehouse}`;
    if (pairs.has(key)) return true;
    pairs.add(key);
  }
  return false;
});

const canSubmit = computed(
  () => scannedBoxes.value.length >= 2 && !submitting.value && !hasDuplicatePair.value,
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
      return;
    }
    if (scannedBoxes.value.length > 0 && box.item_code !== scannedBoxes.value[0].box.item_code) {
      playBeep(false);
      feedbackMsg.value = __("Farklı ürün kodlarına ait koliler birleştirilemez.");
      feedbackType.value = "error";
      return;
    }

    const availableBalance = box.balances.find(
      (b) =>
        !scannedBoxes.value.some(
          (e) => e.box.batch_no === box.batch_no && e.selectedWarehouse === b.warehouse,
        ),
    );
    if (!availableBalance) {
      playBeep(false);
      feedbackMsg.value = __("Bu koli zaten birleştirme listesine eklendi.");
      feedbackType.value = "error";
      return;
    }

    scannedBoxes.value.push({ id: nextEntryId++, box, selectedWarehouse: availableBalance.warehouse });
    lastResult.value = null;
    playBeep(true);
    feedbackMsg.value = __("Koli birleştirme listesine eklendi.");
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

function removeBox(entryId: number) {
  scannedBoxes.value = scannedBoxes.value.filter((e) => e.id !== entryId);
  if (!hasDuplicatePair.value && feedbackType.value === "error") {
    clearFeedback();
  }
}

function onSubmitClick() {
  if (!canSubmit.value) return;
  if (isMixedLot.value) {
    showMixedLotModal.value = true;
    return;
  }
  void executeMerge(0);
}

async function executeMerge(allowMixedLots: 0 | 1) {
  if (!canSubmit.value) return;
  submitting.value = true;
  clearFeedback();
  const sourceBoxes: PackageMergeSourceInput[] = scannedBoxes.value.map((entry) => ({
    batch_no: entry.box.batch_no,
    warehouse: entry.selectedWarehouse,
    qty: selectedQty(entry),
  }));

  try {
    const res = await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_package_merge",
      args: {
        source_boxes: sourceBoxes,
        target_warehouse_barcode: targetWarehouseBarcode.value.trim() || null,
        allow_mixed_lots: allowMixedLots,
      },
      freeze: true,
      freeze_message: __("Koliler Birleştiriliyor ve Etiket Hazırlanıyor..."),
      quiet: true,
    });
    lastResult.value = res?.message as PackageMergeResponse;
    scannedBoxes.value = [];
    targetWarehouseBarcode.value = "";
    showMixedLotModal.value = false;
    playBeep(true);
    window.frappe.show_alert({ message: __("Koliler başarıyla birleştirildi."), indicator: "green" });
  } catch (err: any) {
    showMixedLotModal.value = false;
    playBeep(false);
    feedbackMsg.value = err?.message || __("Koli birleştirme işlemi başarısız oldu.");
    feedbackType.value = "error";
  } finally {
    submitting.value = false;
  }
}

function resetAll() {
  scannedBoxes.value = [];
  targetWarehouseBarcode.value = "";
  showMixedLotModal.value = false;
  lastResult.value = null;
  clearFeedback();
  scannerBarRef.value?.focusInput?.(true);
}

function handleEscapeKey(e: KeyboardEvent) {
  if (showMixedLotModal.value && e.key === "Escape" && !submitting.value) {
    e.preventDefault();
    showMixedLotModal.value = false;
  }
}

onMounted(() => window.addEventListener("keydown", handleEscapeKey));
onUnmounted(() => window.removeEventListener("keydown", handleEscapeKey));
</script>

<template>
  <div class="pda-module-page">
    <BarcodeScannerBar
      ref="scannerBarRef"
      :disabled="scanning || submitting"
      :feedback-msg="feedbackMsg"
      :feedback-type="feedbackType"
      @scan="onScanBox"
      @clear="clearFeedback"
    />

    <section v-if="lastResult" class="pda-module-card merge-result-card" data-testid="merge-result-card">
      <div class="pda-box-header">
        <div>
          <h3 class="pda-empty-title">✅ {{ __("Koli Birleştirme Tamamlandı") }}</h3>
          <p class="pda-empty-desc">
            {{ __("Belge No") }}: <strong>{{ lastResult.stock_entry }}</strong>
          </p>
        </div>
        <span class="lot-type-pill" :class="lastResult.is_mixed_lot ? 'pill-mixed' : 'pill-same'">
          {{ lastResult.is_mixed_lot ? __("Karma Lot Birleştirme") : __("Aynı Lot Birleştirme") }}
        </span>
      </div>

      <div class="pda-meta-grid">
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Hedef Parti") }}</span>
          <strong class="pda-meta-value">{{ lastResult.target_batch }}</strong>
        </div>
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Toplam Miktar") }}</span>
          <strong class="pda-meta-value">{{ lastResult.total_qty }}</strong>
        </div>
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Hedef Raf") }}</span>
          <strong class="pda-meta-value">{{ lastResult.target_warehouse }}</strong>
        </div>
        <div class="pda-meta-box">
          <span class="pda-meta-label">{{ __("Kalite Referansı") }}</span>
          <strong class="pda-meta-value">{{ lastResult.quality_ref || "-" }}</strong>
        </div>
      </div>

      <button type="button" class="pda-btn-primary-lg" data-testid="merge-reset-btn" @click="resetAll">
        {{ __("Yeni Birleştirme Başlat") }}
      </button>
    </section>

    <section v-else-if="scannedBoxes.length > 0" class="pda-module-card">
      <div class="pda-box-header">
        <div>
          <div class="pda-item-code">{{ firstItemCode }}</div>
          <div class="pda-item-name">{{ firstItemName }}</div>
        </div>
        <div class="merge-totals-col">
          <span class="pda-meta-label">{{ __("{0} Koli Seçildi", [scannedBoxes.length]) }}</span>
          <strong class="merge-total-qty">{{ totalMergeQty }} {{ firstStockUom }}</strong>
        </div>
      </div>

      <div class="merge-list">
        <div v-for="(entry, idx) in scannedBoxes" :key="entry.id" class="merge-box-row" :data-testid="`merge-box-row-${idx}`">
          <div class="merge-row-main">
            <div class="merge-row-top">
              <strong class="merge-batch">{{ entry.box.batch_no }}</strong>
              <span class="lot-chip">{{ __("Ana Lot") }}: {{ entry.box.base_lot || entry.box.batch_no }}</span>
              <span v-if="!entry.box.is_standard_batch" class="legacy-chip">{{ __("Standart Dışı") }}</span>
            </div>
            <div class="merge-row-sub">
              <select v-if="entry.box.balances.length > 1" v-model="entry.selectedWarehouse" class="merge-wh-select">
                <option v-for="b in entry.box.balances" :key="b.warehouse" :value="b.warehouse">
                  {{ b.warehouse }} ({{ b.qty }} {{ firstStockUom }})
                </option>
              </select>
              <span v-else class="merge-wh-label">{{ entry.selectedWarehouse }}</span>
              <strong class="merge-row-qty">{{ selectedQty(entry) }} {{ firstStockUom }}</strong>
            </div>
          </div>
          <button
            type="button"
            class="pda-btn-outline merge-remove-btn"
            :data-testid="`merge-remove-btn-${idx}`"
            :aria-label="__('Kaldır')"
            @click="removeBox(entry.id)"
          >
            ✕
          </button>
        </div>
      </div>

      <div v-if="isMixedLot" class="lot-status-banner merge-mixed-warning" data-testid="merge-mixed-warning">
        ⚠️ {{ __("Karma veya standart dışı lot tespit edildi ({0}). Birleştirme öncesi onay gerekecektir.", [distinctBaseLots.join(", ")]) }}
      </div>
      <div v-else-if="scannedBoxes.length >= 2" class="lot-status-banner lot-ok-banner" data-testid="merge-lot-status">
        ✅ {{ __("Aynı Ana Lot: {0} — Kesintisiz Birleştirme", [distinctBaseLots[0]]) }}
      </div>

      <div class="pda-field-group">
        <label class="pda-field-label" for="merge-target-wh">{{ __("Hedef Raf Barkodu (Opsiyonel)") }}</label>
        <input
          id="merge-target-wh"
          v-model="targetWarehouseBarcode"
          type="text"
          class="pda-control-input"
          data-testid="merge-target-wh-input"
          :placeholder="__('Boş bırakılırsa ilk kolinin deposuna aktarılır...')"
          autocomplete="off"
          autocapitalize="off"
          autocorrect="off"
          spellcheck="false"
        />
        <span class="merge-wh-hint">
          {{ defaultTargetWarehouse ? __("Varsayılan: ilk kolinin deposu ({0})", [defaultTargetWarehouse]) : __("Varsayılan: ilk kolinin deposu") }}
        </span>
      </div>

      <div v-if="hasDuplicatePair" class="merge-dup-warning">
        {{ __("Aynı parti ve depo çifti birden fazla satırda seçilemez.") }}
      </div>

      <div class="pda-actions-row">
        <button type="button" class="pda-btn-outline" @click="resetAll">{{ __("Temizle") }}</button>
        <button type="button" class="pda-btn-primary-lg" data-testid="merge-submit-btn" :disabled="!canSubmit" @click="onSubmitClick">
          🔗 {{ __("Kolileri Birleştir") }}
        </button>
      </div>
    </section>

    <div v-else class="pda-empty-hint-card" data-testid="merge-empty-hint">
      <div class="pda-empty-icon">🔗</div>
      <div class="pda-empty-title">{{ __("Birleştirilecek Kolileri Okutun") }}</div>
      <p class="pda-empty-desc">{{ __("Aynı ürüne ait en az 2 koliyi okutarak tek partide birleştirin.") }}</p>
    </div>

    <Teleport to="body">
      <div v-if="showMixedLotModal" class="mixed-modal-backdrop" @click.self="showMixedLotModal = false">
        <div class="mixed-modal" role="dialog" aria-modal="true" data-testid="mixed-lot-confirm-modal">
          <h3 class="mixed-modal-title">⚠️ {{ __("Karma Lot Birleştirme Uyarısı") }}</h3>
          <ul class="mixed-modal-list">
            <li>{{ __("Tekil satınalma / üretim irsaliyesi ve GKK izlenebilirliği tek partide birleşecektir.") }}</li>
            <li>{{ __("Yeni bir 7+4 karma lot numarası üretilecek ve etikete KARMA LOT ibaresi basılacaktır.") }}</li>
            <li>{{ __("En yakın son kullanma tarihi (SKT) ve ağırlıklı ortalama maliyet devralınacaktır.") }}</li>
            <li>{{ __("Kaynak parti detayları Stock Entry açıklamasına ve yeni parti kaydına işlenecektir.") }}</li>
          </ul>
          <div class="pda-actions-row">
            <button type="button" class="pda-btn-outline" data-testid="mixed-lot-cancel-btn" :disabled="submitting" @click="showMixedLotModal = false">
              {{ __("Vazgeç") }}
            </button>
            <button type="button" class="pda-btn-primary-lg" data-testid="mixed-lot-confirm-btn" :disabled="submitting" @click="executeMerge(1)">
              {{ __("Onayla ve Birleştir") }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.merge-result-card { border-color: rgba(22, 163, 74, 0.45); }
.lot-type-pill { padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 800; white-space: nowrap; }
.pill-same { background: rgba(22, 163, 74, 0.14); color: var(--pda-success); }
.pill-mixed { background: rgba(217, 119, 6, 0.16); color: #b45309; }
[data-theme="dark"] .pill-mixed { color: #fbbf24; }
.merge-totals-col { text-align: right; display: flex; flex-direction: column; }
.merge-total-qty { font-size: 1.08rem; font-weight: 800; color: var(--pda-primary); }
.merge-list { display: flex; flex-direction: column; gap: 8px; }
.merge-box-row { display: flex; align-items: center; gap: 8px; padding: 10px; border-radius: 10px; background: var(--pda-surface-alt); border: 1px solid var(--border-color); }
.merge-row-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.merge-row-top, .merge-row-sub { display: flex; align-items: center; justify-content: space-between; gap: 6px; flex-wrap: wrap; }
.merge-batch { font-size: 0.9rem; word-break: break-word; }
.lot-chip, .legacy-chip { font-size: 0.72rem; font-weight: 700; padding: 2px 7px; border-radius: 999px; background: rgba(147, 51, 234, 0.14); color: #7e22ce; }
[data-theme="dark"] .lot-chip { color: #d8b4fe; }
.legacy-chip { background: rgba(217, 119, 6, 0.16); color: #b45309; }
[data-theme="dark"] .legacy-chip { color: #fbbf24; }
.merge-wh-select { flex: 1; min-width: 0; padding: 4px 8px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-color); color: var(--text-color); font-size: 0.82rem; font-weight: 600; }
.merge-wh-label { font-size: 0.8rem; color: var(--text-muted); word-break: break-word; }
.merge-row-qty { font-size: 0.9rem; white-space: nowrap; }
.merge-remove-btn { min-height: 38px; padding: 6px 10px; }
.lot-status-banner { padding: 10px 12px; border-radius: 10px; font-size: 0.85rem; font-weight: 700; }
.lot-ok-banner { background: rgba(22, 163, 74, 0.14); color: var(--pda-success); border: 1px solid rgba(22, 163, 74, 0.3); }
.merge-mixed-warning { background: rgba(217, 119, 6, 0.16); color: #92400e; border: 1px solid rgba(217, 119, 6, 0.4); }
[data-theme="dark"] .merge-mixed-warning { color: #fcd34d; border-color: rgba(251, 191, 36, 0.45); }
.merge-wh-hint { font-size: 0.76rem; color: var(--text-muted); }
.merge-dup-warning { padding: 9px 12px; border-radius: 10px; background: rgba(239, 68, 68, 0.12); color: var(--pda-danger); font-size: 0.84rem; font-weight: 700; }
.mixed-modal-backdrop { position: fixed; inset: 0; z-index: 1300; background: rgba(15, 23, 42, 0.65); display: flex; align-items: center; justify-content: center; padding: 16px; }
.mixed-modal { width: 100%; max-width: 440px; background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); border: 1px solid var(--border-color, #e2e8f0); border-radius: 16px; padding: 18px; display: flex; flex-direction: column; gap: 12px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35); }
.mixed-modal-title { margin: 0; font-size: 1.05rem; font-weight: 800; color: #b45309; }
[data-theme="dark"] .mixed-modal-title { color: #fbbf24; }
.mixed-modal-list { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; font-size: 0.86rem; line-height: 1.4; }
</style>
