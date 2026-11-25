<script setup lang="ts">
import { ref, computed } from "vue";
import type { ReportCategory, ReportDefinition } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  reports: ReportDefinition[];
  activeReportId: string;
}>();

const emit = defineEmits<{
  (e: "select-report", reportId: string): void;
}>();

const searchQuery = ref<string>("");

const filteredReports = computed<ReportDefinition[]>(() => {
  const q = (searchQuery.value || "").trim().toLowerCase();
  if (!q) return props.reports;
  return props.reports.filter((r) => {
    const t = __(r.title).toLowerCase();
    const d = __(r.description).toLowerCase();
    const c = __(r.category).toLowerCase();
    return t.includes(q) || d.includes(q) || c.includes(q) || r.id.toLowerCase().includes(q);
  });
});

interface ReportGroup {
  category: ReportCategory;
  items: ReportDefinition[];
}

const groupedReports = computed<ReportGroup[]>(() => {
  const map = new Map<ReportCategory, ReportDefinition[]>();
  for (const r of filteredReports.value) {
    const existing = map.get(r.category);
    if (existing) existing.push(r);
    else map.set(r.category, [r]);
  }
  return Array.from(map.entries()).map(([category, items]) => ({ category, items }));
});
</script>

<template>
  <aside class="reports-sidebar">
    <div class="sidebar-header">
      <div class="sidebar-title-group">
        <span class="sidebar-icon" aria-hidden="true">📊</span>
        <div>
          <h2 class="sidebar-title">{{ __("Raporlar") }}</h2>
          <span class="sidebar-count">{{ __("{0} Rapor", [filteredReports.length]) }}</span>
        </div>
      </div>
    </div>

    <div class="sidebar-search-box">
      <span class="search-icon" aria-hidden="true">🔍</span>
      <input
        v-model="searchQuery"
        type="text"
        class="sidebar-search-input"
        :placeholder="__('Rapor Ara…')"
      />
      <button
        v-if="searchQuery"
        type="button"
        class="btn-clear-search"
        :title="__('Temizle')"
        @click="searchQuery = ''"
      >
        ✕
      </button>
    </div>

    <div class="sidebar-body">
      <div v-if="groupedReports.length === 0" class="sidebar-empty">
        <span class="empty-icon" aria-hidden="true">📭</span>
        <strong>{{ __("Kayıt Yok") }}</strong>
        <p>{{ __("Aramanıza uygun rapor bulunamadı.") }}</p>
      </div>

      <div v-else class="category-groups">
        <section v-for="group in groupedReports" :key="group.category" class="category-section">
          <h3 class="category-heading">{{ __(group.category) }}</h3>
          <div class="report-list">
            <button
              v-for="report in group.items"
              :key="report.id"
              type="button"
              class="report-card"
              :class="{ selected: activeReportId === report.id }"
              @click="emit('select-report', report.id)"
            >
              <div class="report-card-top">
                <div class="report-title-wrap">
                  <span class="report-icon" aria-hidden="true">{{ report.icon }}</span>
                  <span class="report-title">{{ __(report.title) }}</span>
                </div>
                <span v-if="activeReportId === report.id" class="active-badge">{{ __("Aktif") }}</span>
              </div>
              <p class="report-desc">{{ __(report.description) }}</p>
            </button>
          </div>
        </section>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.reports-sidebar {
  width: 350px;
  min-width: 350px;
  max-width: 350px;
  height: 100%;
  background: var(--card-bg, #ffffff);
  border-right: 1px solid var(--border-color, #e2e8f0);
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  color: var(--text-color, #0f172a);
}
[data-theme="dark"] .reports-sidebar {
  background: var(--ck-glass-bg, #1c2127);
  border-right-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12));
}
.sidebar-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 1.1rem 1.15rem; border-bottom: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc);
}
[data-theme="dark"] .sidebar-header { background: rgba(255, 255, 255, 0.03); }
.sidebar-title-group { display: flex; align-items: center; gap: 0.6rem; }
.sidebar-icon { font-size: 1.4rem; }
.sidebar-title { margin: 0; font-size: 1.05rem; font-weight: 800; color: var(--text-color, #0f172a); }
.sidebar-count { font-size: 0.72rem; color: var(--text-muted, #64748b); font-weight: 600; }
.sidebar-search-box {
  position: relative; padding: 0.65rem 0.85rem; border-bottom: 1px solid var(--border-color, #e2e8f0);
  background: var(--bg-color, #f8fafc);
}
[data-theme="dark"] .sidebar-search-box { background: rgba(255, 255, 255, 0.02); }
.search-icon {
  position: absolute; left: 1.45rem; top: 50%; transform: translateY(-50%);
  font-size: 0.85rem; opacity: 0.55; pointer-events: none;
}
.sidebar-search-input {
  width: 100%; height: 36px; padding: 0 1.85rem 0 2rem; font-size: 0.82rem; border-radius: 0.45rem;
  border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff);
  color: var(--text-color, #0f172a); outline: none; box-sizing: border-box;
}
[data-theme="dark"] .sidebar-search-input { background: #14181d; border-color: rgba(255, 255, 255, 0.18); }
.sidebar-search-input:focus { border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15); }
.btn-clear-search {
  position: absolute; right: 1.35rem; top: 50%; transform: translateY(-50%);
  background: none; border: none; font-size: 0.8rem; color: #94a3b8; cursor: pointer; padding: 0.2rem;
}
.sidebar-body { flex: 1; overflow-y: auto; padding: 0.85rem; }
.sidebar-empty {
  display: flex; flex-direction: column; align-items: center; text-align: center;
  padding: 2.5rem 1rem; gap: 0.4rem; color: var(--text-muted, #64748b); font-size: 0.84rem;
}
.empty-icon { font-size: 2rem; }
.category-groups { display: flex; flex-direction: column; gap: 1.1rem; }
.category-heading {
  margin: 0 0 0.5rem 0.2rem; font-size: 0.72rem; font-weight: 800; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--text-muted, #64748b);
}
.report-list { display: flex; flex-direction: column; gap: 0.55rem; }
.report-card {
  width: 100%; text-align: left; padding: 0.8rem 0.85rem; background: var(--card-bg, #ffffff);
  border: 1.5px solid var(--border-color, #e2e8f0); border-radius: 0.65rem; cursor: pointer;
  display: flex; flex-direction: column; gap: 0.4rem; transition: all 0.15s ease; color: inherit;
}
[data-theme="dark"] .report-card { background: rgba(255, 255, 255, 0.03); border-color: rgba(255, 255, 255, 0.12); }
.report-card:hover { border-color: #93c5fd; transform: translateX(2px); }
.report-card.selected {
  border-color: #2563eb; background: rgba(37, 99, 235, 0.06); box-shadow: 0 0 0 1px #2563eb;
}
[data-theme="dark"] .report-card.selected {
  border-color: #60a5fa; background: rgba(59, 130, 246, 0.14); box-shadow: 0 0 0 1px #60a5fa;
}
.report-card-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 0.5rem; }
.report-title-wrap { display: flex; align-items: center; gap: 0.45rem; font-weight: 800; font-size: 0.86rem; color: var(--text-color, #0f172a); }
.report-icon { font-size: 1rem; flex-shrink: 0; }
.active-badge {
  font-size: 0.62rem; font-weight: 800; background: #2563eb; color: #ffffff;
  padding: 0.1rem 0.4rem; border-radius: 9999px; text-transform: uppercase; flex-shrink: 0;
}
.report-desc { margin: 0; font-size: 0.75rem; line-height: 1.4; color: var(--text-muted, #64748b); }
@media (max-width: 900px) {
  .reports-sidebar { width: 270px; min-width: 270px; max-width: 270px; }
}
@media (max-width: 700px) {
  .reports-sidebar { width: 100%; min-width: 0; max-width: 100%; height: auto; max-height: 240px; border-right: none; border-bottom: 1px solid var(--border-color, #e2e8f0); }
}
</style>
