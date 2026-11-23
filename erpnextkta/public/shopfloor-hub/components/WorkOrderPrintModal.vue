<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import type { WorkOrderPrintFormatOption, WorkOrderPrintOptionsResponse } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);
const PRINT_FORMAT_STORAGE_KEY = "kta_shopfloor_wo_print_format";

const props = defineProps<{ show: boolean; workOrder: string }>();
const emit = defineEmits<{ (e: "close"): void }>();

const loading = ref<boolean>(false);
const error = ref<string | null>(null);
const popupError = ref<string | null>(null);
const options = ref<WorkOrderPrintOptionsResponse | null>(null);
const selectedFormat = ref<string>("");
const useLetterhead = ref<boolean>(false);
const selectedLetterHead = ref<string>("");
const iframeLoading = ref<boolean>(false);
let latestRequestId = 0;

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
            try { return JSON.parse(item)?.message || item; } catch { return item; }
          })
          .filter(Boolean);
        if (msgs.length > 0) return msgs.join(" ");
      }
    } catch { /* fallback below */ }
  }
  return err.message || fallback;
}

function callFrappe<T = any>(method: string, args: Record<string, any> = {}): Promise<T> {
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

function readStoredFormat(): string {
  try { return localStorage.getItem(PRINT_FORMAT_STORAGE_KEY) || ""; } catch { return ""; }
}

function saveStoredFormat(formatName: string) {
  try { if (formatName) localStorage.setItem(PRINT_FORMAT_STORAGE_KEY, formatName); } catch { /* ignore */ }
}

async function fetchPrintOptions() {
  if (!props.show || !props.workOrder) return;
  const reqId = ++latestRequestId;
  loading.value = true;
  error.value = null;
  popupError.value = null;
  options.value = null;
  iframeLoading.value = false;

  try {
    const data = await callFrappe<WorkOrderPrintOptionsResponse>(
      "erpnextkta.kta_shopfloor.api.get_work_order_print_options",
      { work_order: props.workOrder }
    );
    if (reqId !== latestRequestId || !props.show) return;
    if (!data) throw new Error(__("Yazdırma seçenekleri alınamadı."));
    options.value = data;

    const formats = data.print_formats || [];
    const saved = readStoredFormat();
    selectedFormat.value =
      saved && formats.some((f) => f.name === saved)
        ? saved
        : data.default_print_format || formats[0]?.name || "";

    const letterHeads = data.letter_heads || [];
    useLetterhead.value = Boolean(data.with_letterhead && letterHeads.length > 0);
    const hasDefaultLh = Boolean(
      data.default_letter_head && letterHeads.some((lh) => lh.name === data.default_letter_head)
    );
    selectedLetterHead.value = hasDefaultLh ? data.default_letter_head : (letterHeads[0]?.name || "");
  } catch (err: any) {
    if (reqId !== latestRequestId || !props.show) return;
    error.value = extractFrappeError(err, __("Yazdırma seçenekleri alınamadı."));
  } finally {
    if (reqId === latestRequestId) loading.value = false;
  }
}

watch(
  () => [props.show, props.workOrder],
  ([isOpen]) => {
    if (isOpen) {
      fetchPrintOptions();
    } else {
      latestRequestId += 1;
      popupError.value = null;
      iframeLoading.value = false;
    }
  },
  { immediate: true }
);

const selectedFormatObj = computed<WorkOrderPrintFormatOption | null>(() => {
  if (!options.value?.print_formats?.length) return null;
  return options.value.print_formats.find((f) => f.name === selectedFormat.value) || null;
});

const isRawPrinting = computed<boolean>(() => Boolean(selectedFormatObj.value?.raw_printing));

const canPrintActions = computed<boolean>(() =>
  Boolean(options.value?.can_print && selectedFormat.value && !loading.value && !error.value)
);

function buildPrintUrl(triggerPrint: boolean): string {
  const selectedLang = selectedFormatObj.value?.default_print_language || "";
  const letterhead = useLetterhead.value ? selectedLetterHead.value : "";
  const noLetterhead = useLetterhead.value && selectedLetterHead.value ? "0" : "1";
  return (
    `/printview?doctype=${encodeURIComponent("Work Order")}` +
    `&name=${encodeURIComponent(props.workOrder)}` +
    `&format=${encodeURIComponent(selectedFormat.value)}` +
    `&no_letterhead=${noLetterhead}&letterhead=${encodeURIComponent(letterhead)}` +
    `&settings=${encodeURIComponent("{}")}` +
    `${triggerPrint ? "&trigger_print=1" : ""}` +
    `${selectedLang ? "&_lang=" + encodeURIComponent(selectedLang) : ""}`
  );
}

function buildPdfUrl(): string {
  const selectedLang = selectedFormatObj.value?.default_print_language || "";
  const letterhead = useLetterhead.value ? selectedLetterHead.value : "";
  if (selectedFormatObj.value?.print_format_builder_beta) {
    return (
      `/api/method/frappe.utils.weasyprint.download_pdf?doctype=${encodeURIComponent("Work Order")}` +
      `&name=${encodeURIComponent(props.workOrder)}` +
      `&print_format=${encodeURIComponent(selectedFormat.value)}&letterhead=${encodeURIComponent(letterhead)}`
    );
  }
  const noLetterhead = useLetterhead.value && selectedLetterHead.value ? "0" : "1";
  return (
    `/api/method/frappe.utils.print_format.download_pdf?doctype=${encodeURIComponent("Work Order")}` +
    `&name=${encodeURIComponent(props.workOrder)}&format=${encodeURIComponent(selectedFormat.value)}` +
    `&no_letterhead=${noLetterhead}&letterhead=${encodeURIComponent(letterhead)}` +
    `&settings=${encodeURIComponent("{}")}${selectedLang ? "&_lang=" + encodeURIComponent(selectedLang) : ""}`
  );
}

const previewUrl = computed<string>(() =>
  props.show && canPrintActions.value && !isRawPrinting.value ? buildPrintUrl(false) : ""
);

watch(previewUrl, (url) => {
  iframeLoading.value = Boolean(url);
});

function handleFormatChange() {
  saveStoredFormat(selectedFormat.value);
}

function openWindow(url: string) {
  if (!url) return;
  popupError.value = null;
  const win = window.open(url, "_blank");
  if (!win) {
    const msg = __("Lütfen tarayıcı açılır pencere (pop-up) iznini etkinleştirin.");
    popupError.value = msg;
    (window as any).frappe?.show_alert?.({ message: msg, indicator: "orange" });
  }
}

function handleClose() {
  emit("close");
}

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === "Escape" && props.show) handleClose();
}

