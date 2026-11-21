<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);

interface GroupWarehouseOption {
  name: string;
  warehouse_name?: string;
  company?: string;
}

const props = withDefaults(
  defineProps<{
    show: boolean;
    defaultCompany?: string | null;
  }>(),
  { defaultCompany: null }
);

const emit = defineEmits<{
  (e: "close"): void;
  (e: "queued", payload: any): void;
}>();

const companies = ref<string[]>([]);
const company = ref<string>("");
const groupWarehouses = ref<GroupWarehouseOption[]>([]);
const warehouseFilter = ref<string>("");
const warehouseGroup = ref<string>("");
const postingDate = ref<string>("");
const postingTime = ref<string>("");
const ignoreEmptyStock = ref<boolean>(false);

const loadingMeta = ref<boolean>(false);
const loadingGroups = ref<boolean>(false);
const submitting = ref<boolean>(false);
const errorMessage = ref<string | null>(null);

const filteredGroups = computed(() => {
  const q = warehouseFilter.value.trim().toLowerCase();
  if (!q) return groupWarehouses.value;
  return groupWarehouses.value.filter(
    (w) =>
      w.name.toLowerCase().includes(q) ||
      (w.warehouse_name || "").toLowerCase().includes(q)
  );
});

const canSubmit = computed(
  () =>
    !submitting.value &&
    !loadingGroups.value &&
    Boolean(company.value) &&
    Boolean(warehouseGroup.value) &&
    Boolean(postingDate.value)
);

function todayStr(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function nowTimeStr(): string {
  const d = new Date();
  return [
    String(d.getHours()).padStart(2, "0"),
    String(d.getMinutes()).padStart(2, "0"),
    String(d.getSeconds()).padStart(2, "0"),
  ].join(":");
}

function callFrappe<T = any>(method: string, args: Record<string, any> = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    frappe.call({
      method,
      args,
      quiet: true,
      callback: (r: { message?: T }) => resolve(r.message as T),
      error: (err: any) => reject(err),
    });
  });
}

function extractError(err: any, fallback: string): string {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  if (err._server_messages) {
    try {
      const parsed = JSON.parse(err._server_messages);
      if (Array.isArray(parsed) && parsed.length) {
        const msgs = parsed
          .map((x: any) => {
            if (typeof x !== "string") return x?.message || String(x);
            try { return JSON.parse(x)?.message || x; } catch { return x; }
          })
          .filter(Boolean);
        if (msgs.length) return msgs.join(" ");
      }
    } catch { /* fallback */ }
  }
  return err.message || fallback;
}

async function fetchGroupWarehouses() {
  loadingGroups.value = true;
  try {
    const filters: Record<string, any> = { is_group: 1 };
    if (company.value) filters.company = company.value;
    const rows = await callFrappe<GroupWarehouseOption[]>("frappe.client.get_list", {
      doctype: "Warehouse",
      filters,
      fields: ["name", "warehouse_name", "company"],
      order_by: "name asc",
      limit_page_length: 200,
    });
    groupWarehouses.value = Array.isArray(rows) ? rows : [];
    if (!groupWarehouses.value.some((w) => w.name === warehouseGroup.value)) {
      warehouseGroup.value = groupWarehouses.value[0]?.name || "";
    }
  } catch (err: any) {
    errorMessage.value = extractError(err, __("Depo grupları yüklenemedi."));
    groupWarehouses.value = [];
  } finally {
    loadingGroups.value = false;
  }
}

