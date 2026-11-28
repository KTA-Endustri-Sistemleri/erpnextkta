<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import type { PdaOperator, VerifyPdaPinResponse } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    operators: PdaOperator[];
    authExpiredWarning?: boolean;
  }>(),
  { authExpiredWarning: false }
);

const emit = defineEmits<{
  (e: "unlocked", payload: { response: VerifyPdaPinResponse; operator: PdaOperator }): void;
}>();

const search = ref<string>("");
const selectedOperator = ref<PdaOperator | null>(null);
const pinCode = ref<string>("");
const submitting = ref<boolean>(false);
const errorMsg = ref<string | null>(null);

const filteredOperators = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return props.operators || [];
  return (props.operators || []).filter(
    (op) =>
      op.employee_name.toLowerCase().includes(q) ||
      op.employee.toLowerCase().includes(q) ||
      (op.department || "").toLowerCase().includes(q)
  );
});

function selectOperator(op: PdaOperator) {
  selectedOperator.value = op;
  pinCode.value = "";
  errorMsg.value = null;
}

function resetOperator() {
  if (submitting.value) return;
  selectedOperator.value = null;
  pinCode.value = "";
  errorMsg.value = null;
}

function clearPin() {
  if (submitting.value) return;
  pinCode.value = "";
  errorMsg.value = null;
}

function backspacePin() {
  if (submitting.value) return;
  pinCode.value = pinCode.value.slice(0, -1);
}

async function submitPin(pin: string) {
  if (!selectedOperator.value || submitting.value) return;
  submitting.value = true;
  errorMsg.value = null;
  try {
    const res = await new Promise<VerifyPdaPinResponse>((resolve, reject) => {
      const maybePromise = window.frappe.call({
        method: "erpnextkta.kta_stock.services.pda_service.verify_pda_pin",
        args: { employee: selectedOperator.value!.name, pin },
        callback: (r: { message?: VerifyPdaPinResponse }) =>
          resolve(r.message as VerifyPdaPinResponse),
        error: (err: any) => reject(err),
      });
      if (
        maybePromise &&
        typeof (maybePromise as Promise<unknown>).then === "function"
      ) {
        (maybePromise as Promise<{ message?: VerifyPdaPinResponse }>).then(
          (r) => {
            if (r?.message) resolve(r.message);
          },
          (err) => reject(err),
        );
      }
    });
    if (res && res.ok) {
      emit("unlocked", { response: res, operator: selectedOperator.value });
    } else {
      throw new Error(__("PIN doğrulanamadı."));
    }
  } catch (err: any) {
    pinCode.value = "";
    errorMsg.value = err?.message || __("PIN doğrulaması başarısız oldu.");
  } finally {
    submitting.value = false;
  }
}

function pressDigit(digit: string) {
  if (submitting.value || !selectedOperator.value || pinCode.value.length >= 4) return;
  errorMsg.value = null;
  pinCode.value += digit;
  if (pinCode.value.length === 4) {
    submitPin(pinCode.value);
  }
}

function handleKeyDown(e: KeyboardEvent) {
  if (!selectedOperator.value) return;
  if (/^[0-9]$/.test(e.key)) {
    e.preventDefault();
    pressDigit(e.key);
  } else if (e.key === "Backspace") {
    e.preventDefault();
    backspacePin();
  } else if (e.key === "Escape") {
    e.preventDefault();
    resetOperator();
  }
}

onMounted(() => window.addEventListener("keydown", handleKeyDown));
onUnmounted(() => window.removeEventListener("keydown", handleKeyDown));
</script>