onMounted(() => window.addEventListener("keydown", handleKeyDown));
onUnmounted(() => window.removeEventListener("keydown", handleKeyDown));
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="print-overlay" @click.self="handleClose">
      <div class="print-modal" role="dialog" aria-modal="true">
        <div class="print-header">
          <div class="print-header-title-group">
            <span class="print-header-icon" aria-hidden="true">🖨️</span>
            <div>
              <h3 class="print-title">{{ __("İş Emri Yazdır") }}</h3>
              <p class="print-subtitle">{{ __("İş Emri: {0}", [workOrder]) }}</p>
            </div>
          </div>
          <button type="button" class="print-close-btn" :title="__('Kapat')" @click="handleClose">✕</button>
        </div>

        <div class="print-body">
          <div v-if="loading" class="print-state">
            <div class="print-spinner" aria-hidden="true" />
            <span>{{ __("Yazdırma seçenekleri yükleniyor...") }}</span>
          </div>

          <div v-else-if="error" class="print-banner banner-error">
            <span class="banner-icon" aria-hidden="true">⚠️</span>
            <div class="banner-content">
              <span>{{ error }}</span>
              <button type="button" class="btn-retry-inline" @click="fetchPrintOptions">{{ __("Tekrar Dene") }}</button>
            </div>
          </div>

          <template v-else-if="options">
            <div v-if="!options.can_print" class="print-banner banner-warning">
              <span class="banner-icon" aria-hidden="true">⚠️</span>
              <div>{{ __("Bu iş emrini yazdırma yetkiniz yok veya belge durumu yazdırmaya izin vermiyor.") }}</div>
            </div>

            <div v-if="popupError" class="print-banner banner-warning">
              <span class="banner-icon" aria-hidden="true">⚠️</span>
              <div>{{ popupError }}</div>
            </div>

            <div class="print-controls">
              <div class="print-field print-field-format">
                <label for="wo-print-format-select" class="print-label">{{ __("Yazdırma Şablonu") }}</label>
                <select id="wo-print-format-select" v-model="selectedFormat" class="print-select" :disabled="options.print_formats.length === 0" @change="handleFormatChange">
                  <option v-for="fmt in options.print_formats" :key="fmt.name" :value="fmt.name">
                    {{ fmt.is_default ? `${fmt.label} (${__("Varsayılan")})` : fmt.label }}
                  </option>
                </select>
              </div>

              <div class="print-field print-field-checkbox">
                <label class="print-checkbox-label" :class="{ disabled: options.letter_heads.length === 0 }">
                  <input v-model="useLetterhead" type="checkbox" :disabled="options.letter_heads.length === 0" />
                  <span>{{ __("Antetli Yazdır") }}</span>
                </label>
              </div>

              <div v-if="useLetterhead && options.letter_heads.length > 0" class="print-field print-field-lh">
                <label for="wo-letter-head-select" class="print-label">{{ __("Antet") }}</label>
                <select id="wo-letter-head-select" v-model="selectedLetterHead" class="print-select">
                  <option v-for="lh in options.letter_heads" :key="lh.name" :value="lh.name">{{ lh.name }}</option>
                </select>
              </div>
            </div>

            <div v-if="options.print_formats.length === 0" class="print-banner banner-info">
              <span class="banner-icon" aria-hidden="true">ℹ️</span>
              <div>{{ __("Kullanılabilir yazdırma şablonu bulunamadı.") }}</div>
            </div>

            <div v-else-if="isRawPrinting" class="print-banner banner-info">
              <span class="banner-icon" aria-hidden="true">ℹ️</span>
              <div>{{ __("Bu şablon ham yazdırma (Raw Printing) formatındadır; HTML önizleme desteklenmiyor.") }}</div>
            </div>

            <div v-else-if="options.can_print && previewUrl" class="print-preview-wrap">
              <div v-if="iframeLoading" class="preview-loading-overlay">
                <div class="print-spinner" aria-hidden="true" />
                <span>{{ __("Önizleme yükleniyor...") }}</span>
              </div>
              <iframe :src="previewUrl" class="print-preview-frame" :title="__('İş Emri Önizleme')" @load="iframeLoading = false" @error="iframeLoading = false" />
            </div>
          </template>
        </div>

        <div class="print-footer">
          <button type="button" class="print-btn print-btn-secondary" @click="handleClose">{{ __("Kapat") }}</button>
          <div class="print-footer-actions">
            <button type="button" class="print-btn print-btn-secondary" :disabled="!canPrintActions || isRawPrinting" @click="openWindow(buildPrintUrl(false))">{{ __("Tam Sayfa Önizle") }}</button>
            <button type="button" class="print-btn print-btn-secondary" :disabled="!canPrintActions || isRawPrinting" @click="openWindow(buildPdfUrl())">{{ __("PDF İndir") }}</button>
            <button type="button" class="print-btn print-btn-primary" :disabled="!canPrintActions" @click="openWindow(buildPrintUrl(true))">{{ __("Yazdır") }}</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.print-overlay { position: fixed; inset: 0; z-index: 1060; background: rgba(15, 23, 42, 0.55); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; padding: 1rem; box-sizing: border-box; }
