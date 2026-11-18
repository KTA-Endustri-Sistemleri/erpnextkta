<script setup lang="ts">
import { ref, reactive, watch, nextTick, onMounted, onUnmounted } from 'vue';
import type { CreateWorkOrderPayload } from '../types';

const __ = (...args: any[]) => (window as any).__(...args);

interface LinkOption { value: string; label?: string; description?: string; }
interface ItemDefaultBomResponse { item_code: string; item_name?: string | null; bom?: string | null; stock_uom?: string | null; manufacturing_lead_days?: number | null; }
interface CreateWorkOrderResponse { name: string; status?: string; docstatus?: number; }
type ActiveDropdown = 'item' | 'bom' | 'source_wh' | 'fg_wh' | null;

const props = defineProps<{ show: boolean }>();
const emit = defineEmits<{ (e: 'close'): void; (e: 'created', workOrderName: string): void; }>();

const DEFAULT_LEAD_DAYS = 14;
const WH_FILTERS = { is_group: 0, disabled: 0 };
const ITEM_FILTERS = { disabled: 0, has_variants: 0 };

const itemInputRef = ref<HTMLInputElement | null>(null);
const itemQuery = ref('');
const selectedItemCode = ref('');
const selectedItemName = ref('');
const stockUom = ref('');
const leadDays = ref(DEFAULT_LEAD_DAYS);
const showAdvanced = ref(false);
const endDateManuallyEdited = ref(false);
const loadingItemMeta = ref(false);
const submitting = ref(false);
const errorMessage = ref<string | null>(null);

const form = reactive({
  qty: 1,
  bomNo: '',
  sourceWarehouse: '',
  fgWarehouse: '',
  plannedStartDate: '',
  plannedEndDate: '',
});

const activeDropdown = ref<ActiveDropdown>(null);
const searchingField = ref<ActiveDropdown>(null);
const dropdownResults = ref<Record<Exclude<ActiveDropdown, null>, LinkOption[]>>({ item: [], bom: [], source_wh: [], fg_wh: [] });
const highlightedIndex = ref(-1);
let searchTimer: ReturnType<typeof setTimeout> | null = null;

function formatIsoDate(dt: Date): string {
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
}

function addDaysIsoDate(dateStr: string, days: number): string {
  const parts = (dateStr || '').split('-').map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return '';
  const dt = new Date(parts[0], parts[1] - 1, parts[2]);
  dt.setDate(dt.getDate() + (Number(days) || 0));
  return formatIsoDate(dt);
}

