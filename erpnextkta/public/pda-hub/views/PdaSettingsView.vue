<script setup lang="ts">
import { onMounted, ref } from "vue";
import type { PdaPrinterTestResponse, PdaSettingsData } from "../types";
import { setRuntimeTranslations } from "../utils/frappeShim";
import {
  applyTheme,
  getStoredTheme,
  isSoundEnabled,
  setSoundEnabled,
  setStoredTheme,
  type PdaTheme,
} from "../utils/pdaPreferences";
import { playBeep } from "../../line-replenishment-pda/utils/audio";
import PdaPinSettingsCard from "../components/PdaPinSettingsCard.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const emit = defineEmits<{
  (e: "pin-updated"): void;
}>();

const loading = ref(true);
const loadError = ref("");
const settings = ref<PdaSettingsData | null>(null);

const selectedPrinter = ref("");
const selectedFallbackPrinter = ref("");
const savingPrinter = ref(false);
const testingPrinter = ref(false);
const printerError = ref("");
const printerTestResult = ref<PdaPrinterTestResponse | null>(null);

const activeTheme = ref<PdaTheme>(getStoredTheme());
const soundEnabled = ref<boolean>(isSoundEnabled());
const activeLang = ref<string>("tr");
const savingLang = ref(false);

async function loadSettingsData() {
  loading.value = true;
  loadError.value = "";
  try {
    const res = await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_get_settings_data",
      type: "GET",
      quiet: true,
    });
    const data = res?.message as PdaSettingsData | undefined;
    if (!data) {
      loadError.value = __("Ayar bilgileri alınamadı.");
      return;
    }
    settings.value = data;
    selectedPrinter.value = data.printer_preferences?.printer || "";
    selectedFallbackPrinter.value = data.printer_preferences?.fallback_printer || "";
    activeLang.value = data.user_language || "tr";
  } catch (err: any) {
    loadError.value = err?.message || __("Ayar bilgileri yüklenemedi.");
  } finally {
    loading.value = false;
  }
}

async function savePrinterPreferences() {
  if (savingPrinter.value) return;
  printerError.value = "";

  if (
    selectedPrinter.value &&
    selectedFallbackPrinter.value &&
    selectedPrinter.value === selectedFallbackPrinter.value
  ) {
    printerError.value = __("Varsayılan ve yedek yazıcı aynı olamaz.");
    return;
  }

  savingPrinter.value = true;
  try {
    await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_save_printer_preferences",
      args: {
        printer: selectedPrinter.value || null,
        fallback_printer: selectedFallbackPrinter.value || null,
      },
      quiet: true,
    });
    window.frappe.show_alert({ message: __("Zebra yazıcı tercihleri kaydedildi."), indicator: "green" });
  } catch (err: any) {
    printerError.value = err?.message || __("Yazıcı tercihleri kaydedilemedi.");
  } finally {
    savingPrinter.value = false;
  }
}

async function testPrinterConnection() {
  if (!selectedPrinter.value || testingPrinter.value) return;
  printerError.value = "";
  printerTestResult.value = null;
  testingPrinter.value = true;
  try {
    const res = await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_test_printer_connection",
      args: { printer_name: selectedPrinter.value },
      quiet: true,
    });
    printerTestResult.value = res?.message as PdaPrinterTestResponse;
  } catch (err: any) {
    printerError.value = err?.message || __("Yazıcı bağlantısı test edilemedi.");
  } finally {
    testingPrinter.value = false;
  }
}

function selectTheme(theme: PdaTheme) {
  activeTheme.value = theme;
  setStoredTheme(theme);
  applyTheme(theme);
}

function toggleSound() {
  const next = !soundEnabled.value;
  soundEnabled.value = next;
  setSoundEnabled(next);
  if (next) {
    void playBeep(true);
  }
}

async function selectLanguage(lang: "tr" | "en" | "de") {
  if (savingLang.value) return;
  savingLang.value = true;
  try {
    const res = await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_update_user_language",
      args: { language: lang },
      quiet: true,
    });
    const payload = res?.message;
    if (payload?.lang) {
      activeLang.value = payload.lang;
      setRuntimeTranslations(payload.lang, payload.messages || {});
      window.frappe.show_alert({ message: __("Arayüz dili güncellendi."), indicator: "green" });
    }
  } catch (err: any) {
    window.frappe.msgprint({ title: __("Hata"), message: err?.message || __("Dil güncellenemedi."), indicator: "red" });
  } finally {
    savingLang.value = false;
  }
}

function onPinUpdated() {
  emit("pin-updated");
  void loadSettingsData();
}

onMounted(() => {
  void loadSettingsData();
});
</script>

