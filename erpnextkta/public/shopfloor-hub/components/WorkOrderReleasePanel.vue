<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import type {
  WorkOrderContext,
  MaterialAvailabilityResponse,
  MaterialAvailabilityItem,
} from "../types";
import ItemAlternativesModal from "./ItemAlternativesModal.vue";
import WorkOrderPrintButton from "./WorkOrderPrintButton.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    workOrder: string;
    context: WorkOrderContext | null;
    loadingContext?: boolean;
  }>(),
  {
    loadingContext: false,
  }
);

const emit = defineEmits<{
  (e: "released", workOrderName: string): void;
  (e: "switch-to-operations", workOrderName: string): void;
  (e: "refresh"): void;
  (e: "qty-updated", qty: number): void;
  (e: "open-line-transfers", targetWarehouse: string): void;
}>();

const loading = ref<boolean>(false);
const releasing = ref<boolean>(false);
const error = ref<string | null>(null);
const releaseError = ref<string | null>(null);
const justReleased = ref<boolean>(false);
const availability = ref<MaterialAvailabilityResponse | null>(null);
const showShortageModal = ref<boolean>(false);
const showAlternativesModal = ref<boolean>(false);
const activeAltItem = ref<MaterialAvailabilityItem | null>(null);
const copied = ref<boolean>(false);
const editingQty = ref(false);
const tempQty = ref<number>(0);
const savingQty = ref(false);
const qtyInputRef = ref<HTMLInputElement | null>(null);

let latestRequestId = 0;

function openAlternativesModal(item: MaterialAvailabilityItem) {
  activeAltItem.value = item;
  showAlternativesModal.value = true;
}

function closeAlternativesModal() {
  showAlternativesModal.value = false;
  activeAltItem.value = null;
}

function handleAlternativeApplied(updatedAvailability?: any) {
  closeAlternativesModal();
  emit("refresh");
  if (updatedAvailability && updatedAvailability.items) {
    availability.value = updatedAvailability;
  } else {
    fetchAvailability();
  }
}

async function restoreDirectly(item: MaterialAvailabilityItem) {
  if (releasing.value || loading.value) return;
  const targetWo = props.workOrder;
  const rowName = item.row_name || item.item_code;
  const origItem = item.custom_original_item || "";
  const confirmMsg = __(
    '"{0}" satırındaki muadil hammadde yerine orijinal "{1}" koduna dönmek istediğinize emin misiniz?',
    [item.item_code, origItem]
  );

  const doRestore = async () => {
    loading.value = true;
    try {
      const res = await callFrappe<MaterialAvailabilityResponse>(
        "erpnextkta.kta_shopfloor.api.restore_work_order_original",
        {
          work_order: targetWo,
          row_name: rowName,
        }
      );
      (window as any).frappe?.show_alert?.({
        message: __("Orijinal reçete hammaddesi ({0}) geri yüklendi.", [
          origItem,
        ]),
        indicator: "green",
      });
      emit("refresh");
      if (res && res.items) {
        availability.value = res;
      } else {
        await fetchAvailability();
      }
    } catch (err: any) {
      console.error("restore_work_order_original error:", err);
      releaseError.value = extractFrappeError(
        err,
        __("Orijinal hammaddeye dönülürken bir hata oluştu.")
      );
    } finally {
      loading.value = false;
    }
  };

  if ((window as any).frappe?.confirm) {
    (window as any).frappe.confirm(confirmMsg, doRestore);
  } else if (window.confirm(confirmMsg)) {
    doRestore();
  }
}

function extractFrappeError(err: any, fallback: string): string {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  if (err._server_messages) {
    try {
      const parsed = JSON.parse(err._server_messages);
      if (Array.isArray(parsed) && parsed.length > 0) {
        const msgs = parsed
          .map((item: any) => {
            if (typeof item !== "string") return item?.message || String(item);
            try {
              return JSON.parse(item)?.message || item;
            } catch {
              return item;
            }
          })
          .filter(Boolean);
        if (msgs.length > 0) return msgs.join(" ");
      }
    } catch {
      /* fallback below */
    }
  }
  return err.message || fallback;
}

function callFrappe<T = any>(
  method: string,
  args: Record<string, any> = {}
): Promise<T> {
  return new Promise((resolve, reject) => {
    frappe.call({
      method,
      args,
      quiet: true,
      callback: (r: { message?: T }) => {
        if ((window as any).frappe) (window as any).frappe.messages = [];
        resolve(r.message as T);
      },
      error: (err: any) => {
        if ((window as any).frappe) (window as any).frappe.messages = [];
        reject(err);
      },
    });
  });
}

