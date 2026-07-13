<script setup lang="ts">
import { ref, onMounted, watch, computed } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  show: boolean;
  doc: any;
  editData?: any;
  altOpOptions: any[];
  ekranTipi: string;
  onClose: () => void;
  onSubmit: (payload: any) => Promise<void>;
}>();

const loading = ref(false);
const submitting = ref(false);

const alt_operasyon = ref("");
const satir_no = ref("");
const note = ref("");

// Dynamic raw material rows
const hammaddeRows = ref<any[]>([]);
const ortaHammadde = ref<any>({ hammadde: "", boyut_mm: null, islem_adedi: 1, uom: "", yon: "Orta", _showItemResults: false, _itemResults: [] });
const solHammaddeRows = ref<any[]>([]);
const sagHammaddeRows = ref<any[]>([]);

function initRows() {
  if (props.editData && props.editData.hammadde_tuketimleri && props.editData.hammadde_tuketimleri.length > 0) {
    if (props.ekranTipi === 'Çoklu Hammadde') {
      const hList = props.editData.hammadde_tuketimleri;
      const ortaList = hList.filter((x: any) => x.yon === 'Orta' || !x.yon);
      const solList = hList.filter((x: any) => x.yon === 'Sol');
      const sagList = hList.filter((x: any) => x.yon === 'Sağ');

      if (ortaList.length > 0) {
        ortaHammadde.value = { ...ortaList[0], _showItemResults: false, _itemResults: [] };
      } else {
        ortaHammadde.value = { hammadde: "", boyut_mm: null, islem_adedi: 1, uom: "", yon: "Orta", _showItemResults: false, _itemResults: [] };
      }

      solHammaddeRows.value = solList.map((x: any) => ({ ...x, unique_id: Math.random().toString(36).substr(2, 9), _showItemResults: false, _itemResults: [] }));
      sagHammaddeRows.value = sagList.map((x: any) => ({ ...x, unique_id: Math.random().toString(36).substr(2, 9), _showItemResults: false, _itemResults: [] }));
    } else {
      hammaddeRows.value = props.editData.hammadde_tuketimleri.map((r: any) => ({ ...r, unique_id: Math.random().toString(36).substr(2, 9), wip_id: r.source_wip_ids, _showItemResults: false, _itemResults: [] }));
    }
  } else {
    hammaddeRows.value = [];
    ortaHammadde.value = { hammadde: "", boyut_mm: null, islem_adedi: 1, uom: "", yon: "Orta", _showItemResults: false, _itemResults: [] };
    solHammaddeRows.value = [];
    sagHammaddeRows.value = [];
    if (!props.editData && props.ekranTipi !== 'Çoklu Hammadde') {
      addRow();
    }
  }
}

function addRow() {
  hammaddeRows.value.push({ unique_id: Math.random().toString(36).substr(2, 9), hammadde: "", boyut_mm: null, islem_adedi: 1, uom: "", hedef_node_id: "", _showItemResults: false, _itemResults: [] });
}
function removeRow(index: number) {
  hammaddeRows.value.splice(index, 1);
}

function addSolRow() {
  solHammaddeRows.value.push({ unique_id: Math.random().toString(36).substr(2, 9), hammadde: "", boyut_mm: null, yon: "Sol", _showItemResults: false, _itemResults: [] });
}
function removeSolRow(index: number) {
  solHammaddeRows.value.splice(index, 1);
}

function addSagRow() {
  sagHammaddeRows.value.push({ unique_id: Math.random().toString(36).substr(2, 9), hammadde: "", boyut_mm: null, yon: "Sağ", _showItemResults: false, _itemResults: [] });
}
function removeSagRow(index: number) {
  sagHammaddeRows.value.splice(index, 1);
}