.print-modal { --modal-bg: var(--card-bg, #ffffff); --modal-border: var(--border-color, #e2e8f0); --modal-text: var(--text-color, #0f172a); --modal-muted: var(--text-muted, #64748b); width: 100%; max-width: 960px; height: 90vh; max-height: 90vh; background: var(--modal-bg); color: var(--modal-text); border: 1px solid var(--modal-border); border-radius: 0.85rem; box-shadow: 0 20px 45px rgba(15, 23, 42, 0.25); display: flex; flex-direction: column; overflow: hidden; font-family: inherit; }
[data-theme="dark"] .print-modal { --modal-bg: var(--ck-glass-bg, #1c2127); --modal-border: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); --modal-text: #f8fafc; --modal-muted: #94a3b8; box-shadow: 0 24px 54px rgba(0, 0, 0, 0.6); }
.print-header { display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.35rem; border-bottom: 1px solid var(--modal-border); background: var(--bg-color, #f8fafc); flex-shrink: 0; }
[data-theme="dark"] .print-header { background: rgba(255, 255, 255, 0.03); }
.print-header-title-group { display: flex; align-items: center; gap: 0.65rem; }
.print-header-icon { font-size: 1.35rem; line-height: 1; }
.print-title { margin: 0; font-size: 1.05rem; font-weight: 800; color: var(--modal-text); }
.print-subtitle { margin: 0.15rem 0 0; font-size: 0.78rem; color: var(--modal-muted); }
.print-close-btn { background: transparent; border: none; border-radius: 0.4rem; width: 32px; height: 32px; font-size: 1.2rem; color: var(--modal-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background-color 0.15s, color 0.15s; }
.print-close-btn:hover { background: rgba(148, 163, 184, 0.18); color: var(--modal-text); }
.print-body { flex: 1; min-height: 0; padding: 1rem 1.35rem; overflow-y: auto; display: flex; flex-direction: column; gap: 0.85rem; }
.print-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.65rem; color: var(--modal-muted); font-size: 0.88rem; font-weight: 600; min-height: 220px; }
.print-spinner { width: 24px; height: 24px; border: 3px solid rgba(37, 99, 235, 0.2); border-top-color: #2563eb; border-radius: 50%; animation: print-spin 0.75s linear infinite; }
@keyframes print-spin { to { transform: rotate(360deg); } }
.print-banner { display: flex; align-items: flex-start; gap: 0.65rem; padding: 0.75rem 1rem; border-radius: 0.55rem; font-size: 0.82rem; font-weight: 600; line-height: 1.4; flex-shrink: 0; }
.banner-info { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; }
[data-theme="dark"] .banner-info { background: rgba(59, 130, 246, 0.15); border-color: rgba(96, 165, 250, 0.35); color: #93c5fd; }
.banner-warning { background: #fffbeb; border: 1px solid #fde68a; color: #b45309; }
[data-theme="dark"] .banner-warning { background: rgba(245, 158, 11, 0.15); border-color: rgba(251, 191, 36, 0.35); color: #fcd34d; }
.banner-error { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; }
[data-theme="dark"] .banner-error { background: rgba(239, 68, 68, 0.16); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.banner-icon { font-size: 1rem; line-height: 1.25; }
.banner-content { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; flex: 1; flex-wrap: wrap; }
.btn-retry-inline { padding: 0.3rem 0.7rem; border-radius: 0.4rem; border: 1px solid currentColor; background: transparent; color: inherit; font-size: 0.78rem; font-weight: 700; cursor: pointer; }
.print-controls { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 0.85rem 1.15rem; flex-shrink: 0; padding: 0.85rem 1rem; border-radius: 0.6rem; border: 1px solid var(--modal-border); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .print-controls { background: rgba(255, 255, 255, 0.03); }
.print-field { display: flex; flex-direction: column; gap: 0.3rem; }
.print-field-format, .print-field-lh { flex: 1 1 240px; min-width: 200px; }
.print-field-checkbox { justify-content: center; padding-bottom: 0.35rem; }
.print-label { font-size: 0.75rem; font-weight: 700; color: var(--modal-muted); }
.print-select { width: 100%; padding: 0.42rem 0.6rem; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--modal-text); font-size: 0.84rem; font-weight: 600; outline: none; }
[data-theme="dark"] .print-select { background: #14181d; border-color: rgba(255, 255, 255, 0.18); }
.print-select:focus { border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2); }
.print-checkbox-label { display: inline-flex; align-items: center; gap: 0.45rem; font-size: 0.84rem; font-weight: 700; color: var(--modal-text); cursor: pointer; user-select: none; }
.print-checkbox-label.disabled { opacity: 0.5; cursor: not-allowed; }
.print-preview-wrap { position: relative; flex: 1; min-height: 360px; border: 1px solid var(--modal-border); border-radius: 0.6rem; overflow: hidden; background: #ffffff; }
.print-preview-frame { width: 100%; height: 100%; border: none; display: block; background: #ffffff; }
.preview-loading-overlay { position: absolute; inset: 0; z-index: 2; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.6rem; background: rgba(248, 250, 252, 0.88); color: #334155; font-size: 0.84rem; font-weight: 600; }
[data-theme="dark"] .preview-loading-overlay { background: rgba(20, 24, 29, 0.82); color: #e2e8f0; }
.print-footer { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.65rem; padding: 0.9rem 1.35rem; border-top: 1px solid var(--modal-border); background: var(--bg-color, #f8fafc); flex-shrink: 0; }
[data-theme="dark"] .print-footer { background: rgba(255, 255, 255, 0.02); }
.print-footer-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 0.55rem; }
.print-btn { display: inline-flex; align-items: center; justify-content: center; gap: 0.4rem; padding: 0.5rem 1rem; border-radius: 0.5rem; font-size: 0.84rem; font-weight: 700; cursor: pointer; transition: all 0.15s ease; border: none; }
.print-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.print-btn-secondary { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #cbd5e1); color: var(--modal-text); }
[data-theme="dark"] .print-btn-secondary { background: #14181d; border-color: rgba(255, 255, 255, 0.18); }
.print-btn-secondary:hover:not(:disabled) { background: rgba(148, 163, 184, 0.18); }
.print-btn-primary { background: #2563eb; color: #ffffff; }
.print-btn-primary:hover:not(:disabled) { background: #1d4ed8; box-shadow: 0 3px 10px rgba(37, 99, 235, 0.28); }
@media (max-width: 640px) {
  .print-modal { height: 94vh; max-height: 94vh; }
  .print-footer { justify-content: flex-end; }
}
</style>
