<template>
  <div v-if="currentWeekMetrics" class="mrp-drawer-summary-section">
    <div class="mrp-summary-section-header">
      <div class="d-flex align-items-center">
        <i class="fa fa-calculator text-primary mr-2"></i>
        <span class="mrp-summary-section-title">
          {{ __("{0} Netleştirme Hesabı Özeti", [activeWeekLabel]) }}
        </span>
      </div>
      <span v-if="currentWeekMetrics.net > 0" class="mrp-badge mrp-badge-shortage">
        {{ __("Eksik") }}
      </span>
    </div>
    <div class="mrp-strip-cards">
      <div v-for="c in stripCards" :key="c.id" :class="['mrp-strip-card', c.cardClass]">
        <span class="mrp-strip-label">{{ c.label }}</span>
        <span :class="['mrp-strip-val', c.valClass]">{{ c.val }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useMrpState } from "../../composables/useMrpState";

const __ = (...args: any[]) => (window as any).__(...args);

const { weeks, drawerWeekKey, selectedDrawerMaterial } = useMrpState();

const currentWeekObj = computed(() => {
  if (!drawerWeekKey.value) return null;
  return weeks.value.find((w) => w.key === drawerWeekKey.value) || null;
});

const activeWeekLabel = computed(() => {
  if (!drawerWeekKey.value) return "";
  return currentWeekObj.value ? currentWeekObj.value.label : drawerWeekKey.value;
});

const currentWeekMetrics = computed(() => {
  const m = selectedDrawerMaterial.value;
  const wk = drawerWeekKey.value;
  if (!m || !wk || !m.weeks) return null;
  return m.weeks[wk] || null;
});

const balanceBefore = computed(() => {
  const m = selectedDrawerMaterial.value;
  const wk = drawerWeekKey.value;
  if (!m || !wk) return 0;
  const wIdx = weeks.value.findIndex((x) => x.key === wk);
  if (wIdx <= 0) return Number(m.free_stock || 0);
  const prevWk = weeks.value[wIdx - 1]?.key;
  return Number(m.weeks?.[prevWk]?.projected ?? m.free_stock ?? 0);
});

function formatQty(val: number): string {
  if (val === null || val === undefined) return "0";
  return Number(val).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}

const stripCards = computed(() => {
  if (!currentWeekMetrics.value || !selectedDrawerMaterial.value) return [];
  const uom = selectedDrawerMaterial.value.uom;
  const m = currentWeekMetrics.value;
  return [
    { id: "balance", label: `1. ${__("Devreden Bakiye")}`, val: `${formatQty(balanceBefore.value)} ${uom}`, valClass: balanceBefore.value < 0 ? "text-danger" : "text-success", cardClass: "" },
    { id: "po", label: `2. ${__("Açık Teslimat")} (+)`, val: `+${formatQty(m.po)} ${uom}`, valClass: "text-primary", cardClass: "" },
    { id: "gross", label: `3. ${__("Brüt İhtiyaç")} (-)`, val: `-${formatQty(m.gross)} ${uom}`, valClass: "text-danger", cardClass: "" },
    { id: "net", label: `4. ${__("Net Eksik")}`, val: `${formatQty(m.net)} ${uom}`, valClass: m.net > 0 ? "text-danger font-weight-bold" : "text-muted", cardClass: m.net > 0 ? "card-shortage" : "" },
    { id: "order", label: `5. ${__("Önerilen Sipariş")}`, val: `${formatQty(m.order)} ${uom}`, valClass: "text-purple font-weight-bold", cardClass: "card-order" },
    { id: "projected", label: `6. ${__("Projeksiyon Bakiye")}`, val: `${formatQty(m.projected)} ${uom}`, valClass: m.projected < 0 ? "text-danger" : "text-success", cardClass: "" },
  ];
});
</script>

<style scoped>
.mrp-drawer-summary-section {
  padding: 12px 16px; background: var(--mrp-card-bg); border-bottom: 1px solid var(--mrp-border);
}
.mrp-summary-section-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;
}
.mrp-summary-section-title { font-weight: 700; font-size: 12px; color: var(--mrp-text); }
.mrp-strip-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.mrp-strip-card {
  display: flex; flex-direction: column; background: var(--mrp-card-subtle);
  border: 1px solid var(--mrp-border); border-radius: 6px; padding: 6px 8px; text-align: right;
}
.mrp-strip-label { font-size: 10px; color: var(--mrp-text-muted); font-weight: 600; text-align: left; margin-bottom: 2px; }
.mrp-strip-val { font-size: 12px; font-weight: 600; }
.mrp-strip-card.card-shortage { background: rgba(249, 115, 22, 0.08); border-color: rgba(249, 115, 22, 0.35); }
.mrp-strip-card.card-order { background: rgba(126, 34, 206, 0.08); border-color: rgba(126, 34, 206, 0.35); }
.mrp-badge-shortage {
  background: #ffedd5; color: #c2410c; border: 1px solid rgba(194, 65, 12, 0.3);
  font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; white-space: nowrap;
}
[data-theme="dark"] .mrp-badge-shortage { color: #fdba74; background: rgba(249, 115, 22, 0.2); border-color: rgba(253, 186, 116, 0.3); }
.text-purple { color: #7e22ce !important; }

@media (max-width: 576px) {
  .mrp-drawer-summary-section { padding: 10px 12px; }
  .mrp-strip-cards { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 320px) {
  .mrp-strip-cards { grid-template-columns: 1fr; }
}
</style>
