<template>
  <td
    :class="[
      'mrp-td-week',
      cellClass,
      { 'mrp-cell-clickable': true, 'mrp-cell-selected': isSelected }
    ]"
    :title="__('Haftalık açık sipariş ve detayları görmek için tıklayın')"
    @click="focusWeekForMaterial(material.item_code, weekKey)"
  >
    <div class="mrp-cell-wrapper">
      <!-- Main Metric Value -->
      <span v-if="mainVal > 0" class="mrp-val-main">
        {{ formatQty(mainVal) }}
      </span>
      <span v-else-if="mainVal < 0" class="mrp-val-negative">
        {{ formatQty(mainVal) }}
      </span>
      <span v-else-if="!hasSupplies" class="mrp-val-zero">-</span>

      <!-- Supply Indicator Multi-Pills (State-Aware) -->
      <div v-if="weekSupplyBadges.length > 0" class="mrp-supplies-pills">
        <span
          v-for="badge in weekSupplyBadges"
          :key="badge.category"
          :class="['mrp-supply-badge', badge.cssClass]"
          :title="badge.title"
        >
          <i :class="['fa', badge.icon, 'mr-1']"></i>+{{ formatQty(badge.qty) }}
        </span>
      </div>

      <!-- Fallback PO Indicator Pill -->
      <span
        v-else-if="poQty > 0"
        class="mrp-supply-badge mrp-pill-po"
        :title="`${__('Beklenen PO')}: +${formatQty(poQty)}`"
      >
        <i class="fa fa-file-text-o mr-1"></i>+{{ formatQty(poQty) }}
      </span>
    </div>
  </td>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { MaterialItem, WeekBucket } from "../../types/mrp";
import { useMrpState } from "../../composables/useMrpState";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  material: MaterialItem;
  week: WeekBucket;
}>();

const {
  filters,
  activeWeekFilter,
  focusWeekForMaterial,
  isDrawerOpen,
  drawerItemCode,
  drawerWeekKey,
} = useMrpState();

const weekKey = computed(() => props.week.key);
const isSelected = computed(
  () =>
    isDrawerOpen.value &&
    drawerItemCode.value === props.material.item_code &&
    drawerWeekKey.value === weekKey.value
);
const cellData = computed(() => props.material.weeks?.[weekKey.value]);

const mainVal = computed(() => {
  if (!cellData.value) return 0;
  const view = filters.weekly_view;
  if (view === "Net İhtiyaç") return cellData.value.net;
  if (view === "Brüt İhtiyaç") return cellData.value.gross;
  if (view === "Projeksiyon Bakiye") return cellData.value.projected;
  return cellData.value.order; // Default: Önerilen Sipariş
});

const poQty = computed(() => cellData.value?.po || 0);

interface WeekSupplyBadge {
  category: "yolda" | "gumruklemede" | "antrepoda" | "po" | "uyusmazlikta";
  label: string;
  qty: number;
  icon: string;
  cssClass: string;
  title: string;
}

const weekSupplyBadges = computed<WeekSupplyBadge[]>(() => {
  const supplies = props.material.open_supplies?.filter((s) => s.week === weekKey.value) || [];
  if (!supplies.length) return [];

  const groups: Record<
    string,
    { qty: number; category: "yolda" | "gumruklemede" | "antrepoda" | "po" | "uyusmazlikta"; icon: string; cssClass: string; label: string }
  > = {};

  for (const s of supplies) {
    const stateStr = (s.state || "").toLowerCase();
    let cat: "yolda" | "gumruklemede" | "antrepoda" | "po" | "uyusmazlikta" = "po";
    let icon = "fa-file-text-o";
    let cssClass = "mrp-pill-po";
    let label = __("Açık PO");

    if (stateStr.includes("uyuşmaz") || stateStr.includes("uyusmaz")) {
      cat = "uyusmazlikta";
      icon = "fa-exclamation-triangle";
      cssClass = "mrp-pill-dispute";
      label = __("Uyuşmazlık");
    } else if (stateStr.includes("gümrük") || stateStr.includes("gumruk") || stateStr.includes("giriş") || stateStr.includes("giris")) {
      cat = "gumruklemede";
      icon = "fa-hourglass-half";
      cssClass = "mrp-pill-gumruk";
      label = __("Gümrükte");
    } else if (stateStr.includes("antrepo")) {
      cat = "antrepoda";
      icon = "fa-university";
      cssClass = "mrp-pill-antrepo";
      label = __("Antrepoda");
    } else if (stateStr.includes("yol")) {
      cat = "yolda";
      icon = "fa-ship";
      cssClass = "mrp-pill-yolda";
      label = __("Yolda");
    }

    if (!groups[cat]) {
      groups[cat] = { qty: 0, category: cat, icon, cssClass, label };
    }
    groups[cat].qty += Number(s.qty || 0);
  }

  const order: ("gumruklemede" | "antrepoda" | "yolda" | "po" | "uyusmazlikta")[] = [
    "gumruklemede",
    "antrepoda",
    "yolda",
    "po",
    "uyusmazlikta",
  ];

  const result: WeekSupplyBadge[] = [];
  for (const cat of order) {
    if (groups[cat] && groups[cat].qty > 0) {
      const g = groups[cat];
      result.push({
        category: cat,
        label: g.label,
        qty: g.qty,
        icon: g.icon,
        cssClass: g.cssClass,
        title: `${g.label}: +${formatQty(g.qty)}`,
      });
    }
  }

  return result;
});