// Item search logic per row
let searchTimer: any = null;
async function searchItems(txt: string, row: any) {
  if (!txt || txt.length < 2) {
    row._itemResults = [];
    return;
  }
  const r = await frappe.call({
    method: "erpnextkta.kta_calisma_karti.api_impl.hurda.search_allowed_hurda_items",
    args: { doctype: "Item", txt: txt, searchfield: "name", start: 0, page_len: 20, filters: { calisma_karti: props.doc.name } }
  });
  row._itemResults = r.message || [];
}

function onSearchInput(val: string, row: any) {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchItems(val, row);
  }, 300);
}

function selectItem(item: any, row: any) {
  row.hammadde = item[0];
  row._showItemResults = false;
  
  frappe.call({
    method: "erpnextkta.kta_calisma_karti.api_impl.alt_operasyon.get_item_uom",
    args: { item_code: item[0] },
    callback: (r: any) => {
      if (r && r.message) {
        row.uom = r.message;
      }
    }
  });
}

async function handleSubmit() {
  if (!alt_operasyon.value) return frappe.msgprint(__("Lütfen bir alt işlem seçin."));
  
  if (selectedWipIds.value.length > 0 && maxHavuzAdedi.value !== null) {
    const entered = Number(havuzIslemAdedi.value) || 1;
    if (entered > maxHavuzAdedi.value) {
      return frappe.msgprint(__("Havuzdan seçilen ürünler için girilen işlem adedi ({0}), mevcut maksimum adedi ({1}) aşamaz.", [entered, maxHavuzAdedi.value]));
    }
  }

  submitting.value = true;
  try {
    let payloadRows: any[] = [];
    
    if (props.ekranTipi === 'Çoklu Hammadde') {
      let baseIslemAdedi = ortaHammadde.value.islem_adedi || 1;
      
      if (selectedWipIds.value.length > 0) {
         baseIslemAdedi = havuzIslemAdedi.value || 1;
         for (const wipId of selectedWipIds.value) {
            const poolWip = wipPool.value.find(w => w.wip_id === wipId);
            payloadRows.push({
              hammadde: "",
              boyut_mm: 0,
              islem_adedi: baseIslemAdedi,
              uom: "Adet",
              yon: "Orta",
              source_wip_ids: wipId,
              hedef_kavite: poolWip ? poolWip.hedef_kavite : ""
            });
         }
      } else {
        if (ortaHammadde.value.hammadde || (ortaHammadde.value.boyut_mm && ortaHammadde.value.boyut_mm > 0)) {
          payloadRows.push({ ...ortaHammadde.value, yon: "Orta" });
        }
      }

      for(const r of solHammaddeRows.value) {
        if(r.hammadde || (r.boyut_mm && r.boyut_mm > 0)) payloadRows.push({ ...r, yon: "Sol", islem_adedi: baseIslemAdedi });
      }
      for(const r of sagHammaddeRows.value) {
        if(r.hammadde || (r.boyut_mm && r.boyut_mm > 0)) payloadRows.push({ ...r, yon: "Sağ", islem_adedi: baseIslemAdedi });
      }
    } else {
      if (selectedWipIds.value.length > 0) {
         for (const wipId of selectedWipIds.value) {
            const poolWip = wipPool.value.find(w => w.wip_id === wipId);
            if (poolWip && poolWip.mappings && poolWip.mappings.length > 0) {
                for (const m of poolWip.mappings) {
                    payloadRows.push({
                      hammadde: "",
                      boyut_mm: 0,
                      islem_adedi: havuzIslemAdedi.value || 1,
                      uom: "Adet",
                      source_wip_ids: wipId,
                      hedef_kavite: m.pin,
                      hedef_node_id: m.node_id
                    });
                }
            } else {
                payloadRows.push({
                  hammadde: "",
                  boyut_mm: 0,
                  islem_adedi: havuzIslemAdedi.value || 1,
                  uom: "Adet",
                  source_wip_ids: wipId,
                  hedef_kavite: "",
                  hedef_node_id: ""
                });
            }
         }
      }
      const manualRows = hammaddeRows.value.map(r => ({
        hammadde: r.hammadde,
        boyut_mm: r.boyut_mm || 0,
        islem_adedi: r.islem_adedi || 1,
        uom: r.uom || "",
        hedef_node_id: r.hedef_node_id || "",
        source_wip_ids: r.wip_id || r.source_wip_ids || "",
        hedef_kavite: r.hedef_kavite || ""
      }));
      payloadRows = payloadRows.concat(manualRows);
    }

    const payload: any = {
      alt_operasyon: alt_operasyon.value,
      satir_no: satir_no.value,
      note: note.value,
      hammadde_tuketimleri: payloadRows,
      source_wip_ids: selectedWipIds.value.join(",")
    };
    
    if (props.editData?.name) {
      payload.row_id = props.editData.name;
    }
    await props.onSubmit(payload);
    props.onClose();
  } finally {
    submitting.value = false;
  }
}