function stripHtml(value?: string | null): string {
  if (!value) return "";
  return value
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function formatQty(value?: number | null): string {
  const num = Number(value ?? 0);
  if (Number.isNaN(num)) return "0";
  return Number.isInteger(num) ? String(num) : String(Number(num.toFixed(3)));
}

const matchingContext = computed<WorkOrderContext | null>(() => {
  if (!props.context || props.context.work_order !== props.workOrder)
    return null;
  return props.context;
});

const isDraft = computed<boolean>(() => {
  if (!matchingContext.value) return false;
  const docstatus = matchingContext.value.docstatus;
  if (typeof docstatus === "number") return docstatus === 0;
  return matchingContext.value.status === "Draft";
});

const isStoppedOrClosed = computed<boolean>(() => {
  if (!matchingContext.value) return false;
  return (
    matchingContext.value.status === "Stopped" ||
    matchingContext.value.status === "Closed"
  );
});

const isCancelled = computed<boolean>(() => {
  if (!matchingContext.value) return false;
  return (
    matchingContext.value.docstatus === 2 ||
    matchingContext.value.status === "Cancelled"
  );
});

const isReleased = computed<boolean>(() => {
  if (
    !matchingContext.value ||
    isDraft.value ||
    isStoppedOrClosed.value ||
    isCancelled.value
  ) {
    return false;
  }
  const docstatus = matchingContext.value.docstatus;
  if (typeof docstatus === "number") return docstatus === 1;
  return true;
});

const statusLabel = computed<string>(() => matchingContext.value?.status || "");

const statusClass = computed<string>(() => {
  const s = statusLabel.value.toLowerCase().replace(/\s+/g, "-");
  return `status-${s}`;
});

const targetQty = computed<number>(() =>
  Number(matchingContext.value?.qty ?? 0)
);

const targetUom = computed<string>(() => {
  return matchingContext.value?.stock_uom || __("Adet");
});

function startEditQty() {
  tempQty.value = targetQty.value;
  editingQty.value = true;
  nextTick(() => {
    qtyInputRef.value?.focus();
    qtyInputRef.value?.select();
  });
}

function cancelEditQty() {
  editingQty.value = false;
}

async function saveQty() {
  if (!tempQty.value || tempQty.value <= 0 || savingQty.value) return;
  savingQty.value = true;
  try {
    const res = await callFrappe<MaterialAvailabilityResponse>(
      "erpnextkta.kta_shopfloor.api.update_work_order_quantity",
      {
        work_order: props.workOrder,
        qty: tempQty.value,
      }
    );
    (window as any).frappe?.show_alert?.({
      message: __("Hedef miktar güncellendi: {0}", [tempQty.value]),
      indicator: "green",
    });
    editingQty.value = false;
    if (res && res.items) {
      availability.value = res;
    }
    if (props.context) {
      props.context.qty = tempQty.value;
    }
    emit("refresh");
    emit("qty-updated", tempQty.value);
  } catch (err: any) {
    console.error("update_work_order_quantity error:", err);
    const errMsg = extractFrappeError(
      err,
      __("Hedef miktar güncellenirken bir hata oluştu.")
    );
    (window as any).frappe?.show_alert?.({
      message: errMsg,
      indicator: "red",
    });
  } finally {
    savingQty.value = false;
  }
}

const items = computed<MaterialAvailabilityItem[]>(
  () => availability.value?.items || []
);

const shortageItems = computed<MaterialAvailabilityItem[]>(() =>
  items.value.filter(
    (item) =>
      Number(item.shortage_qty || 0) > 0 ||
      Number(item.coverage_percent || 0) < 100
  )
);

const shortageCount = computed<number>(() => {
  if (typeof availability.value?.shortage_count === "number") {
    return availability.value.shortage_count;
  }
  return shortageItems.value.length;
});

const hasShortage = computed<boolean>(() => {
  if (!availability.value) return false;
  return Boolean(availability.value.has_shortage) || shortageCount.value > 0;
});

const hasLineShortage = computed<boolean>(() => {
  if (!availability.value) return false;
  if (typeof availability.value.has_line_shortage === "boolean") {
    return availability.value.has_line_shortage;
  }
  return hasShortage.value;
});

const hasCriticalShortage = computed<boolean>(() => {
  if (!availability.value) return false;
  if (typeof availability.value.has_critical_shortage === "boolean") {
    return availability.value.has_critical_shortage;
  }
  return items.value.some(
    (item) => getItemStatus(item) === "critical_shortage"
  );
});

const canFulfillViaTransfer = computed<boolean>(() => {
  if (!availability.value) return false;
  if (typeof availability.value.can_fulfill_via_transfer === "boolean") {
    return availability.value.can_fulfill_via_transfer;
  }
  return hasLineShortage.value && !hasCriticalShortage.value;
});

const criticalShortageCount = computed<number>(() => {
  if (typeof availability.value?.critical_shortage_count === "number") {
    return availability.value.critical_shortage_count;
  }
  return items.value.filter(
    (item) => getItemStatus(item) === "critical_shortage"
  ).length;
});

const readinessPercent = computed<number>(() => {
  if (!availability.value) return 0;
  const raw = Number(availability.value.overall_readiness_percent ?? 0);
  return Math.max(0, Math.min(100, Math.round(raw * 10) / 10));
});

const isFullyReady = computed<boolean>(() => {
  return (
    Boolean(availability.value) &&
    !hasShortage.value &&
    readinessPercent.value >= 100
  );
});

function copyWorkOrderNumber() {
  if (!props.workOrder) return;
  navigator.clipboard?.writeText(props.workOrder);
  copied.value = true;
  setTimeout(() => {
    copied.value = false;
  }, 1800);
}

async function fetchAvailability() {
  if (!props.workOrder) {
    availability.value = null;
    return;
  }
  const requestId = ++latestRequestId;
  loading.value = true;
  error.value = null;

  try {
    const res = await callFrappe<MaterialAvailabilityResponse>(
      "erpnextkta.kta_shopfloor.api.check_material_availability",
      { work_order: props.workOrder }
    );
    if (requestId !== latestRequestId) return;
    availability.value = res || null;
  } catch (err: any) {
    if (requestId !== latestRequestId) return;
    console.error("check_material_availability error:", err);
    error.value = extractFrappeError(
      err,
      __("Hammadde uygunluk bilgileri alınamadı.")
    );
    availability.value = null;
  } finally {
    if (requestId === latestRequestId) {
      loading.value = false;
    }
  }
}

async function performRelease(allowShortage: 0 | 1) {
  const targetWo = props.workOrder;
  if (releasing.value || !targetWo) return;
  releasing.value = true;
  releaseError.value = null;

  try {
    await callFrappe("erpnextkta.kta_shopfloor.api.release_work_order", {
      work_order: targetWo,
      allow_shortage: allowShortage,
    });
    showShortageModal.value = false;
    (window as any).frappe?.show_alert?.({
      message: __("İş emri başarıyla serbest bırakıldı"),
      indicator: "green",
    });
    if (props.workOrder === targetWo) {
      justReleased.value = true;
      await fetchAvailability();
    }
    emit("released", targetWo);
  } catch (err: any) {
    console.error("release_work_order error:", err);
    releaseError.value = extractFrappeError(
      err,
      __("İş emri serbest bırakılırken bir hata oluştu.")
    );
  } finally {
    releasing.value = false;
  }
}

function handleReleaseClick() {
  if (!props.workOrder || !isDraft.value || releasing.value || loading.value)
    return;
  releaseError.value = null;

  if (hasShortage.value) {
    showShortageModal.value = true;
    return;
  }

  const confirmMsg = __(
    '"{0}" numaralı iş emrini üretime serbest bırakmak istediğinize emin misiniz?',
    [props.workOrder]
  );
  if ((window as any).frappe?.confirm) {
    (window as any).frappe.confirm(confirmMsg, () => performRelease(0));
  } else if (window.confirm(confirmMsg)) {
    performRelease(0);
  }
}

function closeShortageModal() {
  if (!releasing.value) {
    showShortageModal.value = false;
  }
}

function handleGlobalKeydown(e: KeyboardEvent) {
  if (e.key === "Escape" && showShortageModal.value) {
    e.preventDefault();
    closeShortageModal();
  }
}

function getRowDescription(item: MaterialAvailabilityItem): string {
  const cleanDesc = stripHtml(item.description);
  if (item.item_name && item.item_name !== item.item_code) {
    return item.item_name;
  }
  if (cleanDesc && cleanDesc !== item.item_code) {
    return cleanDesc;
  }
  return "—";
}

function getItemStatus(
  item: MaterialAvailabilityItem
): "available" | "transfer_required" | "critical_shortage" {
  if (item.availability_status) {
    return item.availability_status;
  }
  const req = Number(item.required_qty || 0);
  const lineAvail = Number(item.line_available_qty ?? item.available_qty ?? 0);
  const otherQty = Number(item.other_warehouses_qty || 0);
  if (lineAvail >= req) return "available";
  if (lineAvail + otherQty >= req) return "transfer_required";
  return "critical_shortage";
}

function formatOtherWarehousesTooltip(item: MaterialAvailabilityItem): string {
  if (!item.other_warehouses || !item.other_warehouses.length) {
    return "";
  }
  return item.other_warehouses
    .map(
      (wh) =>
        `${wh.warehouse}: ${formatQty(wh.available_qty ?? wh.actual_qty)}${
          item.stock_uom ? " " + item.stock_uom : ""
        }`
    )
    .join("\n");
}

watch(
  () => props.workOrder,
  (newWo, oldWo) => {
    if (newWo !== oldWo) {
      justReleased.value = false;
      releaseError.value = null;
      showShortageModal.value = false;
      showAlternativesModal.value = false;
      activeAltItem.value = null;
      editingQty.value = false;
    }
    fetchAvailability();
  }
);

onMounted(() => {
  window.addEventListener("keydown", handleGlobalKeydown);
  fetchAvailability();
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleGlobalKeydown);
});
</script>