const hasSupplies = computed(() => weekSupplyBadges.value.length > 0 || poQty.value > 0);

const isActionView = computed(() => {
  return filters.weekly_view === "Önerilen Sipariş" || filters.weekly_view === "Net İhtiyaç";
});

const cellClass = computed(() => {
  const isUrgent =
    props.material.first_shortage_week &&
    props.week.label === props.material.first_shortage_week &&
    props.material.is_urgent;

  if (isUrgent) return "mrp-cell-urgent";
  if (isActionView.value && mainVal.value > 0) return "mrp-cell-action-shortage";
  if (mainVal.value > 0) return "mrp-cell-positive";
  if (mainVal.value < 0) return "mrp-cell-negative";
  if (hasSupplies.value) return "mrp-cell-po-only";
  return "mrp-cell-empty";
});

function formatQty(val: number): string {
  if (val === null || val === undefined) return "0";
  return Number(val).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}
</script>

<style scoped>
.mrp-td-week {
  padding: 6px 8px;
  text-align: right;
  vertical-align: middle;
  border-right: 1px solid var(--mrp-border);
  border-bottom: 1px solid var(--mrp-border);
  white-space: nowrap;
  min-width: 90px;
  font-size: 12px;
  user-select: none;
  transition: background-color 0.12s ease;
}

.mrp-cell-clickable {
  cursor: pointer;
}

.mrp-cell-clickable:hover {
  background-color: var(--mrp-cell-hover) !important;
}

.mrp-cell-wrapper {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.mrp-val-main {
  font-weight: 600;
  color: var(--mrp-text);
}

.mrp-val-negative {
  font-weight: 700;
  color: #dc2626;
}

.mrp-val-zero {
  color: var(--mrp-text-muted);
  opacity: 0.4;
}

.mrp-supplies-pills {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  margin-top: 1px;
}

.mrp-supply-badge {
  display: inline-flex;
  align-items: center;
  font-size: 9px;
  font-weight: 600;
  padding: 1px 4px;
  border-radius: 3px;
  white-space: nowrap;
  line-height: 1.2;
}

/* Distinct Badge Color Spectrum */
/* 1. PO: İndigo */
.mrp-pill-po {
  color: #4338ca;
  background: #eef2ff;
  border: 1px solid rgba(67, 56, 202, 0.3);
}

/* 2. Yolda (In-Transit): Amber / Altın Sarısı */
.mrp-pill-yolda {
  color: #b45309;
  background: #fef3c7;
  border: 1px solid rgba(180, 83, 9, 0.3);
}

/* 3. Antrepo: Sky Blue / Camgöbeği */
.mrp-pill-antrepo {
  color: #0369a1;
  background: #e0f2fe;
  border: 1px solid rgba(3, 105, 161, 0.3);
}

/* 4. Gümrük: Canlı Turuncu */
.mrp-pill-gumruk {
  color: #c2410c;
  background: #ffedd5;
  border: 1px solid rgba(194, 65, 12, 0.3);
}

/* 5. Uyuşmazlık: Koyu Kırmızı */
.mrp-pill-dispute {
  color: #b91c1c;
  background: #fee2e2;
  border: 1px solid rgba(185, 28, 28, 0.3);
}

[data-theme="dark"] .mrp-pill-po {
  color: #a5b4fc;
  background: rgba(99, 102, 241, 0.2);
  border-color: rgba(165, 180, 252, 0.3);
}
[data-theme="dark"] .mrp-pill-yolda {
  color: #fcd34d;
  background: rgba(245, 158, 11, 0.2);
  border-color: rgba(252, 211, 77, 0.3);
}
[data-theme="dark"] .mrp-pill-antrepo {
  color: #7dd3fc;
  background: rgba(14, 165, 233, 0.2);
  border-color: rgba(125, 211, 252, 0.3);
}
[data-theme="dark"] .mrp-pill-gumruk {
  color: #fdba74;
  background: rgba(249, 115, 22, 0.2);
  border-color: rgba(253, 186, 116, 0.3);
}
[data-theme="dark"] .mrp-pill-dispute {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.25);
  border-color: rgba(252, 165, 165, 0.3);
}

.mrp-cell-urgent {
  background-color: rgba(190, 18, 60, 0.12);
}
.mrp-cell-urgent .mrp-val-main {
  color: #be123c;
  font-weight: 700;
}
[data-theme="dark"] .mrp-cell-urgent .mrp-val-main {
  color: #fda4af;
}

.mrp-cell-action-shortage {
  background-color: rgba(249, 115, 22, 0.12);
}
.mrp-cell-action-shortage .mrp-val-main {
  color: #c2410c;
  font-weight: 700;
}
[data-theme="dark"] .mrp-cell-action-shortage .mrp-val-main {
  color: #fdba74;
}

.mrp-cell-positive {
  color: var(--mrp-text);
}

.mrp-cell-negative {
  background-color: rgba(220, 38, 38, 0.12);
}

.mrp-cell-empty {
  color: var(--mrp-text-muted);
}

.mrp-cell-selected {
  outline: 2px solid #6366f1 !important;
  outline-offset: -2px;
  background-color: var(--mrp-cell-selected) !important;
  position: relative;
  z-index: 2;
}
</style>
