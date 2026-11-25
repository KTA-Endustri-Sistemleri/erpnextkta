<script setup lang="ts">
import { ref } from "vue";
import type { PdaOperator } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  hasEmployee: boolean;
  hasPin: boolean;
  canManageOperatorPins: boolean;
  manageableOperators: PdaOperator[];
}>();

const emit = defineEmits<{
  (e: "pin-updated"): void;
}>();

const PIN_RE = /^[0-9]{4}$/;

const pinMode = ref<"current_pin" | "account_password">("current_pin");
const currentPin = ref("");
const accountPassword = ref("");
const ownNewPin = ref("");
const ownConfirmPin = ref("");
const ownSaving = ref(false);
const ownError = ref("");

const adminTargetEmployee = ref("");
const adminNewPin = ref("");
const adminConfirmPin = ref("");
const adminSaving = ref(false);
const adminError = ref("");

async function submitOwnPin() {
  if (ownSaving.value || !props.hasEmployee) return;
  ownError.value = "";

  const newPin = ownNewPin.value.trim();
  const confirmPin = ownConfirmPin.value.trim();
  if (!PIN_RE.test(newPin)) {
    ownError.value = __("PIN kodu tam olarak 4 sayısal rakamdan oluşmalıdır.");
    return;
  }
  if (newPin !== confirmPin) {
    ownError.value = __("Yeni PIN kodları birbiriyle eşleşmiyor.");
    return;
  }
  if (props.hasPin && pinMode.value === "current_pin" && !PIN_RE.test(currentPin.value.trim())) {
    ownError.value = __("Mevcut PIN kodu 4 sayısal rakamdan oluşmalıdır.");
    return;
  }
  if (props.hasPin && pinMode.value === "account_password" && !accountPassword.value) {
    ownError.value = __("Hesap şifresi zorunludur.");
    return;
  }

  ownSaving.value = true;
  try {
    await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_update_own_pin",
      args: {
        mode: props.hasPin ? pinMode.value : "initial",
        new_pin: newPin,
        confirm_pin: confirmPin,
        current_pin: props.hasPin && pinMode.value === "current_pin" ? currentPin.value.trim() : undefined,
        account_password: props.hasPin && pinMode.value === "account_password" ? accountPassword.value : undefined,
      },
      quiet: true,
    });
    currentPin.value = "";
    accountPassword.value = "";
    ownNewPin.value = "";
    ownConfirmPin.value = "";
    window.frappe.show_alert({ message: __("PDA PIN kodunuz güncellendi."), indicator: "green" });
    emit("pin-updated");
  } catch (err: any) {
    ownError.value = err?.message || __("PIN güncellenemedi.");
  } finally {
    ownSaving.value = false;
  }
}

async function submitAdminReset() {
  if (adminSaving.value || !props.canManageOperatorPins) return;
  adminError.value = "";

  if (!adminTargetEmployee.value) {
    adminError.value = __("Lütfen bir operatör seçiniz.");
    return;
  }
  const newPin = adminNewPin.value.trim();
  const confirmPin = adminConfirmPin.value.trim();
  if (!PIN_RE.test(newPin)) {
    adminError.value = __("PIN kodu tam olarak 4 sayısal rakamdan oluşmalıdır.");
    return;
  }
  if (newPin !== confirmPin) {
    adminError.value = __("Yeni PIN kodları birbiriyle eşleşmiyor.");
    return;
  }

  adminSaving.value = true;
  try {
    await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_admin_reset_operator_pin",
      args: { target_employee: adminTargetEmployee.value, new_pin: newPin, confirm_pin: confirmPin },
      quiet: true,
    });
    adminNewPin.value = "";
    adminConfirmPin.value = "";
    window.frappe.show_alert({ message: __("Operatör PIN kodu sıfırlandı."), indicator: "green" });
    emit("pin-updated");
  } catch (err: any) {
    adminError.value = err?.message || __("Operatör PIN sıfırlanamadı.");
  } finally {
    adminSaving.value = false;
  }
}
</script>

