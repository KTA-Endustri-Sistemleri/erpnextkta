<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import type {
  ItemAlternativeOption,
  WorkOrderItemAlternativesResponse,
} from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    show: boolean;
    workOrder: string;
    rowName: string;
    itemCode: string;
    itemName?: string;
    customOriginalItem?: string | null;
    isAlternative?: boolean;
    canSwap?: boolean;
  }>(),
  {
    itemName: "",
    customOriginalItem: null,
    isAlternative: false,
    canSwap: true,
  }
);

const emit = defineEmits<{
  (e: "close"): void;
  (e: "applied", updatedAvailability: any): void;
}>();

const loading = ref<boolean>(false);
const applying = ref<boolean>(false);
const activeItemCode = ref<string | null>(null);
const error = ref<string | null>(null);
const alternativesData = ref<WorkOrderItemAlternativesResponse | null>(null);

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

function formatQty(value?: number | null): string {
  const num = Number(value ?? 0);
  if (Number.isNaN(num)) return "0";
  return Number.isInteger(num) ? String(num) : String(Number(num.toFixed(3)));
}

const canSwapEffectively = computed<boolean>(() => {
  if (
    alternativesData.value &&
    typeof alternativesData.value.can_swap === "boolean"
  ) {
    return alternativesData.value.can_swap;
  }
  return props.canSwap ?? true;
});

const alternatives = computed<ItemAlternativeOption[]>(() => {
  return alternativesData.value?.alternatives || [];
});

async function fetchAlternatives() {
  if (!props.show || !props.workOrder || !props.rowName) {
    return;
  }
  loading.value = true;
  error.value = null;

  try {
    const res = await callFrappe<WorkOrderItemAlternativesResponse>(
      "erpnextkta.kta_shopfloor.api.get_work_order_alternatives",
      {
        work_order: props.workOrder,
        row_name: props.rowName,
      }
    );
    alternativesData.value = res || null;
  } catch (err: any) {
    console.error("get_work_order_alternatives error:", err);
    error.value = extractFrappeError(
      err,
      __("Alternatifler yüklenirken bir hata oluştu.")
    );
    alternativesData.value = null;
  } finally {
    loading.value = false;
  }
}

async function selectAlternative(opt: ItemAlternativeOption) {
  if (
    applying.value ||
    !canSwapEffectively.value ||
    opt.item_code === props.itemCode
  )
    return;
  applying.value = true;
  error.value = null;
  activeItemCode.value = opt.item_code;

  try {
    const updatedAvailability = await callFrappe(
      "erpnextkta.kta_shopfloor.api.set_work_order_alternative",
      {
        work_order: props.workOrder,
        row_name: props.rowName,
        alternative_item_code: opt.item_code,
      }
    );
    (window as any).frappe?.show_alert?.({
      message: __('"{0}" alternatifi iş emrine başarıyla atandı.', [
        opt.item_code,
      ]),
      indicator: "green",
    });
    emit("applied", updatedAvailability);
    emit("close");
  } catch (err: any) {
    console.error("set_work_order_alternative error:", err);
    error.value = extractFrappeError(
      err,
      __("Alternatif atanırken bir hata oluştu.")
    );
  } finally {
    applying.value = false;
    activeItemCode.value = null;
  }
}

async function restoreOriginal() {
  if (applying.value || !canSwapEffectively.value) return;
  applying.value = true;
  error.value = null;

  try {
    const updatedAvailability = await callFrappe(
      "erpnextkta.kta_shopfloor.api.restore_work_order_original",
      {
        work_order: props.workOrder,
        row_name: props.rowName,
      }
    );
    (window as any).frappe?.show_alert?.({
      message: __("Orijinal reçete hammaddesi ({0}) geri yüklendi.", [
        props.customOriginalItem || "",
      ]),
      indicator: "green",
    });
    emit("applied", updatedAvailability);
    emit("close");
  } catch (err: any) {
    console.error("restore_work_order_original error:", err);
    error.value = extractFrappeError(
      err,
      __("Orijinal hammaddeye dönülürken bir hata oluştu.")
    );
  } finally {
    applying.value = false;
  }
}

function handleClose() {
  if (!applying.value) {
    emit("close");
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === "Escape" && props.show) {
    e.preventDefault();
    handleClose();
  }
}