function extractFrappeError(err: any, fallback: string): string {
  if (!err) return fallback;
  if (typeof err === 'string') return err;
  if (err._server_messages) {
    try {
      const parsed = JSON.parse(err._server_messages);
      if (Array.isArray(parsed) && parsed.length > 0) {
        const msgs = parsed.map((item: any) => {
          if (typeof item !== 'string') return item?.message || String(item);
          try { return JSON.parse(item)?.message || item; } catch { return item; }
        }).filter(Boolean);
        if (msgs.length > 0) return msgs.join(' ');
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

function resetForm() {
  const today = formatIsoDate(new Date());
  itemQuery.value = '';
  selectedItemCode.value = '';
  selectedItemName.value = '';
  stockUom.value = '';
  leadDays.value = DEFAULT_LEAD_DAYS;
  showAdvanced.value = false;
  endDateManuallyEdited.value = false;
  loadingItemMeta.value = false;
  submitting.value = false;
  errorMessage.value = null;
  activeDropdown.value = null;
  dropdownResults.value = { item: [], bom: [], source_wh: [], fg_wh: [] };
  highlightedIndex.value = -1;
  Object.assign(form, {
    qty: 1,
    bomNo: '',
    sourceWarehouse: '',
    fgWarehouse: '',
    plannedStartDate: today,
    plannedEndDate: addDaysIsoDate(today, DEFAULT_LEAD_DAYS),
  });
}

watch(() => props.show, async (isOpen) => {
  if (isOpen) {
    resetForm();
    await nextTick();
    itemInputRef.value?.focus();
  } else {
    if (searchTimer) clearTimeout(searchTimer);
    activeDropdown.value = null;
  }
});

watch(() => form.plannedStartDate, (nextStart) => {
  if (!endDateManuallyEdited.value && nextStart) {
    form.plannedEndDate = addDaysIsoDate(nextStart, leadDays.value);
  }
});

async function searchLinks(field: Exclude<ActiveDropdown, null>, doctype: string, txt: string, filters: Record<string, any>) {
  searchingField.value = field;
  try {
    const res = await callFrappe<LinkOption[]>('frappe.desk.search.search_link', { doctype, txt: txt || '', filters, page_length: 15 });
    const list = Array.isArray(res) ? res : [];
    dropdownResults.value[field] = list;
    highlightedIndex.value = list.length > 0 ? 0 : -1;
  } catch (err) {
    console.error(`search_link(${doctype}) error:`, err);
  } finally {
    if (searchingField.value === field) searchingField.value = null;
  }
}

function triggerSearch(field: Exclude<ActiveDropdown, null>, doctype: string, txt: string, filters: Record<string, any>, immediate = false) {
  activeDropdown.value = field;
  if (searchTimer) clearTimeout(searchTimer);
  if (immediate) searchLinks(field, doctype, txt, filters);
  else searchTimer = setTimeout(() => searchLinks(field, doctype, txt, filters), 200);
}

function onItemInput() {
  errorMessage.value = null;
  if (selectedItemCode.value && itemQuery.value.trim() !== selectedItemCode.value) {
    selectedItemCode.value = '';
    selectedItemName.value = '';
    stockUom.value = '';
    form.bomNo = '';
  }
  triggerSearch('item', 'Item', itemQuery.value, ITEM_FILTERS);
}

async function selectItem(option: LinkOption) {
  selectedItemCode.value = option.value;
  itemQuery.value = option.value;
  selectedItemName.value = option.label || option.description || '';
  activeDropdown.value = null;
  highlightedIndex.value = -1;
  errorMessage.value = null;

  loadingItemMeta.value = true;
  try {
    const res = await callFrappe<ItemDefaultBomResponse>('erpnextkta.kta_shopfloor.api.get_item_default_bom', { item_code: option.value });
    if (res) {
      form.bomNo = res.bom || '';
      stockUom.value = res.stock_uom || '';
      if (res.item_name) selectedItemName.value = res.item_name;
      const resolvedLead = Number(res.manufacturing_lead_days) || DEFAULT_LEAD_DAYS;
      leadDays.value = resolvedLead;
      endDateManuallyEdited.value = false;
      if (form.plannedStartDate) form.plannedEndDate = addDaysIsoDate(form.plannedStartDate, resolvedLead);
    }
  } catch (err) {
    console.error('get_item_default_bom error:', err);
  } finally {
    loadingItemMeta.value = false;
  }
}

function clearSelectedItem() {
  selectedItemCode.value = '';
  selectedItemName.value = '';
  itemQuery.value = '';
  stockUom.value = '';
  form.bomNo = '';
  leadDays.value = DEFAULT_LEAD_DAYS;
  endDateManuallyEdited.value = false;
  if (form.plannedStartDate) form.plannedEndDate = addDaysIsoDate(form.plannedStartDate, DEFAULT_LEAD_DAYS);
  nextTick(() => itemInputRef.value?.focus());
}

function getBomFilters(): Record<string, any> {
  const code = selectedItemCode.value || itemQuery.value.trim();
  return code ? { item: code, is_active: 1, docstatus: 1 } : { is_active: 1, docstatus: 1 };
}

function selectAdvancedOption(field: 'bom' | 'source_wh' | 'fg_wh', option: LinkOption) {
  if (field === 'bom') form.bomNo = option.value;
  else if (field === 'source_wh') form.sourceWarehouse = option.value;
  else form.fgWarehouse = option.value;
  activeDropdown.value = null;
  highlightedIndex.value = -1;
}

function handleDropdownBlur(field: Exclude<ActiveDropdown, null>) {
  setTimeout(() => {
    if (activeDropdown.value === field) {
      activeDropdown.value = null;
      highlightedIndex.value = -1;
    }
  }, 150);
}

function handleItemKeydown(e: KeyboardEvent) {
  const results = dropdownResults.value.item;
  if (activeDropdown.value !== 'item' || results.length === 0) return;
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    highlightedIndex.value = (highlightedIndex.value + 1) % results.length;
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    highlightedIndex.value = highlightedIndex.value <= 0 ? results.length - 1 : highlightedIndex.value - 1;
  } else if (e.key === 'Enter' && highlightedIndex.value >= 0 && results[highlightedIndex.value]) {
    e.preventDefault();
    selectItem(results[highlightedIndex.value]);
  }
}

function closeModal() {
  if (!submitting.value) emit('close');
}

function handleGlobalKeydown(e: KeyboardEvent) {
  if (!props.show || e.key !== 'Escape') return;
  if (activeDropdown.value) {
    e.stopPropagation();
    activeDropdown.value = null;
    return;
  }
  e.preventDefault();
  closeModal();
}

async function handleSubmit() {
  if (submitting.value || loadingItemMeta.value) return;
  errorMessage.value = null;
  const itemCode = (selectedItemCode.value || itemQuery.value).trim();
  if (!itemCode) {
    errorMessage.value = __('Lütfen bir mamul (Item) seçin.');
    return;
  }
  const parsedQty = Number(form.qty);
  if (Number.isNaN(parsedQty) || parsedQty <= 0) {
    errorMessage.value = __('Üretim miktarı sıfırdan büyük olmalıdır.');
    return;
  }

  submitting.value = true;
  try {
    const payload: CreateWorkOrderPayload = { item_code: itemCode, qty: parsedQty };
    if (form.bomNo.trim()) payload.bom_no = form.bomNo.trim();
    if (form.sourceWarehouse.trim()) payload.source_warehouse = form.sourceWarehouse.trim();
    if (form.fgWarehouse.trim()) payload.fg_warehouse = form.fgWarehouse.trim();
    if (form.plannedStartDate) payload.planned_start_date = form.plannedStartDate;
    if (endDateManuallyEdited.value && form.plannedEndDate) {
      payload.planned_end_date = form.plannedEndDate;
    }

    const res = await callFrappe<CreateWorkOrderResponse>('erpnextkta.kta_shopfloor.api.create_work_order', payload);
    if (!res?.name) throw new Error(__('İş Emri oluşturulamadı.'));

    (window as any).frappe?.show_alert?.({ message: __('Taslak İş Emri Oluşturuldu: {0}', [res.name]), indicator: 'green' });
    emit('created', res.name);
    emit('close');
  } catch (err: any) {
    console.error('create_work_order error:', err);
    errorMessage.value = extractFrappeError(err, __('İş Emri oluşturulurken bir hata oluştu.'));
  } finally {
    submitting.value = false;
  }
}

const warehouseFields: Array<{ key: 'source_wh' | 'fg_wh'; id: string; label: string; placeholder: string; prop: 'sourceWarehouse' | 'fgWarehouse' }> = [
  { key: 'source_wh', id: 'cwo-source-wh', label: 'Kaynak Depo', placeholder: 'Opsiyonel', prop: 'sourceWarehouse' },
  { key: 'fg_wh', id: 'cwo-fg-wh', label: 'Hedef Depo (Mamul)', placeholder: 'Varsayılan mamul deposu', prop: 'fgWarehouse' },
];

onMounted(() => window.addEventListener('keydown', handleGlobalKeydown));
onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown);
  if (searchTimer) clearTimeout(searchTimer);
});
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="cwo-overlay" role="dialog" aria-modal="true" aria-labelledby="cwo-modal-title" @click.self="closeModal">
      <div class="cwo-modal">
        <div class="cwo-header">
          <div class="cwo-header-title-group">
            <span class="cwo-header-icon" aria-hidden="true">⚡</span>
            <div>
              <h2 id="cwo-modal-title" class="cwo-title">{{ __('Yeni İş Emri Aç') }}</h2>
              <p class="cwo-subtitle">{{ __('Hızlı taslak iş emri oluşturma') }}</p>
            </div>
          </div>
          <button type="button" class="cwo-close-btn" :aria-label="__('Kapat')" :disabled="submitting" @click="closeModal">×</button>
        </div>

        <form class="cwo-body" @submit.prevent="handleSubmit">
          <div v-if="errorMessage" class="cwo-error-banner" role="alert"><span aria-hidden="true">⚠️</span><span>{{ errorMessage }}</span></div>

          <div class="cwo-field">
            <label for="cwo-item-input" class="cwo-label">{{ __('Mamul Kodu') }} <span class="cwo-required">*</span></label>
            <div class="cwo-autocomplete">
              <div class="cwo-input-wrap">
                <input id="cwo-item-input" ref="itemInputRef" v-model="itemQuery" type="text" class="cwo-input" :placeholder="__('Mamul kodu veya adı ile arayın...')" autocomplete="off" :disabled="submitting" @focus="triggerSearch('item', 'Item', itemQuery, ITEM_FILTERS, true)" @input="onItemInput" @keydown="handleItemKeydown" @blur="handleDropdownBlur('item')" />
                <button v-if="itemQuery && !submitting" type="button" class="cwo-input-clear" :title="__('Temizle')" @mousedown.prevent="clearSelectedItem">×</button>
              </div>
              <div v-if="activeDropdown === 'item'" class="cwo-dropdown" role="listbox">
                <div v-if="searchingField === 'item'" class="cwo-dropdown-status">{{ __('Aranıyor...') }}</div>
                <div v-else-if="dropdownResults.item.length === 0" class="cwo-dropdown-status">{{ __('Eşleşen mamul bulunamadı') }}</div>
                <button v-for="(opt, idx) in dropdownResults.item" v-else :key="opt.value" type="button" role="option" :aria-selected="idx === highlightedIndex" class="cwo-dropdown-item" :class="{ highlighted: idx === highlightedIndex }" @mousedown.prevent="selectItem(opt)">
                  <span class="cwo-opt-value">{{ opt.value }}</span>
                  <span v-if="opt.label || opt.description" class="cwo-opt-desc">{{ opt.label || opt.description }}</span>
                </button>
              </div>
            </div>
            <div v-if="selectedItemCode || loadingItemMeta" class="cwo-item-meta">
              <span v-if="loadingItemMeta" class="cwo-meta-loading">{{ __('Varsayılan reçete ve termin bilgisi yükleniyor...') }}</span>
              <template v-else>
                <span v-if="selectedItemName" class="cwo-meta-name">{{ selectedItemName }}</span>
                <span v-if="form.bomNo" class="cwo-meta-badge">BOM: {{ form.bomNo }}</span>
                <span v-else class="cwo-meta-badge cwo-meta-warn">{{ __('Varsayılan BOM yok') }}</span>
                <span class="cwo-meta-badge">{{ __('Termin: {0} Gün', [leadDays]) }}</span>
              </template>
            </div>
          </div>

          <div class="cwo-field">
            <label for="cwo-qty-input" class="cwo-label">{{ __('Miktar') }} <span class="cwo-required">*</span></label>
            <div class="cwo-qty-row">
              <input id="cwo-qty-input" v-model.number="form.qty" type="number" min="0.001" step="any" class="cwo-input cwo-qty-input" :disabled="submitting" required />
              <span v-if="stockUom" class="cwo-uom-chip">{{ stockUom }}</span>
            </div>
          </div>

          <div class="cwo-accordion">
            <button type="button" class="cwo-accordion-toggle" :aria-expanded="showAdvanced" @click="showAdvanced = !showAdvanced">
              <span class="cwo-accordion-label"><span class="cwo-chevron" :class="{ open: showAdvanced }">▸</span><span>{{ __('Gelişmiş Seçenekler') }}</span></span>
              <span class="cwo-accordion-hint">{{ form.plannedStartDate }} → {{ form.plannedEndDate || '—' }}</span>
            </button>

            <div v-show="showAdvanced" class="cwo-accordion-body">
              <div class="cwo-field">
                <label for="cwo-bom-input" class="cwo-label">{{ __('Reçete (BOM No)') }}</label>
                <div class="cwo-autocomplete">
                  <input id="cwo-bom-input" v-model="form.bomNo" type="text" class="cwo-input" :placeholder="__('Otomatik (varsayılan BOM)')" autocomplete="off" :disabled="submitting" @focus="triggerSearch('bom', 'BOM', form.bomNo, getBomFilters(), true)" @input="triggerSearch('bom', 'BOM', form.bomNo, getBomFilters())" @blur="handleDropdownBlur('bom')" />
                  <div v-if="activeDropdown === 'bom' && (dropdownResults.bom.length > 0 || searchingField === 'bom')" class="cwo-dropdown">
                    <div v-if="searchingField === 'bom'" class="cwo-dropdown-status">{{ __('Aranıyor...') }}</div>
                    <button v-for="opt in dropdownResults.bom" v-else :key="opt.value" type="button" class="cwo-dropdown-item" @mousedown.prevent="selectAdvancedOption('bom', opt)">
                      <span class="cwo-opt-value">{{ opt.value }}</span>
                      <span v-if="opt.description" class="cwo-opt-desc">{{ opt.description }}</span>
                    </button>
                  </div>
                </div>
              </div>

              <div class="cwo-grid-2">
                <div v-for="wf in warehouseFields" :key="wf.key" class="cwo-field">
                  <label :for="wf.id" class="cwo-label">{{ __(wf.label) }}</label>
                  <div class="cwo-autocomplete">
                    <input :id="wf.id" v-model="form[wf.prop]" type="text" class="cwo-input" :placeholder="__(wf.placeholder)" autocomplete="off" :disabled="submitting" @focus="triggerSearch(wf.key, 'Warehouse', form[wf.prop], WH_FILTERS, true)" @input="triggerSearch(wf.key, 'Warehouse', form[wf.prop], WH_FILTERS)" @blur="handleDropdownBlur(wf.key)" />
                    <div v-if="activeDropdown === wf.key && (dropdownResults[wf.key].length > 0 || searchingField === wf.key)" class="cwo-dropdown">
                      <div v-if="searchingField === wf.key" class="cwo-dropdown-status">{{ __('Aranıyor...') }}</div>
                      <button v-for="opt in dropdownResults[wf.key]" v-else :key="opt.value" type="button" class="cwo-dropdown-item" @mousedown.prevent="selectAdvancedOption(wf.key, opt)">
                        <span class="cwo-opt-value">{{ opt.value }}</span>
                        <span v-if="opt.description" class="cwo-opt-desc">{{ opt.description }}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div class="cwo-grid-2">
                <div class="cwo-field">
                  <label for="cwo-start-date" class="cwo-label">{{ __('Planlanan Başlangıç') }}</label>
                  <input id="cwo-start-date" v-model="form.plannedStartDate" type="date" class="cwo-input" :disabled="submitting" />
                </div>
                <div class="cwo-field">
                  <label for="cwo-end-date" class="cwo-label">{{ __('Planlanan Bitiş') }}</label>
                  <input id="cwo-end-date" v-model="form.plannedEndDate" type="date" class="cwo-input" :disabled="submitting" @input="endDateManuallyEdited = true" />
                </div>
              </div>
            </div>
          </div>

          <div class="cwo-footer">
            <button type="button" class="cwo-btn cwo-btn-cancel" :disabled="submitting" @click="closeModal">{{ __('İptal') }}</button>
            <button type="submit" class="cwo-btn cwo-btn-primary" :disabled="submitting || loadingItemMeta">
              <span v-if="submitting" class="cwo-spinner" aria-hidden="true" />
              <span>{{ submitting ? __('Kaydediliyor...') : __('Taslak Olarak Kaydet') }}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cwo-overlay { position: fixed; inset: 0; z-index: 1050; background: rgba(15, 23, 42, 0.55); backdrop-filter: blur(3px); display: flex; align-items: center; justify-content: center; padding: 1rem; box-sizing: border-box; }
