<template>
  <div v-if="pegging && pegging.length > 0" class="mrp-pegging-container mb-3">
    <div class="mrp-sub-header">
      <i class="fa fa-cogs mr-1 text-danger"></i>
      <span>{{ __("İhtiyaç Yaratan Bitmiş Ürünler (Talep Dağılımı)") }}</span>
    </div>

    <div class="table-responsive">
      <table class="table table-sm table-bordered mrp-sub-table">
        <thead>
          <tr>
            <th style="min-width: 130px;">{{ __("Bitmiş Ürün") }}</th>
            <th style="min-width: 180px;">{{ __("Ürün Açıklaması") }}</th>
            <th style="min-width: 100px;">{{ __("BOM") }}</th>
            <th style="min-width: 120px;">{{ __("Müşteri Grubu") }}</th>
            <th class="text-right" style="min-width: 90px;">{{ __("Toplam İhtiyaç") }}</th>
            <th
              v-for="w in weeks"
              :key="w.key"
              class="text-right"
              :class="{ 'mrp-col-highlight': w.key === selectedWeek }"
              style="min-width: 75px;"
            >
              {{ w.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in pegging" :key="`${p.finished_item}-${p.bom}`">
            <td>
              <a
                :href="`/app/item/${encodeURIComponent(p.finished_item)}`"
                target="_blank"
                class="font-weight-bold"
              >
                {{ p.finished_item }}
              </a>
            </td>
            <td>{{ p.item_name || "-" }}</td>
            <td>
              <a :href="`/app/bom/${encodeURIComponent(p.bom)}`" target="_blank">
                {{ p.bom }}
              </a>
            </td>
            <td>{{ p.customer_group || "-" }}</td>
            <td class="text-right font-weight-bold text-danger">
              -{{ formatQty(p.total) }} {{ uom }}
            </td>
            <td
              v-for="w in weeks"
              :key="w.key"
              class="text-right"
              :class="{ 'mrp-col-highlight': w.key === selectedWeek }"
            >
              <span v-if="(p.weeks?.[w.key] || 0) > 0" class="text-danger font-weight-bold">
                -{{ formatQty(p.weeks[w.key]) }}
              </span>
              <span v-else class="text-muted opacity-50">-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PeggingDemand, WeekBucket } from "../../types/mrp";

const __ = (...args: any[]) => (window as any).__(...args);

defineProps<{
  pegging: PeggingDemand[];
  weeks: WeekBucket[];
  uom: string;
  selectedWeek?: string | null;
}>();

function formatQty(val: number): string {
  if (val === null || val === undefined) return "0";
  return Number(val).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}
</script>

<style scoped>
.mrp-pegging-container {
  background: #ffffff;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.mrp-sub-header {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: #64748b;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
}

.mrp-sub-table {
  font-size: 11px;
  margin-bottom: 0;
}

.mrp-sub-table th {
  background: #f8fafc;
  color: #475569;
  font-weight: 600;
  padding: 4px 6px;
}

.mrp-sub-table td {
  padding: 4px 6px;
  vertical-align: middle;
}

.mrp-col-highlight {
  background-color: #eff6ff !important;
}
</style>
