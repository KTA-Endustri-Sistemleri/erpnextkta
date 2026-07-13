<script setup lang="ts">
import { ref, watch } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  show: boolean;
  wipId: string | null;
  nodeId: string | null;
}>();

const emit = defineEmits(["close", "save"]);

const pinNumber = ref<string>("");

watch(() => props.show, (val) => {
  if (val) {
    pinNumber.value = "";
  }
});

function handleSubmit() {
  if (!pinNumber.value) {
    frappe.msgprint(__("Lütfen pin/kavite numarasını girin."));
    return;
  }
  emit("save", { nodeId: props.nodeId, pin: pinNumber.value });
}
</script>

<template>
  <Teleport to="body">
    <div v-if="props.show" class="ck-modal-overlay">
      <div class="ck-modal ck-glass-modal" style="max-width: 400px;">
        <div class="ck-modal-header">
          <b>{{ __("Soket Pin / Kavite Numarası") }}</b>
          <button class="ck-modal-close" @click="emit('close')">&times;</button>
        </div>

        <div class="ck-modal-body">
          <div class="ck-form-group">
            <label>{{ __("Pin / Kavite No:") }}</label>
            <input type="text" v-model="pinNumber" class="ck-input" :placeholder="__('Örn: A1, Pin-3, vs.')" @keyup.enter="handleSubmit" />
          </div>
          <div class="ck-muted" style="font-size: 11px; margin-top: -10px;">
            {{ __("Seçili Düğüm:") }} {{ props.nodeId }}
          </div>
        </div>

        <div class="ck-modal-footer">
          <button class="ck-btn ck-btn--ghost" @click="emit('close')">{{ __("Vazgeç") }}</button>
          <button class="ck-btn ck-btn--primary" style="flex: 2" @click="handleSubmit">{{ __("Kaydet") }}</button>
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
.ck-input { width: 100%; padding: 12px 16px; border-radius: 12px; border: 1px solid var(--ck-glass-border); background: var(--ck-glass-input-bg, rgba(255,255,255,0.05)); color: var(--ck-text); font-size: 15px; }
.ck-btn { padding: 12px 16px; border-radius: 12px; font-size: 15px; font-weight: bold; border: none; cursor: pointer; text-align: center; transition: all 0.2s ease; }
.ck-btn--primary { background: var(--ck-primary); color: white; }
.ck-btn--ghost { background: transparent; color: var(--ck-text); border: 1px solid var(--ck-glass-border); }
</style>
