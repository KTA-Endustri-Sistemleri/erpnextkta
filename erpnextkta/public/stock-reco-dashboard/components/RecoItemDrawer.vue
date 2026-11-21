<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import type { RecoAnalyticsItem, RecoDocDetail } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  selected: RecoAnalyticsItem | null;
  details: RecoDocDetail[];
  detailsLoading: boolean;
  liveConnected?: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "refresh-details"): void;
  (e: "open-doc", docName: string): void;
}>();

function fmt(v: number | null | undefined): string {
  const n = Number(v || 0);
  return n.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

function barWidth(diff: number): number {
  const abs = Math.abs(Number(diff || 0));
  const wh = props.selected?.warehouses || [];
  const max = Math.max(...wh.map((w) => Math.abs(Number(w.diff || 0))), 0.0000001);
  return Math.min(100, (abs / max) * 100);
}

function docStatusLabel(ds: number): string {
  const n = Number(ds);
  if (n === 0) return __("Taslak");
  if (n === 1) return __("Onaylı");
  return String(ds ?? "");
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === "Escape" && props.selected) emit("close");
}

onMounted(() => window.addEventListener("keydown", handleKeyDown));
onUnmounted(() => window.removeEventListener("keydown", handleKeyDown));
</script>

<template>
  <aside class="sr-drawer" :class="{ open: !!selected }" :aria-hidden="!selected">
    <div class="sr-drawer-head">
      <div class="sr-drawer-title">
        <div class="mono code">{{ selected?.item_code }}</div>
        <div class="name">{{ selected?.item_name }}</div>
      </div>
      <button type="button" class="sr-btn-icon" :title="__('Kapat')" @click="emit('close')">✕</button>
    </div>

    <div class="sr-drawer-body">
      <div class="sr-drawer-kpis">
        <div class="mini">
          <div class="t">{{ __("Net") }}</div>
          <div class="v" :class="{ plus: (selected?.net_diff || 0) >= 0, minus: (selected?.net_diff || 0) < 0 }">
            {{ fmt(selected?.net_diff) }} {{ selected?.uom }}
          </div>
        </div>
        <div class="mini">
          <div class="t">{{ __("Belgeler") }}</div>
          <div class="v">{{ selected?.docs_count || 0 }}</div>
        </div>
        <div class="mini">
          <div class="t">{{ __("Depolar") }}</div>
          <div class="v">{{ selected?.warehouses?.length || 0 }}</div>
        </div>
        <div class="mini">
          <div class="t">{{ __("Risk") }}</div>
          <div class="v">{{ fmt(selected?.risk_score) }}</div>
        </div>
      </div>

      <div class="sr-section">
        <div class="sr-section-head">
          <h4>{{ __("Depo Dağılımı") }}</h4>
        </div>
        <div v-if="selected?.warehouses?.length" class="sr-bars">
          <div v-for="w in selected.warehouses" :key="w.warehouse" class="sr-bar-row" :title="w.warehouse">
            <div class="wh truncate">{{ w.warehouse }}</div>
            <div class="bar"><div class="fill" :style="{ width: barWidth(w.diff) + '%' }" /></div>
            <div class="val mono" :class="{ plus: w.diff >= 0, minus: w.diff < 0 }">{{ fmt(w.diff) }}</div>
          </div>
        </div>
        <div v-else class="muted sr-empty-sm">{{ __("Depo verisi bulunamadı.") }}</div>
      </div>

      <div class="sr-section">
        <div class="sr-section-head">
          <h4>{{ __("Belgeler") }}</h4>
          <button type="button" class="sr-btn-xs" :disabled="detailsLoading" @click="emit('refresh-details')">
            🔄 {{ __("Yenile") }}
          </button>
        </div>

        <div v-if="detailsLoading" class="sr-loading">{{ __("Yükleniyor...") }}</div>

        <div v-else class="sr-doc-table-wrap">
          <table class="sr-table">
            <thead>
              <tr>
                <th>{{ __("Belge") }}</th>
                <th>{{ __("Tarih") }}</th>
                <th>{{ __("Durum") }}</th>
                <th>{{ __("Depo") }}</th>
                <th class="right">{{ __("Fark") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in details" :key="d.name" class="sr-row" @click="emit('open-doc', d.name)">
                <td class="mono doc-link">{{ d.name }}</td>
                <td class="mono">{{ d.posting_date }}</td>
                <td>{{ docStatusLabel(d.docstatus) }}</td>
                <td class="truncate">{{ d.warehouse }}</td>
                <td class="right mono" :class="{ plus: d.diff_qty >= 0, minus: d.diff_qty < 0 }">{{ fmt(d.diff_qty) }}</td>
              </tr>
              <tr v-if="!details.length">
                <td colspan="5" class="muted sr-empty-sm">{{ __("Belge bulunamadı.") }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sr-drawer { --sr-navbar-h: var(--navbar-height, 60px); position: fixed; top: var(--sr-navbar-h); right: 0; height: calc(100vh - var(--sr-navbar-h)); width: 540px; max-width: 94vw; background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); border-left: 1px solid var(--border-color, #e2e8f0); box-shadow: -8px 0 28px rgba(15, 23, 42, 0.14); transform: translateX(100%); transition: transform 0.2s ease; z-index: 1050; display: flex; flex-direction: column; }
[data-theme="dark"] .sr-drawer { background: var(--ck-glass-bg, #1c2127); border-left-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); color: #f8fafc; }
.sr-drawer.open { transform: translateX(0); }
.sr-drawer-head { padding: 0.95rem 1.1rem; border-bottom: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); display: flex; justify-content: space-between; align-items: flex-start; gap: 0.75rem; }
[data-theme="dark"] .sr-drawer-head { background: rgba(255, 255, 255, 0.03); }
.sr-drawer-title .code { font-size: 0.78rem; color: var(--text-muted, #64748b); }
.sr-drawer-title .name { font-size: 0.96rem; font-weight: 800; margin-top: 0.15rem; }
.sr-btn-icon { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #cbd5e1); border-radius: 0.4rem; padding: 0.28rem 0.55rem; cursor: pointer; color: var(--text-muted, #64748b); }
[data-theme="dark"] .sr-btn-icon { background: rgba(255, 255, 255, 0.06); border-color: rgba(255, 255, 255, 0.16); color: #cbd5e1; }
.sr-drawer-body { padding: 1rem 1.1rem; overflow: auto; display: flex; flex-direction: column; gap: 1rem; }
.sr-drawer-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.6rem; }
@media (max-width: 560px) { .sr-drawer-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.mini { border: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); border-radius: 0.65rem; padding: 0.65rem; }
[data-theme="dark"] .mini { background: rgba(255, 255, 255, 0.03); border-color: rgba(255, 255, 255, 0.12); }
.mini .t { font-size: 0.73rem; color: var(--text-muted, #64748b); font-weight: 600; }
.mini .v { font-size: 0.92rem; font-weight: 800; margin-top: 0.35rem; }
.sr-section { display: flex; flex-direction: column; gap: 0.6rem; }
.sr-section-head { display: flex; justify-content: space-between; align-items: center; }
.sr-section-head h4 { margin: 0; font-size: 0.85rem; font-weight: 800; }
.sr-btn-xs { padding: 0.25rem 0.55rem; font-size: 0.75rem; font-weight: 700; border-radius: 0.4rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--bg-color, #f8fafc); color: var(--text-color, #0f172a); cursor: pointer; }
[data-theme="dark"] .sr-btn-xs { background: rgba(255, 255, 255, 0.06); border-color: rgba(255, 255, 255, 0.16); color: #f8fafc; }
.sr-bars { display: flex; flex-direction: column; gap: 0.5rem; }
.sr-bar-row { display: grid; grid-template-columns: 1fr 140px 80px; gap: 0.6rem; align-items: center; }
.sr-bar-row .wh { font-size: 0.78rem; }
.sr-bar-row .bar { height: 9px; background: var(--bg-color, #f1f5f9); border-radius: 9999px; overflow: hidden; }
[data-theme="dark"] .sr-bar-row .bar { background: rgba(255, 255, 255, 0.1); }
.sr-bar-row .fill { height: 100%; background: #2563eb; border-radius: 9999px; opacity: 0.75; }
.sr-doc-table-wrap { border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.55rem; overflow-x: auto; }
.sr-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; text-align: left; }
.sr-table th { padding: 0.5rem 0.65rem; background: var(--bg-color, #f8fafc); border-bottom: 1px solid var(--border-color, #e2e8f0); color: var(--text-muted, #64748b); font-weight: 700; white-space: nowrap; }
[data-theme="dark"] .sr-table th { background: rgba(255, 255, 255, 0.04); }
.sr-table td { padding: 0.5rem 0.65rem; border-bottom: 1px solid var(--border-color, #e2e8f0); }
.sr-row { cursor: pointer; }
.sr-row:hover { background: rgba(37, 99, 235, 0.06); }
.doc-link { color: #2563eb; font-weight: 700; text-decoration: underline; }
[data-theme="dark"] .doc-link { color: #60a5fa; }
.plus { color: #15803d; }
.minus { color: #dc2626; }
[data-theme="dark"] .plus { color: #4ade80; }
[data-theme="dark"] .minus { color: #f87171; }
.right { text-align: right; }
.truncate { max-width: 180px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.muted { color: var(--text-muted, #64748b); font-size: 0.78rem; }
.sr-loading, .sr-empty-sm { padding: 0.85rem; text-align: center; }
</style>
