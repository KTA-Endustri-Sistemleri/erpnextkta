<script setup lang="ts">
import { computed, ref, onMounted, watch } from "vue";
import CkAltOperasyonModal from "../components/CkAltOperasyonModal.vue";
import CkGraphViewerModal from "../components/CkGraphViewerModal.vue";
import NodeSelectorModal from "../components/NodeSelectorModal.vue";
import SocketPinModal from "../components/SocketPinModal.vue";
import InjectionMoldModal from "../components/InjectionMoldModal.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  doc: any;
  canEditData: boolean;
  onAdd: (payload: any) => Promise<void>;
  onUpdate: (payload: any) => Promise<void>;
  onDelete: (rowname: string) => Promise<void>;
}>();

const formatYon = (yon?: string) => {
  if (yon === 'Sol') return 'T1';
  if (yon === 'Sağ') return 'T2';
  if (yon === 'Orta') return 'C';
  return yon || '';
};

const sortTuketimler = (tuketimler: any[]) => {
  if (!tuketimler) return [];
  const order: Record<string, number> = { 'Sol': 1, 'Orta': 2, 'Sağ': 3 };
  
  // Clone to avoid mutating the reactive object
  let processed = tuketimler.map(t => ({...t}));
  
  const graphRows = processed.filter(t => !t.hammadde || t.hammadde === 'GRAPH');
  const realRows = processed.filter(t => !!t.hammadde && t.hammadde !== 'GRAPH');
  
  if (graphRows.length > 0 && realRows.length > 0) {
     const combinedWips = graphRows
       .map(g => g.source_wip_ids)
       .filter(Boolean)
       .join(",");
       
     if (combinedWips) {
       realRows[0].source_wip_ids = combinedWips;
     }
     
     processed = realRows;
  }
  
  return processed.sort((a, b) => {
    const aOrder = order[a.yon || 'Orta'] || 99;
    const bOrder = order[b.yon || 'Orta'] || 99;
    return aOrder - bOrder;
  });
};

function isQCLocked(h: any): boolean {
  if (!props.doc.alt_operasyon_bazli_kalite) return false;
  return (h.quality_inspection_status || "").trim() === "Onaylandı" && !!(h.quality_inspection || "").trim();
}

// Sort rows by sequence from master doctype (populated by backend), then by idx
const sortedRows = computed(() => {
  const rows: any[] = props.doc?.alt_operasyon_kayitlari ?? [];
  return [...rows].sort((a, b) => {
    const seqDiff = (a.alt_operasyon_sequence ?? 0) - (b.alt_operasyon_sequence ?? 0);
    if (seqDiff !== 0) return seqDiff;
    return (a.idx ?? 0) - (b.idx ?? 0);
  });
});

const altOpOptions = ref<any[]>([]);
const ekranTipi = ref<string>("Tekli Hammadde");
const showModal = ref(false);
const showGraphModal = ref(false);
const activeGraphWipId = ref<string | null>(null);
const editingRow = ref<any>(null);

// Modal states for Graph Actions
const showNodeSelector = ref(false);
const showSocketPin = ref(false);
const showInjectionMold = ref(false);
const pendingAltOperasyon = ref<any>(null);
const activeNodesForSelector = ref<any[]>([]);
const activeNodeForSocket = ref<any>(null);
const activeNodesForInjection = ref<any[]>([]);

async function fetchAltOpOptions() {
  const r = await frappe.call({
    method: "erpnextkta.kta_calisma_karti.api.get_alt_operasyon_options",
    args: { parent_operation: props.doc.operasyon },
  });
  if (r.message && !Array.isArray(r.message)) {
    altOpOptions.value = r.message.options || [];
    ekranTipi.value = r.message.ekran_tipi || "Tekli Hammadde";
  } else {
    // Fallback for older api response format if needed
    altOpOptions.value = r.message || [];
    ekranTipi.value = "Tekli Hammadde";
  }
}

const wipLabelMap = ref<Record<string, string>>({});

async function loadWipLabels() {
  const wipIds: string[] = [];
  const rows: any[] = props.doc?.alt_operasyon_kayitlari ?? [];
  for (const r of rows) {
    if (r.hammadde_tuketimleri) {
      for (const tk of r.hammadde_tuketimleri) {
        if (tk.source_wip_ids) {
          const ids = tk.source_wip_ids.split(",").map((i: string) => i.trim());
          wipIds.push(...ids);
        }
      }
    }
  }
  
  if (wipIds.length > 0) {
    try {
      const res = await frappe.call({
        method: "erpnextkta.kta_calisma_karti.api_impl.alt_operasyon.get_wip_source_info",
        args: { wip_ids: Array.from(new Set(wipIds)) }
      });
      if (res.message) {
        wipLabelMap.value = res.message;
      }
    } catch (e) {
      console.error(e);
    }
  }
}

