<script setup lang="ts">
import { ref, computed, watch } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  show: boolean;
  templates: any[];
  defaultTemplate?: string;
  itemCode?: string;
  /** "approve" (default) veya "reject" — amaç Reddedildi de QI belgesi oluşturmak */
  intent?: "approve" | "reject";
  onClose: () => void;
  onFetchDetails: (name: string) => Promise<any>;
  onSubmit: (payload: { template_name: string; readings: any[]; sample_size: number }) => Promise<void>;
}>();

const selectedTemplate = ref(props.defaultTemplate || "");
/** Şablondan gelen tüm parametreler */
const parameters = ref<any[]>([]);
/** Şablona ait ekler / dosyalar */
const attachments = ref<any[]>([]);
/** Kullanıcının eklediği okumalar (parametre havuzundan seçilmiş) */
const readings = ref<any[]>([]);
const loadingDetails = ref(false);
const submitting = ref(false);
const sampleSize = ref(1);

/** Halihazırda eklenmiş parametrelerin specification listesi */
const addedSpecs = computed(() => new Set(readings.value.map((r) => r.specification)));

/** Eklenebilir parametreler (henüz eklenmeyen) */
const availableParams = computed(() =>
  parameters.value.filter((p) => !addedSpecs.value.has(p.specification))
);

async function loadTemplate(name: string) {
  if (!name) {
    parameters.value = [];
    attachments.value = [];
    readings.value = [];
    return;
  }
  loadingDetails.value = true;
  try {
    const res = await props.onFetchDetails(name);
    const msg = res?.message;
    if (Array.isArray(msg)) {
      parameters.value = msg;
      attachments.value = [];
    } else if (msg && typeof msg === "object") {
      parameters.value = msg.parameters || [];
      attachments.value = msg.attachments || [];
    } else {
      parameters.value = [];
      attachments.value = [];
    }
    readings.value = []; // Temizle — kullanıcı kendisi ekleyecek
  } finally {
    loadingDetails.value = false;
  }
}

watch(
  () => selectedTemplate.value,
  (next) => loadTemplate(next)
);

watch(
  () => props.show,
  (next) => {
    if (next) {
      selectedTemplate.value = props.defaultTemplate || "";
      readings.value = [];
      attachments.value = [];
      sampleSize.value = 1;
      if (selectedTemplate.value) loadTemplate(selectedTemplate.value);
    }
  }
);

/** Havuzdan bir parametre ekle */
function addParam(p: any) {
  const isNumeric = Boolean(p.numeric);
  // Reject modunda parametreler varsayılan olarak Rejected gelir
  const defaultStatus = props.intent === "reject" ? "Rejected" : "Accepted";
  readings.value.push({
    specification: p.specification,
    reading_1: isNumeric ? "" : undefined,
    reading_value: isNumeric ? undefined : "",
    status: defaultStatus,
    numeric: isNumeric,
    min_value: p.min_value,
    max_value: p.max_value,
  });
}

/** Tüm parametreleri ekle */
function addAll() {
  for (const p of availableParams.value) {
    addParam(p);
  }
}

/** Eklenen bir okumayı kaldır */
function removeReading(index: number) {
  readings.value.splice(index, 1);
}

function updateStatus(index: number, status: string) {
  readings.value[index].status = status;
}

function onReadingChange(index: number) {
  const r = readings.value[index];
  if (r.numeric && r.reading_1 !== "") {
    const val = parseFloat(r.reading_1);
    if (!isNaN(val)) {
      r.status =
        (r.min_value !== null && r.min_value !== undefined && val < parseFloat(r.min_value)) ||
        (r.max_value !== null && r.max_value !== undefined && val > parseFloat(r.max_value))
          ? "Rejected"
          : "Accepted";
    }
  }
}

