<template>
  <div v-if="hasMultiSupplierOrders" class="mrp-supplier-orders-container">
    <div class="mrp-sub-header">
      <i class="fa fa-pie-chart mr-1 text-purple"></i>
      <span>{{ __("Tedarikçi Bazlı Planlanan Sipariş Dağılımı") }}</span>
      <span class="badge badge-purple ml-2">{{ __(material.sourcing_strategy) }}</span>
    </div>

    <div class="table-responsive">
      <table class="table table-sm table-bordered mrp-sub-table">
        <thead>
          <tr>
            <th style="min-width: 180px;">{{ __("Tedarikçi") }}</th>
            <th class="text-center" style="min-width: 80px;">{{ __("Kota") }}</th>
            <th class="text-right" style="min-width: 100px;">{{ __("Birim Fiyat") }}</th>
            <th class="text-right" style="min-width: 90px;">{{ __("MOQ") }}</th>
            <th class="text-right" style="min-width: 90px;">{{ __("Paket") }}</th>
            <th
              v-for="w in activeWeeks"
              :key="w.key"
              class="text-right"
              :class="{ 'mrp-col-highlight': w.key === selectedWeek }"
              style="min-width: 90px;"
            >
              {{ w.label }}
            </th>
            <th class="text-right font-weight-bold" style="min-width: 110px;">{{ __("Toplam Sipariş") }}</th>
            <th class="text-right font-weight-bold" style="min-width: 110px;">{{ __("Tahmini Tutar") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="sup in supplierRows" :key="sup.supplier">
            <td class="font-weight-bold">
              <i class="fa fa-building-o mr-1 text-muted"></i>
              {{ sup.supplier }}
            </td>
            <td class="text-center">
              <span v-if="sup.quota_share > 0" class="badge badge-light font-weight-bold text-purple">
                %{{ Math.round(sup.quota_share) }}
              </span>
              <span v-else class="text-muted">-</span>
            </td>
            <td class="text-right">
              {{ sup.price > 0 ? formatMoney(sup.price, sup.currency) : "-" }}
            </td>
            <td class="text-right">{{ sup.moq > 0 ? formatQty(sup.moq) : "-" }}</td>
            <td class="text-right">{{ sup.pack > 1 ? formatQty(sup.pack) : "1" }}</td>
            <td
              v-for="w in activeWeeks"
              :key="`${sup.supplier}-${w.key}`"
              class="text-right font-weight-bold"
              :class="{
                'text-purple': (sup.weekly_orders[w.key] || 0) > 0,
                'text-muted': !(sup.weekly_orders[w.key] > 0),
                'mrp-col-highlight': w.key === selectedWeek
              }"
            >
              {{ (sup.weekly_orders[w.key] || 0) > 0 ? formatQty(sup.weekly_orders[w.key]) : "-" }}
            </td>
            <td class="text-right font-weight-bold text-purple">
              {{ formatQty(sup.total_qty) }} {{ material.uom }}
            </td>
            <td class="text-right font-weight-bold text-success">
              {{ formatMoney(sup.total_amount, sup.currency) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { MaterialItem, WeekBucket, SupplierQuotaInfo } from "../../types/mrp";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  material: MaterialItem;
  weeks: WeekBucket[];
  selectedWeek?: string | null;
}>();

const hasMultiSupplierOrders = computed(() => {
  const bySup = props.material.planned_orders_by_supplier;
  return Boolean(bySup && Object.keys(bySup).length > 1);
});

// Sadece sipariş olan veya ilk 8 haftayı göster
const activeWeeks = computed(() => {
  const bySup = props.material.planned_orders_by_supplier || {};
  const hasOrderWeeks = new Set<string>();
  for (const wkMap of Object.values(bySup)) {
    for (const [w, q] of Object.entries(wkMap)) {
      if ((q as number) > 0) hasOrderWeeks.add(w);
    }
  }
  return props.weeks.filter((w, idx) => idx < 8 || hasOrderWeeks.has(w.key));
});

const supplierRows = computed(() => {
  const bySup = props.material.planned_orders_by_supplier || {};
  const quotas: SupplierQuotaInfo[] = props.material.suppliers_quota || [];
  const quotaMap = new Map<string, SupplierQuotaInfo>(quotas.map((q) => [q.supplier, q]));

  return Object.keys(bySup).map((supName) => {
    const qInfo = quotaMap.get(supName);
    const wkOrders: Record<string, number> = bySup[supName] || {};
    const totalQty: number = Object.values(wkOrders).reduce(
      (sum: number, q: number) => sum + (Number(q) || 0),
      0
    );
    const price: number = qInfo?.price || props.material.unit_price || 0;
    const currency: string = qInfo?.currency || props.material.currency || "EUR";
    const totalAmount: number = totalQty * price;

    return {
      supplier: supName,
      quota_share: qInfo?.quota_share || 0,
      moq: qInfo?.moq || 0,
      pack: qInfo?.pack || 1,
      price,
      currency,
      weekly_orders: wkOrders,
      total_qty: totalQty,
      total_amount: totalAmount,
    };
  });
});

function formatQty(val: number): string {
  if (val === null || val === undefined) return "0";
  return Number(val).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}

function formatMoney(val: number, currency: string): string {
  if (!val) return "0 " + (currency || "");
  const num = Number(val).toLocaleString("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${num} ${currency || ""}`;
}
</script>

<style scoped>
.mrp-supplier-orders-container {
  margin-bottom: 12px;
  background: #ffffff;
  border: 1px solid #e9d5ff;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(126, 34, 206, 0.05);
}

.mrp-sub-header {
  font-size: 11px;
  font-weight: 700;
  padding: 6px 10px;
  background: #faf5ff;
  border-bottom: 1px solid #f3e8ff;
  color: #6b21a8;
  display: flex;
  align-items: center;
}

.badge-purple {
  background-color: #f3e8ff;
  color: #7e22ce;
  border: 1px solid #d8b4fe;
  font-size: 10px;
  padding: 2px 6px;
}

.text-purple {
  color: #7e22ce !important;
}

.mrp-sub-table {
  font-size: 11px;
  margin-bottom: 0;
}

.mrp-sub-table th {
  background-color: #fcfaff;
  color: #4c1d95;
  font-weight: 600;
  padding: 6px 8px;
  vertical-align: middle;
}

.mrp-sub-table td {
  padding: 6px 8px;
  vertical-align: middle;
}

.mrp-col-highlight {
  background-color: #ede9fe !important;
}
</style>
