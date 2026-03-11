<script setup lang="ts">
import { ref, onMounted, watch } from "vue";

const props = defineProps<{
  show: boolean;
  templates: any[];
  defaultTemplate?: string;
  itemCode?: string;
  onClose: () => void;
  onFetchDetails: (name: string) => Promise<any>;
  onSubmit: (payload: { template_name: string; readings: any[] }) => Promise<void>;
}>();

const selectedTemplate = ref(props.defaultTemplate || "");
const parameters = ref<any[]>([]);
const readings = ref<any[]>([]);
const loadingDetails = ref(false);
const submitting = ref(false);

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
    // Initialize readings
    readings.value = parameters.value.map(p => ({
      specification: p.specification,
      reading_1: "",
      status: "Accepted",
      numeric: p.numeric,
      min_value: p.min_value,
      max_value: p.max_value
    }));
  } finally {
    loadingDetails.value = false;
  }
}

watch(() => selectedTemplate.value, (next) => {
  loadTemplate(next);
});

watch(() => props.show, (next) => {
    if (next) {
        selectedTemplate.value = props.defaultTemplate || "";
        if (selectedTemplate.value) loadTemplate(selectedTemplate.value);
    }
});

async function handleSubmit() {
  if (!selectedTemplate.value) return frappe.msgprint("Lütfen bir şablon seçin.");
  
  // Validation: Numeric fields should have values
  for (const r of readings.value) {
    if (r.numeric && (r.reading_1 === "" || r.reading_1 === null)) {
      return frappe.msgprint(`${r.specification} için bir değer girmelisiniz.`);
    }
  }

  submitting.value = true;
  try {
    await props.onSubmit({
      template_name: selectedTemplate.value,
      readings: readings.value
    });
    props.onClose();
  } finally {
    submitting.value = false;
  }
}

function updateStatus(index: number, status: string) {
    readings.value[index].status = status;
}

// Auto status for numeric
function onReadingChange(index: number) {
    const r = readings.value[index];
    if (r.numeric && r.reading_1 !== "") {
        const val = parseFloat(r.reading_1);
        if (!isNaN(val)) {
            if ((r.min_value !== null && val < r.min_value) || (r.max_value !== null && val > r.max_value)) {
                r.status = "Rejected";
            } else {
                r.status = "Accepted";
            }
        }
    }
}

</script>

<template>
  <div v-if="props.show" class="ck-modal-overlay">
    <div class="ck-modal">
      <div class="ck-modal-header">
        <b>Kalite Muayene Formu</b>
        <button class="ck-modal-close" @click="props.onClose">&times;</button>
      </div>

      <div class="ck-modal-body">
        <div class="ck-form-group">
          <label>Ürün: <b>{{ props.itemCode }}</b></label>
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

        <div v-else-if="parameters.length > 0" class="ck-reading-list">
          <div v-for="(p, i) in readings" :key="i" class="ck-reading-item">
            <div class="ck-reading-info">
              <span class="ck-reading-spec">{{ p.specification }}</span>
              <span v-if="p.numeric" class="ck-reading-limits">
                 ({{ p.min_value }} - {{ p.max_value }})
              </span>
            </div>
            
            <div class="ck-reading-input-row">
              <input 
                v-if="p.numeric"
                type="number" 
                v-model="p.reading_1" 
                class="ck-input" 
                placeholder="Değer"
                @input="onReadingChange(i)"
              />
              <input 
                v-else
                type="text" 
                v-model="p.reading_1" 
                class="ck-input" 
                placeholder="Sonuç"
              />

              <div class="ck-status-btns">
                <button 
                  class="ck-status-btn" 
                  :class="p.status === 'Accepted' && 'is-ok' "
                  @click="updateStatus(i, 'Accepted')"
                >✔</button>
                <button 
                  class="ck-status-btn" 
                  :class="p.status === 'Rejected' && 'is-reject' "
                  @click="updateStatus(i, 'Rejected')"
                >✖</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="selectedTemplate" class="ck-empty">
          Bu şablonda parametre tanımlanmamış.
        </div>
      </div>

      <div class="ck-modal-footer">
        <button class="ck-btn ck-btn--ghost" @click="props.onClose" :disabled="submitting">Vazgeç</button>
        <button 
            class="ck-btn ck-btn--success" 
            style="flex: 2" 
            @click="handleSubmit" 
            :disabled="submitting || !selectedTemplate || parameters.length === 0"
        >
            {{ submitting ? 'Kaydediliyor...' : 'Kaydet ve Onayla' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ck-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
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

.ck-reading-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
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