watch(
  () => [props.show, props.workOrder, props.rowName],
  ([showVal]) => {
    if (showVal) {
      fetchAlternatives();
    } else {
      error.value = null;
      alternativesData.value = null;
      activeItemCode.value = null;
    }
  }
);

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
  if (props.show) {
    fetchAlternatives();
  }
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeydown);
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="alt-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="alt-modal-title"
      @click.self="handleClose"
    >
      <div class="alt-modal">
        <!-- Header -->
        <div class="alt-modal-header">
          <div class="alt-header-title-group">
            <span class="alt-header-icon" aria-hidden="true">🔀</span>
            <div>
              <h2 id="alt-modal-title" class="alt-modal-title">
                {{ __("Alternatif Hammadde Seçimi") }}
              </h2>
              <span class="alt-wo-badge">{{ workOrder }}</span>
            </div>
          </div>
          <button
            type="button"
            class="alt-close-btn"
            :disabled="applying"
            :aria-label="__('Kapat')"
            @click="handleClose"
          >
            ✕
          </button>
        </div>

        <!-- Subheader: Current Item Info -->
        <div class="alt-item-banner">
          <div class="alt-item-info">
            <span class="alt-item-label">{{ __("Mevcut Kalem:") }}</span>
            <strong class="alt-item-code">{{ itemCode }}</strong>
            <span
              v-if="itemName && itemName !== itemCode"
              class="alt-item-name"
            >
              ({{ itemName }})
            </span>
          </div>

          <div v-if="isAlternative" class="alt-original-tag">
            <span>🏷️</span>
            <span>
              {{
                __("Şu an muadil kullanılıyor (Orijinal: {0})", [
                  customOriginalItem || "—",
                ])
              }}
            </span>
          </div>
        </div>

        <!-- Body -->
        <div class="alt-modal-body">
          <!-- Error banner -->
          <div v-if="error" class="alt-alert alt-alert-danger" role="alert">
            <div class="alt-alert-left">
              <span aria-hidden="true">⚠️</span>
              <span>{{ error }}</span>
            </div>
            <button
              v-if="!applying"
              type="button"
              class="alt-btn-retry"
              @click="fetchAlternatives"
            >
              {{ __("Tekrar Dene") }}
            </button>
          </div>

          <!-- Loading state -->
          <div v-if="loading" class="alt-state">
            <div class="alt-spinner" />
            <span>{{ __("Onaylı alternatifler yükleniyor…") }}</span>
          </div>

          <!-- Empty state -->
          <div
            v-else-if="alternatives.length === 0"
            class="alt-state alt-empty"
          >
            <span class="alt-empty-icon" aria-hidden="true">📦</span>
            <span class="alt-empty-msg">
              {{
                __("Bu hammadde için tanımlı onaylı bir alternatif bulunmuyor.")
              }}
            </span>
          </div>

          <!-- Alternatives Table -->
          <div v-else class="alt-table-responsive">
            <table class="alt-table">
              <thead>
                <tr>
                  <th>{{ __("Alternatif Kodu & Adı") }}</th>
                  <th class="text-right">{{ __("Hatta Stok") }}</th>
                  <th class="text-right">{{ __("Diğer Depolarda") }}</th>
                  <th class="text-center">{{ __("Eylem") }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="opt in alternatives"
                  :key="opt.item_code"
                  :class="{
                    'row-active': opt.item_code === itemCode,
                  }"
                >
                  <!-- Alternatif Kodu & Adı -->
                  <td>
                    <div class="alt-comp-cell">
                      <div class="alt-comp-header">
                        <strong class="alt-comp-code">{{
                          opt.item_code
                        }}</strong>
                        <span
                          v-if="opt.two_way"
                          class="badge-twoway"
                          :title="__('Çift Yönlü Muadil')"
                        >
                          ⇄ {{ __("Çift Yönlü") }}
                        </span>
                      </div>
                      <span
                        v-if="opt.item_name && opt.item_name !== opt.item_code"
                        class="alt-comp-name"
                      >
                        {{ opt.item_name }}
                      </span>
                    </div>
                  </td>

                  <!-- Hatta Stok -->
                  <td class="text-right alt-num-cell">
                    <span
                      :class="{
                        'qty-avail': Number(opt.line_available_qty) > 0,
                        'qty-zero': Number(opt.line_available_qty) <= 0,
                      }"
                    >
                      {{ formatQty(opt.line_available_qty) }}
                    </span>
                    <span v-if="opt.stock_uom" class="alt-uom">{{
                      opt.stock_uom
                    }}</span>
                  </td>

                  <!-- Diğer Depolarda -->
                  <td class="text-right alt-num-cell">
                    <span
                      :class="{
                        'qty-avail': Number(opt.other_warehouses_qty) > 0,
                        'qty-zero': Number(opt.other_warehouses_qty) <= 0,
                      }"
                    >
                      {{ formatQty(opt.other_warehouses_qty) }}
                    </span>
                    <span v-if="opt.stock_uom" class="alt-uom">{{
                      opt.stock_uom
                    }}</span>
                  </td>

                  <!-- Eylem Butonu -->
                  <td class="text-center">
                    <span
                      v-if="opt.item_code === itemCode"
                      class="btn-selected-badge"
                    >
                      ✅ {{ __("Seçili") }}
                    </span>
                    <button
                      v-else
                      type="button"
                      class="btn-select-alt"
                      :disabled="applying || !canSwapEffectively"
                      @click="selectAlternative(opt)"
                    >
                      <span
                        v-if="applying && activeItemCode === opt.item_code"
                        class="btn-spinner-sm"
                        aria-hidden="true"
                      />
                      <span>
                        {{
                          applying && activeItemCode === opt.item_code
                            ? __("Seçiliyor…")
                            : __("Muadili Seç")
                        }}
                      </span>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Footer -->
        <div class="alt-modal-footer">
          <div class="alt-footer-left">
            <button
              v-if="isAlternative && canSwapEffectively"
              type="button"
              class="btn-restore-orig"
              :disabled="applying"
              @click="restoreOriginal"
            >
              <span
                v-if="applying && !activeItemCode"
                class="btn-spinner-sm"
                aria-hidden="true"
              />
              <span v-else aria-hidden="true">↩️</span>
              <span>
                {{
                  applying && !activeItemCode
                    ? __("Geri Yükleniyor…")
                    : __("Orijinal Reçete Koduna Dön")
                }}
              </span>
            </button>
          </div>

          <div class="alt-footer-right">
            <button
              type="button"
              class="btn-alt-cancel"
              :disabled="applying"
              @click="handleClose"
            >
              {{ __("Kapat") }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.alt-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1065;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  box-sizing: border-box;
}

