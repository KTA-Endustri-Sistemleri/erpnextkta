<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import { overlayState } from "../utils/frappeShim";

const __ = (...args: any[]) => (window as any).__(...args);

function closeMsgprint() {
  overlayState.msgprint = null;
}

function resolveConfirm(accepted: boolean) {
  const current = overlayState.confirm;
  overlayState.confirm = null;
  if (!current) return;
  if (accepted) current.onConfirm();
  else current.onCancel?.();
}

function handleEsc(e: KeyboardEvent) {
  if (e.key !== "Escape") return;
  if (overlayState.confirm?.show) resolveConfirm(false);
  else if (overlayState.msgprint?.show) closeMsgprint();
}

onMounted(() => window.addEventListener("keydown", handleEsc));
onUnmounted(() => window.removeEventListener("keydown", handleEsc));
</script>

<template>
  <Teleport to="body">
    <div v-if="overlayState.freezing" class="pda-freeze-overlay" role="status" aria-live="polite">
      <div class="pda-freeze-card">
        <div class="pda-freeze-spinner" />
        <p class="pda-freeze-text">{{ overlayState.freezeMessage || __("İşlem yapılıyor...") }}</p>
      </div>
    </div>

    <div v-if="overlayState.alerts.length > 0" class="pda-toast-stack" aria-live="polite">
      <div v-for="alert in overlayState.alerts" :key="alert.id" class="pda-toast" :class="`ind-${alert.indicator}`">
        {{ alert.message }}
      </div>
    </div>

    <div v-if="overlayState.msgprint?.show" class="pda-modal-overlay" @click.self="closeMsgprint">
      <div class="pda-modal-card" role="dialog" aria-modal="true">
        <div class="pda-modal-head" :class="`ind-${overlayState.msgprint.indicator}`">
          <h3>{{ overlayState.msgprint.title }}</h3>
          <button type="button" class="pda-modal-close" :title="__('Kapat')" @click="closeMsgprint">✕</button>
        </div>
        <div class="pda-modal-body">{{ overlayState.msgprint.message }}</div>
        <div class="pda-modal-foot">
          <button type="button" class="pda-mbtn pda-mbtn-primary" @click="closeMsgprint">{{ __("Tamam") }}</button>
        </div>
      </div>
    </div>

    <div v-if="overlayState.confirm?.show" class="pda-modal-overlay" @click.self="resolveConfirm(false)">
      <div class="pda-modal-card" role="dialog" aria-modal="true">
        <div class="pda-modal-head">
          <h3>{{ overlayState.confirm.title }}</h3>
          <button type="button" class="pda-modal-close" :title="__('Kapat')" @click="resolveConfirm(false)">✕</button>
        </div>
        <div class="pda-modal-body">{{ overlayState.confirm.message }}</div>
        <div class="pda-modal-foot">
          <button type="button" class="pda-mbtn pda-mbtn-cancel" @click="resolveConfirm(false)">{{ __("Vazgeç") }}</button>
          <button type="button" class="pda-mbtn pda-mbtn-primary" @click="resolveConfirm(true)">{{ __("Onayla") }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.pda-freeze-overlay { position: fixed; inset: 0; z-index: 1090; background: rgba(15, 23, 42, 0.55); backdrop-filter: blur(2px); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.pda-freeze-card { background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.85rem; padding: 1.25rem 1.75rem; display: flex; flex-direction: column; align-items: center; gap: 0.75rem; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25); }
[data-theme="dark"] .pda-freeze-card { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); color: #f8fafc; }
.pda-freeze-spinner { width: 34px; height: 34px; border: 3px solid rgba(37, 99, 235, 0.2); border-top-color: #2563eb; border-radius: 50%; animation: pda-spin 0.8s linear infinite; }
@keyframes pda-spin { to { transform: rotate(360deg); } }
.pda-freeze-text { margin: 0; font-size: 0.92rem; font-weight: 700; }
.pda-toast-stack { position: fixed; top: 14px; left: 50%; transform: translateX(-50%); z-index: 1085; display: flex; flex-direction: column; gap: 0.5rem; width: min(92vw, 440px); pointer-events: none; }
.pda-toast { padding: 0.75rem 1rem; border-radius: 0.65rem; font-size: 0.88rem; font-weight: 700; color: #ffffff; background: #1e293b; box-shadow: 0 12px 24px rgba(15, 23, 42, 0.3); text-align: center; }
.pda-toast.ind-green { background: #15803d; }
.pda-toast.ind-red { background: #b91c1c; }
.pda-toast.ind-orange { background: #b45309; }
.pda-modal-overlay { position: fixed; inset: 0; z-index: 1080; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(3px); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.pda-modal-card { width: 100%; max-width: 440px; background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.85rem; overflow: hidden; box-shadow: 0 24px 48px rgba(15, 23, 42, 0.3); }
[data-theme="dark"] .pda-modal-card { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); color: #f8fafc; }
.pda-modal-head { display: flex; justify-content: space-between; align-items: center; padding: 0.9rem 1.15rem; background: var(--control-bg, #f1f5f9); border-bottom: 1px solid var(--border-color, #e2e8f0); }
[data-theme="dark"] .pda-modal-head { background: rgba(255, 255, 255, 0.04); }
.pda-modal-head.ind-red { background: #fef2f2; color: #991b1b; }
[data-theme="dark"] .pda-modal-head.ind-red { background: rgba(239, 68, 68, 0.18); color: #fca5a5; }
.pda-modal-head h3 { margin: 0; font-size: 1rem; font-weight: 800; }
.pda-modal-close { background: transparent; border: none; font-size: 1.15rem; color: inherit; cursor: pointer; }
.pda-modal-body { padding: 1.15rem; font-size: 0.92rem; line-height: 1.45; }
.pda-modal-foot { display: flex; justify-content: flex-end; gap: 0.65rem; padding: 0.85rem 1.15rem; border-top: 1px solid var(--border-color, #e2e8f0); background: var(--control-bg, #f8fafc); }
[data-theme="dark"] .pda-modal-foot { background: rgba(255, 255, 255, 0.02); }
.pda-mbtn { min-height: 44px; padding: 0.55rem 1.15rem; border-radius: 0.5rem; font-size: 0.9rem; font-weight: 700; cursor: pointer; border: none; }
.pda-mbtn-cancel { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #cbd5e1); color: var(--text-color, #334155); }
[data-theme="dark"] .pda-mbtn-cancel { background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #cbd5e1; }
.pda-mbtn-primary { background: #2563eb; color: #ffffff; }
</style>