const wipPool = ref<any[]>([]);
const selectedWipIds = ref<string[]>([]);
const poolLoading = ref(false);

async function fetchWipPool(operasyon: string) {
  if (!operasyon) {
    wipPool.value = [];
    selectedWipIds.value = [];
    return;
  }
  poolLoading.value = true;
  try {
    const args: any = {
      work_order: props.doc.custom_work_order,
      operasyon: operasyon
    };
    if (props.editData?.name) {
      args.exclude_row = props.editData.name;
    }
    const res = await frappe.call({
      method: "erpnextkta.kta_calisma_karti.api_impl.alt_operasyon.get_work_order_pool",
      args: args
    });
    wipPool.value = res.message || [];
    
    wipPool.value.forEach(w => {
        w.mappings = [];
        if (props.editData && props.editData.hammadde_tuketimleri) {
            const matches = props.editData.hammadde_tuketimleri.filter((r:any) => r.source_wip_ids === w.wip_id);
            for (const match of matches) {
                w.mappings.push({
                    node_id: match.hedef_node_id || "",
                    pin: match.hedef_kavite || ""
                });
            }
        }
        if (w.mappings.length === 0) {
            w.mappings.push({ node_id: "", pin: "" });
        }
    });
  } finally {
    poolLoading.value = false;
  }
}

watch(() => props.show, (val) => {
  if (val) {
    if (props.editData) {
      alt_operasyon.value = props.editData.alt_operasyon || "";
      satir_no.value = props.editData.satir_no || "";
      note.value = props.editData.note || "";
      if (props.editData.hammadde_tuketimleri && props.editData.hammadde_tuketimleri.length > 0) {
          const poolItems = props.editData.hammadde_tuketimleri.filter((r:any) => r.source_wip_ids);
          if (poolItems.length > 0) {
              const allIds = poolItems.map((r:any) => r.source_wip_ids).join(",");
              selectedWipIds.value = allIds.split(",").map((s:string) => s.trim()).filter((s:string) => s);
              havuzIslemAdedi.value = poolItems[0].islem_adedi || 1;
          }
      }
    } else {
      alt_operasyon.value = "";
      satir_no.value = "";
      note.value = "";
      selectedWipIds.value = [];
    }
    initRows();
    fetchWipPool(props.doc.operasyon);
  }
});

const havuzIslemAdedi = ref<number | "">("");

const maxHavuzAdedi = computed(() => {
  if (selectedWipIds.value.length === 0) return null;
  const selectedWips = wipPool.value.filter((w: any) => selectedWipIds.value.includes(w.wip_id));
  if (selectedWips.length === 0) return null;
  return Math.min(...selectedWips.map((w: any) => w.islem_adedi || 1));
});

const isQCRequired = computed(() => {
  return !!props.doc.alt_operasyon_bazli_kalite;
});
</script>