.alt-modal {
  width: 100%;
  max-width: 680px;
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

[data-theme="dark"] .alt-modal {
  background: var(--ck-glass-bg, #1c2127);
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14));
}

.alt-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  background: var(--bg-color, #f8fafc);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

[data-theme="dark"] .alt-modal-header {
  background: rgba(255, 255, 255, 0.03);
  border-bottom-color: rgba(255, 255, 255, 0.12);
}

.alt-header-title-group {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.alt-header-icon {
  font-size: 1.35rem;
  line-height: 1;
}

.alt-modal-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 800;
  color: var(--text-color, #0f172a);
}

.alt-wo-badge {
  font-size: 0.72rem;
  font-weight: 700;
  color: #2563eb;
  padding: 0.1rem 0.45rem;
  border-radius: 0.35rem;
  background: rgba(37, 99, 235, 0.08);
  margin-top: 0.15rem;
  display: inline-block;
}

.alt-close-btn {
  background: transparent;
  border: none;
  font-size: 1.2rem;
  line-height: 1;
  color: var(--text-muted, #64748b);
  cursor: pointer;
  padding: 0.25rem 0.45rem;
  border-radius: 0.35rem;
  transition: background-color 0.15s, color 0.15s;
}

.alt-close-btn:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.18);
  color: var(--text-color, #0f172a);
}

/* Subheader item banner */
.alt-item-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.65rem;
  padding: 0.75rem 1.25rem;
  background: #f1f5f9;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

[data-theme="dark"] .alt-item-banner {
  background: rgba(255, 255, 255, 0.05);
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

.alt-item-info {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
}

.alt-item-label {
  color: var(--text-muted, #64748b);
  font-weight: 600;
}

.alt-item-code {
  color: #2563eb;
  font-weight: 800;
}

.alt-item-name {
  color: var(--text-muted, #475569);
  font-size: 0.8rem;
}

.alt-original-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.76rem;
  font-weight: 700;
  padding: 0.2rem 0.65rem;
  border-radius: 9999px;
  background: #ede9fe;
  color: #6d28d9;
  border: 1px solid #ddd6fe;
}

[data-theme="dark"] .alt-original-tag {
  background: rgba(139, 92, 246, 0.2);
  border-color: rgba(167, 139, 250, 0.35);
  color: #c4b5fd;
}

/* Body */
.alt-modal-body {
  padding: 1.15rem 1.25rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.alt-alert {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 0.95rem;
  border-radius: 0.55rem;
  font-size: 0.82rem;
  font-weight: 600;
}

.alt-alert-danger {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

[data-theme="dark"] .alt-alert-danger {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(248, 113, 113, 0.35);
  color: #fca5a5;
}

.alt-alert-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.alt-btn-retry {
  padding: 0.25rem 0.6rem;
  border-radius: 0.35rem;
  background: #2563eb;
  color: #ffffff;
  border: none;
  font-size: 0.75rem;
  font-weight: 700;
  cursor: pointer;
}

.alt-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 2.2rem 1rem;
  color: var(--text-muted, #64748b);
  font-size: 0.86rem;
  text-align: center;
}

.alt-spinner {
  width: 26px;
  height: 26px;
  border: 3px solid rgba(37, 99, 235, 0.2);
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: alt-spin 0.8s linear infinite;
}

.alt-empty-icon {
  font-size: 2rem;
}

.alt-empty-msg {
  font-weight: 600;
}

/* Table */
.alt-table-responsive {
  width: 100%;
  overflow-x: auto;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.6rem;
}

.alt-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.alt-table th {
  text-align: left;
  padding: 0.6rem 0.75rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  color: var(--text-muted, #64748b);
  background: var(--bg-color, #f8fafc);
  border-bottom: 1.5px solid var(--border-color, #e2e8f0);
  white-space: nowrap;
}

[data-theme="dark"] .alt-table th {
  background: rgba(255, 255, 255, 0.04);
}

.alt-table td {
  padding: 0.65rem 0.75rem;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  color: var(--text-color, #0f172a);
  vertical-align: middle;
}

.alt-table tbody tr:last-child td {
  border-bottom: none;
}

.alt-table tbody tr:hover {
  background: rgba(37, 99, 235, 0.03);
}

.alt-table tbody tr.row-active {
  background: rgba(34, 197, 94, 0.05);
}

.text-right {
  text-align: right !important;
}

.text-center {
  text-align: center !important;
}

.alt-comp-cell {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.alt-comp-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.alt-comp-code {
  color: #2563eb;
  font-weight: 700;
  white-space: nowrap;
}

.alt-comp-name {
  font-size: 0.74rem;
  color: var(--text-muted, #64748b);
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.badge-twoway {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 9999px;
  background: #fef3c7;
  color: #b45309;
}

[data-theme="dark"] .badge-twoway {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}

.alt-num-cell {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  white-space: nowrap;
}

.qty-avail {
  color: #15803d;
  font-weight: 700;
}

.qty-zero {
  color: var(--text-muted, #94a3b8);
}

[data-theme="dark"] .qty-avail {
  color: #4ade80;
}

.alt-uom {
  font-size: 0.72rem;
  color: var(--text-muted, #64748b);
  margin-left: 0.2rem;
}

.btn-selected-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.65rem;
  border-radius: 0.45rem;
  font-size: 0.75rem;
  font-weight: 700;
  background: #dcfce7;
  color: #15803d;
}

[data-theme="dark"] .btn-selected-badge {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.btn-select-alt {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.8rem;
  border-radius: 0.45rem;
  background: #2563eb;
  color: #ffffff;
  border: none;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.15s, box-shadow 0.15s;
}

.btn-select-alt:hover:not(:disabled) {
  background: #1d4ed8;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.3);
}

.btn-select-alt:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Footer */
.alt-modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.85rem 1.25rem;
  border-top: 1px solid var(--border-color, #e2e8f0);
  background: var(--bg-color, #f8fafc);
}

[data-theme="dark"] .alt-modal-footer {
  background: rgba(255, 255, 255, 0.03);
}

.alt-footer-left,
.alt-footer-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-restore-orig {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.45rem 0.85rem;
  border-radius: 0.45rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.15s;
}

.btn-restore-orig:hover:not(:disabled) {
  background: #fee2e2;
}

.btn-restore-orig:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

[data-theme="dark"] .btn-restore-orig {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(248, 113, 113, 0.3);
  color: #fca5a5;
}

.btn-alt-cancel {
  padding: 0.45rem 0.95rem;
  border-radius: 0.45rem;
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #cbd5e1);
  color: var(--text-muted, #475569);
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
}

.btn-alt-cancel:hover:not(:disabled) {
  background: #f1f5f9;
}

.btn-spinner-sm {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: alt-spin 0.75s linear infinite;
}

@keyframes alt-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