watch(() => props.doc?.alt_operasyon_kayitlari, () => {
  loadWipLabels();
}, { deep: true, immediate: true });

onMounted(() => {
  fetchAltOpOptions();
});

function onAltOperasyonEkle() {
  editingRow.value = null;
  showModal.value = true;
}

const activeGraphOpRefs = ref<string[] | null>(null);

function getTargetWipId(altOperasyonRef: string, fallbackIds: string, operationRow: any): string {
  if (operationRow && operationRow.wip_snapshots) {
    try {
      const snaps = typeof operationRow.wip_snapshots === 'string' ? JSON.parse(operationRow.wip_snapshots) : operationRow.wip_snapshots;
      if (snaps && snaps.created_wips && snaps.created_wips.length > 0) {
        return snaps.created_wips.join(',');
      }
    } catch (e) {
      console.error("Failed to parse wip_snapshots in getTargetWipId", e);
    }
  }
  
  if (!props.doc?.hammadde_tuketimleri) return fallbackIds;
  const targetRow = props.doc.hammadde_tuketimleri.find((r: any) => r.alt_operasyon_ref === altOperasyonRef && r.wip_id);
  return targetRow?.wip_id || fallbackIds;
}

function openGraphViewer(wipId: string, currentOpRef?: string) {
  activeGraphWipId.value = wipId;
  if (currentOpRef) {
    const idx = props.doc.alt_operasyon_kayitlari?.findIndex((r: any) => r.name === currentOpRef);
    if (idx !== undefined && idx !== -1) {
      activeGraphOpRefs.value = props.doc.alt_operasyon_kayitlari.slice(0, idx + 1).map((r: any) => r.name);
    } else {
      activeGraphOpRefs.value = null;
    }
  } else {
    activeGraphOpRefs.value = null;
  }
  showGraphModal.value = true;
}

function onAltOperasyonDuzenle(h: any) {
  if (!h?.name) {
    frappe.msgprint("Satır kimliği (row name) bulunamadı.");
    return;
  }
  editingRow.value = h;
  showModal.value = true;
}

async function handleModalSubmit(payload: any) {
  const selectedOption = altOpOptions.value.find((o) => o.value === payload.alt_operasyon);
  const behavior = selectedOption?.sanal_yarimamul_davranisi;

  if (behavior && !payload._modalProcessed) {
    const sourceWipIds = payload.source_wip_ids ? payload.source_wip_ids.split(",").map((s: string) => s.trim()) : [];
    const mainWipId = sourceWipIds[0] || null;

    let graphNodes = [];
    if (mainWipId) {
        try {
            const r = await frappe.call({
                method: "erpnextkta.kta_calisma_karti.api.get_wip_graph",
                args: { wip_id: mainWipId }
            });
            if (r.message && r.message.nodes) {
                graphNodes = r.message.nodes;
                const graphEdges = r.message.edges || [];
                
                // Formulate display titles for UX
                graphNodes.forEach(n => {
                    let cableMat = null;
                    if (n.type.includes("Uç")) {
                        // try to find the connected Kablo Merkezi
                        const edge = graphEdges.find(e => e.source === n.id || e.target === n.id);
                        if (edge) {
                            const otherId = edge.source === n.id ? edge.target : edge.source;
                            const otherNode = graphNodes.find(on => on.id === otherId);
                            if (otherNode && otherNode.type === "Kablo Merkezi" && otherNode.materials) {
                                cableMat = otherNode.materials.find(m => m.yon === "Orta");
                            }
                        }
                    }
                    if (cableMat && cableMat.hammadde) {
                        const cableLength = cableMat.boyut_mm ? ` (${cableMat.boyut_mm}mm)` : "";
                        n.display_title = `${n.type} — ${cableMat.hammadde}${cableLength}`;
                    } else {
                        n.display_title = n.type;
                    }
                });
            }
        } catch (e) {
            console.error("Graph fetch error", e);
        }
    }

    pendingAltOperasyon.value = payload;
    activeGraphWipId.value = mainWipId;

    if (behavior === "Soketler" || behavior === "Soket Çakma") {
      activeNodesForSelector.value = graphNodes.filter(n => n.status !== "Dolu"); // Show open/available nodes
      showNodeSelector.value = true;
      return;
    } else if (behavior === "Uca / Düğüme Bileşen Ekler" || behavior === "Seçili Düğüme Komponent Ekle" || behavior === "Bileşeni Aktifleştirir" || behavior === "Ucu Böler") {
      activeNodesForSelector.value = graphNodes; 
      showNodeSelector.value = true;
      return;
    } else if (behavior === "Enjeksiyon" || behavior === "Enjeksiyon Baskı") {
      activeNodesForInjection.value = graphNodes.filter(n => n.status === "Soketlendi" || n.status === "Birleşti" || n.status === "Dolu");
      showInjectionMold.value = true;
      return;
    }
  }

  await proceedSubmit(payload);
}

