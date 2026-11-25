<script setup lang="ts">
import type { WorkOrderViewMode } from '../types';

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  activeView: WorkOrderViewMode;
}>();

const emit = defineEmits<{
  (e: 'update:activeView', view: WorkOrderViewMode): void;
  (e: 'change-view', view: WorkOrderViewMode): void;
}>();

interface NavTab {
  id: WorkOrderViewMode;
  icon: string;
  label: string;
}

const tabs: NavTab[] = [
  { id: 'work_orders', icon: '⚡', label: 'Work Orders' },
  { id: 'operations', icon: '📋', label: 'Operations' },
  { id: 'work_cards', icon: '⏱️', label: 'Work Cards' },
  { id: 'reports', icon: '📊', label: 'Reports' },
];

function handleSelectTab(view: WorkOrderViewMode) {
  if (props.activeView === view) return;
  emit('update:activeView', view);
  emit('change-view', view);
}
</script>

<template>
  <header class="shopfloor-navbar">
    <div class="navbar-brand">
      <span class="brand-icon" aria-hidden="true">🏭</span>
      <span class="brand-title">SHOPFLOOR HUB</span>
    </div>

    <nav class="navbar-tabs" role="tablist" :aria-label="__('Shopfloor Views')">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        role="tab"
        :aria-selected="activeView === tab.id"
        class="nav-tab-btn"
        :class="{ active: activeView === tab.id }"
        @click="handleSelectTab(tab.id)"
      >
        <span class="tab-icon" aria-hidden="true">{{ tab.icon }}</span>
        <span class="tab-label">{{ __(tab.label) }}</span>
      </button>
    </nav>

    <div class="navbar-spacer" aria-hidden="true" />
  </header>
</template>

<style scoped>
.shopfloor-navbar {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  width: 100%;
  min-height: 54px;
  padding: 0 1.5rem;
  background: var(--card-bg, #ffffff);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.04);
  box-sizing: border-box;
  flex-shrink: 0;
  z-index: 20;
}

[data-theme='dark'] .shopfloor-navbar {
  background: var(--ck-glass-bg, #1c2127);
  border-bottom-color: var(--ck-glass-border, rgba(255, 255, 255, 0.1));
}

.navbar-brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  justify-self: start;
}

.brand-icon {
  font-size: 1.2rem;
  line-height: 1;
}

.brand-title {
  font-size: 0.95rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: var(--text-color, #0f172a);
  white-space: nowrap;
}

.navbar-tabs {
  display: flex;
  align-items: stretch;
  gap: 0.5rem;
  height: 54px;
  justify-self: center;
}

.nav-tab-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0 1.15rem;
  border: none;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: var(--text-muted, #64748b);
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.16s ease, background-color 0.16s ease, border-color 0.16s ease;
  white-space: nowrap;
}

.nav-tab-btn:hover {
  color: var(--text-color, #0f172a);
  background: rgba(37, 99, 235, 0.05);
}

[data-theme='dark'] .nav-tab-btn:hover {
  background: rgba(255, 255, 255, 0.05);
}

.nav-tab-btn.active {
  color: #2563eb;
  font-weight: 700;
  background: rgba(37, 99, 235, 0.08);
  border-bottom-color: #2563eb;
}

[data-theme='dark'] .nav-tab-btn.active {
  color: #60a5fa;
  background: rgba(59, 130, 246, 0.14);
  border-bottom-color: #60a5fa;
}

.tab-icon {
  font-size: 1rem;
  line-height: 1;
}

.navbar-spacer {
  justify-self: end;
}

@media (max-width: 768px) {
  .shopfloor-navbar {
    grid-template-columns: auto 1fr;
    gap: 0.75rem;
    padding: 0 0.85rem;
  }

  .navbar-tabs {
    justify-self: end;
    max-width: 100%;
    overflow-x: auto;
  }

  .navbar-spacer {
    display: none;
  }

  .nav-tab-btn {
    padding: 0 0.75rem;
    font-size: 0.82rem;
  }
}
</style>