<template>
  <Teleport to="body">
    <div v-if="props.show" class="ck-modal-overlay">
      <div class="ck-modal ck-glass-modal" style="max-width: 600px;">
        <div class="ck-modal-header">
          <b>{{ props.editData ? __("Alt İşlem Düzenle") : __("Alt İşlem Ekle") }}</b>
          <button class="ck-modal-close" @click="props.onClose">&times;</button>
        </div>

        <div class="ck-modal-body">
          <div class="ck-form-row">
            <div class="ck-form-group" style="flex: 2;">
              <label>{{ __("Alt İşlem") }}</label>
              <select v-model="alt_operasyon" class="ck-select">
                <option value="" disabled>{{ __("Seçiniz...") }}</option>
                <option v-for="opt in props.altOpOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>
            <div class="ck-form-group" style="flex: 1;" v-if="isQCRequired">
              <label>{{ __("Satır No") }}</label>
              <input type="text" v-model="satir_no" class="ck-input" :placeholder="__('Örn: K1')" />
            </div>
          </div>

          <!-- Dynamic Materials Section -->
          <div class="ck-form-group" style="margin-top: 10px; border-top: 1px dashed var(--ck-glass-border-soft); padding-top: 20px;">
            
            <!-- HAVUZ KISMI -->
            <div v-if="wipPool.length > 0" style="border: 1px solid var(--ck-primary); border-radius: 8px; padding: 12px; margin-bottom: 16px; background: rgba(0,0,0,0.02);">
              <label class="form-label" style="text-align: center; border-bottom: 1px solid var(--ck-primary); padding-bottom: 8px; margin-bottom: 12px; display: block; font-weight: bold; color: var(--ck-primary);">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px; vertical-align: text-bottom;"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
                {{ __("ÖNCEKİ İŞLEMLERDEN GELENLER (HAVUZ)") }}
              </label>
              <div v-if="poolLoading" style="text-align: center; color: var(--ck-muted);">{{ __("Yükleniyor...") }}</div>
              <div v-else style="display: flex; flex-direction: column; gap: 8px;">
                <div v-for="wip in wipPool" :key="wip.wip_id" style="display: flex; flex-direction: column; gap: 4px; padding: 4px; border-radius: 4px;" :style="{ background: selectedWipIds.includes(wip.wip_id) ? 'rgba(0,0,0,0.05)' : 'transparent' }">
                  <label style="display: flex; align-items: center; flex: 1; cursor: pointer;">
                    <input type="checkbox" :value="wip.wip_id" v-model="selectedWipIds" />
                    <span style="margin-left: 8px;">{{ wip.label }} <strong style="color: var(--ck-primary); font-size: 11px; margin-left: 4px;">({{ wip.islem_adedi || 1 }} Adet)</strong></span>
                  </label>
                  <div v-if="selectedWipIds.includes(wip.wip_id)" style="margin-left: 24px; display: flex; flex-direction: column; gap: 6px; margin-top: 4px;">
                    <div v-for="(m, idx) in wip.mappings" :key="idx" style="display: flex; gap: 6px; align-items: center;">
                      <select class="ck-select ck-select-small" v-model="m.node_id" style="width: 120px; padding: 4px 8px; font-size: 12px; min-height: unset; height: 26px;">
                          <template v-if="wip.endpoints && wip.endpoints.length > 0">
                              <option value="" disabled>{{ __("Uç Seç") }}</option>
                              <option v-for="ep in wip.endpoints" :key="ep.id" :value="ep.id">{{ ep.label }}</option>
                          </template>
                          <template v-else>
                              <option value="" disabled>{{ __("Uç Seç") }}</option>
                              <option value="T1">{{ __("Sol Uç (T1)") }}</option>
                              <option value="T2">{{ __("Sağ Uç (T2)") }}</option>
                          </template>
                      </select>
                      <input type="text" class="ck-input ck-input-small" v-model="m.pin" :placeholder="__('Pin/Kavite No')" style="width: 100px; padding: 4px 8px; font-size: 12px; min-height: unset; height: 26px;" />
                      
                      <button class="ck-btn ck-btn-secondary" style="padding: 0 8px; height: 26px; border-radius: 4px; font-size: 14px; display: flex; align-items: center; justify-content: center;" @click.prevent.stop="wip.mappings.push({node_id:'', pin:''})" title="Uç Ekle">+</button>
                      <button v-if="wip.mappings.length > 1" class="ck-btn ck-btn-danger" style="padding: 0 8px; height: 26px; border-radius: 4px; font-size: 14px; display: flex; align-items: center; justify-content: center;" @click.prevent.stop="wip.mappings.splice(idx, 1)" title="Ucu Sil">&times;</button>
                    </div>
                  </div>
                </div>
                
                <div v-if="selectedWipIds.length > 0" style="margin-top: 12px; border-top: 1px dashed var(--ck-primary); padding-top: 12px;">
                  <label class="form-label">
                    {{ __("Havuz Ürünleri İçin İşlem Adedi") }}
                    <span v-if="maxHavuzAdedi !== null" style="color: var(--ck-primary); font-size: 11px; margin-left: 8px; text-transform: none;">
                      (Maksimum: {{ maxHavuzAdedi }})
                    </span>
                  </label>
                  <input type="number" class="ck-input" v-model="havuzIslemAdedi" :max="maxHavuzAdedi !== null ? maxHavuzAdedi : undefined" :placeholder="__('Kaç adet işlenecek? (Örn: 1)')" style="max-width: 250px;" />
                  <div v-if="maxHavuzAdedi !== null && Number(havuzIslemAdedi) > maxHavuzAdedi" style="color: var(--ck-danger, red); font-size: 11px; margin-top: 6px;">
                    {{ __("Girilen miktar mevcut maksimum adedi ({0}) aşıyor!", [maxHavuzAdedi]) }}
                  </div>
                </div>
              </div>
            </div>

            <template v-if="props.ekranTipi === 'Çoklu Hammadde'">

              <!-- ORTA KISIM: KABLO -->
              <div v-if="selectedWipIds.length === 0" style="border: 1px solid var(--ck-glass-border); border-radius: 8px; padding: 12px; margin-bottom: 16px; background: rgba(0,0,0,0.02);">
                <label class="form-label" style="text-align: center; border-bottom: 1px solid var(--ck-glass-border); padding-bottom: 8px; margin-bottom: 12px; display: block; font-weight: bold; color: var(--ck-primary);">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px; vertical-align: text-bottom;"><path d="M4 9a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H4z"></path><path d="M4 21a2 2 0 0 1-2-2v-2a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H4z"></path><path d="M15 9v6"></path><path d="M9 9v6"></path></svg>
                  {{ __("ANA KABLO / MALZEME (ORTA)") }}
                </label>
                <div style="display: flex; gap: 8px; align-items: flex-start;">
                  <div class="ck-search-wrapper" style="flex: 2; min-width: 140px;">
                    <input type="text" v-model="ortaHammadde.hammadde" class="ck-input" :placeholder="__('Kablo/Hammadde seç...')" @focus="ortaHammadde._showItemResults = true" @input="onSearchInput(ortaHammadde.hammadde, ortaHammadde)" />
                    <div v-if="ortaHammadde._showItemResults && ortaHammadde._itemResults && ortaHammadde._itemResults.length > 0" class="ck-search-results">
                      <div v-for="item in ortaHammadde._itemResults" :key="item[0]" class="ck-search-item" @click="selectItem(item, ortaHammadde)">
                        <div class="ck-item-code">{{ item[0] }}</div>
                        <div class="ck-item-name">{{ item[1] }}</div>
                      </div>
                    </div>
                  </div>
                  <div style="flex: 1;">
                    <input type="number" class="ck-input" v-model="ortaHammadde.boyut_mm" :placeholder="__('Boy (mm)')" />
                  </div>
                  <div style="flex: 1;">
                    <input type="number" class="ck-input" v-model="ortaHammadde.islem_adedi" :placeholder="__('Adet')" />
                  </div>
                </div>
              </div>

              <!-- YAN KISIMLAR (SOL / SAĞ) -->
              <div style="display: flex; gap: 16px;">
                
                <!-- SOL UÇ -->
                <div style="flex: 1; border: 1px dashed var(--ck-glass-border); border-radius: 8px; padding: 12px; background: rgba(0,0,0,0.01);">
                  <label class="form-label" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--ck-glass-border); padding-bottom: 8px; margin-bottom: 12px; color: var(--ck-text);">
                    <span><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px;"><circle cx="12" cy="12" r="10"></circle><polyline points="12 8 8 12 12 16"></polyline><line x1="16" y1="12" x2="8" y2="12"></line></svg> {{ __("SOL UÇ") }}</span>
                    <button class="ck-btn ck-btn-secondary" style="font-size: 10px; padding: 2px 6px; height: auto;" @click="addSolRow">
                      + {{ __("Ekle") }}
                    </button>
                  </label>
                  <div v-if="solHammaddeRows.length === 0" style="text-align: center; color: var(--ck-muted); font-size: 12px; font-style: italic; padding: 8px 0;">
                    {{ __("Sol uca eklenecek malzeme yok") }}
                  </div>
                  <div v-for="(row, index) in solHammaddeRows" :key="row.unique_id" style="display: flex; gap: 4px; margin-bottom: 8px; align-items: flex-start;">
                    <div class="ck-search-wrapper" style="flex: 3;">
                      <input type="text" v-model="row.hammadde" class="ck-input ck-input-small" :placeholder="__('Malzeme...')" @focus="row._showItemResults = true" @input="onSearchInput(row.hammadde, row)" />
                      <div v-if="row._showItemResults && row._itemResults && row._itemResults.length > 0" class="ck-search-results">
                        <div v-for="item in row._itemResults" :key="item[0]" class="ck-search-item" @click="selectItem(item, row)">
                          <div class="ck-item-code">{{ item[0] }}</div>
                        </div>
                      </div>
                    </div>
                    <div style="flex: 2;">
                      <input type="number" class="ck-input ck-input-small" v-model="row.boyut_mm" :placeholder="__('Sıyırma/Boy')" />
                    </div>
                    <button class="ck-btn ck-btn-danger" style="padding: 0 8px; height: 36px; border-radius: 8px;" @click="removeSolRow(index)">
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                  </div>
                </div>

                <!-- SAĞ UÇ -->
                <div style="flex: 1; border: 1px dashed var(--ck-glass-border); border-radius: 8px; padding: 12px; background: rgba(0,0,0,0.01);">
                  <label class="form-label" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--ck-glass-border); padding-bottom: 8px; margin-bottom: 12px; color: var(--ck-text);">
                    <span>{{ __("SAĞ UÇ") }} <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left:4px;"><circle cx="12" cy="12" r="10"></circle><polyline points="12 16 16 12 12 8"></polyline><line x1="8" y1="12" x2="16" y2="12"></line></svg></span>
                    <button class="ck-btn ck-btn-secondary" style="font-size: 10px; padding: 2px 6px; height: auto;" @click="addSagRow">
                      + {{ __("Ekle") }}
                    </button>
                  </label>
                  <div v-if="sagHammaddeRows.length === 0" style="text-align: center; color: var(--ck-muted); font-size: 12px; font-style: italic; padding: 8px 0;">
                    {{ __("Sağ uca eklenecek malzeme yok") }}
                  </div>
                  <div v-for="(row, index) in sagHammaddeRows" :key="row.unique_id" style="display: flex; gap: 4px; margin-bottom: 8px; align-items: flex-start;">
                    <div class="ck-search-wrapper" style="flex: 3;">
                      <input type="text" v-model="row.hammadde" class="ck-input ck-input-small" :placeholder="__('Malzeme...')" @focus="row._showItemResults = true" @input="onSearchInput(row.hammadde, row)" />
                      <div v-if="row._showItemResults && row._itemResults && row._itemResults.length > 0" class="ck-search-results">
                        <div v-for="item in row._itemResults" :key="item[0]" class="ck-search-item" @click="selectItem(item, row)">
                          <div class="ck-item-code">{{ item[0] }}</div>
                        </div>
                      </div>
                    </div>
                    <div style="flex: 2;">
                      <input type="number" class="ck-input ck-input-small" v-model="row.boyut_mm" :placeholder="__('Sıyırma/Boy')" />
                    </div>
                    <button class="ck-btn ck-btn-danger" style="padding: 0 8px; height: 36px; border-radius: 8px;" @click="removeSagRow(index)">
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                  </div>
                </div>
                
              </div>
            </template>
            
            <template v-else>
              <div style="margin-top: 24px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                  <label style="margin: 0;">{{ __("Kullanılan Hammaddeler") }}</label>
                  <button class="ck-btn ck-btn--ghost ck-btn-small" style="font-size: 11px; padding: 4px 8px;" @click="addRow">
                    + {{ __("Yeni Ekle") }}
                  </button>
                </div>

                <div v-if="hammaddeRows.length === 0" class="ck-info-box" style="margin-top: 0;">
                  <div class="ck-info-text">{{ __("Bu işlem için hammadde tanımlanmadı.") }}</div>
                </div>

                <div class="ck-material-list">
                  <div v-for="(row, idx) in hammaddeRows" :key="row.unique_id" class="ck-material-row">
                    <!-- Item Search -->
                    <div class="ck-search-wrapper" style="flex: 2; min-width: 140px;">
                      <input 
                        type="text" 
                        v-model="row.hammadde" 
                        class="ck-input" 
                        :placeholder="__('Hammadde seç...')"
                        @focus="row._showItemResults = true"
                        @input="onSearchInput(row.hammadde, row)"
                      />
                      <div v-if="row._showItemResults && row._itemResults && row._itemResults.length > 0" class="ck-search-results">
                        <div 
                          v-for="item in row._itemResults" 
                          :key="item[0]" 
                          class="ck-search-item"
                          @click="selectItem(item, row)"
                        >
                          <div class="ck-item-code">{{ item[0] }}</div>
                          <div class="ck-item-name">{{ item[1] }}</div>
                        </div>
                      </div>
                    </div>

                    <div style="flex: 1; min-width: 80px;">
                      <input type="number" v-model.number="row.boyut_mm" class="ck-input" :placeholder="__('Boy (mm)')" />
                    </div>

                    <div style="flex: 1; min-width: 80px;">
                      <input type="number" v-model.number="row.islem_adedi" class="ck-input" :placeholder="__('Adet')" />
                    </div>

                    <div style="flex: 1; min-width: 100px;">
                      <input type="text" v-model="row.hedef_node_id" class="ck-input" :placeholder="__('Hedef Node ID')" title="Sanal Yarımamül düğüm ID'si (opsiyonel)" />
                    </div>

                    <div style="flex: 1; min-width: 100px;">
                      <input type="text" v-model="row.hedef_kavite" class="ck-input" :placeholder="__('Pin/Kavite No')" />
                    </div>

                    <button class="ck-btn ck-btn-icon ck-btn--danger" style="padding: 10px; border-radius: 10px; height: 44px; display: flex; align-items: center;" @click="removeRow(idx)" title="Sil">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>
                    </button>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <div class="ck-form-group" style="margin-top: 20px;">
              <label>{{ __("Not Açıklama") }}</label>
              <textarea v-model="note" class="ck-input" rows="2" :placeholder="__('Varsa notlarınız...')"></textarea>
          </div>

        </div>

        <div class="ck-modal-footer">
          <button class="ck-btn ck-btn--ghost" @click="props.onClose" :disabled="submitting">{{ __("Vazgeç") }}</button>
          <button
            class="ck-btn ck-btn--primary"
            style="flex: 2"
            @click="handleSubmit"
            :disabled="submitting"
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

.ck-material-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ck-material-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.ck-btn-small {
  padding: 8px 14px;
  font-size: 13px;
  border-radius: 8px;
  font-weight: 700;
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