<template>
  <div class="pin-settings-stack">
    <section class="pda-module-card" data-testid="own-pin-card">
      <div class="settings-card-head">
        <h3 class="settings-card-title">🔐 {{ __("Kişisel PDA PIN Kodu") }}</h3>
      </div>

      <p v-if="!hasEmployee" class="settings-info-box">
        {{ __("Bu kullanıcıya bağlı aktif personel kartı bulunmadığından kişisel PIN tanımlanamaz.") }}
      </p>

      <div v-else class="settings-form-stack">
        <div v-if="hasPin" class="pin-mode-tabs">
          <button
            type="button"
            class="pin-mode-tab"
            :class="{ active: pinMode === 'current_pin' }"
            data-testid="pin-mode-current"
            @click="pinMode = 'current_pin'"
          >
            {{ __("Mevcut PIN İle") }}
          </button>
          <button
            type="button"
            class="pin-mode-tab"
            :class="{ active: pinMode === 'account_password' }"
            data-testid="pin-mode-password"
            @click="pinMode = 'account_password'"
          >
            {{ __("PIN'imi Unuttum (Şifre İle)") }}
          </button>
        </div>

        <div v-if="hasPin && pinMode === 'current_pin'" class="pda-field-group">
          <label class="pda-field-label" for="own-current-pin">{{ __("Mevcut 4 Haneli PIN") }}</label>
          <input
            id="own-current-pin"
            v-model="currentPin"
            type="password"
            inputmode="numeric"
            maxlength="4"
            class="pda-control-input"
            data-testid="own-current-pin-input"
            autocomplete="off"
          />
        </div>

        <div v-else-if="hasPin && pinMode === 'account_password'" class="pda-field-group">
          <label class="pda-field-label" for="own-account-password">{{ __("Frappe Hesap Şifreniz") }}</label>
          <input
            id="own-account-password"
            v-model="accountPassword"
            type="password"
            class="pda-control-input"
            data-testid="own-password-input"
            autocomplete="current-password"
          />
        </div>

        <div class="pda-field-group">
          <label class="pda-field-label" for="own-new-pin">{{ __("Yeni 4 Haneli PIN") }}</label>
          <input
            id="own-new-pin"
            v-model="ownNewPin"
            type="password"
            inputmode="numeric"
            maxlength="4"
            class="pda-control-input"
            data-testid="own-new-pin-input"
            autocomplete="new-password"
          />
        </div>

        <div class="pda-field-group">
          <label class="pda-field-label" for="own-confirm-pin">{{ __("Yeni PIN Tekrar") }}</label>
          <input
            id="own-confirm-pin"
            v-model="ownConfirmPin"
            type="password"
            inputmode="numeric"
            maxlength="4"
            class="pda-control-input"
            data-testid="own-confirm-pin-input"
            autocomplete="new-password"
          />
        </div>

        <div v-if="ownError" class="settings-error-box">{{ ownError }}</div>

        <button
          type="button"
          class="pda-btn-primary-lg"
          data-testid="save-own-pin-btn"
          :disabled="ownSaving"
          @click="submitOwnPin"
        >
          {{ hasPin ? __("PIN Güncelle") : __("PIN Oluştur") }}
        </button>
      </div>
    </section>

    <section v-if="canManageOperatorPins" class="pda-module-card" data-testid="admin-pin-reset-card">
      <div class="settings-card-head">
        <h3 class="settings-card-title">🛡️ {{ __("Operatör PIN Sıfırlama (Yönetici)") }}</h3>
      </div>

      <p v-if="manageableOperators.length === 0" class="settings-info-box">
        {{ __("Sıfırlama yetkiniz kapsamında başka aktif PDA operatörü bulunamadı.") }}
      </p>

      <div v-else class="settings-form-stack">
        <div class="pda-field-group">
          <label class="pda-field-label" for="admin-target-op">{{ __("Operatör Seçimi") }}</label>
          <select
            id="admin-target-op"
            v-model="adminTargetEmployee"
            class="pda-control-input"
            data-testid="admin-target-operator"
          >
            <option value="">{{ __("-- Operatör Seçiniz --") }}</option>
            <option v-for="op in manageableOperators" :key="op.name" :value="op.name">
              {{ op.employee_name }}{{ op.department ? ` (${op.department})` : "" }}
            </option>
          </select>
        </div>

        <div class="pda-field-group">
          <label class="pda-field-label" for="admin-new-pin">{{ __("Yeni 4 Haneli PIN") }}</label>
          <input
            id="admin-new-pin"
            v-model="adminNewPin"
            type="password"
            inputmode="numeric"
            maxlength="4"
            class="pda-control-input"
            data-testid="admin-new-pin-input"
            autocomplete="new-password"
          />
        </div>

        <div class="pda-field-group">
          <label class="pda-field-label" for="admin-confirm-pin">{{ __("Yeni PIN Tekrar") }}</label>
          <input
            id="admin-confirm-pin"
            v-model="adminConfirmPin"
            type="password"
            inputmode="numeric"
            maxlength="4"
            class="pda-control-input"
            data-testid="admin-confirm-pin-input"
            autocomplete="new-password"
          />
        </div>

        <div v-if="adminError" class="settings-error-box">{{ adminError }}</div>

        <button
          type="button"
          class="pda-btn-primary-lg"
          data-testid="admin-reset-pin-btn"
          :disabled="adminSaving"
          @click="submitAdminReset"
        >
          {{ __("Operatör PIN'ini Sıfırla") }}
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.pin-settings-stack, .settings-form-stack { display: flex; flex-direction: column; gap: 12px; }
.settings-card-title { margin: 0; font-size: 1.02rem; font-weight: 800; }
.pin-mode-tabs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.pin-mode-tab {
  min-height: 40px; padding: 6px 10px; border-radius: 10px; border: 1px solid var(--border-color);
  background: var(--pda-surface-alt); color: var(--text-color); font-size: 0.8rem; font-weight: 700; cursor: pointer;
}
.pin-mode-tab.active { border-color: var(--pda-primary); background: rgba(37, 99, 235, 0.14); color: var(--pda-primary); }
[data-theme="dark"] .pin-mode-tab.active { color: #93c5fd; }
.settings-info-box {
  margin: 0; padding: 10px 12px; border-radius: 10px; background: var(--pda-surface-alt);
  border: 1px solid var(--border-color); color: var(--text-muted); font-size: 0.85rem; line-height: 1.4;
}
.settings-error-box {
  padding: 9px 12px; border-radius: 10px; background: rgba(239, 68, 68, 0.12);
  color: var(--pda-danger); font-size: 0.85rem; font-weight: 700;
}
</style>
