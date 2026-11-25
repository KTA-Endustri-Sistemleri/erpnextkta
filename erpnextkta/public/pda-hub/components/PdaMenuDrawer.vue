<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import type { PdaMenuCategory, PdaModuleKey, PdaScreenKey } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    isOpen: boolean;
    categories: PdaMenuCategory[];
    activeScreen: PdaModuleKey;
    selectedCategoryKey?: string | null;
    openPickingCount: number;
  }>(),
  { selectedCategoryKey: null },
);

const emit = defineEmits<{
  (e: "close"): void;
  (e: "select-screen", key: PdaScreenKey): void;
  (e: "select-category", key: string): void;
  (e: "select-all-modules"): void;
}>();

function handleKeyDown(e: KeyboardEvent) {
  if (props.isOpen && e.key === "Escape") {
    e.preventDefault();
    emit("close");
  }
}

function onSelectScreen(key: PdaScreenKey) {
  emit("select-screen", key);
  emit("close");
}

function onSelectCategory(key: string) {
  emit("select-category", key);
  emit("close");
}

function onAllModules() {
  emit("select-all-modules");
  emit("close");
}

onMounted(() => {
  window.addEventListener("keydown", handleKeyDown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeyDown);
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="isOpen"
      class="pda-drawer-backdrop"
      data-testid="drawer-backdrop"
      @click.self="emit('close')"
    >
      <aside
        class="pda-drawer-panel"
        role="dialog"
        aria-modal="true"
        :aria-label="__('Menü')"
        data-testid="pda-menu-drawer"
      >
        <div class="pda-drawer-head">
          <div class="pda-drawer-brand">
            <span>📱</span>
            <strong>{{ __("KTA PDA") }}</strong>
          </div>
          <button
            type="button"
            class="pda-drawer-close"
            data-testid="drawer-close-btn"
            :aria-label="__('Menüyü Kapat')"
            @click="emit('close')"
          >
            ✕
          </button>
        </div>

        <nav class="pda-drawer-body">
          <button
            v-if="categories.length > 1"
            type="button"
            class="pda-drawer-all-btn"
            :class="{ active: activeScreen === 'home' && selectedCategoryKey === null }"
            data-testid="drawer-all-modules-btn"
            @click="onAllModules"
          >
            <span>🏠</span>
            <span>{{ __("Ana Modüller") }}</span>
          </button>

          <div v-if="categories.length === 0" class="pda-drawer-empty">
            {{ __("Yetkili Modül Bulunamadı") }}
          </div>

          <section
            v-for="cat in categories"
            :key="cat.key"
            class="pda-drawer-group"
          >
            <button
              type="button"
              class="pda-drawer-cat-head"
              :class="{ active: activeScreen === 'home' && selectedCategoryKey === cat.key }"
              @click="onSelectCategory(cat.key)"
            >
              <span>{{ cat.icon }}</span>
              <span>{{ __(cat.title) }}</span>
            </button>

            <div class="pda-drawer-items">
              <button
                v-for="item in cat.items"
                :key="item.key"
                type="button"
                class="pda-drawer-item"
                :class="{ active: activeScreen === item.key }"
                :data-testid="`drawer-item-${item.key}`"
                @click="onSelectScreen(item.key)"
              >
                <span class="pda-drawer-item-left">
                  <span class="pda-drawer-item-icon">{{ item.icon }}</span>
                  <span class="pda-drawer-item-title">{{ __(item.title) }}</span>
                </span>
                <span
                  v-if="item.key === 'picking'"
                  class="pda-drawer-badge"
                  data-testid="drawer-picking-badge"
                >
                  {{ openPickingCount }}
                </span>
              </button>
            </div>
          </section>
        </nav>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.pda-drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(15, 23, 42, 0.56);
  display: flex;
  justify-content: flex-start;
  align-items: stretch;
}

.pda-drawer-panel {
  width: min(300px, 84vw);
  max-width: 100%;
  height: 100%;
  background: var(--card-bg, #ffffff);
  color: var(--text-color, #0f172a);
  border-right: 1px solid var(--border-color, #e2e8f0);
  display: flex;
  flex-direction: column;
  box-shadow: 4px 0 24px rgba(15, 23, 42, 0.24);
}

.pda-drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

.pda-drawer-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1rem;
  font-weight: 800;
}

.pda-drawer-close {
  min-width: 40px;
  min-height: 40px;
  border-radius: 10px;
  border: 1px solid var(--border-color, #e2e8f0);
  background: var(--pda-surface-alt, #f1f5f9);
  color: var(--text-color, #0f172a);
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
}

.pda-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.pda-drawer-all-btn,
.pda-drawer-cat-head,
.pda-drawer-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-color, #0f172a);
  text-align: left;
  cursor: pointer;
}

.pda-drawer-all-btn {
  min-height: 46px;
  padding: 10px 12px;
  font-size: 0.94rem;
  font-weight: 800;
  border-color: var(--border-color, #e2e8f0);
  background: var(--pda-surface-alt, #f1f5f9);
}

.pda-drawer-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pda-drawer-cat-head {
  padding: 6px 8px;
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted, #64748b);
}

.pda-drawer-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pda-drawer-item {
  min-height: 48px;
  padding: 10px 12px;
  justify-content: space-between;
  border-color: var(--border-color, #e2e8f0);
  background: var(--bg-color, #f8fafc);
  font-size: 0.92rem;
  font-weight: 700;
}

.pda-drawer-item.active,
.pda-drawer-all-btn.active {
  border-color: var(--pda-primary, #2563eb);
  background: rgba(37, 99, 235, 0.12);
  color: var(--pda-primary, #2563eb);
}

[data-theme="dark"] .pda-drawer-item.active,
[data-theme="dark"] .pda-drawer-all-btn.active {
  background: rgba(59, 130, 246, 0.22);
  color: #93c5fd;
}

.pda-drawer-item-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.pda-drawer-item-icon {
  font-size: 1.2rem;
}

.pda-drawer-item-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pda-drawer-badge {
  min-width: 28px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 0.78rem;
  font-weight: 800;
  text-align: center;
}

[data-theme="dark"] .pda-drawer-badge {
  background: rgba(37, 99, 235, 0.3);
  color: #bfdbfe;
}

.pda-drawer-empty {
  padding: 20px 12px;
  text-align: center;
  font-size: 0.88rem;
  color: var(--text-muted, #64748b);
}
</style>
