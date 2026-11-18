<script setup lang="ts">
const __ = (...args: any[]) => (window as any).__(...args);
</script>

<template>
  <header class="workspace-header">
    <div class="workspace-header-content">
      <h1 class="workspace-title">
        <slot name="title">{{ __('Shopfloor Hub') }}</slot>
      </h1>
      <p class="workspace-subtitle">
        <slot name="subtitle">
          {{ __('Gerçek Zamanlı İş Emri Yürütme ve Üretim Teyidi') }}
        </slot>
      </p>
    </div>
    <div class="workspace-header-actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.workspace-header {
  position: sticky;
  top: -1.25rem;
  z-index: 15;
  margin: -1.25rem -2rem 1.25rem -2rem;
  padding: 1rem 2rem 0.85rem 2rem;
  background: var(--card-bg, #ffffff);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}
[data-theme='dark'] .workspace-header {
  background: var(--ck-glass-bg, #1c2127);
  border-bottom-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12));
}
.workspace-header-content {
  display: flex;
  flex-direction: column;
}
.workspace-title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 800;
  color: var(--text-color, #0f172a);
}
.workspace-subtitle {
  margin: 0.2rem 0 0;
  font-size: 0.82rem;
  color: var(--text-muted, #64748b);
}
.workspace-header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
</style>
