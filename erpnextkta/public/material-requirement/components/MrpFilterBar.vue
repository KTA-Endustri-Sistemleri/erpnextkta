<template>
  <div class="mrp-filter-card">
    <div class="mrp-filter-header" @click="isCollapsed = !isCollapsed">
      <div class="mrp-filter-title">
        <i class="fa fa-sliders mr-2"></i>
        <span>{{ __("Filtreler") }}</span>
      </div>
      <div class="mrp-filter-toggle">
        <span class="text-muted small mr-2">
          {{ isCollapsed ? __("Filtreleri Göster") : __("Filtreleri Gizle") }}
        </span>
        <i :class="['fa', isCollapsed ? 'fa-chevron-down' : 'fa-chevron-up']"></i>
      </div>
    </div>

    <div v-show="!isCollapsed" class="mrp-filter-body">
      <div class="row mrp-filter-row">
        <!-- Bitiş Tarihi -->
        <div class="col-md-4 col-sm-12 mb-2">
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
            class="form-control form-control-sm mrp-input"
            @change="handleToDateChange"
          />
          <div class="mrp-start-info text-muted mt-1">
            <i class="fa fa-calendar-check-o mr-1"></i>
            {{ __("Başlangıç") }}: <strong>{{ formattedWeekStart }}</strong> ({{ __("Bu Hafta") }})
          </div>
        </div>

        <!-- Haftalık Gösterim -->
        <div class="col-md-4 col-sm-6 mb-2">
          <label class="mrp-label">{{ __("Haftalık Gösterim") }}</label>
          <select
            v-model="filters.weekly_view"
            class="form-control form-control-sm mrp-select"
          >
            <option value="Önerilen Sipariş">{{ __("Önerilen Sipariş") }}</option>
            <option value="Net İhtiyaç">{{ __("Net İhtiyaç") }}</option>
            <option value="Brüt İhtiyaç">{{ __("Brüt İhtiyaç") }}</option>
            <option value="Projeksiyon Bakiye">{{ __("Projeksiyon Bakiye") }}</option>
          </select>
        </div>

        <!-- Gruplama Şekli -->
        <div class="col-md-4 col-sm-6 mb-2">
          <label class="mrp-label">{{ __("Gruplama Şekli") }}</label>
          <select
            v-model="filters.group_by"
            class="form-control form-control-sm mrp-select"
            @change="fetchMrpData"
          >
            <option value="Bitmiş Ürün + Hammadde">{{ __("Bitmiş Ürün + Hammadde") }}</option>
            <option value="Sadece Hammadde">{{ __("Sadece Hammadde") }}</option>
          </select>
        </div>
      </div>

      <div class="row mrp-filter-row">
        <!-- Tedarikçi -->
        <div class="col-md-3 col-sm-6 mb-2">
          <label class="mrp-label">{{ __("Tedarikçi") }}</label>
          <input
            v-model="filters.supplier"
            type="text"
            class="form-control form-control-sm mrp-input"
            :placeholder="__('Tedarikçi Filtrele...')"
            @keydown.enter="fetchMrpData"
          />
        </div>

        <!-- Hammadde -->
        <div class="col-md-3 col-sm-6 mb-2">
          <label class="mrp-label">{{ __("Hammadde") }}</label>
          <input
            v-model="filters.hammadde"
            type="text"
            class="form-control form-control-sm mrp-input"
            :placeholder="__('Hammadde Kodu...')"
            @keydown.enter="fetchMrpData"
          />
        </div>

        <!-- Müşteri Grubu -->
        <div class="col-md-3 col-sm-6 mb-2">
          <label class="mrp-label">{{ __("Müşteri Grubu") }}</label>
          <input
            v-model="filters.custom_musteri_grubu"
            type="text"
            class="form-control form-control-sm mrp-input"
            :placeholder="__('Müşteri Grubu...')"
            @keydown.enter="fetchMrpData"
          />
        </div>

        <!-- Ürün Grubu -->
        <div class="col-md-3 col-sm-6 mb-2">
          <label class="mrp-label">{{ __("Ürün Grubu") }}</label>
          <input
            v-model="filters.item_group"
            type="text"
            class="form-control form-control-sm mrp-input"
            :placeholder="__('Ürün Grubu...')"
            @keydown.enter="fetchMrpData"
          />
        </div>
      </div>

      <div class="d-flex justify-content-between align-items-center mt-2 pt-2 border-top">
        <div class="form-check">
          <input
            id="onlyShortagesCheck"
            v-model="filters.only_shortages"
            type="checkbox"
            class="form-check-input"
          />
          <label for="onlyShortagesCheck" class="form-check-label small font-weight-bold ml-1">
            {{ __("Sadece Eksik Olanlar") }}
          </label>
        </div>

        <div class="d-flex gap-2">
          <button
            type="button"
            class="btn btn-xs btn-default mr-2"
            @click="resetFilters"
          >
            <i class="fa fa-refresh mr-1"></i> {{ __("Sıfırla") }}
          </button>
          <button
            type="button"
            class="btn btn-xs btn-primary"
            :disabled="loading"
            @click="fetchMrpData"
          >
            <i class="fa fa-search mr-1"></i> {{ __("Raporu Yenile") }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useMrpState } from "../composables/useMrpState";

const __ = (...args: any[]) => (window as any).__(...args);

const isCollapsed = ref(false);
const {
  filters,
  settings,
  loading,
  isCustomToDate,
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

function resetFilters() {
  filters.supplier = "";
  filters.hammadde = "";
  filters.custom_musteri_grubu = "";
  filters.item_group = "";
  filters.only_shortages = false;
  filters.weekly_view = "Önerilen Sipariş";
  filters.group_by = "Bitmiş Ürün + Hammadde";
  resetToHorizon();
}
</script>

<style scoped>
.mrp-filter-card {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  margin-bottom: 12px;
  overflow: hidden;
}

.mrp-filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  background: var(--bg-light-gray, #f8fafc);
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

.mrp-filter-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--text-color, #1e293b);
}

.mrp-filter-body {
  padding: 12px 14px;
}

.mrp-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-muted, #64748b);
  margin-bottom: 4px;
  display: block;
}

.mrp-horizon-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-gray, #e2e8f0);
  color: var(--text-muted, #475569);
  text-transform: none;
}

.mrp-reset-horizon-btn {
  font-size: 11px;
  text-decoration: underline;
  cursor: pointer;
  background: none;
  border: none;
}

.mrp-reset-horizon-btn:hover {
  color: var(--primary-color, #1d4ed8) !important;
}

.mrp-input,
.mrp-select {
  border-radius: 6px;
  border: 1px solid var(--border-color, #cbd5e1);
  font-size: 12px;
}

.mrp-input:focus,
.mrp-select:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.mrp-start-info {
  font-size: 11px;
  line-height: 1.3;
}
</style>
