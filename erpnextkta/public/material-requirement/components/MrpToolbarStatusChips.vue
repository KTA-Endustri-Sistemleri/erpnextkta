<template>
  <div class="mrp-filter-chips">
    <button
      v-for="chip in visibleChips"
      :key="chip.key"
      type="button"
      :class="[
        'mrp-chip-btn',
        `mrp-chip-${chip.key}`,
        { active: filters.status_filter === chip.key },
      ]"
      :title="chip.title ? __(chip.title) : undefined"
      @click="setStatusFilter(chip.key)"
    >
      <span v-if="chip.dot" :class="['mrp-dot', `mrp-dot-${chip.dot}`]"></span>
      <i v-else-if="chip.icon" :class="[chip.icon, 'mr-1']"></i>
      {{ __(chip.label) }}
      <span class="badge">{{ chip.count }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { StatusFilterType } from "../types/mrp";
import { useMrpState } from "../composables/useMrpState";

const __ = (...args: any[]) => (window as any).__(...args);

const { filters, summary, setStatusFilter } = useMrpState();

interface StatusChipConfig {
  key: StatusFilterType;
  label: string;
  count: number;
  dot?: string;
  icon?: string;
  title?: string;
  show?: boolean;
}

const visibleChips = computed<StatusChipConfig[]>(() => {
  const s = summary.value;
  const list: StatusChipConfig[] = [
    { key: "all", label: "Tümü", count: s.total_items },
    { key: "urgent", label: "Acil Eksikler", count: s.urgent_count, dot: "urgent" },
    { key: "shortages", label: "Tüm Eksikler", count: s.shortage_count, dot: "shortage" },
    { key: "has_po", label: "Açık PO", count: s.po_count, icon: "fa fa-truck" },
  ];
  if (s.antrepo_count) list.push({ key: "antrepoda", label: "Antrepoda", count: s.antrepo_count, icon: "fa fa-university", title: "Gümrüklü antrepoda bekleyen hammaddeleri göster" });
  if (s.gumruk_count) list.push({ key: "gumruklemede", label: "Gümrükte", count: s.gumruk_count, icon: "fa fa-hourglass-half", title: "Gümrükleme / çekim işlemi başlatılmış teslimatları göster" });
  if (s.yolda_count) list.push({ key: "yolda", label: "Yolda", count: s.yolda_count, icon: "fa fa-ship", title: "Sevkiyatta / Yolda olan hammaddeleri göster" });
  if (s.uyusmazlik_count) list.push({ key: "uyusmazlikta", label: "Uyuşmazlık", count: s.uyusmazlik_count, icon: "fa fa-exclamation-triangle", title: "Kapıda uyuşmazlık veya kalite problemi nedeniyle bloke olan teslimatlar" });
  list.push({ key: "sufficient", label: "Yeterli Stok", count: s.sufficient_count, dot: "sufficient" });
  return list;
});
</script>

<style scoped>
.mrp-filter-chips { display: flex; gap: 5px; flex-wrap: wrap; }
.mrp-chip-btn {
  display: inline-flex; align-items: center; gap: 5px; padding: 2px 7px;
  font-size: 11px; font-weight: 500; border: 1px solid var(--mrp-border);
  border-radius: 6px; background: var(--mrp-card-bg); color: var(--mrp-text);
  cursor: pointer; transition: all 0.15s ease; height: 26px;
}
.mrp-chip-btn:hover { background: var(--mrp-cell-hover); }
.mrp-chip-btn.active { background: #4338ca; color: #ffffff; border-color: #4338ca; }
.mrp-chip-antrepoda.active { background: #0284c7; border-color: #0284c7; color: #ffffff; }
.mrp-chip-gumruklemede.active { background: #ea580c; border-color: #ea580c; color: #ffffff; }
.mrp-chip-yolda.active { background: #d97706; border-color: #d97706; color: #ffffff; }
.mrp-chip-uyusmazlikta.active { background: #dc2626; border-color: #dc2626; color: #ffffff; }
.mrp-chip-uyusmazlikta:not(.active) { color: #dc2626; border-color: rgba(220, 38, 38, 0.4); background: rgba(220, 38, 38, 0.12); }
.mrp-chip-btn .badge { background: rgba(0, 0, 0, 0.08); color: inherit; font-size: 10px; padding: 1px 5px; border-radius: 10px; }
.mrp-chip-btn.active .badge { background: rgba(255, 255, 255, 0.25); color: #ffffff; }

.mrp-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.mrp-dot-urgent { background: #be123c; }
.mrp-dot-shortage { background: #f97316; }
.mrp-dot-sufficient { background: #15803d; }

@media (max-width: 576px) {
  .mrp-filter-chips { flex-wrap: nowrap; width: max-content; }
}
@media (max-width: 320px) {
  .mrp-filter-chips { flex-wrap: wrap; width: 100%; }
}
</style>
