<template>
  <div v-if="hasMultiSupplierOrders" :class="['mrp-supplier-orders-container', { 'no-header': hideHeader }]">
    <div v-if="!hideHeader" class="mrp-sub-header">
      <i class="fa fa-pie-chart mr-1 text-purple"></i>
      <span>{{ __("Tedarikçi Bazlı Planlanan Sipariş Dağılımı") }}</span>
      <span class="badge badge-purple ml-2">{{ __(material.sourcing_strategy) }}</span>
    </div>

    <!-- Supplier Cards List (Modern Flex Cards) -->
    <div class="mrp-supplier-cards-list">
      <div
        v-for="sup in supplierRows"
        :key="sup.supplier"
        class="mrp-supplier-row-card"
      >
        <!-- Left: Supplier Identity, Quota, Unit Price, MOQ/Pack -->
        <div class="mrp-supplier-info">
          <div class="mrp-supplier-title-row">
            <span class="mrp-supplier-name" :title="sup.supplier">
              <i class="fa fa-building-o mr-1 text-muted"></i>
              {{ sup.supplier }}
            </span>
            <span v-if="sup.quota_share > 0" class="mrp-quota-badge" :title="__('Kota Payı')">
              %{{ Math.round(sup.quota_share) }}
            </span>
          </div>

          <div class="mrp-supplier-meta-row">
            <span class="mrp-meta-chip" :title="__('Birim Fiyat')">
              <i class="fa fa-tag mr-1 text-muted"></i>{{ sup.price > 0 ? formatMoney(sup.price, sup.currency) : "-" }}
            </span>
            <span v-if="sup.moq > 0 || sup.pack > 1" class="mrp-meta-chip" :title="__('Minimum Sipariş / Paket Katı')">
              <i class="fa fa-archive mr-1 text-muted"></i>MOQ: {{ formatQty(sup.moq) }} | {{ __("Paket") }}: {{ formatQty(sup.pack) }}
            </span>
          </div>
        </div>

        <!-- Right: Week Order Qty & Estimated Amount Pills -->
        <div class="mrp-supplier-order-badges">
          <span
            :class="[
              'mrp-order-qty-pill',
              getWeekOrderQty(sup) > 0 ? 'is-active' : 'is-empty'
            ]"
            :title="selectedWeek ? `${selectedWeekLabel} ${__('Siparişi')}` : __('Toplam Sipariş')"
          >
            {{ getWeekOrderQty(sup) > 0 ? '+' + formatQty(getWeekOrderQty(sup)) + ' ' + material.uom : '0 ' + material.uom }}
          </span>
          <span
            v-if="getWeekOrderAmount(sup) > 0"
            class="mrp-order-amount-pill"
            :title="__('Tahmini Tutar')"
          >
            {{ formatMoney(getWeekOrderAmount(sup), sup.currency) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { MaterialItem, WeekBucket, SupplierQuotaInfo } from "../../types/mrp";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    material: MaterialItem;
    weeks: WeekBucket[];
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

const hasMultiSupplierOrders = computed(() => {
  const bySup = props.material.planned_orders_by_supplier;
  return Boolean(bySup && Object.keys(bySup).length > 1);
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

function getWeekOrderQty(sup: any): number {
  if (props.selectedWeek) {
    return Number(sup.weekly_orders[props.selectedWeek] || 0);
  }
  return Number(sup.total_qty || 0);
}

function getWeekOrderAmount(sup: any): number {
  const qty = getWeekOrderQty(sup);
  return qty * (sup.price || 0);
}

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
  margin: 0;
  padding: 0;
  background: var(--mrp-card-bg, #ffffff);
  border: none;
}

.mrp-supplier-orders-container.no-header {
  background: transparent;
}

.mrp-sub-header {
  font-size: 11px;
  font-weight: 700;
  padding: 8px 12px 4px 12px;
  color: #7e22ce;
  display: flex;
  align-items: center;
}

.badge-purple {
  background-color: rgba(126, 34, 206, 0.12);
  color: #7e22ce;
  border: 1px solid rgba(126, 34, 206, 0.3);
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
}

.text-purple {
  color: #7e22ce !important;
}

.mrp-supplier-cards-list {
  display: flex;
  flex-direction: column;
}

.mrp-supplier-row-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--mrp-border, #e2e8f0);
  background: var(--mrp-card-bg, #ffffff);
  gap: 12px;
  transition: background 0.15s ease;
}

.mrp-supplier-row-card:last-child {
  border-bottom: none;
}

.mrp-supplier-row-card:hover {
  background: var(--mrp-cell-hover, rgba(126, 34, 206, 0.04));
}

.mrp-supplier-info {
  flex: 1;
  min-width: 0;
}

.mrp-supplier-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mrp-supplier-name {
  font-weight: 700;
  font-size: 12px;
  color: var(--mrp-text, #0f172a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mrp-quota-badge {
  font-size: 10px;
  font-weight: 700;
  color: #7e22ce;
  background: rgba(126, 34, 206, 0.1);
  border: 1px solid rgba(126, 34, 206, 0.25);
  border-radius: 4px;
  padding: 1px 6px;
}

.mrp-supplier-meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 3px;
}

.mrp-meta-chip {
  font-size: 10px;
  color: var(--mrp-text-muted, #64748b);
  background: var(--mrp-card-subtle, #f8fafc);
  border: 1px solid var(--mrp-border, #cbd5e1);
  border-radius: 4px;
  padding: 1px 6px;
}

.mrp-supplier-order-badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
  flex-shrink: 0;
}

.mrp-order-qty-pill {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  border-radius: 9999px;
  padding: 3px 10px;
  white-space: nowrap;
}

.mrp-order-qty-pill.is-active {
  color: #7e22ce;
  background: rgba(126, 34, 206, 0.1);
  border: 1px solid rgba(126, 34, 206, 0.3);
}

.mrp-order-qty-pill.is-empty {
  color: var(--mrp-text-muted, #94a3b8);
  background: var(--mrp-card-subtle, #f1f5f9);
  border: 1px solid var(--mrp-border, #e2e8f0);
}

.mrp-order-amount-pill {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  color: #15803d;
  background: rgba(22, 163, 74, 0.1);
  border: 1px solid rgba(22, 163, 74, 0.25);
  border-radius: 9999px;
  padding: 2px 8px;
  white-space: nowrap;
}
</style>