<template>
  <div class="release-panel">
    <!-- Release Error Banner -->
    <div
      v-if="releaseError"
      class="panel-alert panel-alert-danger"
      role="alert"
    >
      <div class="alert-left">
        <span aria-hidden="true">⚠️</span>
        <span>{{ releaseError }}</span>
      </div>
      <button type="button" class="alert-dismiss" @click="releaseError = null">
        ✕
      </button>
    </div>

    <!-- Header Summary Banner -->
    <section class="panel-card summary-banner">
      <div class="summary-top">
        <div class="wo-identity">
          <div class="wo-chip-wrapper">
            <a
              :href="`/app/work-order/${workOrder}`"
              target="_blank"
              class="wo-badge-link"
              :title="__('İş Emrini Yeni Sekmede Aç')"
            >
              <span class="wo-icon" aria-hidden="true">⚡</span>
              <span class="wo-text">{{ workOrder }}</span>
              <span class="external-icon" aria-hidden="true">↗</span>
            </a>
            <button
              type="button"
              class="btn-copy-chip"
              :title="__('Numarayı Kopyala')"
              @click="copyWorkOrderNumber"
            >
              <span v-if="copied" class="copied-text">{{
                __("Kopyalandı!")
              }}</span>
              <span v-else aria-hidden="true">📋</span>
            </button>
          </div>

          <span
            v-if="matchingContext && statusLabel"
            class="status-pill"
            :class="statusClass"
          >
            <span class="status-dot" />
            {{ __(statusLabel) }}
          </span>
          <span
            v-else-if="loadingContext"
            class="skeleton-pill"
            aria-hidden="true"
          />
        </div>

        <div class="summary-actions">
          <WorkOrderPrintButton v-if="workOrder" :work-order="workOrder" />
          <button
            type="button"
            class="btn-refresh-matrix"
            :disabled="loading"
            :title="__('Stok Durumunu Yenile')"
            @click="fetchAvailability"
          >
            <span :class="{ spinning: loading }">↻</span>
            <span>{{ __("Stok Yenile") }}</span>
          </button>
        </div>
      </div>

      <div class="summary-details">
        <div class="detail-item detail-product">
          <span class="detail-label">{{ __("Üretilecek Mamul") }}</span>
          <div v-if="matchingContext" class="detail-product-val">
            <span class="product-code">{{
              matchingContext.item_code || "—"
            }}</span>
            <span
              v-if="
                matchingContext.item_name &&
                matchingContext.item_name !== matchingContext.item_code
              "
              class="product-name"
            >
              {{ matchingContext.item_name }}
            </span>
          </div>
          <div
            v-else-if="loadingContext"
            class="skeleton-stack"
            aria-hidden="true"
          >
            <span class="skeleton-line skeleton-w-md" />
            <span class="skeleton-line skeleton-w-lg" />
          </div>
          <div v-else class="detail-product-val">
            <span class="product-code">—</span>
          </div>
        </div>

        <div class="detail-item detail-qty">
          <span class="detail-label">{{ __("Hedef Miktar") }}</span>
          <div v-if="matchingContext" class="detail-qty-val">
            <div v-if="editingQty" class="qty-edit-inline">
              <input
                ref="qtyInputRef"
                type="number"
                v-model.number="tempQty"
                min="1"
                step="any"
                class="qty-edit-input"
                :disabled="savingQty"
                @keydown.enter.prevent="saveQty"
                @keydown.esc.prevent="cancelEditQty"
              />
              <span class="uom-chip">{{ targetUom }}</span>
              <button
                type="button"
                class="btn-qty-save"
                :disabled="savingQty || !tempQty || tempQty <= 0"
                :title="__('Kaydet')"
                @click="saveQty"
              >
                <span v-if="savingQty" class="btn-spinner-xs" aria-hidden="true" />
                <span v-else aria-hidden="true">✓</span>
              </button>
              <button
                type="button"
                class="btn-qty-cancel"
                :disabled="savingQty"
                :title="__('İptal')"
                @click="cancelEditQty"
              >
                ✕
              </button>
            </div>
            <template v-else>
              <strong>{{ formatQty(targetQty) }}</strong>
              <span class="uom-chip">{{ targetUom }}</span>
              <button
                v-if="!isReleased && matchingContext.docstatus === 0"
                type="button"
                class="btn-edit-qty"
                :title="__('Hedef Miktarı Düzenle')"
                @click="startEditQty"
              >
                ✏️
              </button>
            </template>
          </div>
          <div
            v-else-if="loadingContext"
            class="skeleton-qty"
            aria-hidden="true"
          >
            <span class="skeleton-line skeleton-w-sm" />
          </div>
          <div v-else class="detail-qty-val">
            <strong>—</strong>
          </div>
        </div>
      </div>

      <!-- Overall Readiness Progress Bar & Badge -->
      <div class="readiness-box">
        <div class="readiness-header">
          <span class="readiness-title">{{
            __("Genel Hammadde Hazırlık Durumu")
          }}</span>
          <span
            v-if="loading && !availability"
            class="readiness-badge badge-neutral"
          >
            {{ __("Kontrol Ediliyor…") }}
          </span>
          <span v-else-if="isFullyReady" class="readiness-badge badge-ready">
            {{ __("%{0} Hazır (Tüm bileşenler mevcut)", [readinessPercent]) }}
          </span>
          <span v-else-if="availability" class="readiness-badge badge-shortage">
            ⚠️
            {{
              __("%{0} Hazır ({1} Kalem Eksik)", [
                readinessPercent,
                shortageCount,
              ])
            }}
          </span>
        </div>

        <div class="readiness-track">
          <div
            class="readiness-fill"
            :class="{
              'fill-ready': isFullyReady,
              'fill-warning': hasShortage && readinessPercent >= 50,
              'fill-danger': hasShortage && readinessPercent < 50,
            }"
            :style="{ width: (availability ? readinessPercent : 0) + '%' }"
          />
        </div>
      </div>

      <!-- Material Availability 3-Tier Status Banner -->
      <div
        v-if="availability && !loading"
        class="availability-banner"
        :class="{
          'banner-critical': hasCriticalShortage,
          'banner-transfer': !hasCriticalShortage && canFulfillViaTransfer,
          'banner-ready': !hasCriticalShortage && !canFulfillViaTransfer,
        }"
        role="status"
      >
        <div v-if="hasCriticalShortage" class="banner-content">
          <span class="banner-icon" aria-hidden="true">⚠️</span>
          <span>
            {{
              __(
                "Kritik hammadde eksikliği mevcut. {0} kalem fabrika genelinde temin edilememiştir.",
                [criticalShortageCount]
              )
            }}
          </span>
        </div>
        <div v-else-if="canFulfillViaTransfer" class="banner-content">
          <span class="banner-icon" aria-hidden="true">ℹ️</span>
          <span>
            {{
              __(
                "Hatta eksik olan malzemeler Merkez/Diğer depolarda mevcuttur. Hat transferi yapılarak üretime hazır hale getirilebilir."
              )
            }}
          </span>
        </div>
        <div v-else class="banner-content">
          <span class="banner-icon" aria-hidden="true">✅</span>
          <span>
            {{ __("Tüm hammaddeler hatta kullanıma hazır.") }}
          </span>
        </div>
      </div>
    </section>

    <!-- Release / Status Action Bar -->
    <section v-if="matchingContext" class="panel-card action-card">
      <div v-if="isStoppedOrClosed" class="stopped-banner">
        <div class="released-info">
          <span class="released-icon" aria-hidden="true">⛔</span>
          <div>
            <strong class="stopped-title">
              {{
                __("Bu iş emri {0} durumundadır.", [__(matchingContext.status)])
              }}
            </strong>
            <p class="released-sub">
              {{
                __(
                  "Durdurulmuş veya kapatılmış iş emirleri için serbest bırakma veya operasyon teyidi yapılamaz."
                )
              }}
            </p>
          </div>
        </div>
      </div>

      <div v-else-if="isCancelled" class="stopped-banner">
        <div class="released-info">
          <span class="released-icon" aria-hidden="true">🚫</span>
          <div>
            <strong class="stopped-title">{{
              __("Bu iş emri iptal edilmiştir.")
            }}</strong>
          </div>
        </div>
      </div>

      <div v-else-if="isReleased" class="released-banner">
        <div class="released-info">
          <span class="released-icon" aria-hidden="true">✅</span>
          <div>
            <div class="released-title-row">
              <strong class="released-title">{{
                __("Bu iş emri üretime serbest bırakılmıştır.")
              }}</strong>
              <span
                v-if="matchingContext.custom_released_with_shortage"
                class="shortage-release-tag"
              >
                ⚠️ {{ __("Eksik Hammadde ile Serbest Bırakıldı") }}
              </span>
            </div>
            <p v-if="justReleased" class="released-sub">
              {{
                __(
                  "İş emri durumu güncellendi. Operasyon teyitlerini başlatmak için geçiş yapabilirsiniz."
                )
              }}
            </p>
          </div>
        </div>
        <button
          type="button"
          class="btn-switch-ops"
          @click="emit('switch-to-operations', workOrder)"
        >
          📋 {{ __("Operasyon Teyidine Geç") }}
        </button>
      </div>

      <div v-else-if="isDraft" class="draft-release-bar">
        <div class="draft-info">
          <span class="draft-badge">{{ __("Taslak İş Emri") }}</span>
          <p class="draft-hint">
            {{
              hasShortage
                ? __(
                    "Eksik hammadde bulunuyor. İsterseniz uyarıyı onaylayarak serbest bırakabilirsiniz."
                  )
                : __(
                    "Tüm bileşen stokları uygun. İş emrini üretime serbest bırakabilirsiniz."
                  )
            }}
          </p>
        </div>
        <button
          type="button"
          class="btn-release-primary"
          :disabled="loading || releasing || !availability"
          @click="handleReleaseClick"
        >
          <span v-if="releasing" class="btn-spinner" aria-hidden="true" />
          <span v-else aria-hidden="true">🚀</span>
          <span>
            {{
              releasing
                ? __("Serbest Bırakılıyor…")
                : __("İş Emrini Serbest Bırak (Release)")
            }}
          </span>
        </button>
      </div>
    </section>

    <!-- Material Availability Matrix Table -->
    <section class="panel-card matrix-card">
      <div class="matrix-header">
        <div class="matrix-title-group">
          <h3 class="matrix-title">{{ __("Hammadde Uygunluk Matrisi") }}</h3>
          <span v-if="availability" class="matrix-count">
            {{ __("{0} Bileşen", [items.length]) }}
          </span>
        </div>
      </div>

      <div v-if="loading && !availability" class="matrix-state">
        <div class="matrix-spinner" />
        <span>{{ __("Hammadde Stok Durumu Kontrol Ediliyor…") }}</span>
      </div>

      <div v-else-if="error" class="matrix-state matrix-error">
        <span>⚠️ {{ error }}</span>
        <button type="button" class="btn-retry" @click="fetchAvailability">
          {{ __("Tekrar Dene") }}
        </button>
      </div>

      <div v-else-if="items.length === 0" class="matrix-state">
        <span class="empty-icon">📦</span>
        <span>{{ __("Bu iş emri için malzeme gereksinimi bulunmuyor.") }}</span>
      </div>

      <div v-else class="table-responsive">
        <table class="matrix-table">
          <thead>
            <tr>
              <th>{{ __("Hammadde") }}</th>
              <th class="text-right">{{ __("İhtiyaç") }}</th>
              <th class="text-right">{{ __("Hatta (Tüketim Deposu)") }}</th>
              <th class="text-right">{{ __("Diğer Depolarda") }}</th>
              <th>{{ __("Karşılama Oranı") }}</th>
              <th class="text-center">{{ __("Durum") }}</th>
              <th v-if="!isReleased" class="text-center">{{ __("İşlem") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in items"
              :key="`${item.item_code}-${
                item.warehouse || item.source_warehouse || ''
              }`"
              :class="{
                'row-critical': getItemStatus(item) === 'critical_shortage',
                'row-transfer': getItemStatus(item) === 'transfer_required',
              }"
            >
              <td>
                <div class="comp-cell">
                  <div class="comp-code-line">
                    <span class="comp-code">{{ item.item_code }}</span>
                    <span
                      v-if="item.is_alternative"
                      class="alt-badge-pill"
                      :title="
                        __('Orijinal: {0}', [item.custom_original_item || ''])
                      "
                    >
                      🏷️
                      {{
                        __("Muadil (Orijinal: {0})", [
                          item.custom_original_item || "—",
                        ])
                      }}
                    </span>
                  </div>
                  <span
                    v-if="
                      getRowDescription(item) && getRowDescription(item) !== '—'
                    "
                    class="comp-desc"
                    :title="stripHtml(item.description) || item.item_name"
                  >
                    {{ getRowDescription(item) }}
                  </span>
                </div>
              </td>
              <td class="text-right num-cell">
                <span>{{ formatQty(item.required_qty) }}</span>
                <span v-if="item.stock_uom || item.uom" class="cell-uom">
                  {{ item.stock_uom || item.uom }}
                </span>
              </td>
              <td class="text-right num-cell">
                <div>
                  <span>{{
                    formatQty(item.line_available_qty ?? item.available_qty)
                  }}</span>
                  <span v-if="item.stock_uom || item.uom" class="cell-uom">
                    {{ item.stock_uom || item.uom }}
                  </span>
                </div>
                <div
                  v-if="Number(item.line_reserved_qty || 0) > 0"
                  class="reserved-subtext"
                >
                  {{
                    __("(Rezerve: {0})", [formatQty(item.line_reserved_qty)])
                  }}
                </div>
              </td>
              <td class="text-right num-cell">
                <div
                  v-if="Number(item.other_warehouses_qty || 0) > 0"
                  class="other-wh-wrapper"
                  :title="formatOtherWarehousesTooltip(item)"
                >
                  <span class="other-wh-qty">{{
                    formatQty(item.other_warehouses_qty)
                  }}</span>
                  <span v-if="item.stock_uom || item.uom" class="cell-uom">
                    {{ item.stock_uom || item.uom }}
                  </span>
                  <span
                    v-if="
                      item.other_warehouses && item.other_warehouses.length > 0
                    "
                    class="wh-info-icon"
                    aria-hidden="true"
                  >
                    🏢
                  </span>
                </div>
                <span v-else class="no-other-wh">—</span>
              </td>
              <td>
                <div class="coverage-cell">
                  <div class="mini-track">
                    <div
                      class="mini-fill"
                      :class="{
                        'mini-ok': Number(item.coverage_percent || 0) >= 100,
                        'mini-warn':
                          Number(item.coverage_percent || 0) > 0 &&
                          Number(item.coverage_percent || 0) < 100,
                        'mini-danger': Number(item.coverage_percent || 0) <= 0,
                      }"
                      :style="{
                        width:
                          Math.min(
                            100,
                            Math.max(0, Number(item.coverage_percent || 0))
                          ) + '%',
                      }"
                    />
                  </div>
                  <span class="coverage-pct"
                    >%{{ Math.round(Number(item.coverage_percent || 0)) }}</span
                  >
                </div>
              </td>
              <td class="text-center">
                <span
                  v-if="getItemStatus(item) === 'available'"
                  class="item-badge item-badge-ok"
                >
                  ✅ {{ __("Hatta Mevcut") }}
                </span>
                <span
                  v-else-if="getItemStatus(item) === 'transfer_required'"
                  class="item-badge item-badge-transfer"
                >
                  ⚠️ {{ __("Transfer Edilebilir") }}
                </span>
                <span v-else class="item-badge item-badge-critical">
                  🚫 {{ __("Fabrikada Yok") }}
                </span>
              </td>
              <td v-if="!isReleased" class="text-center">
                <div
                  v-if="
                    ((item.has_alternatives || item.is_alternative) && isDraft) ||
                    (getItemStatus(item) !== 'available' && item.has_sibling_line_stock)
                  "
                  class="alt-actions-cell"
                >
                  <template v-if="(item.has_alternatives || item.is_alternative) && isDraft">
                    <div v-if="item.is_alternative" class="alt-actions-group">
                      <button
                        type="button"
                        class="btn-alt-action btn-alt-change"
                        :title="__('Muadili Değiştir')"
                        @click="openAlternativesModal(item)"
                      >
                        🔄 {{ __("Değiştir") }}
                      </button>
                      <button
                        type="button"
                        class="btn-alt-action btn-alt-restore"
                        :title="__('Orijinal Reçete Koduna Dön')"
                        @click="restoreDirectly(item)"
                      >
                        ↩️ {{ __("Orijinal") }}
                      </button>
                    </div>
                    <button
                      v-else-if="getItemStatus(item) !== 'available'"
                      type="button"
                      class="btn-alt-action btn-alt-highlight"
                      :title="__('Onaylı Muadil Seç')"
                      @click="openAlternativesModal(item)"
                    >
                      🔄 {{ __("Muadil Seç") }}
                    </button>
                    <button
                      v-else
                      type="button"
                      class="btn-alt-action btn-alt-secondary"
                      :title="__('Onaylı Muadili İncele / Seç')"
                      @click="openAlternativesModal(item)"
                    >
                      🔄 {{ __("Muadil") }}
                    </button>
                  </template>
                  <button
                    v-if="getItemStatus(item) !== 'available' && item.has_sibling_line_stock"
                    type="button"
                    class="btn-alt-action btn-line-transfer"
                    :title="__('Kardeş Hattan Transfer Yap')"
                    @click="emit('open-line-transfers', item.warehouse || item.source_warehouse || '')"
                  >
                    🔄 {{ __("Hat Transferi") }}
                  </button>
                </div>
                <span v-else class="no-alt-text">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Shortage Force Release Confirmation Modal -->
    <Teleport to="body">
      <div
        v-if="showShortageModal"
        class="shortage-modal-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortage-modal-title"
        @click.self="closeShortageModal"
      >
        <div class="shortage-modal">
          <div class="shortage-modal-header">
            <h2 id="shortage-modal-title" class="shortage-modal-title">
              ⚠️ {{ __("Eksik Hammadde Uyarısı") }}
            </h2>
            <button
              type="button"
              class="modal-close-btn"
              :disabled="releasing"
              :aria-label="__('Kapat')"
              @click="closeShortageModal"
            >
              ×
            </button>
          </div>

          <div class="shortage-modal-body">
            <div
              v-if="releaseError"
              class="panel-alert panel-alert-danger"
              role="alert"
            >
              <div class="alert-left">
                <span aria-hidden="true">⚠️</span>
                <span>{{ releaseError }}</span>
              </div>
              <button
                type="button"
                class="alert-dismiss"
                @click="releaseError = null"
              >
                ✕
              </button>
            </div>

            <p class="shortage-modal-message">
              {{
                __("Bu iş emrinde {0} adet bileşende hammadde eksiktir.", [
                  shortageItems.length,
                ])
              }}
            </p>
            <p
              v-if="canFulfillViaTransfer"
              class="shortage-modal-transfer-note"
            >
              ℹ️
              {{
                __(
                  "Hatta eksik olan malzemeler Merkez/Diğer depolarda mevcuttur."
                )
              }}
            </p>

            <div class="shortage-list-wrap">
              <table class="shortage-list-table">
                <thead>
                  <tr>
                    <th>{{ __("Bileşen") }}</th>
                    <th class="text-right">{{ __("İhtiyaç") }}</th>
                    <th class="text-right">{{ __("Hatta Mevcut") }}</th>
                    <th class="text-right">{{ __("Eksik") }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="s in shortageItems" :key="s.item_code">
                    <td>
                      <div class="shortage-item-info">
                        <span class="shortage-item-code">{{
                          s.item_code
                        }}</span>
                        <span
                          v-if="s.item_name && s.item_name !== s.item_code"
                          class="shortage-item-name"
                        >
                          {{ s.item_name }}
                        </span>
                      </div>
                    </td>
                    <td class="text-right num-cell">
                      {{ formatQty(s.required_qty) }}
                      {{ s.stock_uom || s.uom || "" }}
                    </td>
                    <td class="text-right num-cell">
                      {{ formatQty(s.line_available_qty ?? s.available_qty) }}
                      {{ s.stock_uom || s.uom || "" }}
                    </td>
                    <td class="text-right">
                      <span class="shortage-badge-red">
                        -{{ formatQty(s.shortage_qty) }}
                        {{ s.stock_uom || s.uom || "" }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="shortage-modal-footer">
            <button
              type="button"
              class="btn-modal-cancel"
              :disabled="releasing"
              @click="closeShortageModal"
            >
              {{ __("Vazgeç") }}
            </button>
            <button
              type="button"
              class="btn-modal-force"
              :disabled="releasing"
              @click="performRelease(1)"
            >
              <span v-if="releasing" class="btn-spinner" aria-hidden="true" />
              <span>{{
                releasing
                  ? __("Serbest Bırakılıyor…")
                  : __("Yine de Serbest Bırak (Force Release)")
              }}</span>
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Item Alternatives Modal -->
    <ItemAlternativesModal
      :show="showAlternativesModal"
      :work-order="workOrder"
      :row-name="activeAltItem?.row_name || activeAltItem?.item_code || ''"
      :item-code="activeAltItem?.item_code || ''"
      :item-name="activeAltItem?.item_name || ''"
      :custom-original-item="activeAltItem?.custom_original_item || null"
      :is-alternative="Boolean(activeAltItem?.is_alternative)"
      :can-swap="activeAltItem?.can_swap ?? true"
      @close="closeAlternativesModal"
      @applied="handleAlternativeApplied"
    />
  </div>
</template>

<style scoped>
.release-panel {
  display: flex;
  flex-direction: column;
  gap: 1.15rem;
}

.panel-card {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.85rem;
  padding: 1.25rem 1.35rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

[data-theme="dark"] .panel-card {
  background: var(--ck-glass-bg, #1c2127);
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12));
}

.panel-alert {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.85rem 1.1rem;
  border-radius: 0.65rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.panel-alert-danger {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

[data-theme="dark"] .panel-alert-danger {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(248, 113, 113, 0.35);
  color: #fca5a5;
}

.alert-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.alert-dismiss {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 1rem;
  opacity: 0.7;
}

/* Summary Banner */
.summary-banner {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.summary-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.wo-identity {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.wo-chip-wrapper {
  display: inline-flex;
  align-items: center;
  background: rgba(37, 99, 235, 0.08);
  border: 1px solid rgba(37, 99, 235, 0.22);
  border-radius: 0.6rem;
  padding: 0.2rem 0.4rem 0.2rem 0.75rem;
  gap: 0.4rem;
}

.wo-badge-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 1.1rem;
  font-weight: 800;
  color: #2563eb;
  text-decoration: none;
}

.wo-badge-link:hover {
  text-decoration: underline;
}

.external-icon {
  font-size: 0.8rem;
  opacity: 0.7;
}

.btn-copy-chip {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.25rem 0.4rem;
  border-radius: 0.35rem;
  color: #2563eb;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
}

.btn-copy-chip:hover {
  background: rgba(37, 99, 235, 0.14);
}

.copied-text {
  font-size: 0.72rem;
  font-weight: 700;
  color: #16a34a;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.28rem 0.8rem;
  border-radius: 9999px;
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.status-draft {
  background: #fef3c7;
  color: #b45309;
}

.status-not-started {
  background: #f1f5f9;
  color: #475569;
}

.status-in-process {
  background: #dbeafe;
  color: #1d4ed8;
}

.status-completed {
  background: #dcfce7;
  color: #15803d;
}

.status-stopped,
.status-closed,
.status-cancelled {
  background: #fee2e2;
  color: #b91c1c;
}

[data-theme="dark"] .status-draft {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}

[data-theme="dark"] .status-not-started {
  background: rgba(148, 163, 184, 0.2);
  color: #cbd5e1;
}

[data-theme="dark"] .status-completed {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

[data-theme="dark"] .status-stopped,
[data-theme="dark"] .status-closed,
[data-theme="dark"] .status-cancelled {
  background: rgba(239, 68, 68, 0.2);
  color: #fca5a5;
}

.skeleton-pill,
.skeleton-line {
  display: inline-block;
  border-radius: 9999px;
  background: linear-gradient(
    90deg,
    rgba(148, 163, 184, 0.16) 25%,
    rgba(148, 163, 184, 0.3) 50%,
    rgba(148, 163, 184, 0.16) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.3s ease-in-out infinite;
}

.skeleton-pill {
  width: 88px;
  height: 24px;
}

.skeleton-stack {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding-top: 0.15rem;
}

.skeleton-qty {
  display: flex;
  align-items: center;
  padding-top: 0.2rem;
}

.skeleton-line {
  height: 14px;
  border-radius: 0.35rem;
}

.skeleton-w-sm {
  width: 72px;
  height: 20px;
}

.skeleton-w-md {
  width: 140px;
}

.skeleton-w-lg {
  width: 210px;
  height: 12px;
}

@keyframes skeleton-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.summary-actions {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.btn-refresh-matrix {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.75rem;
  background: var(--bg-color, #f8fafc);
  border: 1px solid var(--border-color, #cbd5e1);
  border-radius: 0.45rem;
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-muted, #475569);
  cursor: pointer;
}

.btn-refresh-matrix:hover:not(:disabled) {
  background: #e2e8f0;
  color: #0f172a;
}

.btn-refresh-matrix:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinning {
  display: inline-block;
  animation: spin 0.8s linear infinite;
}

.summary-details {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background: var(--bg-color, #f8fafc);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.65rem;
}

[data-theme="dark"] .summary-details {
  background: rgba(255, 255, 255, 0.03);
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.detail-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted, #64748b);
  letter-spacing: 0.02em;
}

.detail-product-val {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.product-code {
  font-size: 1rem;
  font-weight: 800;
  color: var(--text-color, #0f172a);
}

.product-name {
  font-size: 0.84rem;
  color: var(--text-muted, #64748b);
}

.detail-qty-val {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 1.25rem;
  font-weight: 800;
  color: var(--text-color, #0f172a);
}

.uom-chip {
  font-size: 0.74rem;
  font-weight: 700;
  padding: 0.15rem 0.5rem;
  border-radius: 0.35rem;
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
}

.btn-edit-qty {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 0.35rem;
  padding: 0.2rem 0.35rem;
  font-size: 0.9rem;
  cursor: pointer;
  line-height: 1;
  transition: all 0.15s ease-in-out;
  color: var(--text-muted, #64748b);
  opacity: 0.75;
}

.btn-edit-qty:hover {
  opacity: 1;
  background: rgba(37, 99, 235, 0.1);
  border-color: rgba(37, 99, 235, 0.25);
  transform: scale(1.05);
}

.qty-edit-inline {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: nowrap;
}

.qty-edit-input {
  width: 90px;
  padding: 0.25rem 0.5rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-color, #0f172a);
  background: var(--card-bg, #ffffff);
  border: 1.5px solid var(--primary-color, #2563eb);
  border-radius: 0.4rem;
  outline: none;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.qty-edit-input:focus {
  border-color: #1d4ed8;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25);
}

.qty-edit-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-qty-save,
.btn-qty-cancel {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 0.4rem;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  border: none;
  transition: all 0.15s ease;
}

.btn-qty-save {
  background: #16a34a;
  color: #ffffff;
}

.btn-qty-save:hover:not(:disabled) {
  background: #15803d;
  transform: translateY(-1px);
}

.btn-qty-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-qty-cancel {
  background: #f1f5f9;
  color: #64748b;
  border: 1px solid #cbd5e1;
}

.btn-qty-cancel:hover:not(:disabled) {
  background: #e2e8f0;
  color: #0f172a;
}

.btn-qty-cancel:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-spinner-xs {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
}

[data-theme="dark"] .qty-edit-input {
  background: #1e293b;
  color: #f8fafc;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

[data-theme="dark"] .btn-edit-qty {
  color: #94a3b8;
}

[data-theme="dark"] .btn-edit-qty:hover {
  background: rgba(59, 130, 246, 0.2);
  border-color: rgba(59, 130, 246, 0.4);
}

[data-theme="dark"] .btn-qty-cancel {
  background: #334155;
  color: #cbd5e1;
  border-color: #475569;
}

[data-theme="dark"] .btn-qty-cancel:hover:not(:disabled) {
  background: #475569;
  color: #ffffff;
}

/* Readiness Progress */
.readiness-box {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.readiness-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.readiness-title {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted, #64748b);
}

.readiness-badge {
  font-size: 0.78rem;
  font-weight: 700;
  padding: 0.2rem 0.65rem;
  border-radius: 9999px;
}

.badge-neutral {
  background: #f1f5f9;
  color: #475569;
}

.badge-ready {
  background: #dcfce7;
  color: #15803d;
}

.badge-shortage {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
}

[data-theme="dark"] .badge-ready {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

[data-theme="dark"] .badge-shortage {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(248, 113, 113, 0.35);
  color: #fca5a5;
}

.readiness-track {
  height: 10px;
  background: #e2e8f0;
  border-radius: 9999px;
  overflow: hidden;
}

[data-theme="dark"] .readiness-track {
  background: rgba(255, 255, 255, 0.1);
}

.readiness-fill {
  height: 100%;
  border-radius: 9999px;
  transition: width 0.35s ease;
}

.fill-ready {
  background: linear-gradient(90deg, #16a34a 0%, #22c55e 100%);
}

.fill-warning {
  background: linear-gradient(90deg, #d97706 0%, #f59e0b 100%);
}

.fill-danger {
  background: linear-gradient(90deg, #dc2626 0%, #ef4444 100%);
}

/* Availability 3-Tier Status Banner */
.availability-banner {
  display: flex;
  align-items: center;
  padding: 0.85rem 1.15rem;
  border-radius: 0.65rem;
  font-size: 0.86rem;
  font-weight: 600;
  margin-top: 0.35rem;
}

.banner-content {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.banner-icon {
  font-size: 1.15rem;
  line-height: 1;
}

.banner-ready {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
}

.banner-transfer {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
}

.banner-critical {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

[data-theme="dark"] .banner-ready {
  background: rgba(34, 197, 94, 0.16);
  border-color: rgba(74, 222, 128, 0.3);
  color: #86efac;
}

[data-theme="dark"] .banner-transfer {
  background: rgba(245, 158, 11, 0.16);
  border-color: rgba(251, 191, 36, 0.3);
  color: #fcd34d;
}

[data-theme="dark"] .banner-critical {
  background: rgba(239, 68, 68, 0.16);
  border-color: rgba(248, 113, 113, 0.3);
  color: #fca5a5;
}

/* Action Card */
.action-card {
  padding: 1rem 1.35rem;
}

.released-banner,
.draft-release-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.released-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.released-icon {
  font-size: 1.4rem;
}

.released-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.released-title {
  display: block;
  font-size: 0.92rem;
  color: #15803d;
}

[data-theme="dark"] .released-title {
  color: #4ade80;
}

.shortage-release-tag {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.14rem 0.55rem;
  border-radius: 9999px;
  background: #fef3c7;
  color: #b45309;
}

[data-theme="dark"] .shortage-release-tag {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}

.stopped-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.stopped-title {
  display: block;
  font-size: 0.92rem;
  color: #b91c1c;
}

[data-theme="dark"] .stopped-title {
  color: #fca5a5;
}

.released-sub {
  margin: 0.15rem 0 0;
  font-size: 0.8rem;
  color: var(--text-muted, #64748b);
}

.btn-switch-ops {
  padding: 0.6rem 1.15rem;
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.86rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.15s, box-shadow 0.15s;
}

.btn-switch-ops:hover {
  background: #1d4ed8;
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.25);
}

.draft-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.draft-badge {
  align-self: flex-start;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 0.12rem 0.5rem;
  border-radius: 0.35rem;
  background: #fef3c7;
  color: #b45309;
}

.draft-hint {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-muted, #64748b);
}

.btn-release-primary {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1.25rem;
  background: #16a34a;
  color: #ffffff;
  border: none;
  border-radius: 0.55rem;
  font-size: 0.88rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.15s, box-shadow 0.15s;
}

.btn-release-primary:hover:not(:disabled) {
  background: #15803d;
  box-shadow: 0 4px 12px rgba(22, 163, 74, 0.28);
}

.btn-release-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Matrix Table */
.matrix-card {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.matrix-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.matrix-title-group {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.matrix-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 800;
  color: var(--text-color, #0f172a);
}

.matrix-count {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.15rem 0.55rem;
  border-radius: 9999px;
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
}

.matrix-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 2.5rem 1rem;
  color: var(--text-muted, #64748b);
  font-size: 0.88rem;
  text-align: center;
}

.matrix-error {
  color: #b91c1c;
}

.matrix-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(37, 99, 235, 0.2);
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.btn-retry {
  padding: 0.4rem 0.85rem;
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 0.45rem;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
}

.empty-icon {
  font-size: 2rem;
}

.table-responsive {
  width: 100%;
  overflow-x: auto;
}

.matrix-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.matrix-table th {
  text-align: left;
  padding: 0.65rem 0.75rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  color: var(--text-muted, #64748b);
  background: var(--bg-color, #f8fafc);
  border-bottom: 1.5px solid var(--border-color, #e2e8f0);
  white-space: nowrap;
}

[data-theme="dark"] .matrix-table th {
  background: rgba(255, 255, 255, 0.04);
}

.matrix-table td {
  padding: 0.7rem 0.75rem;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  color: var(--text-color, #0f172a);
  vertical-align: middle;
}

.matrix-table tbody tr:hover {
  background: rgba(37, 99, 235, 0.03);
}

.matrix-table tbody tr.row-shortage {
  background: rgba(239, 68, 68, 0.03);
}

.matrix-table tbody tr.row-critical {
  background: rgba(239, 68, 68, 0.05);
}

.matrix-table tbody tr.row-transfer {
  background: rgba(245, 158, 11, 0.05);
}

.text-right {
  text-align: right !important;
}

.text-center {
  text-align: center !important;
}

.comp-cell {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.comp-code-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.alt-badge-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.12rem 0.5rem;
  border-radius: 9999px;
  background: #ede9fe;
  color: #6d28d9;
  border: 1px solid #ddd6fe;
}

[data-theme="dark"] .alt-badge-pill {
  background: rgba(139, 92, 246, 0.2);
  border-color: rgba(167, 139, 250, 0.35);
  color: #c4b5fd;
}

.alt-actions-cell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.btn-line-transfer {
  background: #fffbeb;
  border-color: #fde68a;
  color: #b45309;
}

.btn-line-transfer:hover {
  background: #fef3c7;
}

[data-theme="dark"] .btn-line-transfer {
  background: rgba(245, 158, 11, 0.16);
  border-color: rgba(251, 191, 36, 0.35);
  color: #fcd34d;
}

[data-theme="dark"] .btn-line-transfer:hover {
  background: rgba(245, 158, 11, 0.25);
}

.alt-actions-group {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.btn-alt-action {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.6rem;
  border-radius: 0.4rem;
  font-size: 0.74rem;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.btn-alt-highlight {
  background: #2563eb;
  color: #ffffff;
  border-color: #2563eb;
}

.btn-alt-highlight:hover {
  background: #1d4ed8;
  border-color: #1d4ed8;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25);
}

.btn-alt-secondary {
  background: var(--bg-color, #f8fafc);
  border-color: var(--border-color, #cbd5e1);
  color: var(--text-color, #0f172a);
}

.btn-alt-secondary:hover {
  background: #e2e8f0;
}

[data-theme="dark"] .btn-alt-secondary {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.15);
  color: #f8fafc;
}

[data-theme="dark"] .btn-alt-secondary:hover {
  background: rgba(255, 255, 255, 0.1);
}

.btn-alt-change {
  background: rgba(37, 99, 235, 0.1);
  border-color: rgba(37, 99, 235, 0.25);
  color: #2563eb;
}

.btn-alt-change:hover {
  background: rgba(37, 99, 235, 0.2);
}

[data-theme="dark"] .btn-alt-change {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.3);
  color: #93c5fd;
}

.btn-alt-restore {
  background: #fef2f2;
  border-color: #fecaca;
  color: #dc2626;
}

.btn-alt-restore:hover {
  background: #fee2e2;
}

[data-theme="dark"] .btn-alt-restore {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(248, 113, 113, 0.3);
  color: #fca5a5;
}

.no-alt-text {
  color: var(--text-muted, #94a3b8);
  font-size: 0.8rem;
}

.comp-code {
  font-weight: 700;
  color: #2563eb;
  white-space: nowrap;
}

.comp-desc {
  display: inline-block;
  max-width: 240px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-muted, #475569);
  font-size: 0.76rem;
}

.comp-warehouse {
  font-size: 0.78rem;
  color: var(--text-muted, #64748b);
  white-space: nowrap;
}

.num-cell {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  white-space: nowrap;
}

.cell-uom {
  font-size: 0.72rem;
  font-weight: 500;
  color: var(--text-muted, #64748b);
  margin-left: 0.2rem;
}

.reserved-subtext {
  font-size: 0.72rem;
  color: var(--text-muted, #64748b);
  font-weight: 500;
  margin-top: 0.15rem;
}

.other-wh-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  cursor: help;
  padding: 0.1rem 0.35rem;
  border-radius: 0.35rem;
  transition: background-color 0.15s ease;
}

.other-wh-wrapper:hover {
  background: rgba(37, 99, 235, 0.08);
}

.wh-info-icon {
  font-size: 0.76rem;
  opacity: 0.8;
}

.no-other-wh {
  color: var(--text-muted, #94a3b8);
}

.coverage-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 110px;
}

.mini-track {
  flex: 1;
  height: 6px;
  background: #e2e8f0;
  border-radius: 9999px;
  overflow: hidden;
}

[data-theme="dark"] .mini-track {
  background: rgba(255, 255, 255, 0.12);
}

.mini-fill {
  height: 100%;
  border-radius: 9999px;
}

.mini-ok {
  background: #16a34a;
}

.mini-warn {
  background: #f59e0b;
}

.mini-danger {
  background: #ef4444;
}

.coverage-pct {
  font-size: 0.76rem;
  font-weight: 700;
  min-width: 40px;
  text-align: right;
}

.item-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.18rem 0.55rem;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 700;
  white-space: nowrap;
}

.item-badge-ok {
  background: #dcfce7;
  color: #15803d;
}

.item-badge-warn,
.item-badge-transfer {
  background: #fef3c7;
  color: #b45309;
}

.item-badge-critical {
  background: #fee2e2;
  color: #b91c1c;
}

[data-theme="dark"] .item-badge-ok {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

[data-theme="dark"] .item-badge-warn,
[data-theme="dark"] .item-badge-transfer {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}

[data-theme="dark"] .item-badge-critical {
  background: rgba(239, 68, 68, 0.2);
  color: #fca5a5;
}

.shortage-val {
  color: #dc2626;
  font-weight: 800;
}

[data-theme="dark"] .shortage-val {
  color: #f87171;
}

.no-shortage {
  color: var(--text-muted, #94a3b8);
}

.shortage-modal-transfer-note {
  margin: -0.35rem 0 0;
  font-size: 0.82rem;
  font-weight: 600;
  color: #b45309;
}

[data-theme="dark"] .shortage-modal-transfer-note {
  color: #fbbf24;
}

/* Shortage Modal */
.shortage-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1060;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.shortage-modal {
  width: 100%;
  max-width: 640px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: var(--card-bg, #ffffff);
  color: var(--text-color, #0f172a);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.85rem;
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.24);
  overflow: hidden;
}

[data-theme="dark"] .shortage-modal {
  background: var(--ck-glass-bg, #1c2127);
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14));
}

.shortage-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  background: #fef2f2;
  border-bottom: 1px solid #fecaca;
}

[data-theme="dark"] .shortage-modal-header {
  background: rgba(239, 68, 68, 0.16);
  border-bottom-color: rgba(248, 113, 113, 0.3);
}

.shortage-modal-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 800;
  color: #991b1b;
}

[data-theme="dark"] .shortage-modal-title {
  color: #fca5a5;
}

.modal-close-btn {
  background: transparent;
  border: none;
  font-size: 1.35rem;
  line-height: 1;
  color: inherit;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
}

.shortage-modal-body {
  padding: 1.2rem 1.25rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.shortage-modal-message {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-color, #0f172a);
}

.shortage-list-wrap {
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.6rem;
  overflow: hidden;
}

.shortage-list-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.shortage-list-table th {
  text-align: left;
  padding: 0.55rem 0.75rem;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  background: var(--bg-color, #f8fafc);
  color: var(--text-muted, #64748b);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

.shortage-list-table td {
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

.shortage-list-table tbody tr:last-child td {
  border-bottom: none;
}

.shortage-item-info {
  display: flex;
  flex-direction: column;
}

.shortage-item-code {
  font-weight: 700;
  color: var(--text-color, #0f172a);
}

.shortage-item-name {
  font-size: 0.74rem;
  color: var(--text-muted, #64748b);
}

.shortage-badge-red {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  font-weight: 800;
  font-size: 0.76rem;
}

[data-theme="dark"] .shortage-badge-red {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(248, 113, 113, 0.35);
  color: #fca5a5;
}

.shortage-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.65rem;
  padding: 0.95rem 1.25rem;
  border-top: 1px solid var(--border-color, #e2e8f0);
  background: var(--bg-color, #f8fafc);
}

[data-theme="dark"] .shortage-modal-footer {
  background: rgba(255, 255, 255, 0.03);
}

.btn-modal-cancel {
  padding: 0.55rem 1rem;
  border-radius: 0.5rem;
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #cbd5e1);
  color: var(--text-muted, #475569);
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
}

.btn-modal-force {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.55rem 1.05rem;
  border-radius: 0.5rem;
  background: #dc2626;
  border: 1px solid #dc2626;
  color: #ffffff;
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
}

.btn-modal-force:hover:not(:disabled) {
  background: #b91c1c;
}

.btn-modal-force:disabled,
.btn-modal-cancel:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
