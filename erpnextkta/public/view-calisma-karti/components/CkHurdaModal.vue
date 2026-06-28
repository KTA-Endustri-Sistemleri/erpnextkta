<script setup lang="ts">
import { ref, onMounted, watch } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  show: boolean;
  doc: any; // Calisma Karti doc
  editData?: any; // If editing, pass the row data
  onClose: () => void;
  onSubmit: (payload: any) => Promise<void>;
}>();

const loading = ref(false);
const submitting = ref(false);

const parca_no = ref("");
const hurda_nedeni = ref("");
const miktar = ref<number | null>(null);
const aciklama = ref("");

const nedenOptions = ref<string[]>([]);
const itemResults = ref<any[]>([]);
const showItemResults = ref(false);

async function loadNedenOptions() {
  const r = await frappe.call("erpnextkta.kta_calisma_karti.api_impl.hurda.get_hurda_nedeni_options");
  nedenOptions.value = r.message || [];
}

async function searchItems(txt: string) {
  if (!txt || txt.length < 2) {
    itemResults.value = [];
    return;
  }
  const r = await frappe.call({
    method: "erpnextkta.kta_calisma_karti.api_impl.hurda.search_allowed_hurda_items",
    args: {
      doctype: "Item",
      txt: txt,
      searchfield: "name",
      start: 0,
      page_len: 20,
      filters: { calisma_karti: props.doc.name }
    }
  });
  itemResults.value = r.message || [];
}

function selectItem(item: any) {
  parca_no.value = item[0];
  showItemResults.value = false;
}

async function handleSubmit() {
  if (!parca_no.value) return frappe.msgprint(__("Lütfen bir parça seçin."));
  if (!miktar.value || miktar.value <= 0) return frappe.msgprint(__("Lütfen geçerli bir miktar girin."));
  if (!hurda_nedeni.value) return frappe.msgprint(__("Lütfen bir hurda nedeni seçin."));

  submitting.value = true;
  try {
    const payload: any = {
      parca_no: parca_no.value,
      hurda_nedeni: hurda_nedeni.value,
      miktar: miktar.value,
      aciklama: aciklama.value
    };
    if (props.editData?.name) {
      payload.rowname = props.editData.name;
    }
    await props.onSubmit(payload);
    props.onClose();
  } finally {
    submitting.value = false;
  }
}

watch(() => props.show, (val) => {
  if (val) {
    if (props.editData) {
      parca_no.value = props.editData.parca_no || "";
      hurda_nedeni.value = props.editData.hurda_nedeni || "";
      miktar.value = props.editData.miktar || null;
      aciklama.value = props.editData.aciklama || "";
    } else {
      parca_no.value = "";
      hurda_nedeni.value = "";
      miktar.value = null;
      aciklama.value = "";
    }
    loadNedenOptions();
  }
});

let searchTimer: any = null;
watch(() => parca_no.value, (val) => {
  if (!props.show) return;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchItems(val);
  }, 300);
});

</script>

<template>
  <Teleport to="body">
    <div v-if="props.show" class="ck-modal-overlay">
      <div class="ck-modal ck-glass-modal">
        <div class="ck-modal-header">
          <b>{{ props.editData ? __("Hurda Düzenle") : __("Hurda Ekle") }}</b>
          <button class="ck-modal-close" @click="props.onClose">&times;</button>
        </div>

        <div class="ck-modal-body">
          <!-- Item Search -->
          <div class="ck-form-group">
            <label>{{ __("Parça Numarası") }}</label>
            <div class="ck-search-wrapper">
              <input 
                type="text" 
                v-model="parca_no" 
                class="ck-input" 
                :placeholder="__('Parça ara veya kod gir...')"
                @focus="showItemResults = true"
              />
              <div v-if="showItemResults && itemResults.length > 0" class="ck-search-results">
                <div 
                  v-for="item in itemResults" 
                  :key="item[0]" 
                  class="ck-search-item"
                  @click="selectItem(item)"
                >
                  <div class="ck-item-code">{{ item[0] }}</div>
                  <div class="ck-item-name">{{ item[1] }}</div>
                </div>
              </div>
            </div>
          </div>

        <div class="ck-form-group">
            <label>{{ __("Miktar") }}</label>
            <input type="number" v-model.number="miktar" class="ck-input" placeholder="0.00" />
        </div>

        <div class="ck-form-group">
            <label>{{ __("Hurda Nedeni") }}</label>
            <div class="ck-pill-list">
                <button 
                    v-for="opt in nedenOptions" 
                    :key="opt" 
                    type="button"
                    class="ck-pill"
                    :class="{ 'is-active': hurda_nedeni === opt }"
                    @click="hurda_nedeni = opt"
                >
                    {{ opt }}
                </button>
            </div>
        </div>

          <div class="ck-form-group">
              <label>{{ __("Açıklama (Opsiyonel)") }}</label>
              <textarea v-model="aciklama" class="ck-input" rows="2" :placeholder="__('Ek bilgi...')"></textarea>
          </div>

          <div class="ck-info-box" v-if="parca_no">
              <div class="ck-info-text">{{ __("Birim ve Depo bilgileri İş Emri üzerinden otomatik atanacaktır.") }}</div>
          </div>
        </div>

        <div class="ck-modal-footer">
          <button class="ck-btn ck-btn--ghost" @click="props.onClose" :disabled="submitting">{{ __("Vazgeç") }}</button>
          <button
            class="ck-btn ck-btn--primary"
            style="flex: 2"
            @click="handleSubmit"
            :disabled="submitting || !parca_no || !miktar || !hurda_nedeni"
          >
            {{ submitting ? __("Kaydediliyor...") : __("Kaydet") }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.ck-glass-modal {
  background: var(--ck-bg);
  border: 1px solid var(--ck-glass-border);
  box-shadow: 0 20px 50px rgba(0,0,0,0.4);
}

.ck-modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 20px;
}