<template>
  <div class="pin-lock-screen">
    <div class="pin-lock-container">
      <div class="pin-brand-head">
        <span class="pin-logo">🔐</span>
        <div>
          <h1 class="pin-title">{{ __("PDA Terminal Kilidi") }}</h1>
          <p class="pin-sub">{{ __("Devam etmek için personel kartınızı seçin ve 4 haneli PIN kodunuzu girin.") }}</p>
        </div>
      </div>

      <div v-if="authExpiredWarning" class="pin-alert pin-alert-warn">
        <span>⚠️ {{ __("Oturum süresi doldu. PIN ile yeniden giriş yapın veya standart oturum açın.") }}</span>
      </div>

      <template v-if="!selectedOperator">
        <input
          v-model="search"
          type="text"
          class="pin-search-input"
          :placeholder="__('Personel Ara...')"
        />

        <div v-if="filteredOperators.length === 0" class="pin-empty">
          {{ __("Yetkili ambar veya sevk personeli bulunamadı.") }}
        </div>

        <div v-else class="operator-grid">
          <button
            v-for="op in filteredOperators"
            :key="op.name"
            type="button"
            data-testid="operator-card"
            class="operator-card"
            @click="selectOperator(op)"
          >
            <div class="op-main">
              <strong class="op-name">{{ op.employee_name }}</strong>
              <span class="op-meta">{{ op.department }} · {{ op.employee }}</span>
            </div>
            <span class="op-pin-badge" :class="op.has_pin ? 'has-pin' : 'no-pin'">
              {{ op.has_pin ? __("PIN Hazır") : __("PIN Yok") }}
            </span>
          </button>
        </div>

        <div class="pin-login-footer">
          <a href="/login?redirect-to=/pda" class="pin-login-link">
            {{ __("Farklı Kullanıcı ile Giriş Yap") }}
          </a>
        </div>
      </template>

      <template v-else>
        <div class="selected-op-bar">
          <div>
            <strong class="op-name">{{ selectedOperator.employee_name }}</strong>
            <div class="op-meta">{{ selectedOperator.department }}</div>
          </div>
          <button type="button" class="btn-change-op" :disabled="submitting" @click="resetOperator">
            ← {{ __("Personel Değiştir") }}
          </button>
        </div>

        <div class="pin-dots" aria-label="PIN">
          <span
            v-for="idx in 4"
            :key="idx"
            data-testid="pin-dot"
            class="pin-dot"
            :class="{ filled: pinCode.length >= idx }"
          />
        </div>

        <div v-if="errorMsg" data-testid="pin-error" class="pin-alert pin-alert-err">
          ⚠️ {{ errorMsg }}
        </div>

        <div data-testid="pin-keypad" class="keypad-grid">
          <button
            v-for="d in ['1', '2', '3', '4', '5', '6', '7', '8', '9']"
            :key="d"
            type="button"
            :data-testid="`pin-key-${d}`"
            class="key-btn"
            :disabled="submitting"
            @click="pressDigit(d)"
          >
            {{ d }}
          </button>
          <button type="button" class="key-btn key-action" :disabled="submitting" @click="clearPin">
            {{ __("Temizle") }}
          </button>
          <button type="button" data-testid="pin-key-0" class="key-btn" :disabled="submitting" @click="pressDigit('0')">
            0
          </button>
          <button type="button" class="key-btn key-action" :disabled="submitting" @click="backspacePin">
            ⌫
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.pin-lock-screen { min-height: 100vh; display: flex; justify-content: center; align-items: flex-start; padding: 1rem; background: var(--bg-color, #f8fafc); color: var(--text-color, #0f172a); }
.pin-lock-container { width: 100%; max-width: 540px; display: flex; flex-direction: column; gap: 0.9rem; }
.pin-brand-head { display: flex; align-items: center; gap: 0.8rem; padding: 0.9rem 1rem; background: #1e293b; color: #ffffff; border-radius: 0.85rem; }
.pin-logo { font-size: 1.75rem; }
.pin-title { margin: 0; font-size: 1.15rem; font-weight: 800; }
.pin-sub { margin: 0.2rem 0 0; font-size: 0.8rem; color: #cbd5e1; }
.pin-alert { padding: 0.7rem 0.9rem; border-radius: 0.6rem; font-size: 0.85rem; font-weight: 700; }
.pin-alert-warn { background: #fef3c7; border: 1px solid #fde68a; color: #92400e; }
.pin-alert-err { background: #fee2e2; border: 1px solid #fca5a5; color: #b91c1c; text-align: center; }
[data-theme="dark"] .pin-alert-err { background: rgba(239, 68, 68, 0.2); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.pin-search-input { width: 100%; min-height: 48px; padding: 0.65rem 0.9rem; border-radius: 0.65rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-size: 0.95rem; }
.pin-empty { text-align: center; padding: 2rem 1rem; color: var(--text-muted, #64748b); background: var(--card-bg, #ffffff); border: 1px dashed var(--border-color, #cbd5e1); border-radius: 0.75rem; }
.operator-grid { display: flex; flex-direction: column; gap: 0.6rem; }
.operator-card { width: 100%; min-height: 62px; padding: 0.8rem 1rem; border-radius: 0.75rem; border: 1px solid var(--border-color, #e2e8f0); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; text-align: left; cursor: pointer; box-shadow: 0 2px 4px rgba(15, 23, 42, 0.04); }
.operator-card:active { transform: scale(0.99); border-color: #2563eb; }
.op-main { display: flex; flex-direction: column; gap: 0.15rem; }
.op-name { font-size: 1rem; font-weight: 800; }
.op-meta { font-size: 0.78rem; color: var(--text-muted, #64748b); }
.op-pin-badge { padding: 0.25rem 0.6rem; border-radius: 9999px; font-size: 0.74rem; font-weight: 700; white-space: nowrap; }
.has-pin { background: #dcfce7; color: #15803d; }
.no-pin { background: #f1f5f9; color: #64748b; }
[data-theme="dark"] .has-pin { background: rgba(34, 197, 94, 0.2); color: #86efac; }
[data-theme="dark"] .no-pin { background: rgba(255, 255, 255, 0.08); color: #94a3b8; }
.pin-login-footer { text-align: center; padding-top: 0.4rem; }
.pin-login-link { color: #2563eb; font-size: 0.86rem; font-weight: 700; text-decoration: underline; }
.selected-op-bar { display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; padding: 0.85rem 1rem; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; }
.btn-change-op { min-height: 42px; padding: 0.45rem 0.85rem; border-radius: 0.5rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--control-bg, #f1f5f9); color: var(--text-color, #0f172a); font-size: 0.84rem; font-weight: 700; cursor: pointer; }
.pin-dots { display: flex; justify-content: center; gap: 1rem; padding: 0.75rem 0; }
.pin-dot { width: 20px; height: 20px; border-radius: 50%; border: 2px solid #94a3b8; background: transparent; transition: all 0.12s; }
.pin-dot.filled { border-color: #2563eb; background: #2563eb; transform: scale(1.1); }
.keypad-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.65rem; }
.key-btn { min-height: 68px; border-radius: 0.85rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-size: 1.55rem; font-weight: 800; cursor: pointer; box-shadow: 0 2px 5px rgba(15, 23, 42, 0.06); }
.key-btn:active:not(:disabled) { background: #2563eb; color: #ffffff; }
.key-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.key-action { font-size: 1rem; background: var(--control-bg, #f1f5f9); }
</style>
