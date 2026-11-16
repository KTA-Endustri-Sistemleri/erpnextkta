<template>
  <div v-if="pegging && pegging.length > 0" :class="['mrp-pegging-container', { 'no-header': hideHeader }]">
    <div v-if="!hideHeader" class="mrp-sub-header">
      <i class="fa fa-cogs mr-1 text-danger"></i>
      <span>{{ __("İhtiyaç Yaratan Bitmiş Ürünler (Talep Dağılımı)") }}</span>
    </div>

    <!-- Empty state for selected week -->
    <div
      v-if="selectedWeek && displayPegging.length === 0"
      class="mrp-pegging-empty py-3 px-3 text-center text-muted small"
    >
      <i class="fa fa-info-circle mr-1"></i>
      {{ __("Bu hafta için hammadde talebi doğuran bitmiş ürün bulunmamaktadır.") }}
    </div>

    <!-- Pegging Flex List (Modern Card Layout) -->
    <div v-else class="mrp-pegging-list">
      <div
        v-for="p in displayPegging"
        :key="`${p.finished_item}-${p.bom}`"
        class="mrp-pegging-item-card"
      >
        <!-- Left: Finished Item Code, Name, BOM, Customer Group -->
        <div class="mrp-pegging-info">
          <div class="mrp-pegging-header-line">
            <a
              :href="`/app/item/${encodeURIComponent(p.finished_item)}`"
              target="_blank"
              class="mrp-item-code-link"
              :title="__('Mamul Detayı')"
            >
              <i class="fa fa-cube mr-1 text-muted"></i>
              {{ p.finished_item }}
            </a>

            <a
              v-if="p.bom"
              :href="`/app/bom/${encodeURIComponent(p.bom)}`"
              target="_blank"
              class="mrp-bom-badge"
              :title="__('Ürün Reçetesi (BOM)')"
            >
              <i class="fa fa-sitemap mr-1"></i>{{ p.bom }}
            </a>

            <span
              v-if="p.customer_group"
              class="mrp-customer-badge"
              :title="__('Müşteri Grubu')"
            >
              <i class="fa fa-users mr-1"></i>{{ p.customer_group }}
            </span>
          </div>

          <div
            v-if="p.item_name && p.item_name !== p.finished_item"
            class="mrp-item-name-sub"
            :title="p.item_name"
          >
            {{ p.item_name }}
          </div>
        </div>

        <!-- Right: Demand Quantity Badge -->
        <div class="mrp-pegging-demand">
          <span
            class="mrp-demand-pill"
            :title="selectedWeek ? `${selectedWeekLabel} ${__('İhtiyacı')}` : __('Toplam İhtiyaç')"
          >
            -{{ formatQty(selectedWeek ? (p.weeks?.[selectedWeek] || 0) : p.total) }} {{ uom }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { PeggingDemand, WeekBucket } from "../../types/mrp";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    pegging: PeggingDemand[];
    weeks: WeekBucket[];
    uom: string;
    selectedWeek?: string | null;
    hideHeader?: boolean;
  }>(),
  {
    selectedWeek: null,
    hideHeader: false,
  }
);

const selectedWeekLabel = computed(() => {
  if (!props.selectedWeek) return "";
  const match = props.weeks.find((w) => w.key === props.selectedWeek);
  return match ? match.label : props.selectedWeek;
});

const displayPegging = computed(() => {
  if (!props.selectedWeek) {
    return props.pegging || [];
  }
  return (props.pegging || []).filter(
    (p) => (p.weeks?.[props.selectedWeek!] || 0) > 0
  );
});

function formatQty(val: number): string {
  if (val === null || val === undefined) return "0";
  return Number(val).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}
</script>

<style scoped>
.mrp-pegging-container {
  background: var(--mrp-card-bg, #ffffff);
  padding: 0;
  border: none;
  margin: 0;
}

.mrp-pegging-container.no-header {
  background: transparent;
}

.mrp-sub-header {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--mrp-text-muted, #64748b);
  margin-bottom: 6px;
  padding: 8px 12px 4px 12px;
  display: flex;
  align-items: center;
}

.mrp-pegging-empty {
  background: var(--mrp-card-subtle, #f8fafc);
  border: 1px dashed var(--mrp-border, #cbd5e1);
  border-radius: 6px;
  margin: 10px 12px;
}

.mrp-pegging-list {
  display: flex;
  flex-direction: column;
}

.mrp-pegging-item-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--mrp-border, #e2e8f0);
  background: var(--mrp-card-bg, #ffffff);
  gap: 12px;
  transition: background 0.15s ease;
}

.mrp-pegging-item-card:last-child {
  border-bottom: none;
}

.mrp-pegging-item-card:hover {
  background: var(--mrp-cell-hover, rgba(37, 99, 235, 0.04));
}

.mrp-pegging-info {
  flex: 1;
  min-width: 0;
}

.mrp-pegging-header-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.mrp-item-code-link {
  font-weight: 700;
  font-size: 12px;
  color: #2563eb;
  text-decoration: none;
}

.mrp-item-code-link:hover {
  text-decoration: underline;
}

.mrp-bom-badge {
  font-size: 10px;
  font-weight: 600;
  color: var(--mrp-text-muted, #64748b);
  background: var(--mrp-card-subtle, #f1f5f9);
  border: 1px solid var(--mrp-border, #cbd5e1);
  border-radius: 4px;
  padding: 1px 6px;
  text-decoration: none;
}

.mrp-bom-badge:hover {
  color: #2563eb;
  border-color: #93c5fd;
}

.mrp-customer-badge {
  font-size: 10px;
  font-weight: 600;
  color: #475569;
  background: rgba(148, 163, 184, 0.15);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 4px;
  padding: 1px 6px;
}

.mrp-item-name-sub {
  font-size: 11px;
  color: var(--mrp-text-muted, #64748b);
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mrp-pegging-demand {
  flex-shrink: 0;
}

.mrp-demand-pill {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  color: #dc2626;
  background: rgba(220, 38, 38, 0.1);
  border: 1px solid rgba(220, 38, 38, 0.25);
  border-radius: 9999px;
  padding: 3px 10px;
  white-space: nowrap;
}
</style>
