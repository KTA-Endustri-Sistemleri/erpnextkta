<script setup lang="ts">
import type { MaterialShortageItemRow } from "../../types";
import { formatQty } from "../../reports/operationFormatters";

const __ = (...args: any[]) => (window as any).__(...args);

defineProps<{
  items: MaterialShortageItemRow[];
}>();

function itemStatusMeta(item: MaterialShortageItemRow): { cls: string; icon: string; label: string } {
  if (item.availability_status === "critical" || item.availability_status === "critical_shortage") {
    return { cls: "st-critical", icon: "🚫", label: __("Kritik Eksik") };
  }
  if (item.availability_status === "transfer_required") {
    return { cls: "st-transfer", icon: "⚠️", label: __("Transfer Gerekli") };
  }
  return { cls: "st-available", icon: "✅", label: __("Mevcut") };
}
</script>

<template>
  <tr class="detail-row">
    <td colspan="9" class="detail-td">
      <div class="shortage-items-panel">
        <div v-if="items.length === 0" class="items-empty">
          📦 {{ __("Bu iş emri için malzeme gereksinimi bulunmuyor.") }}
        </div>
        <table v-else class="inner-items-table">
          <thead>
            <tr>
              <th>{{ __("Hammadde") }}</th>
              <th>{{ __("Operasyon") }}</th>
              <th>{{ __("Kaynak Depo") }}</th>
              <th class="text-right">{{ __("Kalan İhtiyaç") }}</th>
              <th class="text-right">{{ __("Hat Deposu") }}</th>
              <th class="text-right">{{ __("Diğer Depolar") }}</th>
              <th class="text-right">{{ __("Eksik Miktar") }}</th>
              <th class="text-center">{{ __("Durum") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, idx) in items" :key="`${item.item_code}-${item.source_warehouse || ''}-${idx}`">
              <td>
                <div class="item-cell">
                  <span class="item-code">{{ item.item_code }}</span>
                  <span
                    v-if="item.item_name && item.item_name !== item.item_code"
                    class="item-name"
                    :title="item.item_name"
                  >
                    {{ item.item_name }}
                  </span>
                </div>
              </td>
              <td class="muted-cell">{{ item.operation ? __(item.operation) : "—" }}</td>
              <td class="muted-cell">{{ item.source_warehouse || "—" }}</td>
              <td class="text-right num-cell">
                {{ formatQty(item.remaining_required_qty) }}
                <small v-if="item.stock_uom">{{ item.stock_uom }}</small>
              </td>
              <td class="text-right num-cell">
                {{ formatQty(item.line_actual_qty) }}
                <small v-if="item.stock_uom">{{ item.stock_uom }}</small>
              </td>
              <td class="text-right num-cell">
                <template v-if="Number(item.other_warehouses_qty) > 0">
                  {{ formatQty(item.other_warehouses_qty) }}
                  <small v-if="item.stock_uom">{{ item.stock_uom }}</small>
                </template>
                <span v-else class="muted-cell">—</span>
              </td>
              <td class="text-right num-cell" :class="{ 'shortage-val': Number(item.shortage_qty) > 0 }">
                {{ formatQty(item.shortage_qty) }}
                <small v-if="Number(item.shortage_qty) > 0 && item.stock_uom">{{ item.stock_uom }}</small>
              </td>
              <td class="text-center">
                <span class="st-badge" :class="itemStatusMeta(item).cls">
                  <span aria-hidden="true">{{ itemStatusMeta(item).icon }}</span>
                  <span>{{ itemStatusMeta(item).label }}</span>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </td>
  </tr>
</template>

<style scoped>
.detail-td { padding: 0 !important; }
.shortage-items-panel {
  padding: 0.65rem 0.9rem 0.75rem 1.85rem;
  background: var(--bg-color, #f8fafc);
  border-left: 3px solid #f59e0b;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}
[data-theme="dark"] .shortage-items-panel {
  background: rgba(255, 255, 255, 0.03);
  border-left-color: #fbbf24;
  border-bottom-color: rgba(255, 255, 255, 0.1);
}
.items-empty { font-size: 0.8rem; color: var(--text-muted, #64748b); font-weight: 600; padding: 0.4rem 0; }
.inner-items-table {
  width: 100%; border-collapse: collapse; font-size: 0.78rem;
  background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.5rem; overflow: hidden;
}
[data-theme="dark"] .inner-items-table {
  background: var(--ck-glass-bg, #181d23); border-color: rgba(255, 255, 255, 0.1);
}
.inner-items-table th {
  text-align: left; padding: 0.45rem 0.65rem; background: var(--bg-color, #f1f5f9);
  color: var(--text-muted, #64748b); font-weight: 700; border-bottom: 1px solid var(--border-color, #e2e8f0); white-space: nowrap;
}
[data-theme="dark"] .inner-items-table th { background: rgba(255, 255, 255, 0.04); }
.inner-items-table td {
  padding: 0.48rem 0.65rem; border-bottom: 1px solid var(--border-color, #e2e8f0); vertical-align: middle;
}
.inner-items-table tr:last-child td { border-bottom: none; }
.item-cell { display: flex; flex-direction: column; gap: 0.1rem; }
.item-code { font-weight: 700; color: var(--text-color, #0f172a); }
.item-name { font-size: 0.7rem; color: var(--text-muted, #64748b); max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.muted-cell { color: var(--text-muted, #64748b); }
.num-cell { font-variant-numeric: tabular-nums; white-space: nowrap; }
.shortage-val { font-weight: 800; color: #dc2626; }
[data-theme="dark"] .shortage-val { color: #f87171; }
.st-badge {
  display: inline-flex; align-items: center; gap: 0.25rem;
  font-size: 0.68rem; padding: 0.1rem 0.48rem; border-radius: 9999px; font-weight: 800; white-space: nowrap;
}
.st-critical { background: #fee2e2; color: #b91c1c; }
.st-transfer { background: #fef3c7; color: #b45309; }
.st-available { background: #dcfce7; color: #15803d; }
[data-theme="dark"] .st-critical { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
[data-theme="dark"] .st-transfer { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }
[data-theme="dark"] .st-available { background: rgba(34, 197, 94, 0.18); color: #86efac; }
.text-right { text-align: right; }
.text-center { text-align: center; }
</style>