<template>
  <div class="pda-module-page">
    <div v-if="loading" class="pda-module-card" data-testid="settings-loading">
      {{ __("Ayarlar yükleniyor...") }}
    </div>

    <div v-else-if="loadError" class="pda-module-card">
      <div class="settings-error-box">{{ loadError }}</div>
      <button type="button" class="pda-btn-primary-lg" @click="loadSettingsData">
        {{ __("Tekrar Dene") }}
      </button>
    </div>

    <template v-else-if="settings">
      <PdaPinSettingsCard
        :has-employee="settings.has_employee"
        :has-pin="settings.has_pin"
        :can-manage-operator-pins="settings.can_manage_operator_pins"
        :manageable-operators="settings.manageable_operators"
        @pin-updated="onPinUpdated"
      />

      <section class="pda-module-card" data-testid="printer-settings-card">
        <h3 class="settings-card-title">🖨️ {{ __("Zebra Yazıcı Tercihleri") }}</h3>

        <div class="pda-field-group">
          <label class="pda-field-label" for="printer-primary">{{ __("Varsayılan Yazıcı") }}</label>
          <select
            id="printer-primary"
            v-model="selectedPrinter"
            class="pda-control-input"
            data-testid="printer-primary-select"
          >
            <option value="">{{ __("-- Seçilmedi --") }}</option>
            <option v-for="p in settings.authorized_printers" :key="p.name" :value="p.name">
              {{ p.printer_name }} ({{ p.name }})
            </option>
          </select>
        </div>

        <div class="pda-field-group">
          <label class="pda-field-label" for="printer-fallback">{{ __("Yedek Yazıcı") }}</label>
          <select
            id="printer-fallback"
            v-model="selectedFallbackPrinter"
            class="pda-control-input"
            data-testid="printer-fallback-select"
          >
            <option value="">{{ __("-- Seçilmedi --") }}</option>
            <option v-for="p in settings.authorized_printers" :key="p.name" :value="p.name">
              {{ p.printer_name }} ({{ p.name }})
            </option>
          </select>
        </div>

        <div v-if="printerError" class="settings-error-box">{{ printerError }}</div>

        <div
          v-if="printerTestResult"
          class="printer-status-badge"
          :class="printerTestResult.online ? 'status-online' : 'status-offline'"
          data-testid="printer-test-status"
        >
          {{ printerTestResult.printer }}: {{ printerTestResult.status }}
          <span v-if="printerTestResult.message"> — {{ printerTestResult.message }}</span>
        </div>

        <div class="pda-actions-row">
          <button
            type="button"
            class="pda-btn-outline"
            data-testid="test-printer-btn"
            :disabled="!selectedPrinter || testingPrinter"
            @click="testPrinterConnection"
          >
            {{ __("Bağlantıyı Test Et") }}
          </button>
          <button
            type="button"
            class="pda-btn-primary-lg"
            data-testid="save-printer-btn"
            :disabled="savingPrinter"
            @click="savePrinterPreferences"
          >
            {{ __("Yazıcı Tercihlerini Kaydet") }}
          </button>
        </div>
      </section>

      <section class="pda-module-card" data-testid="terminal-prefs-card">
        <h3 class="settings-card-title">🎛️ {{ __("Terminal & Görünüm") }}</h3>

        <div class="pda-field-group">
          <span class="pda-field-label">{{ __("Tema") }}</span>
          <div class="toggle-grid">
            <button
              type="button"
              class="pref-pill-btn"
              :class="{ active: activeTheme === 'light' }"
              data-testid="theme-light-btn"
              @click="selectTheme('light')"
            >
              ☀️ {{ __("Açık Tema") }}
            </button>
            <button
              type="button"
              class="pref-pill-btn"
              :class="{ active: activeTheme === 'dark' }"
              data-testid="theme-dark-btn"
              @click="selectTheme('dark')"
            >
              🌙 {{ __("Koyu Tema") }}
            </button>
          </div>
        </div>

        <div class="pda-field-group">
          <span class="pda-field-label">{{ __("Sesli Uyarılar") }}</span>
          <button
            type="button"
            class="pref-pill-btn"
            :class="{ active: soundEnabled }"
            data-testid="sound-toggle-btn"
            @click="toggleSound"
          >
            {{ soundEnabled ? `🔊 ${__("Sesli Uyarılar Açık")}` : `🔇 ${__("Sesli Uyarılar Kapalı")}` }}
          </button>
        </div>

        <div class="pda-field-group">
          <span class="pda-field-label">{{ __("Arayüz Dili") }}</span>
          <div class="lang-grid">
            <button
              type="button"
              class="pref-pill-btn"
              :class="{ active: activeLang === 'tr' }"
              data-testid="lang-btn-tr"
              :disabled="savingLang"
              @click="selectLanguage('tr')"
            >
              Türkçe
            </button>
            <button
              type="button"
              class="pref-pill-btn"
              :class="{ active: activeLang === 'en' }"
              data-testid="lang-btn-en"
              :disabled="savingLang"
              @click="selectLanguage('en')"
            >
              English
            </button>
            <button
              type="button"
              class="pref-pill-btn"
              :class="{ active: activeLang === 'de' }"
              data-testid="lang-btn-de"
              :disabled="savingLang"
              @click="selectLanguage('de')"
            >
              Deutsch
            </button>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.settings-card-title { margin: 0; font-size: 1.02rem; font-weight: 800; }
.toggle-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.lang-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.pref-pill-btn {
  min-height: 44px; padding: 8px 10px; border-radius: 10px; border: 1.5px solid var(--border-color);
  background: var(--pda-surface-alt); color: var(--text-color); font-size: 0.86rem; font-weight: 700; cursor: pointer;
}
.pref-pill-btn.active { border-color: var(--pda-primary); background: rgba(37, 99, 235, 0.14); color: var(--pda-primary); }
[data-theme="dark"] .pref-pill-btn.active { color: #93c5fd; }
.settings-error-box {
  padding: 9px 12px; border-radius: 10px; background: rgba(239, 68, 68, 0.12);
  color: var(--pda-danger); font-size: 0.85rem; font-weight: 700;
}
.printer-status-badge { padding: 9px 12px; border-radius: 10px; font-size: 0.84rem; font-weight: 700; }
.status-online { background: rgba(22, 163, 74, 0.14); color: var(--pda-success); }
.status-offline { background: rgba(239, 68, 68, 0.14); color: var(--pda-danger); }
</style>
