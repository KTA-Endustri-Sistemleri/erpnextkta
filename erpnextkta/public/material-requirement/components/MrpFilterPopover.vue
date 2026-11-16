<template>
  <div ref="popoverRef" class="mrp-filter-popover">
    <!-- Header -->
    <div class="mrp-popover-header">
      <div class="mrp-popover-title">
        <i class="fa fa-sliders mr-2"></i>
        <span>{{ __("Gelişmiş Filtreler") }}</span>
        <span v-if="activeFilterCount > 0" class="badge mrp-active-badge">
          {{ activeFilterCount }}
        </span>
      </div>
      <button
        type="button"
        class="btn btn-xs btn-link mrp-popover-close-btn"
        :title="__('Kapat')"
        @click="$emit('close')"
      >
        <i class="fa fa-times"></i>
      </button>
    </div>

    <!-- Body -->
    <div class="mrp-popover-body">
      <div class="mrp-popover-grid">
        <!-- Tedarikçi -->
        <div class="mrp-field-col">
          <label class="mrp-label">{{ __("Tedarikçi") }}</label>
          <input
            v-model="filters.supplier"
            type="text"
            class="form-control form-control-sm mrp-popover-input"
            :placeholder="__('Tedarikçi Ara...')"
            @keydown.enter="handleApply"
          />
        </div>

        <!-- Hammadde -->
        <div class="mrp-field-col">
          <label class="mrp-label">{{ __("Hammadde") }}</label>
          <input
            v-model="filters.hammadde"
            type="text"
            class="form-control form-control-sm mrp-popover-input"
            :placeholder="__('Kod veya Açıklama...')"
            @keydown.enter="handleApply"
          />
        </div>

        <!-- Ürün Grubu -->
        <div class="mrp-field-col">
          <label class="mrp-label">{{ __("Ürün Grubu") }}</label>
          <input
            v-model="filters.item_group"
            type="text"
            class="form-control form-control-sm mrp-popover-input"
            :placeholder="__('Ürün Grubu...')"
            @keydown.enter="handleApply"
          />
        </div>

        <!-- Müşteri Grubu -->
        <div class="mrp-field-col">
          <label class="mrp-label">{{ __("Müşteri Grubu") }}</label>
          <input
            v-model="filters.custom_musteri_grubu"
            type="text"
            class="form-control form-control-sm mrp-popover-input"
            :placeholder="__('Müşteri Grubu...')"
            @keydown.enter="handleApply"
          />
        </div>

        <!-- Bitiş Tarihi -->
        <div class="mrp-field-col mrp-field-col-full">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <label class="mrp-label mb-0">{{ __("Bitiş Tarihi") }}</label>
            <button
              v-if="isCustomToDate"
              type="button"
              class="btn btn-xs btn-link text-primary p-0 mrp-reset-horizon-btn"
              :title="__('MRP Ayarlarındaki planlama ufkuna göre sıfırla')"
              @click="resetToHorizon"
            >
              <i class="fa fa-undo mr-1"></i>{{ __("Ufka Sıfırla") }}
            </button>
            <span v-else class="mrp-horizon-tag">
              {{ settings.planning_horizon_days }} {{ __("Gün") }}
            </span>
          </div>
          <input
            v-model="filters.to_date"
            type="date"
            class="form-control form-control-sm mrp-popover-input"
            @change="handleToDateChange"
          />
        </div>
      </div>

      <!-- Sadece Eksik Olanlar & Başlangıç Tarihi Bilgisi -->
      <div class="mrp-popover-checkbox-row">
        <div class="form-check">
          <input
            id="popoverOnlyShortages"
            v-model="filters.only_shortages"
            type="checkbox"
            class="form-check-input mrp-checkbox"
          />
          <label
            for="popoverOnlyShortages"
            class="form-check-label small font-weight-bold ml-1"
          >
            {{ __("Sadece Eksik Olanlar") }}
          </label>
        </div>
        <div class="mrp-start-info text-muted small">
          <i class="fa fa-calendar-check-o mr-1"></i>
          {{ __("Başlangıç") }}: <strong>{{ formattedWeekStart }}</strong>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="mrp-popover-footer">
      <button
        type="button"
        class="btn btn-xs btn-default"
        @click="resetFilters"
      >
        <i class="fa fa-refresh mr-1"></i> {{ __("Filtreleri Sıfırla") }}
      </button>
      <button
        type="button"
        class="btn btn-xs btn-primary"
        :disabled="loading"
        @click="handleApply"
      >
        <i class="fa fa-search mr-1"></i> {{ __("Raporu Yenile") }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useMrpState } from "../composables/useMrpState";