async function proceedSubmit(payload: any) {
  if (editingRow.value) {
    await props.onUpdate(payload);
    frappe.show_alert({ message: __("Alt İşlem güncellendi"), indicator: "green" });
  } else {
    await props.onAdd(payload);
    frappe.show_alert({ message: __("Alt İşlem eklendi"), indicator: "green" });
  }
}

// Modal Handlers
function handleNodeSelectorSave(nodeId: string) {
  if (pendingAltOperasyon.value) {
    const selectedOption = altOpOptions.value.find((o) => o.value === pendingAltOperasyon.value.alt_operasyon);
    const behavior = selectedOption?.sanal_yarimamul_davranisi;

    if (behavior === "Soketler" || behavior === "Soket Çakma") {
        // We selected the node, now we need to ask for the pin number!
        showNodeSelector.value = false;
        activeNodeForSocket.value = nodeId;
        showSocketPin.value = true;
        return;
    }

    const payload = { ...pendingAltOperasyon.value, _modalProcessed: true };
    if (payload.hammadde_tuketimleri && payload.hammadde_tuketimleri.length > 0) {
        payload.hammadde_tuketimleri[0].hedef_node_id = nodeId;
    }
    showNodeSelector.value = false;
    proceedSubmit(payload);
  }
}

function handleSocketPinSave(data: { nodeId: string; pin: string }) {
  if (pendingAltOperasyon.value) {
    const payload = { ...pendingAltOperasyon.value, _modalProcessed: true };
    if (payload.hammadde_tuketimleri && payload.hammadde_tuketimleri.length > 0) {
        payload.hammadde_tuketimleri[0].hedef_node_id = data.nodeId;
        payload.note = (payload.note || "") + `\nPin: ${data.pin}`;
    }
    showSocketPin.value = false;
    proceedSubmit(payload);
  }
}

function handleInjectionMoldSave(nodeId: string) {
  if (pendingAltOperasyon.value) {
    const payload = { ...pendingAltOperasyon.value, _modalProcessed: true };
    if (payload.hammadde_tuketimleri && payload.hammadde_tuketimleri.length > 0) {
        payload.hammadde_tuketimleri[0].hedef_node_id = nodeId;
    }
    showInjectionMold.value = false;
    proceedSubmit(payload);
  }
}

function onAltOperasyonSil(h: any) {
  if (!h?.name) {
    frappe.msgprint("Satır kimliği (row name) bulunamadı.");
    return;
  }

  const locked = isQCLocked(h);
  const isQcUser = props.doc.is_qc_user;

  let msg = __("Bu işlem satırı silinecek. Emin misiniz?");
  if (locked && isQcUser) {
    msg = __("Bu kayda bağlı kalite kontrol belgesi de iptal edilecektir. Devam etmek istiyor musunuz?");
  }

  frappe.confirm(msg, async () => {
    await props.onDelete(h.name);
    frappe.show_alert({ message: __("Alt İşlem silindi"), indicator: "green" });
  });
}

function formatSatirNo(val: any): string {
  if (!val) return val;
  const parts = String(val).split('.');
  const intPart = parts[0].padStart(2, '0');
  const decPart = parts[1] ? parts[1].padStart(2, '0') : '';
  return decPart ? `${intPart}.${decPart}` : intPart;
}
</script>