async function initModalData() {
  loadingMeta.value = true;
  errorMessage.value = null;
  warehouseFilter.value = "";
  warehouseGroup.value = "";
  postingDate.value = todayStr();
  postingTime.value = nowTimeStr();
  ignoreEmptyStock.value = false;

  try {
    const rows = await callFrappe<{ name: string }[]>("frappe.client.get_list", {
      doctype: "Company",
      fields: ["name"],
      order_by: "name asc",
      limit_page_length: 100,
    });
    companies.value = (Array.isArray(rows) ? rows : []).map((r) => r.name);
    const fallbackDef =
      props.defaultCompany ||
      (typeof frappe !== "undefined" && frappe.defaults?.get_user_default?.("Company")) ||
      companies.value[0] ||
      "";
    company.value = fallbackDef;
    await fetchGroupWarehouses();
  } catch (err: any) {
    errorMessage.value = extractError(err, __("Şirket listesi yüklenemedi."));
  } finally {
    loadingMeta.value = false;
  }
}

watch(
  () => props.show,
  (isOpen) => {
    if (isOpen) initModalData();
  },
  { immediate: true }
);

function onCompanyChange() {
  warehouseGroup.value = "";
  fetchGroupWarehouses();
}

function handleClose() {
  if (!submitting.value) emit("close");
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === "Escape" && props.show) handleClose();
}

async function handleSubmit() {
  if (!canSubmit.value) {
    errorMessage.value = __("Lütfen şirket, depo grubu ve tarih alanlarını doldurun.");
    return;
  }
  submitting.value = true;
  errorMessage.value = null;
  try {
    const res = await callFrappe(
      "erpnextkta.kta_stock.services.stock_reconciliation_service.create_stock_reco_docs_for_warehouse_group",
      {
        warehouse_group: warehouseGroup.value,
        company: company.value,
        posting_date: postingDate.value,
        posting_time: postingTime.value || nowTimeStr(),
        ignore_empty_stock: ignoreEmptyStock.value ? 1 : 0,
      }
    );
    emit("queued", res);
    emit("close");
  } catch (err: any) {
    errorMessage.value = extractError(
      err,
      __("Toplu sayım belgeleri kuyruğa alınırken bir hata oluştu.")
    );
  } finally {
    submitting.value = false;
  }
}

