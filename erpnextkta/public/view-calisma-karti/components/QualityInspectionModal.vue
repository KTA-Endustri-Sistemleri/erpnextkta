<script setup lang="ts">
import { ref, computed, watch } from "vue";

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
    readings.value = [];
    return;
  }
  loadingDetails.value = true;
  try {
    const res = await props.onFetchDetails(name);
    parameters.value = res.message || [];
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
  if (!selectedTemplate.value) return frappe.msgprint("Lütfen bir şablon seçin.");
  if (readings.value.length === 0)
    return frappe.msgprint("En az bir parametre eklemelisiniz.");

  for (const r of readings.value) {
    const val = r.numeric ? r.reading_1 : r.reading_value;
    if (r.numeric && (val === "" || val === null || val === undefined)) {
      return frappe.msgprint(`${r.specification} için bir değer girmelisiniz.`);
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
  <div v-if="props.show" class="ck-modal-overlay">
    <div class="ck-modal">
      <div class="ck-modal-header" :style="props.intent === 'reject' ? 'border-bottom-color: var(--ck-danger)' : ''">
        <b>{{ props.intent === 'reject' ? 'Kalite Ret Formu' : 'Kalite Muayene Formu' }}</b>
        <button class="ck-modal-close" @click="props.onClose">&times;</button>
      </div>

      <div class="ck-modal-body">
        <!-- Ürün & Sample Size -->
        <div class="ck-form-row">
          <div class="ck-form-group" style="flex:1">
            <label>Ürün: <b>{{ props.itemCode }}</b></label>
          </div>
          <div class="ck-form-group" style="width:100px">
            <label>Numune Sayısı</label>
            <input type="number" v-model.number="sampleSize" min="1" class="ck-input" style="text-align:center" />
          </div>
        </div>

        <div class="ck-form-group">
          <label>Kalite Şablonu</label>
          <select v-model="selectedTemplate" class="ck-select">
            <option value="">Şablon Seçiniz...</option>
            <option v-for="t in props.templates" :key="t.name" :value="t.name">
              {{ t.quality_inspection_template_name || t.name }}
            </option>
          </select>
        </div>

        <div v-if="loadingDetails" class="ck-muted text-center" style="padding: 20px;">
          Parametreler yükleniyor...
        </div>

        <template v-else-if="parameters.length > 0">
          <!-- Parametre havuzu (henüz eklenmeyenler) -->
          <div v-if="availableParams.length > 0" class="ck-param-pool">
            <div class="ck-pool-header">
              <span class="ck-pool-title">Parametreler</span>
              <button class="ck-add-all-btn" type="button" @click="addAll">
                + Tümünü Ekle
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
                  placeholder="Değer"
                  @input="onReadingChange(i)"
                />
                <input
                  v-else
                  type="text"
                  v-model="r.reading_value"
                  class="ck-input"
                  placeholder="Sonuç"
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
            Yukarıdan parametre ekleyin.
          </div>
        </template>

        <div v-else-if="selectedTemplate" class="ck-empty">
          Bu şablonda parametre tanımlanmamış.
        </div>
      </div>

      <div class="ck-modal-footer">
        <button class="ck-btn ck-btn--ghost" @click="props.onClose" :disabled="submitting">Vazgeç</button>
        <button
          class="ck-btn"
          :class="props.intent === 'reject' ? 'ck-btn--danger' : 'ck-btn--success'"
          style="flex: 2"
          @click="handleSubmit"
          :disabled="submitting || !selectedTemplate || readings.length === 0"
        >
          {{ submitting ? 'Kaydediliyor...' : (props.intent === 'reject' ? 'Kaydet ve Reddet' : 'Kaydet ve Onayla') }}
        </button>
      </div>
    </div>
  </div>
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
</style>
