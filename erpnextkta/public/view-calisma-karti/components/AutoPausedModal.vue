<script setup lang="ts">
import { ref, watch, computed } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  show: boolean;
  cards: any[];
  operator?: string;
  onAction: (action: 'baslat' | 'git', docname: string) => Promise<void>;
  onClose?: () => void;
}>();

const selectedKart = ref("");
const loading = ref(false);
const transitionState = ref<'idle' | 'success'>('idle');

const targetCard = computed(() => props.cards.find(c => c.name === selectedKart.value));

watch(() => props.show, (next) => {
  if (next) {
    selectedKart.value = "";
    loading.value = false;
    transitionState.value = 'idle';
  }
});

async function handleAction(action: 'baslat' | 'git') {
  if (!selectedKart.value) return frappe.msgprint(__("Lütfen İşlem Yapılacak Kartı Seçiniz"));

  loading.value = true;
  try {
    await props.onAction(action, selectedKart.value);
    
    if (action === 'baslat') {
      transitionState.value = 'success';
      setTimeout(() => {
        frappe.set_route('view-calisma-karti', selectedKart.value);
        if (props.onClose) props.onClose();
      }, 3000);
    } else {
      frappe.set_route('view-calisma-karti', selectedKart.value);
      if (props.onClose) props.onClose();
    }
  } catch (e) {
    console.error(e);
  } finally {
    if (transitionState.value !== 'success') {
      loading.value = false;
    }
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="props.show" class="ck-modal-overlay">
      <div class="ck-modal">
        <div class="ck-modal-header" style="border-bottom-color: var(--ck-warning)">
          <b>{{ __("Bekleyen Çalışma Kartınız Var") }}</b>
          <button v-if="props.onClose && transitionState === 'idle'" class="ck-close-btn" @click="props.onClose()">&times;</button>
        </div>

        <div v-if="transitionState === 'success'" class="ck-modal-body" style="text-align: center; padding: 40px 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 250px;">
          <div class="ck-spinner" style="margin-bottom: 24px;"></div>
          <h3 style="margin-bottom: 12px; font-weight: 800; color: var(--ck-text, #111827);">{{ targetCard?.name }} {{ __("Başlatılıyor...") }}</h3>
          <p style="color: var(--ck-text-muted, rgba(17,24,39,0.7)); line-height: 1.5;">{{ __("Lütfen bekleyin, ilgili karta yönlendiriliyorsunuz.") }}</p>
        </div>

        <template v-else>
          <div class="ck-modal-body">
            <div class="ck-alert ck-alert-warning" style="margin-bottom: 16px;">
              <strong>{{ __("Dikkat") }}:</strong> {{ __("Sistem tarafından otomatik olarak beklemeye alınmış açık kartlarınız bulunuyor. Lütfen aşağıdan bir kart seçerek mesainize göre ilgili işlemi gerçekleştirin.") }}
            </div>

            <div class="ck-cards-list">
              <div 
                v-for="c in props.cards" :key="c.name" 
                class="ck-card-item" 
                :class="{'ck-card-item--active': selectedKart === c.name}"
                @click="selectedKart = c.name"
              >
                <div class="ck-card-title">{{ c.name }}</div>
                <div class="ck-card-subtitle">
                  <span><strong>{{ __("Operasyon") }}:</strong> {{ c.operasyon || '-' }}</span>
                  <span style="margin-left: 12px;"><strong>{{ __("Ürün") }}:</strong> {{ c.urun_kodu || '-' }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="ck-modal-footer">
            <button class="ck-btn ck-btn--success" style="flex: 1" @click="handleAction('baslat')" :disabled="loading || !selectedKart">
              {{ __("Seçili Karta Devam Et") }}
            </button>
            <button class="ck-btn ck-btn--secondary" style="flex: 1" @click="handleAction('git')" :disabled="loading || !selectedKart">
              {{ __("Kartı Görüntüle") }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.ck-modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1050;
  padding: 10px;
}

.ck-modal {
  background: var(--ck-bg, #f3f4f6);
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
  border-bottom: 2px solid var(--ck-border, rgba(0,0,0,0.08));
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ck-close-btn {
  background: transparent;
  border: none;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  color: var(--ck-text-muted, rgba(17, 24, 39, 0.65));
  padding: 0;
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
}

.ck-close-btn:hover {
  background: rgba(0,0,0,0.05);
  color: var(--ck-text, #111827);
}

.ck-modal-body {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.ck-modal-footer {
  padding: 16px;
  border-top: 1px solid var(--ck-border, rgba(0,0,0,0.08));
  display: flex;
  gap: 10px;
}

.ck-cards-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ck-card-item {
  border: 2px solid var(--ck-border, rgba(0,0,0,0.08));
  border-radius: 12px;
  padding: 14px;
  background: var(--ck-surface, #ffffff);
  cursor: pointer;
  transition: all 0.2s ease;
}

.ck-card-item:hover {
  border-color: rgba(0,0,0,0.2);
  transform: translateY(-1px);
}

.ck-card-item--active {
  border-color: var(--ck-success, #22c55e);
  background: rgba(34, 197, 94, 0.05);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.15);
}

.ck-card-title {
  font-weight: 800;
  font-size: 15px;
  margin-bottom: 6px;
  color: var(--ck-text, #111827);
}

.ck-card-subtitle {
  font-size: 13px;
  color: var(--ck-text-muted, rgba(17, 24, 39, 0.8));
}

.ck-alert {
  padding: 12px;
  border-radius: 8px;
  font-size: 13px;
}

.ck-alert-warning {
  background-color: var(--alert-warning-bg, rgba(245, 158, 11, .16));
  color: var(--warning, #f59e0b);
  border: 1px solid var(--warning, #f59e0b);
}

.ck-btn {
  border: 1px solid var(--ck-glass-border, rgba(0, 0, 0, 0.08));
  border-bottom: 2px solid var(--ck-glass-bottom-edge, rgba(0, 0, 0, 0.1));
  border-radius: 12px;
  padding: 12px 14px;
  font-weight: 800;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.6);
  transition: all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1);
  font-size: 14px;
  cursor: pointer;
}

.ck-btn:active {
  transform: scale(0.96) translateY(2px);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1), inset 0 2px 4px rgba(0, 0, 0, 0.2);
  border-bottom-width: 1px;
}

.ck-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ck-btn--success {
  background: var(--ck-success, #22c55e);
  color: #fff;
}

.ck-btn--secondary {
  background: var(--ck-secondary, #64748b);
  color: #fff;
}

.ck-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid var(--ck-border, rgba(0,0,0,0.1));
  border-top-color: var(--ck-success, #22c55e);
  border-radius: 50%;
  animation: ck-spin 1s linear infinite;
}

@keyframes ck-spin {
  to {
    transform: rotate(360deg);
  }
}

:global([data-theme="dark"]) .ck-modal {
  --ck-bg: #1f2937;
  --ck-border: rgba(255, 255, 255, 0.1);
  --ck-text: #f9fafb;
  --ck-text-muted: rgba(249, 250, 251, 0.7);
  --ck-surface: #374151;
  --ck-glass-border: rgba(255, 255, 255, 0.1);
  --ck-glass-bottom-edge: rgba(255, 255, 255, 0.15);
}

:global([data-theme="dark"]) .ck-alert-warning {
  --alert-warning-bg: rgba(245, 158, 11, 0.1);
}
</style>