.cwo-modal { --cwo-surface: var(--card-bg, #ffffff); --cwo-surface-alt: var(--bg-color, #f8fafc); --cwo-border: var(--border-color, #e2e8f0); --cwo-input-bg: var(--card-bg, #ffffff); --cwo-input-border: var(--border-color, #cbd5e1); --cwo-text: var(--text-color, #0f172a); --cwo-muted: var(--text-muted, #64748b); --cwo-accent: #2563eb; --cwo-accent-hover: #1d4ed8; --cwo-dropdown-bg: var(--card-bg, #ffffff); width: 100%; max-width: 540px; max-height: 90vh; overflow-y: auto; background: var(--cwo-surface); color: var(--cwo-text); border: 1px solid var(--cwo-border); border-radius: 0.85rem; box-shadow: 0 20px 45px rgba(15, 23, 42, 0.22); display: flex; flex-direction: column; font-family: inherit; }
[data-theme='dark'] .cwo-modal { --cwo-surface: var(--ck-glass-bg, #1c2127); --cwo-surface-alt: rgba(255, 255, 255, 0.03); --cwo-border: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); --cwo-input-bg: #14181d; --cwo-input-border: rgba(255, 255, 255, 0.16); --cwo-text: #f8fafc; --cwo-muted: #94a3b8; --cwo-accent: #3b82f6; --cwo-accent-hover: #2563eb; --cwo-dropdown-bg: #1e242c; box-shadow: 0 24px 54px rgba(0, 0, 0, 0.55); }
.cwo-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 1.1rem 1.35rem; border-bottom: 1px solid var(--cwo-border); background: var(--cwo-surface-alt); border-radius: 0.85rem 0.85rem 0 0; }
.cwo-header-title-group { display: flex; align-items: center; gap: 0.65rem; }
.cwo-header-icon { font-size: 1.35rem; line-height: 1; }
.cwo-title { margin: 0; font-size: 1.05rem; font-weight: 800; color: var(--cwo-text); }
.cwo-subtitle { margin: 0.15rem 0 0; font-size: 0.78rem; color: var(--cwo-muted); }
.cwo-close-btn { background: transparent; border: none; border-radius: 0.4rem; width: 32px; height: 32px; font-size: 1.35rem; line-height: 1; color: var(--cwo-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background-color 0.15s, color 0.15s; }
.cwo-close-btn:hover:not(:disabled) { background: rgba(148, 163, 184, 0.18); color: var(--cwo-text); }
.cwo-body { padding: 1.25rem 1.35rem; display: flex; flex-direction: column; gap: 1rem; }
.cwo-error-banner { display: flex; align-items: flex-start; gap: 0.5rem; padding: 0.75rem 0.9rem; border-radius: 0.55rem; background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; font-size: 0.82rem; font-weight: 600; }
[data-theme='dark'] .cwo-error-banner { background: rgba(239, 68, 68, 0.15); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.cwo-field { display: flex; flex-direction: column; gap: 0.35rem; }
.cwo-label { font-size: 0.8rem; font-weight: 700; color: var(--cwo-text); }
.cwo-required { color: #ef4444; }
.cwo-autocomplete { position: relative; }
.cwo-input-wrap { position: relative; display: flex; align-items: center; }
.cwo-input { width: 100%; height: 38px; padding: 0 0.75rem; font-size: 0.86rem; border-radius: 0.5rem; border: 1px solid var(--cwo-input-border); background: var(--cwo-input-bg); color: var(--cwo-text); box-sizing: border-box; outline: none; transition: border-color 0.15s, box-shadow 0.15s; }
.cwo-input:focus { border-color: var(--cwo-accent); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15); }
.cwo-input-wrap .cwo-input { padding-right: 2rem; }
.cwo-input-clear { position: absolute; right: 0.45rem; background: none; border: none; font-size: 1.1rem; line-height: 1; color: var(--cwo-muted); cursor: pointer; padding: 0.2rem 0.35rem; }
.cwo-input-clear:hover { color: var(--cwo-text); }
.cwo-dropdown { position: absolute; left: 0; right: 0; top: calc(100% + 4px); z-index: 30; max-height: 220px; overflow-y: auto; background: var(--cwo-dropdown-bg); border: 1px solid var(--cwo-input-border); border-radius: 0.55rem; box-shadow: 0 10px 25px rgba(15, 23, 42, 0.18); display: flex; flex-direction: column; }
.cwo-dropdown-status { padding: 0.65rem 0.85rem; font-size: 0.8rem; color: var(--cwo-muted); }
.cwo-dropdown-item { display: flex; flex-direction: column; align-items: flex-start; gap: 0.1rem; width: 100%; padding: 0.55rem 0.85rem; border: none; border-bottom: 1px solid var(--cwo-border); background: transparent; color: var(--cwo-text); text-align: left; cursor: pointer; transition: background-color 0.12s; }
.cwo-dropdown-item:last-child { border-bottom: none; }
.cwo-dropdown-item:hover, .cwo-dropdown-item.highlighted { background: rgba(37, 99, 235, 0.12); }
.cwo-opt-value { font-size: 0.84rem; font-weight: 700; color: var(--cwo-accent); }
.cwo-opt-desc { font-size: 0.74rem; color: var(--cwo-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.cwo-item-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; margin-top: 0.25rem; }
.cwo-meta-loading { font-size: 0.74rem; color: var(--cwo-muted); }
.cwo-meta-name { font-size: 0.76rem; font-weight: 600; color: var(--cwo-muted); margin-right: 0.2rem; }
.cwo-meta-badge { font-size: 0.7rem; font-weight: 700; padding: 0.12rem 0.45rem; border-radius: 9999px; background: rgba(37, 99, 235, 0.12); color: var(--cwo-accent); }
.cwo-meta-warn { background: rgba(245, 158, 11, 0.18); color: #b45309; }
[data-theme='dark'] .cwo-meta-warn { color: #fbbf24; }
.cwo-qty-row { display: flex; align-items: center; gap: 0.5rem; }
.cwo-qty-input { max-width: 180px; font-weight: 700; }
.cwo-uom-chip { padding: 0.38rem 0.7rem; border-radius: 0.45rem; font-size: 0.78rem; font-weight: 700; background: var(--cwo-surface-alt); border: 1px solid var(--cwo-border); color: var(--cwo-muted); }
.cwo-accordion { border: 1px solid var(--cwo-border); border-radius: 0.6rem; overflow: visible; background: var(--cwo-surface-alt); }
.cwo-accordion-toggle { width: 100%; display: flex; align-items: center; justify-content: space-between; padding: 0.65rem 0.9rem; background: transparent; border: none; color: var(--cwo-text); font-size: 0.82rem; font-weight: 700; cursor: pointer; }
.cwo-accordion-label { display: flex; align-items: center; gap: 0.4rem; }
.cwo-chevron { display: inline-block; transition: transform 0.15s ease; font-size: 0.85rem; }
.cwo-chevron.open { transform: rotate(90deg); }
.cwo-accordion-hint { font-size: 0.72rem; font-weight: 600; color: var(--cwo-muted); }
.cwo-accordion-body { padding: 0.85rem 0.9rem 0.95rem; border-top: 1px solid var(--cwo-border); display: flex; flex-direction: column; gap: 0.85rem; }
.cwo-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
@media (max-width: 520px) { .cwo-grid-2 { grid-template-columns: 1fr; } }
.cwo-footer { display: flex; justify-content: flex-end; gap: 0.65rem; padding-top: 0.5rem; border-top: 1px solid var(--cwo-border); }
.cwo-btn { display: inline-flex; align-items: center; justify-content: center; gap: 0.45rem; padding: 0.55rem 1.05rem; border-radius: 0.5rem; font-size: 0.84rem; font-weight: 700; cursor: pointer; transition: all 0.15s ease; }
.cwo-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.cwo-btn-cancel { background: var(--cwo-surface-alt); border: 1px solid var(--cwo-input-border); color: var(--cwo-muted); }
.cwo-btn-cancel:hover:not(:disabled) { background: rgba(148, 163, 184, 0.18); color: var(--cwo-text); }
.cwo-btn-primary { background: var(--cwo-accent); border: 1px solid var(--cwo-accent); color: #ffffff; }
.cwo-btn-primary:hover:not(:disabled) { background: var(--cwo-accent-hover); border-color: var(--cwo-accent-hover); box-shadow: 0 3px 10px rgba(37, 99, 235, 0.25); }
.cwo-spinner { width: 14px; height: 14px; border: 2px solid rgba(255, 255, 255, 0.35); border-top-color: #ffffff; border-radius: 50%; animation: cwo-spin 0.75s linear infinite; }
@keyframes cwo-spin { to { transform: rotate(360deg); } }
</style>