<template>
  <div class="ck-card">
    <div class="ck-view-action" v-if="props.canEditData">
      <button class="ck-btn ck-btn--ghost ck-btn--wide" @click="onAltOperasyonEkle">{{ __("Alt İşlem Ekle") }}</button>
    </div>

    <div v-if="sortedRows.length === 0" class="ck-empty-state">{{ __("Kayıt yok.") }}</div>

    <div v-else class="ck-mini-list">
      <div v-for="(h, i) in sortedRows" :key="h.name || i" class="ck-mini-item">
        <div style="display: flex; gap: 12px; align-items: stretch; flex: 1; min-width: 0;">
            <div v-if="h.satir_no" style="display: flex; align-items: center; justify-content: center; padding-right: 12px; border-right: 2px solid var(--ck-glass-border-soft); margin-right: 4px;">
                <span style="font-size: 22px; font-weight: 900; color: var(--ck-text); opacity: 0.9;">{{ formatSatirNo(h.satir_no) }}</span>
            </div>
            <div class="ck-mini-content">
                <b class="ck-mini-title">{{ h.alt_operasyon_title || h.alt_operasyon }}</b>
            
            <template v-if="h.hammadde_tuketimleri && h.hammadde_tuketimleri.length > 0">
              <div class="ck-muted ck-mini-sub" v-for="(tk, iidx) in sortTuketimler(h.hammadde_tuketimleri)" :key="iidx">
                <template v-if="(!tk.hammadde || tk.hammadde === 'GRAPH') && tk.source_wip_ids">
                  <!-- GRAPH marker: Havuzdan seçilen WIP referansı -->
                  <div v-for="(swid, widx) in tk.source_wip_ids.split(',').map(s => s.trim()).filter(Boolean)" :key="widx" style="margin-top: 2px; padding-left: 10px; border-left: 2px solid var(--ck-primary);">
                    <template v-if="wipLabelMap[swid]">
                      <span style="color: var(--ck-text); font-weight: 500; font-size: 0.9em;">
                        {{ wipLabelMap[swid] }}
                      </span>
                    </template>
                    <template v-else>
                      <span style="color: var(--ck-primary); font-weight: bold;">[{{ __("HAVUZDAN SEÇİLDİ") }}]</span>
                    </template>
                    <span style="font-weight: 500; margin-left: 6px;">[{{ tk.islem_adedi || 1 }} {{ __("Adet") }}]</span>
                    <span 
                      style="cursor: pointer; font-size: 14px; margin-left: 4px;"
                      title="Grafiği Görüntüle"
                      @click="openGraphViewer(swid)"
                    >🔍</span>
                  </div>
                </template>
                <template v-else-if="tk.hammadde">
                  <template v-if="tk.source_wip_ids">
                    <div style="margin-bottom: 4px; display: flex; align-items: stretch; gap: 8px;">
                      <template v-if="tk.hammadde && tk.hammadde.trim()">
                        <div style="display: flex; align-items: center;">
                          <b v-if="formatYon(tk.yon)">{{ formatYon(tk.yon) }}:</b> 
                          <span style="color: var(--ck-primary); font-weight: bold; margin-left: 4px; margin-right: 4px;">{{ tk.hammadde }} &lt;</span>
                          <template v-if="tk.boyut_mm > 0"> ({{ __("Boy") }}: {{ tk.boyut_mm }}mm)</template>
                          <template v-if="tk.uom && ['m', 'metre', 'meter'].includes(tk.uom.toLowerCase())">
                            <span style="font-weight: 500;"> [{{ tk.islem_adedi || 1 }} {{ __("Adet") }}]</span>
                            <span class="ck-muted" style="font-size: 0.85em; margin-left: 4px;">(Tüketim: {{ parseFloat(((tk.boyut_mm || 0) * (tk.islem_adedi || 1) / 1000).toFixed(3)) }} m)</span>
                          </template>
                          <template v-else>
                            <span style="font-weight: 500;"> [{{ tk.islem_adedi || 1 }} {{ tk.uom || __("Adet") }}]</span>
                          </template>
                        </div>
                        <div style="display: flex; align-items: center;">
                            <span 
                              style="cursor: pointer; font-size: 14px; text-decoration: none;"
                              title="Birleştirilmiş İşlem Grafiğini Görüntüle"
                              @click="openGraphViewer(getTargetWipId(tk.alt_operasyon_ref, tk.source_wip_ids, h), tk.alt_operasyon_ref)"
                            >
                              🔍
                            </span>
                        </div>
                      </template>
                      
                      <div style="display: flex; flex-direction: column; justify-content: center; border-left: 2px solid var(--ck-glass-border); padding-left: 8px;">
                          <div v-for="(swid, widx) in tk.source_wip_ids.split(',').map(s => s.trim()).filter(Boolean)" :key="widx">
                            <template v-if="wipLabelMap[swid]">
                              <span style="color: var(--ck-text); font-weight: 500; font-size: 0.9em; text-decoration: none;">
                                {{ wipLabelMap[swid] }}
                              </span>
                            </template>
                            <template v-else>
                              <span style="color: var(--ck-primary); font-weight: bold; margin-right: 4px;">[{{ __("HAVUZDAN SEÇİLDİ") }}]</span>
                            </template>
                          </div>
                      </div>
                    </div>
                  </template>
                  <template v-else>
                    <b v-if="formatYon(tk.yon)">{{ formatYon(tk.yon) }}:</b> {{ tk.hammadde }}
                    <template v-if="tk.boyut_mm > 0"> ({{ __("Boy") }}: {{ tk.boyut_mm }}mm)</template>
                    <template v-if="tk.uom && ['m', 'metre', 'meter'].includes(tk.uom.toLowerCase())">
                      <span style="font-weight: 500;"> [{{ tk.islem_adedi || 1 }} {{ __("Adet") }}]</span>
                      <span class="ck-muted" style="font-size: 0.85em; margin-left: 4px;">(Tüketim: {{ parseFloat(((tk.boyut_mm || 0) * (tk.islem_adedi || 1) / 1000).toFixed(3)) }} m)</span>
                    </template>
                    <template v-else>
                      <span style="font-weight: 500;"> [{{ tk.islem_adedi || 1 }} {{ tk.uom || __("Adet") }}]</span>
                    </template>
                  </template>
                </template>
                <template v-else>
                  <span class="ck-muted" v-if="tk.boyut_mm > 0">
                    <b v-if="formatYon(tk.yon)">{{ formatYon(tk.yon) }}:</b> {{ tk.boyut_mm }}mm ({{ __("Sıyırma") }})
                  </span>
                  <span class="ck-muted" v-else>
                    <b v-if="formatYon(tk.yon)">{{ formatYon(tk.yon) }}:</b> ({{ __("Sıyırmasız") }})
                  </span>
                </template>
              </div>
            </template>
            <template v-else>
              <div class="ck-muted ck-mini-sub" style="font-style: italic;">{{ __("Hammadde eklenmemiş.") }}</div>
            </template>
            
            <div class="ck-muted ck-mini-sub" v-if="h.note">{{ h.note }}</div>
            </div>
        </div>

        <div class="ck-mini-actions" v-if="props.canEditData">
          <template v-if="!isQCLocked(h) || props.doc.is_qc_user">
            <button class="ck-btn ck-btn--ghost ck-btn-small" @click="onAltOperasyonDuzenle(h)">{{ __("Düzenle") }}</button>
            <button class="ck-btn ck-btn--danger ck-btn-small" @click="onAltOperasyonSil(h)">{{ __("Sil") }}</button>
          </template>
          <template v-else>
            <span class="ck-badge ck-badge--success ck-badge--small" style="font-size: 10px; padding: 2px 6px;">
              🔒 {{ __("Kalite Onaylı") }}
            </span>
          </template>
        </div>
      </div>
    </div>

    <CkAltOperasyonModal
      :show="showModal"
      :doc="props.doc"
      :editData="editingRow"
      :altOpOptions="altOpOptions"
      :ekranTipi="ekranTipi"
      @close="showModal = false"
      @submit="handleModalSubmit"
    />

    <CkGraphViewerModal
      :show="showGraphModal"
      :wipId="activeGraphWipId"
      :allowedOpRefs="activeGraphOpRefs"
      @close="showGraphModal = false"
    />

    <NodeSelectorModal
      :show="showNodeSelector"
      :wipId="activeGraphWipId"
      :nodes="activeNodesForSelector"
      @close="showNodeSelector = false"
      @save="handleNodeSelectorSave"
    />
    <SocketPinModal
      :show="showSocketPin"
      :wipId="activeGraphWipId"
      :nodeId="activeNodeForSocket"
      @close="showSocketPin = false"
      @save="handleSocketPinSave"
    />
    <InjectionMoldModal
      :show="showInjectionMold"
      :wipId="activeGraphWipId"
      :nodes="activeNodesForInjection"
      @close="showInjectionMold = false"
      @save="handleInjectionMoldSave"
    />
  </div>
</template>

<style scoped>
.ck-view-action {
  padding: 0 10px 14px 10px;
  display: flex;
}
.ck-empty-state {
  padding: 10px;
  text-align: center;
  color: var(--ck-text-muted);
  font-size: 13px;
  opacity: 0.7;
}
.ck-mini-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 10px 10px;
}
.ck-mini-item {
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border-soft);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  box-shadow: var(--ck-glass-highlight), 0 2px 8px rgba(0,0,0,0.02);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.ck-mini-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--ck-glass-highlight), 0 6px 16px rgba(0,0,0,0.06);
}
@media (max-width: 480px) {
  .ck-mini-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
.ck-mini-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ck-mini-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--ck-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ck-mini-sub {
  font-size: 12px;
  opacity: 0.8;
}
.ck-mini-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.ck-btn-small {
  padding: 8px 14px;
  font-size: 13px;
  border-radius: 8px;
  font-weight: 700;
}
</style>