.ck-modal {
  width: 100%;
  max-width: 440px;
  max-height: 92vh;
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ck-modal-header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--ck-glass-border-soft);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ck-modal-header b {
  font-size: 18px;
  letter-spacing: -0.02em;
}

.ck-modal-close {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: var(--ck-text-muted);
  line-height: 1;
}

.ck-modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.ck-modal-footer {
  padding: 20px 24px;
  border-top: 1px solid var(--ck-glass-border-soft);
  display: flex;
  gap: 12px;
}

.ck-form-group {
  margin-bottom: 20px;
}

.ck-form-group label {
  display: block;
  font-size: 13px;
  font-weight: 700;
  color: var(--ck-text-muted);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.ck-form-row {
  display: flex;
  gap: 16px;
}

.ck-input, .ck-select {
  width: 100%;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid var(--ck-glass-border);
  background: var(--ck-glass-input-bg, rgba(255,255,255,0.05));
  color: var(--ck-text);
  font-size: 15px;
  transition: all 0.2s ease;
}

.ck-input:focus, .ck-select:focus {
  outline: none;
  border-color: var(--ck-primary);
  background: var(--ck-glass-input-bg-focus, rgba(255,255,255,0.1));
  box-shadow: 0 0 0 4px rgba(var(--ck-primary-rgb), 0.1);
}

.ck-pill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.ck-pill {
  padding: 10px 16px;
  border-radius: 14px;
  border: 1px solid var(--ck-glass-border);
  background: var(--ck-glass-bg);
  color: var(--ck-text-muted);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
  line-height: 1.2;
}
.ck-pill:hover {
  background: var(--ck-glass-border-soft);
  color: var(--ck-text);
  border-color: var(--ck-glass-border);
}
.ck-pill.is-active {
  background: var(--ck-primary);
  color: var(--ck-primary-contrast);
  border-color: var(--ck-primary);
  box-shadow: 0 4px 15px rgba(0,0,0,0.2);
  transform: translateY(-1px);
}

.ck-search-wrapper {
  position: relative;
}

.ck-search-results {
  position: absolute;
  top: calc(100% + 4px);
  left: 0; right: 0;
  background: var(--ck-bg);
  border: 1px solid var(--ck-glass-border);
  border-radius: 12px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 100;
  box-shadow: 0 10px 30px rgba(0,0,0,0.2);
}

.ck-search-item {
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--ck-glass-border-soft);
}

.ck-search-item:last-child {
  border-bottom: none;
}

.ck-search-item:hover {
  background: var(--ck-ghost-bg);
}

.ck-item-code {
  font-weight: 800;
  font-size: 14px;
  color: var(--ck-primary);
}

.ck-item-name {
  font-size: 12px;
  color: var(--ck-text-muted);
}

.ck-info-box {
    background: rgba(var(--ck-primary-rgb), 0.08);
    border-radius: 12px;
    padding: 12px 16px;
    border-left: 4px solid var(--ck-primary);
    margin-top: -10px;
    margin-bottom: 20px;
}

.ck-info-text {
    font-size: 12px;
    color: var(--ck-text);
    line-height: 1.5;
}
</style>