const __ = (...args: any[]) => (window as any).__(...args);

const emit = defineEmits<{
  (e: "close"): void;
}>();

const popoverRef = ref<HTMLElement | null>(null);

const {
  filters,
  settings,
  loading,
  isCustomToDate,
  activeFilterCount,
  resetFilters,
  handleToDateChange,
  resetToHorizon,
  fetchMrpData,
} = useMrpState();

const formattedWeekStart = computed(() => {
  if (!filters.from_date) return "";
  try {
    const parts = filters.from_date.split("-");
    if (parts.length === 3) {
      return `${parts[2]}.${parts[1]}.${parts[0]}`;
    }
  } catch (e) {
    // fallback
  }
  return filters.from_date;
});

function handleApply() {
  fetchMrpData();
  emit("close");
}

function handleClickOutside(event: MouseEvent) {
  if (popoverRef.value && !popoverRef.value.contains(event.target as Node)) {
    const wrapper = popoverRef.value.parentElement;
    if (wrapper && wrapper.contains(event.target as Node)) {
      return;
    }
    emit("close");
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") {
    emit("close");
  }
}

onMounted(() => {
  document.addEventListener("click", handleClickOutside, true);
  document.addEventListener("keydown", handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener("click", handleClickOutside, true);
  document.removeEventListener("keydown", handleKeydown);
});
</script>

<style scoped>
.mrp-filter-popover {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: auto;
  width: 450px;
  max-width: calc(100vw - 24px);
  background: var(--mrp-glass-bg, rgba(255, 255, 255, 0.95));
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--mrp-border);
  border-radius: 8px;
  box-shadow: var(--card-shadow, 0 10px 25px -5px rgba(0, 0, 0, 0.15));
  z-index: 1050;
  overflow: hidden;
  animation: mrpPopoverFadeIn 0.15s ease-out;
}

@keyframes mrpPopoverFadeIn {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.mrp-popover-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--mrp-header-bg);
  border-bottom: 1px solid var(--mrp-border);
}

.mrp-popover-title {
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: 13px;
  color: var(--mrp-text);
}

.mrp-active-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 10px;
  background: #6366f1;
  color: #ffffff;
  margin-left: 6px;
}

.mrp-popover-close-btn {
  color: var(--mrp-text-muted);
  font-size: 13px;
  padding: 2px 6px;
  line-height: 1;
}

.mrp-popover-close-btn:hover {
  color: var(--mrp-text);
}

.mrp-popover-body {
  padding: 12px 14px;
  background: var(--mrp-card-bg);
}

.mrp-popover-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 12px;
}

.mrp-field-col {
  display: flex;
  flex-direction: column;
}

.mrp-field-col-full {
  grid-column: 1 / -1;
}

.mrp-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--mrp-text-muted);
  margin-bottom: 4px;
  letter-spacing: 0.3px;
}

.mrp-popover-input {
  border-radius: 6px;
  border: 1px solid var(--mrp-border);
  background-color: var(--mrp-card-bg);
  color: var(--mrp-text);
  font-size: 12px;
  height: 28px;
  padding: 2px 8px;
}

.mrp-popover-input:focus {
  border-color: #6366f1;
  outline: none;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
}

.mrp-horizon-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--mrp-card-subtle);
  color: var(--mrp-text-muted);
}

.mrp-reset-horizon-btn {
  font-size: 10px;
  font-weight: 600;
  text-decoration: none;
}

.mrp-popover-checkbox-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--mrp-border);
}

.mrp-popover-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  background: var(--mrp-header-bg);
  border-top: 1px solid var(--mrp-border);
}

@media (max-width: 576px) {
  .mrp-filter-popover {
    width: 340px;
    max-width: calc(100vw - 20px);
  }
  .mrp-popover-grid {
    grid-template-columns: 1fr;
    gap: 8px;
  }
}

@media (max-width: 320px) {
  .mrp-filter-popover {
    width: 296px;
    max-width: calc(100vw - 12px);
    left: -4px;
  }
  .mrp-popover-body {
    padding: 10px 8px;
  }
  .mrp-popover-footer {
    padding: 8px 10px;
    flex-wrap: wrap;
    gap: 6px;
  }
  .mrp-popover-footer .btn {
    flex: 1;
    text-align: center;
  }
}
</style>