onMounted(() => window.addEventListener("keydown", handleKeyDown));
onUnmounted(() => window.removeEventListener("keydown", handleKeyDown));
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="bcr-overlay" @click.self="handleClose">
      <div class="bcr-modal" role="dialog" aria-modal="true">
        <div class="bcr-header">
          <div>
            <h3 class="bcr-title">🏭 {{ __("Depo Grubundan Toplu Sayım Oluştur") }}</h3>
            <p class="bcr-sub">{{ __("Seçilen depo grubundaki tüm alt depolar için taslak sayım belgesi oluşturulur.") }}</p>
          </div>
          <button type="button" class="bcr-close" :disabled="submitting" :title="__('Kapat')" @click="handleClose">✕</button>
        </div>

        <div class="bcr-body">
          <div v-if="errorMessage" class="bcr-error" role="alert">⚠️ {{ errorMessage }}</div>

          <div class="bcr-field">
            <label class="bcr-label">{{ __("Şirket") }}</label>
            <select v-model="company" class="bcr-input" :disabled="loadingMeta || submitting" @change="onCompanyChange">
              <option value="">{{ __("-- Şirket Seçin --") }}</option>
              <option v-for="c in companies" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>

          <div class="bcr-field">
            <label class="bcr-label">{{ __("Depo Grubu") }}</label>
            <input
              v-model="warehouseFilter"
              type="text"
              class="bcr-input bcr-filter-input"
              :disabled="loadingGroups || submitting"
              :placeholder="__('Depo grubu adıyla filtrele...')"
            />
            <select v-model="warehouseGroup" class="bcr-input" :disabled="loadingGroups || submitting">
              <option value="">{{ loadingGroups ? __("Yükleniyor...") : __("-- Depo Grubu Seçin --") }}</option>
              <option v-for="w in filteredGroups" :key="w.name" :value="w.name">
                {{ w.name }}
              </option>
            </select>
          </div>

          <div class="bcr-grid-2">
            <div class="bcr-field">
              <label class="bcr-label">{{ __("Sayım Tarihi") }}</label>
              <input v-model="postingDate" type="date" class="bcr-input" :disabled="submitting" />
            </div>
            <div class="bcr-field">
              <label class="bcr-label">{{ __("Sayım Saati") }}</label>
              <input v-model="postingTime" type="time" step="1" class="bcr-input" :disabled="submitting" />
            </div>
          </div>

          <label class="bcr-check-row">
            <input v-model="ignoreEmptyStock" type="checkbox" class="bcr-checkbox" :disabled="submitting" />
            <span>{{ __("Boş Stokları Yoksay") }}</span>
          </label>
        </div>

        <div class="bcr-footer">
          <button type="button" class="bcr-btn bcr-btn-cancel" :disabled="submitting" @click="handleClose">{{ __("Vazgeç") }}</button>
          <button type="button" class="bcr-btn bcr-btn-primary" :disabled="!canSubmit" @click="handleSubmit">
            {{ submitting ? __("Oluşturuluyor...") : __("⚡ Toplu Sayım Başlat") }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.bcr-overlay { position: fixed; inset: 0; z-index: 1060; background: rgba(15, 23, 42, 0.56); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.bcr-modal { width: 100%; max-width: 560px; max-height: 90vh; display: flex; flex-direction: column; background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.85rem; box-shadow: 0 22px 48px rgba(15, 23, 42, 0.28); overflow: hidden; }
[data-theme="dark"] .bcr-modal { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); color: #f8fafc; }
.bcr-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; padding: 1rem 1.3rem; background: var(--bg-color, #f8fafc); border-bottom: 1px solid var(--border-color, #e2e8f0); }
[data-theme="dark"] .bcr-header { background: rgba(255, 255, 255, 0.03); }
.bcr-title { margin: 0; font-size: 1.02rem; font-weight: 800; }
.bcr-sub { margin: 0.2rem 0 0; font-size: 0.78rem; color: var(--text-muted, #64748b); }
.bcr-close { background: transparent; border: none; font-size: 1.15rem; color: var(--text-muted, #64748b); cursor: pointer; padding: 0.2rem 0.4rem; }
.bcr-body { padding: 1.15rem 1.3rem; overflow-y: auto; display: flex; flex-direction: column; gap: 0.9rem; }
.bcr-error { padding: 0.65rem 0.85rem; border-radius: 0.5rem; background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; font-size: 0.82rem; font-weight: 600; }
[data-theme="dark"] .bcr-error { background: rgba(239, 68, 68, 0.16); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.bcr-field { display: flex; flex-direction: column; gap: 0.35rem; }
.bcr-label { font-size: 0.78rem; font-weight: 700; color: var(--text-muted, #475569); }
.bcr-input { width: 100%; padding: 0.48rem 0.65rem; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-size: 0.84rem; font-weight: 600; box-sizing: border-box; }
[data-theme="dark"] .bcr-input { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #f8fafc; }
.bcr-filter-input { font-size: 0.79rem; padding: 0.38rem 0.65rem; }
.bcr-grid-2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; }
.bcr-check-row { display: inline-flex; align-items: center; gap: 0.5rem; font-size: 0.84rem; font-weight: 600; cursor: pointer; margin: 0; }
.bcr-checkbox { width: 16px; height: 16px; accent-color: #2563eb; cursor: pointer; }
.bcr-footer { display: flex; justify-content: flex-end; gap: 0.65rem; padding: 0.95rem 1.3rem; border-top: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .bcr-footer { background: rgba(255, 255, 255, 0.02); }
.bcr-btn { padding: 0.52rem 1.05rem; border-radius: 0.5rem; font-size: 0.84rem; font-weight: 700; cursor: pointer; border: none; }
.bcr-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.bcr-btn-cancel { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #cbd5e1); color: var(--text-muted, #475569); }
[data-theme="dark"] .bcr-btn-cancel { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #cbd5e1; }
.bcr-btn-primary { background: #2563eb; color: #ffffff; }
.bcr-btn-primary:hover:not(:disabled) { background: #1d4ed8; }
</style>