async function handleSubmit() {
  if (!selectedTemplate.value) return frappe.msgprint(__("Lütfen bir şablon seçin."));
  if (readings.value.length === 0)
    return frappe.msgprint(__("En az bir parametre eklemelisiniz."));

  for (const r of readings.value) {
    const val = r.numeric ? r.reading_1 : r.reading_value;
    if (r.numeric && (val === "" || val === null || val === undefined)) {
      return frappe.msgprint(r.specification + " " + __("için bir değer girmelisiniz."));
    }
  }

  submitting.value = true;
  try {
    await props.onSubmit({
      template_name: selectedTemplate.value,
      readings: readings.value,
      sample_size: sampleSize.value || 1,
    });
    props.onClose();
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="props.show" class="ck-modal-overlay">
      <div class="ck-modal">
        <div class="ck-modal-header" :style="props.intent === 'reject' ? 'border-bottom-color: var(--ck-danger)' : ''">
          <b>{{ props.intent === 'reject' ? __("Kalite Ret Formu") : __("Kalite Muayene Formu") }}</b>
          <button class="ck-modal-close" @click="props.onClose">&times;</button>
        </div>

        <div class="ck-modal-body">
          <!-- Ürün & Sample Size -->
          <div class="ck-form-row">
            <div class="ck-form-group" style="flex:1">
              <label>{{ __("Ürün:") }} <b>{{ props.itemCode }}</b></label>
            </div>
            <div class="ck-form-group" style="width:100px">
              <label>{{ __("Numune Sayısı") }}</label>
              <input type="number" v-model.number="sampleSize" min="1" class="ck-input" style="text-align:center" />
            </div>
          </div>

          <div class="ck-form-group">
            <label>{{ __("Kalite Şablonu") }}</label>
            <select v-model="selectedTemplate" class="ck-select">
              <option value="">{{ __("Şablon Seçiniz...") }}</option>
              <option v-for="t in props.templates" :key="t.name" :value="t.name">
                {{ t.quality_inspection_template_name || t.name }}
              </option>
            </select>
          </div>

          <!-- Şablon Ekleri / Attachments -->
          <div v-if="attachments.length > 0" class="ck-attachments-group">
            <div class="ck-attachments-header">
              <svg class="ck-attach-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
              </svg>
              <span>{{ __("Şablon Ekleri") }} ({{ attachments.length }})</span>
            </div>
            <div class="ck-attachment-chips">
              <a
                v-for="att in attachments"
                :key="att.name"
                :href="att.file_url"
                target="_blank"
                rel="noopener noreferrer"
                class="ck-attachment-chip"
                :title="att.file_name"
              >
                <svg class="ck-file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                <span class="ck-attachment-name">{{ att.file_name }}</span>
                <svg class="ck-external-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
              </a>
            </div>
          </div>

          <div v-if="loadingDetails" class="ck-muted text-center" style="padding: 20px;">{{ __("Parametreler yükleniyor...") }}</div>

          <template v-else-if="parameters.length > 0">
            <!-- Parametre havuzu (henüz eklenmeyenler) -->
            <div v-if="availableParams.length > 0" class="ck-param-pool">
              <div class="ck-pool-header">
                <span class="ck-pool-title">{{ __("Parametreler") }}</span>
                <button class="ck-add-all-btn" type="button" @click="addAll">
          + {{ __("Tümünü Ekle") }}
        </button>
              </div>
              <div class="ck-param-chips">
                <button
                  v-for="p in availableParams"
                  :key="p.specification"
                  type="button"
                  class="ck-param-chip"
                  @click="addParam(p)"
                >
                  + {{ p.specification }}
                  <span v-if="p.numeric" class="ck-chip-limits">
                    ({{ p.min_value }}–{{ p.max_value }})
                  </span>
                </button>
              </div>
            </div>

            <div
              v-if="availableParams.length > 0 && readings.length > 0"
              class="ck-divider"
            ></div>

            <!-- Eklenen okumalar -->
            <div v-if="readings.length > 0" class="ck-reading-list">
              <div v-for="(r, i) in readings" :key="i" class="ck-reading-item">
                <div class="ck-reading-info">
                  <span class="ck-reading-spec">{{ r.specification }}</span>
                  <div style="display:flex; align-items:center; gap:6px;">
                    <span v-if="r.numeric" class="ck-reading-limits">
                      ({{ r.min_value }} – {{ r.max_value }})
                    </span>
                    <button class="ck-remove-btn" type="button" @click="removeReading(i)">✕</button>
                  </div>
                </div>

                <div class="ck-reading-input-row">
                  <input
                    v-if="r.numeric"
                    type="number"
                    v-model="r.reading_1"
                    class="ck-input"
                    :placeholder="__('Değer')"
                    @input="onReadingChange(i)"
                  />
                  <input
                    v-else
                    type="text"
                    v-model="r.reading_value"
                    class="ck-input"
                    :placeholder="__('Sonuç')"
                  />

                  <div class="ck-status-btns">
                    <button
                      class="ck-status-btn"
                      :class="r.status === 'Accepted' && 'is-ok'"
                      @click="updateStatus(i, 'Accepted')"
                    >✔</button>
                    <button
                      class="ck-status-btn"
                      :class="r.status === 'Rejected' && 'is-reject'"
                      @click="updateStatus(i, 'Rejected')"
                    >✖</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Hiç eklenmemiş -->
            <div v-else class="ck-empty" style="padding: 16px 0;">
        {{ __("Yukarıdan parametre ekleyin.") }}
      </div>
          </template>

          <div v-else-if="selectedTemplate" class="ck-empty">
        {{ __("Bu şablonda parametre tanımlanmamış.") }}
      </div>
        </div>

        <div class="ck-modal-footer">
          <button class="ck-btn ck-btn--ghost" @click="props.onClose" :disabled="submitting">{{ __("Vazgeç") }}</button>
          <button
            class="ck-btn"
            :class="props.intent === 'reject' ? 'ck-btn--danger' : 'ck-btn--success'"
            style="flex: 2"
            @click="handleSubmit"
            :disabled="submitting || !selectedTemplate || readings.length === 0"
          >
            {{ submitting ? __("Kaydediliyor...") : (props.intent === 'reject' ? __("Kaydet ve Reddet") : __("Kaydet ve Onayla")) }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.ck-form-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  margin-bottom: 0;
}

.ck-modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 10px;
}

.ck-modal {
  background: var(--ck-bg);
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 25px rgba(0,0,0,0.2);
}

.ck-modal-header {
  padding: 16px;
  border-bottom: 1px solid var(--ck-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ck-modal-close {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: var(--ck-text-muted);
}

.ck-modal-body {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.ck-modal-footer {
  padding: 16px;
  border-top: 1px solid var(--ck-border);
  display: flex;
  gap: 10px;
}

.ck-form-group {
  margin-bottom: 16px;
}

.ck-form-group label {
  display: block;
  font-size: 13px;
  color: var(--ck-text-muted);
  margin-bottom: 6px;
}

.ck-select, .ck-input {
  width: 100%;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid var(--ck-border);
  background: var(--ck-surface);
  color: var(--ck-text);
  font-size: 14px;
}

/* Parametre havuzu */
.ck-param-pool {
  margin-bottom: 12px;
}

.ck-pool-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.ck-pool-title {
  font-size: 12px;
  color: var(--ck-text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.ck-add-all-btn {
  font-size: 12px;
  font-weight: 700;
  color: var(--ck-info, #3b82f6);
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 6px;
}

.ck-add-all-btn:hover {
  text-decoration: underline;
}

.ck-param-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ck-param-chip {
  padding: 6px 10px;
  border-radius: 20px;
  border: 1px dashed var(--ck-border-strong);
  background: var(--ck-surface);
  color: var(--ck-text);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.ck-param-chip:hover {
  background: var(--ck-ghost-bg);
  border-color: var(--ck-info, #3b82f6);
  color: var(--ck-info, #3b82f6);
}

.ck-chip-limits {
  opacity: 0.65;
  font-weight: 400;
}

.ck-divider {
  height: 1px;
  background: var(--ck-border-soft);
  margin: 12px 0;
}

/* Eklenen okumalar */
.ck-reading-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ck-reading-item {
  padding: 12px;
  border: 1px solid var(--ck-border-soft);
  border-radius: 12px;
  background: var(--btn-default-bg);
}

.ck-reading-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.ck-reading-spec {
  font-weight: 700;
  font-size: 13px;
}

.ck-reading-limits {
  font-size: 11px;
  color: var(--ck-text-muted);
}

.ck-remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--ck-text-muted);
  font-size: 14px;
  padding: 0 2px;
  line-height: 1;
}

.ck-remove-btn:hover {
  color: var(--ck-danger);
}

.ck-reading-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.ck-status-btns {
  display: flex;
  gap: 4px;
}

.ck-status-btn {
  border: 1px solid var(--ck-border);
  background: var(--ck-surface);
  border-radius: 8px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-weight: bold;
}

.ck-status-btn.is-ok {
  background: var(--ck-success);
  color: #fff;
  border-color: var(--ck-success);
}

.ck-status-btn.is-reject {
  background: var(--ck-danger);
  color: #fff;
  border-color: var(--ck-danger);
}

/* Şablon Ekleri */
.ck-attachments-group {
  margin-bottom: 16px;
  padding: 10px 12px;
  background: var(--ck-surface-soft, rgba(255, 255, 255, 0.03));
  border: 1px solid var(--ck-border-soft);
  border-radius: 12px;
}

.ck-attachments-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ck-text-muted);
  margin-bottom: 8px;
}

.ck-attach-icon {
  width: 14px;
  height: 14px;
  color: var(--ck-info, #3b82f6);
}

.ck-attachment-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ck-attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--ck-surface);
  border: 1px solid var(--ck-border);
  border-radius: 8px;
  color: var(--ck-text);
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  max-width: 100%;
}

.ck-attachment-chip:hover {
  background: var(--ck-primary-light, rgba(59, 130, 246, 0.1));
  border-color: var(--ck-primary, #3b82f6);
  color: var(--ck-primary, #3b82f6);
  transform: translateY(-1px);
  text-decoration: none;
}

.ck-file-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  opacity: 0.7;
}

.ck-attachment-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}

.ck-external-icon {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  opacity: 0.5;
  transition: transform 0.2s;
}

.ck-attachment-chip:hover .ck-external-icon {
  opacity: 1;
  transform: translate(1px, -1px);
}
</style>
