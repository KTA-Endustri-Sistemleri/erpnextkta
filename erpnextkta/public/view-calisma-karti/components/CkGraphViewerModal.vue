<script setup lang="ts">
import { ref, watch, computed } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  show: boolean;
  wipId: string | null;
  allowedOpRefs?: string[] | null;
}>();

const emit = defineEmits(["close"]);

const loading = ref(false);
const graphDataList = ref<any[]>([]);

async function loadGraphData() {
  if (!props.wipId) return;
  loading.value = true;
  
  const wipIds = props.wipId.split(',').map(s => s.trim()).filter(Boolean);
  const newData = [];
  
  try {
    let fetchedGraphs = [];
    for (const wid of wipIds) {
      const res = await frappe.call({
        method: "frappe.client.get_value",
        args: {
          doctype: "KTA Sanal Yarimamul",
          filters: wid,
          fieldname: "graph_state"
        }
      });
      if (res && res.message && res.message.graph_state) {
        fetchedGraphs.push(JSON.parse(res.message.graph_state));
      }
    }

    if (props.allowedOpRefs && props.allowedOpRefs.length > 0) {
      const allowed = props.allowedOpRefs;
      const currentOpRef = allowed[allowed.length - 1];
      
      // Filter out leftover WIPs: If we fetched output WIPs, some are leftovers without the currentOpRef.
      // We only want to show the main output WIPs that actually contain the current operation.
      const mainGraphs = fetchedGraphs.filter(g => g.nodes.some(n => n.operation_ref === currentOpRef));
      if (mainGraphs.length > 0) {
        fetchedGraphs = mainGraphs;
      }
      
      fetchedGraphs.forEach(parsed => {
        parsed.nodes = parsed.nodes.filter((n: any) => {
          if (!n.operation_ref) return true;
          return allowed.includes(n.operation_ref);
        });
        const validNodeIds = new Set(parsed.nodes.map((n: any) => n.id));
        parsed.edges = parsed.edges.filter((e: any) => validNodeIds.has(e.source) && validNodeIds.has(e.target));
      });
    }
    
    for (const parsed of fetchedGraphs) {
      const stringified = JSON.stringify(parsed);
      const isDuplicate = newData.some(existing => JSON.stringify(existing) === stringified);
      if (!isDuplicate) {
        newData.push(parsed);
      }
    }
    
    graphDataList.value = newData;
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

watch([() => props.show, () => props.wipId], ([newShow, newWipId]) => {
  if (newShow && newWipId) {
    loadGraphData();
  }
});

function getOutgoingNodes(sourceId: string, graph: any) {
  if (!graph || !graph.edges) return [];
  const edges = graph.edges.filter((e: any) => e.source === sourceId);
  return edges.map((e: any) => graph.nodes.find((n: any) => n.id === e.target)).filter(Boolean);
}

const rootNodesList = computed(() => {
  return graphDataList.value.map(graph => {
    if (!graph || !graph.nodes) return [];
    const edgeTargets = graph.edges.map((e: any) => e.target);
    return graph.nodes.filter((n: any) => !edgeTargets.includes(n.id));
  });
});

const sharedLeftNodes = computed(() => {
  const shared: any[] = [];
  const rootsToCompare = [];
  const graphsToCompare = [];

  // Flatten all roots across all graphs
  for (let i = 0; i < graphDataList.value.length; i++) {
    const roots = rootNodesList.value[i] || [];
    for (const r of roots) {
      rootsToCompare.push(r);
      graphsToCompare.push(graphDataList.value[i]);
    }
  }

  if (rootsToCompare.length < 2) return [];

  // Sadece ilk kök üzerinden gidelim, diğerleriyle ortak mı diye bakacağız
  const firstRoot = rootsToCompare[0];
  const firstGraph = graphsToCompare[0];
  
  const t1s = getOutgoingNodes(firstRoot.id, firstGraph).filter(n => n.type.includes('T1'));
  for (const t1 of t1s) {
    const grands = getOutgoingNodes(t1.id, firstGraph);
    const merges = grands.filter(g => (g.type.includes('Birleşim') || g.type.includes('Soket')) && g.operation_ref);
    for (const merge of merges) {
      // Bu merge düğümüne TÜM köklerden ulaşılabiliyor mu?
      let inAll = true;
      for (let i = 1; i < rootsToCompare.length; i++) {
        const otherRoot = rootsToCompare[i];
        const otherGraph = graphsToCompare[i];
        const otherT1s = getOutgoingNodes(otherRoot.id, otherGraph).filter(n => n.type.includes('T1'));
        const reachesMerge = otherT1s.some(ot1 => {
           return getOutgoingNodes(ot1.id, otherGraph).some(gn => gn.operation_ref === merge.operation_ref);
        });
        if (!reachesMerge) {
          inAll = false;
          break;
        }
      }
      
      if (inAll) {
        if (!shared.find(s => s.operation_ref === merge.operation_ref)) {
          shared.push(merge);
        }
      }
    }
  }
  return shared;
});

const sharedRightNodes = computed(() => {
  const shared: any[] = [];
  const rootsToCompare = [];
  const graphsToCompare = [];

  for (let i = 0; i < graphDataList.value.length; i++) {
    const roots = rootNodesList.value[i] || [];
    for (const r of roots) {
      rootsToCompare.push(r);
      graphsToCompare.push(graphDataList.value[i]);
    }
  }

  if (rootsToCompare.length < 2) return [];

  const firstRoot = rootsToCompare[0];
  const firstGraph = graphsToCompare[0];
  
  const t2s = getOutgoingNodes(firstRoot.id, firstGraph).filter(n => !n.type.includes('T1'));
  for (const t2 of t2s) {
    const grands = getOutgoingNodes(t2.id, firstGraph);
    const merges = grands.filter(g => (g.type.includes('Birleşim') || g.type.includes('Soket')) && g.operation_ref);
    for (const merge of merges) {
      let inAll = true;
      for (let i = 1; i < rootsToCompare.length; i++) {
        const otherRoot = rootsToCompare[i];
        const otherGraph = graphsToCompare[i];
        const otherT2s = getOutgoingNodes(otherRoot.id, otherGraph).filter(n => !n.type.includes('T1'));
        const reachesMerge = otherT2s.some(ot2 => {
           return getOutgoingNodes(ot2.id, otherGraph).some(gn => gn.operation_ref === merge.operation_ref);
        });
        if (!reachesMerge) {
          inAll = false;
          break;
        }
      }
      
      if (inAll) {
        if (!shared.find(s => s.operation_ref === merge.operation_ref)) {
          shared.push(merge);
        }
      }
    }
  }
  return shared;
});


    const getDisplayStatus = (node) => {
      if (!node) return "";
      if (node.type && node.type.includes && node.type.includes('Uç')) {
        if (node.materials && node.materials.length > 0) {
          const hasHammadde = node.materials.some(m => m.hammadde && String(m.hammadde).toLowerCase() !== 'none');
          if (!hasHammadde) return 'Açık';
        } else {
          return 'Açık';
        }
      }
      return node.status || "";
    };

function getStatusColor(status: string) {
  if (status === "Aktif") return "var(--ck-primary)";
  if (status === "Dolu") return "#2ecc71";
  if (status === "Soketlendi") return "#2980b9";
  if (status === "Beklemede") return "#f39c12";
  if (status === "Bölündü") return "#9b59b6";
  if (status === "Açık") return "#e74c3c";
  return "var(--ck-text-muted)";
}

function getPinForNode(sourceId: string, graph: any) {
  if (!graph || !graph.edges) return null;
  const edge = graph.edges.find((e: any) => e.source === sourceId && e.pin);
  return edge ? edge.pin : null;
}
</script>

<template>
  <div class="ck-modal-overlay" v-if="props.show" @click.self="emit('close')">
    <div class="ck-modal" style="max-width: 800px; width: 90%;">
      <div class="ck-modal-header">
        <h3 style="margin: 0;">{{ __("Sanal Yarımamül Yapısı") }} <span class="ck-muted" style="font-size: 14px;">{{ props.wipId }}</span></h3>
        <button class="ck-modal-close" @click="emit('close')">✕</button>
      </div>

      <div class="ck-modal-body" style="background: var(--ck-glass-bg); padding: 30px; text-align: center; min-height: 200px;">
        <div v-if="loading" class="ck-muted" style="margin-top: 50px;">{{ __("Yükleniyor...") }}</div>
        <div v-else-if="graphDataList.length === 0" class="ck-muted" style="margin-top: 50px;">{{ __("Graph verisi bulunamadı.") }}</div>
        
        <div v-else class="graph-container">
          <!-- DEBUG INFO -->
          <div style="font-size: 10px; color: red; margin-bottom: 10px;">
            DEBUG: Fetched for {{ props.wipId }} | Allowed: {{ props.allowedOpRefs }}
          </div>
          
          <div style="display: flex; align-items: center; justify-content: center; gap: 0;">
            <!-- Shared Left Node if Multi -->
            <div v-if="sharedLeftNodes.length > 0" style="display: flex; align-items: center;">
              <div style="display: flex; flex-direction: column; gap: 10px;">
                <div v-for="node in sharedLeftNodes" :key="node.id" class="graph-node" :style="{ borderColor: getStatusColor(getDisplayStatus(node)) }">
                  <div class="node-type" :style="{ color: getStatusColor(getDisplayStatus(node)) }">{{ node.type === 'Kablo Merkezi' ? 'Kablo' : node.type }}</div>
                  <div class="node-status">{{ getDisplayStatus(node) }}</div>
                  <div class="node-mats" v-if="node.materials && node.materials.length > 0">
                    <div v-for="(m, i) in node.materials" :key="i" style="line-height: 1.2; margin-top: 4px;">
                      <template v-if="m.hammadde">
                        {{ m.hammadde }}
                        <div v-if="m.boyut_mm" class="ck-muted" style="font-size: 0.9em; margin-top: 2px;">({{ m.boyut_mm }}mm)</div>
                      </template>
                      <template v-else-if="m.boyut_mm">
                        <div class="ck-muted" style="font-size: 0.9em;">{{ m.boyut_mm }}mm (Sıyırma)</div>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
              <div style="font-size: 120px; font-weight: 100; color: var(--ck-border); line-height: 0.5; margin: 0 5px; transform: scaleY(1.5);">}</div>
            </div>

            <!-- The Rows -->
            <div style="display: flex; flex-direction: column; gap: 10px;">
              <template v-for="(rootNodes, graphIndex) in rootNodesList" :key="graphIndex">
                <div class="horizontal-tree" v-for="root in rootNodes" :key="root.id" style="margin: 0;">
                  <!-- Left Branch (T1) -->
                  <div class="ht-branch left-branch">
                    <template v-for="child in getOutgoingNodes(root.id, graphDataList[graphIndex]).filter(n => n.type.includes('T1'))" :key="child.id">
                      <!-- Grandchildren of T1 -->
                      <template v-for="grand in getOutgoingNodes(child.id, graphDataList[graphIndex])" :key="grand.id">
                        <template v-if="!(grand.type.includes('Birleşim') && sharedLeftNodes.some(s => s.operation_ref === grand.operation_ref))">
                          <div class="graph-node" :style="{ borderColor: getStatusColor(getDisplayStatus(grand)) }">
                            <div class="node-type" :style="{ color: getStatusColor(getDisplayStatus(grand)) }">{{ grand.type === 'Kablo Merkezi' ? 'Kablo' : grand.type }}</div>
                            <div class="node-status">{{ getDisplayStatus(grand) }}</div>
                            <div class="node-status" v-if="getPinForNode(grand.id, graphDataList[graphIndex])" style="background: #2980b9; color: white; margin-top: 4px;">Pin: {{ getPinForNode(grand.id, graphDataList[graphIndex]) }}</div>
                            <div class="node-mats" v-if="grand.materials && grand.materials.length > 0">
                              <div v-for="(m, i) in grand.materials" :key="i" style="line-height: 1.2; margin-top: 4px;">
                                <template v-if="m.hammadde">
                                  {{ m.hammadde }}
                                  <div v-if="m.boyut_mm" class="ck-muted" style="font-size: 0.9em; margin-top: 2px;">({{ m.boyut_mm }}mm)</div>
                                </template>
                                <template v-else-if="m.boyut_mm">
                                  <div class="ck-muted" style="font-size: 0.9em;">{{ m.boyut_mm }}mm (Sıyırma)</div>
                                </template>
                              </div>
                            </div>
                          </div>
                          <div class="ht-line"></div>
                        </template>
                      </template>
                      <!-- T1 Child -->
                      <div class="graph-node" :style="{ borderColor: getStatusColor(getDisplayStatus(child)) }">
                        <div class="node-type" :style="{ color: getStatusColor(getDisplayStatus(child)) }">{{ child.type === 'Kablo Merkezi' ? 'Kablo' : child.type }}</div>
                        <div class="node-status">{{ getDisplayStatus(child) }}</div>
                        <div class="node-status" v-if="getPinForNode(child.id, graphDataList[graphIndex])" style="background: #2980b9; color: white; margin-top: 4px;">Pin: {{ getPinForNode(child.id, graphDataList[graphIndex]) }}</div>
                        <div class="node-mats" v-if="child.materials && child.materials.length > 0">
                          <div v-for="(m, i) in child.materials" :key="i" style="line-height: 1.2; margin-top: 4px;">
                            <template v-if="m.hammadde">
                              {{ m.hammadde }}
                              <div v-if="m.boyut_mm" class="ck-muted" style="font-size: 0.9em; margin-top: 2px;">({{ m.boyut_mm }}mm)</div>
                            </template>
                            <template v-else-if="m.boyut_mm">
                              <div class="ck-muted" style="font-size: 0.9em;">{{ m.boyut_mm }}mm (Sıyırma)</div>
                            </template>
                          </div>
                        </div>
                      </div>
                      <div class="ht-line"></div>
                    </template>
                  </div>

                  <!-- ROOT (Kablo Merkezi) -->
                  <div class="graph-node" :style="{ borderColor: getStatusColor(getDisplayStatus(root)) }">
                    <div class="node-type" :style="{ color: getStatusColor(getDisplayStatus(root)) }">{{ root.type === 'Kablo Merkezi' ? 'Kablo' : root.type }}</div>
                    <div class="node-status">{{ getDisplayStatus(root) }}</div>
                    <div class="node-status" v-if="getPinForNode(root.id, graphDataList[graphIndex])" style="background: #2980b9; color: white; margin-top: 4px;">Pin: {{ getPinForNode(root.id, graphDataList[graphIndex]) }}</div>
                    <div class="node-mats" v-if="root.materials && root.materials.length > 0">
                      <div v-for="(m, i) in root.materials" :key="i" style="line-height: 1.2; margin-top: 4px;">
                        <template v-if="m.hammadde">
                          {{ m.hammadde }}
                          <div v-if="m.boyut_mm" class="ck-muted" style="font-size: 0.9em; margin-top: 2px;">({{ m.boyut_mm }}mm)</div>
                        </template>
                        <template v-else-if="m.boyut_mm">
                          <div class="ck-muted" style="font-size: 0.9em;">{{ m.boyut_mm }}mm (Sıyırma)</div>
                        </template>
                      </div>
                    </div>
                  </div>

                  <!-- Right Branch (T2) -->
                  <div class="ht-branch right-branch">
                    <template v-for="child in getOutgoingNodes(root.id, graphDataList[graphIndex]).filter(n => !n.type.includes('T1'))" :key="child.id">
                      <div class="ht-line"></div>
                      <!-- T2 Child -->
                      <div class="graph-node" :style="{ borderColor: getStatusColor(getDisplayStatus(child)) }">
                        <div class="node-type" :style="{ color: getStatusColor(getDisplayStatus(child)) }">{{ child.type === 'Kablo Merkezi' ? 'Kablo' : child.type }}</div>
                        <div class="node-status">{{ getDisplayStatus(child) }}</div>
                        <div class="node-status" v-if="getPinForNode(child.id, graphDataList[graphIndex])" style="background: #2980b9; color: white; margin-top: 4px;">Pin: {{ getPinForNode(child.id, graphDataList[graphIndex]) }}</div>
                        <div class="node-mats" v-if="child.materials && child.materials.length > 0">
                          <div v-for="(m, i) in child.materials" :key="i" style="line-height: 1.2; margin-top: 4px;">
                            <template v-if="m.hammadde">
                              {{ m.hammadde }}
                              <div v-if="m.boyut_mm" class="ck-muted" style="font-size: 0.9em; margin-top: 2px;">({{ m.boyut_mm }}mm)</div>
                            </template>
                            <template v-else-if="m.boyut_mm">
                              <div class="ck-muted" style="font-size: 0.9em;">{{ m.boyut_mm }}mm (Sıyırma)</div>
                            </template>
                          </div>
                        </div>
                      </div>
                      <!-- Grandchildren of T2 -->
                      <template v-for="grand in getOutgoingNodes(child.id, graphDataList[graphIndex])" :key="grand.id">
                        <template v-if="!(grand.type.includes('Birleşim') && sharedRightNodes.some(s => s.operation_ref === grand.operation_ref))">
                          <div class="ht-line"></div>
                          <div class="graph-node" :style="{ borderColor: getStatusColor(getDisplayStatus(grand)) }">
                            <div class="node-type" :style="{ color: getStatusColor(getDisplayStatus(grand)) }">{{ grand.type === 'Kablo Merkezi' ? 'Kablo' : grand.type }}</div>
                            <div class="node-status">{{ getDisplayStatus(grand) }}</div>
                            <div class="node-status" v-if="getPinForNode(grand.id, graphDataList[graphIndex])" style="background: #2980b9; color: white; margin-top: 4px;">Pin: {{ getPinForNode(grand.id, graphDataList[graphIndex]) }}</div>
                            <div class="node-mats" v-if="grand.materials && grand.materials.length > 0">
                              <div v-for="(m, i) in grand.materials" :key="i" style="line-height: 1.2; margin-top: 4px;">
                                <template v-if="m.hammadde">
                                  {{ m.hammadde }}
                                  <div v-if="m.boyut_mm" class="ck-muted" style="font-size: 0.9em; margin-top: 2px;">({{ m.boyut_mm }}mm)</div>
                                </template>
                                <template v-else-if="m.boyut_mm">
                                  <div class="ck-muted" style="font-size: 0.9em;">{{ m.boyut_mm }}mm (Sıyırma)</div>
                                </template>
                              </div>
                            </div>
                          </div>
                        </template>
                      </template>
                    </template>
                  </div>
                </div>
              </template>
            </div>

            <!-- Shared Right Node if Multi -->
            <div v-if="sharedRightNodes.length > 0" style="display: flex; align-items: center;">
              <div style="font-size: 120px; font-weight: 100; color: var(--ck-border); line-height: 0.5; margin: 0 5px; transform: scaleY(1.5);">{</div>
              <div style="display: flex; flex-direction: column; gap: 10px;">
                <div v-for="node in sharedRightNodes" :key="node.id" class="graph-node" :style="{ borderColor: getStatusColor(getDisplayStatus(node)) }">
                  <div class="node-type" :style="{ color: getStatusColor(getDisplayStatus(node)) }">{{ node.type === 'Kablo Merkezi' ? 'Kablo' : node.type }}</div>
                  <div class="node-status">{{ getDisplayStatus(node) }}</div>
                  <div class="node-mats" v-if="node.materials && node.materials.length > 0">
                    <div v-for="(m, i) in node.materials" :key="i" style="line-height: 1.2; margin-top: 4px;">
                      <template v-if="m.hammadde">
                        {{ m.hammadde }}
                        <div v-if="m.boyut_mm" class="ck-muted" style="font-size: 0.9em; margin-top: 2px;">({{ m.boyut_mm }}mm)</div>
                      </template>
                      <template v-else-if="m.boyut_mm">
                        <div class="ck-muted" style="font-size: 0.9em;">{{ m.boyut_mm }}mm (Sıyırma)</div>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.horizontal-tree {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: nowrap;
  margin: 20px 0;
  overflow-x: auto;
  padding-bottom: 10px;
}
.ht-branch {
  display: flex;
  align-items: center;
}
.ht-line {
  height: 2px;
  width: 40px;
  background-color: var(--ck-border);
}
.graph-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}
.graph-level {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}
.graph-children {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}
.edge-line {
  width: 2px;
  height: 20px;
  background-color: var(--ck-glass-border-soft);
  margin: 5px 0;
}
.children-row {
  display: flex;
  justify-content: center;
  gap: 30px;
  position: relative;
}
.children-row::before {
  content: '';
  position: absolute;
  top: -5px;
  left: 20%;
  right: 20%;
  height: 2px;
  background-color: var(--ck-glass-border-soft);
}
.child-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
}
.child-wrapper::before {
  content: '';
  position: absolute;
  top: -5px;
  width: 2px;
  height: 5px;
  background-color: var(--ck-glass-border-soft);
}
.graph-node {
  background: white;
  border: 2px solid var(--ck-glass-border-soft);
  border-radius: 12px;
  padding: 12px 20px;
  min-width: 140px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  display: flex;
  flex-direction: column;
  gap: 4px;
  position: relative;
  z-index: 1;
}
.node-type {
  font-weight: 800;
  font-size: 14px;
}
.node-id {
  font-size: 10px;
  font-family: monospace;
}
.node-status {
  font-size: 11px;
  font-weight: bold;
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 4px;
  display: inline-block;
  align-self: center;
}
.node-mats {
  font-size: 11px;
  margin-top: 6px;
  border-top: 1px dashed #ccc;
  padding-top: 6px;
}
</style>
