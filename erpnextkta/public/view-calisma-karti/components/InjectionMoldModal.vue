<script setup lang="ts">
import { ref, watch } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  show: boolean;
  wipId: string | null;
  nodes: any[];
}>();

const emit = defineEmits(["close", "submit"]);

const selectedNodeId = ref<string>("");

watch(() => props.show, (val) => {
  if (val) {
    selectedNodeId.value = "";
  }
});

function handleSubmit() {
  if (!selectedNodeId.value) {
    frappe.msgprint(__("Lütfen kalıplanacak düğümü seçin."));
    return;
  }
  emit("submit", selectedNodeId.value);
}
</script>

<template>
  <Teleport to="body">
    <div v-if="props.show" class="ck-modal-overlay">
      <div class="ck-modal ck-glass-modal" style="max-width: 400px;">
        <div class="ck-modal-header">
          <b>{{ __("Enjeksiyon Kalıp Noktası Seçimi") }}</b>
          <button class="ck-modal-close" @click="emit('close')">&times;</button>
        </div>

        <div class="ck-modal-body">
          <div class="ck-form-group">
            <label>{{ __("Sanal Yarımamül:") }} {{ props.wipId }}</label>
            <div v-if="props.nodes && props.nodes.length === 0" class="ck-muted" style="text-align: center; margin-top: 10px;">
              {{ __("Kalıplanabilir (Birleşmiş/Soketlenmiş) düğüm bulunamadı.") }}
            </div>
            <div v-else class="node-list">
              <label v-for="node in props.nodes" :key="node.id" class="node-item" :class="{ 'is-selected': selectedNodeId === node.id }">
                <input type="radio" :value="node.id" v-model="selectedNodeId" style="display: none;" />
                <div class="node-icon">
                  <svg v-if="selectedNodeId === node.id" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" color="var(--ck-primary)"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" color="var(--ck-glass-border)"><circle cx="12" cy="12" r="10"></circle></svg>
                </div>
                <div class="node-info">
                  <div class="node-title">{{ node.type }}</div>
                  <div class="node-status">{{ node.status }}</div>
                </div>
              </label>
            </div>
          </div>
        </div>

        <div class="ck-modal-footer">
          <button class="ck-btn ck-btn--ghost" @click="emit('close')">{{ __("Vazgeç") }}</button>
          <button class="ck-btn ck-btn--primary" style="flex: 2" @click="handleSubmit">{{ __("Kalıpla") }}</button>
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
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 10000; padding: 20px;
}
.ck-modal {
  width: 100%; border-radius: 20px; display: flex; flex-direction: column; overflow: hidden;
}
.ck-modal-header {
  padding: 20px 24px; border-bottom: 1px solid var(--ck-glass-border-soft); display: flex; justify-content: space-between; align-items: center;
}
.ck-modal-header b { font-size: 18px; letter-spacing: -0.02em; }
.ck-modal-close { background: none; border: none; font-size: 28px; cursor: pointer; color: var(--ck-text-muted); line-height: 1; }
.ck-modal-body { padding: 24px; overflow-y: auto; flex: 1; }
.ck-modal-footer { padding: 20px 24px; border-top: 1px solid var(--ck-glass-border-soft); display: flex; gap: 12px; }
.ck-form-group { margin-bottom: 20px; }
.ck-form-group label { display: block; font-size: 13px; font-weight: 700; color: var(--ck-text-muted); margin-bottom: 8px; text-transform: uppercase; }
.ck-btn { padding: 12px 16px; border-radius: 12px; font-size: 15px; font-weight: bold; border: none; cursor: pointer; text-align: center; transition: all 0.2s ease; }
.ck-btn--primary { background: var(--ck-primary); color: white; }
.ck-btn--ghost { background: transparent; color: var(--ck-text); border: 1px solid var(--ck-glass-border); }

.node-list { display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }
.node-item {
  display: flex; align-items: center; gap: 12px; padding: 12px 16px;
  border: 1px solid var(--ck-glass-border-soft); border-radius: 12px;
  cursor: pointer; transition: all 0.2s ease; background: var(--ck-glass-bg);
}
.node-item:hover { background: var(--ck-ghost-bg); transform: translateY(-1px); }
.node-item.is-selected { border-color: var(--ck-primary); background: rgba(var(--ck-primary-rgb), 0.05); }
.node-icon { display: flex; align-items: center; justify-content: center; }
.node-info { display: flex; flex-direction: column; gap: 2px; }
.node-title { font-weight: bold; font-size: 14px; color: var(--ck-text); }
.node-status { font-size: 11px; color: var(--ck-text-muted); }
</style>
