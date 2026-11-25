<script setup lang="ts">
import { computed } from "vue";
import type { ReportDefinition } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  reports: ReportDefinition[];
  activeReportId: string;
}>();

const emit = defineEmits<{
  (e: "select-work-order", workOrder: string, operation?: string): void;
}>();

const activeReport = computed<ReportDefinition | null>(
  () => props.reports.find((r) => r.id === props.activeReportId) || props.reports[0] || null
);

function handleSelectWorkOrder(workOrder: string, operation?: string) {
  emit("select-work-order", workOrder, operation);
}
</script>

<template>
  <section v-if="activeReport" class="reports-workspace">
    <div class="report-hero-card">
      <div class="hero-left">
        <span class="hero-icon" aria-hidden="true">{{ activeReport.icon }}</span>
        <div>
          <span class="hero-category">{{ __(activeReport.category) }}</span>
          <h2 class="hero-title">{{ __(activeReport.title) }}</h2>
          <p class="hero-desc">{{ __(activeReport.description) }}</p>
        </div>
      </div>
    </div>

    <component :is="activeReport.component" @select-work-order="handleSelectWorkOrder" />
  </section>

  <div v-else class="reports-empty-state">
    <div class="empty-icon" aria-hidden="true">📊</div>
    <h3 class="empty-title">{{ __("Bir Rapor Seçin") }}</h3>
    <p class="empty-desc">{{ __("Lütfen sol paneldeki katalogdan görüntülemek istediğiniz raporu seçin.") }}</p>
  </div>
</template>

<style scoped>
.reports-workspace {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.report-hero-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.9rem 1.15rem;
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.75rem;
}

[data-theme="dark"] .report-hero-card {
  background: var(--ck-glass-bg, #1c2127);
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.1));
}

.hero-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.hero-icon {
  font-size: 1.5rem;
  line-height: 1.1;
}

.hero-category {
  display: inline-block;
  font-size: 0.68rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #2563eb;
  margin-bottom: 0.15rem;
}

[data-theme="dark"] .hero-category {
  color: #60a5fa;
}

.hero-title {
  margin: 0;
  font-size: 1.08rem;
  font-weight: 800;
  color: var(--text-color, #0f172a);
}

.hero-desc {
  margin: 0.2rem 0 0;
  font-size: 0.8rem;
  color: var(--text-muted, #64748b);
}

.reports-empty-state {
  text-align: center;
  padding: 5rem 1rem;
  background: var(--card-bg, #ffffff);
  border: 2px dashed var(--border-color, #e2e8f0);
  border-radius: 0.85rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
}

[data-theme="dark"] .reports-empty-state {
  background: var(--ck-glass-bg, #1c2127);
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12));
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 0.4rem;
}

.empty-title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 800;
  color: var(--text-color, #0f172a);
}

.empty-desc {
  margin: 0;
  font-size: 0.86rem;
  color: var(--text-muted, #64748b);
  max-width: 420px;
}
</style>
