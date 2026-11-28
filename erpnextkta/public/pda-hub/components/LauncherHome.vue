<script setup lang="ts">
import { computed } from "vue";
import type { PdaMenuCategory, PdaScreenKey } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    menuCategories: PdaMenuCategory[];
    selectedCategoryKey?: string | null;
    openPickingCount: number;
    operatorName?: string;
    showMissingPinBanner?: boolean;
  }>(),
  { selectedCategoryKey: null, operatorName: "", showMissingPinBanner: false },
);

const emit = defineEmits<{
  (e: "select", moduleKey: PdaScreenKey): void;
  (e: "select-category", categoryKey: string | null): void;
  (e: "open-settings"): void;
}>();

const activeCategory = computed<PdaMenuCategory | null>(() => {
  const categories = props.menuCategories || [];
  if (categories.length === 0) return null;
  if (categories.length === 1) return categories[0];
  if (!props.selectedCategoryKey) return null;
  return categories.find((cat) => cat.key === props.selectedCategoryKey) || null;
});

function categoryHasPicking(category: PdaMenuCategory): boolean {
  return category.items.some((item) => item.key === "picking");
}
</script>

<template>
  <div class="launcher-home">
    <div class="launcher-intro">
      <h2 class="launcher-title">
        {{ activeCategory ? __(activeCategory.title) : __("Depo İşlemleri") }}
      </h2>
      <p class="launcher-sub">
        {{
          operatorName
            ? __("Hoş geldiniz, {0}. Başlamak için işlem seçin.", [operatorName])
            : __("Başlamak için işlem seçin.")
        }}
      </p>
    </div>

    <div
      v-if="showMissingPinBanner"
      class="missing-pin-banner"
      data-testid="missing-pin-banner"
    >
      <div class="missing-pin-text">
        🔑 {{ __("Hızlı geçiş için 4 haneli PDA PIN kodunuz henüz tanımlı değil.") }}
      </div>
      <button
        type="button"
        class="missing-pin-cta"
        data-testid="missing-pin-cta"
        @click="emit('open-settings')"
      >
        {{ __("Şimdi Belirle") }}
      </button>
    </div>

    <div
      v-if="menuCategories.length === 0"
      class="no-modules-card"
      data-testid="no-authorized-modules"
    >
      <div class="no-modules-icon">🔒</div>
      <h3 class="no-modules-title">{{ __("Yetkili Modül Bulunamadı") }}</h3>
      <p class="no-modules-desc">
        {{
          __(
            "Size atanmış aktif bir PDA modülü bulunmamaktadır. Yöneticinizle iletişime geçin.",
          )
        }}
      </p>
    </div>

    <div
      v-else-if="menuCategories.length > 1 && !activeCategory"
      class="launcher-grid"
    >
      <button
        v-for="cat in menuCategories"
        :key="cat.key"
        type="button"
        :data-testid="`category-card-${cat.key}`"
        class="module-card accent-blue"
        @click="emit('select-category', cat.key)"
      >
        <div class="card-top">
          <span class="card-icon">{{ cat.icon }}</span>
          <span v-if="categoryHasPicking(cat)" class="count-badge">
            {{ __("{0} Açık Emir", [props.openPickingCount]) }}
          </span>
        </div>
        <div class="card-body">
          <h3 class="card-title">{{ __(cat.title) }}</h3>
          <p class="card-desc">
            {{ __("{0} İşlem", [cat.items.length]) }}
          </p>
        </div>
      </button>
    </div>

    <div v-else-if="activeCategory" class="launcher-grid">
      <button
        v-for="mod in activeCategory.items"
        :key="mod.key"
        type="button"
        :data-testid="`module-card-${mod.key}`"
        class="module-card"
        :class="mod.accent"
        @click="emit('select', mod.key)"
      >
        <div class="card-top">
          <span class="card-icon">{{ mod.icon }}</span>
          <span v-if="mod.key === 'picking'" class="count-badge">
            {{ __("{0} Açık Emir", [props.openPickingCount]) }}
          </span>
        </div>
        <div class="card-body">
          <h3 class="card-title">{{ __(mod.title) }}</h3>
          <p class="card-desc">{{ __(mod.subtitle) }}</p>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.launcher-home { display: flex; flex-direction: column; gap: 1rem; padding: 1rem; }
.launcher-intro { display: flex; flex-direction: column; gap: 0.35rem; }
.launcher-title { margin: 0; font-size: 1.2rem; font-weight: 800; color: var(--text-color, #0f172a); }
.launcher-sub { margin: 0; font-size: 0.85rem; color: var(--text-muted, #64748b); }
.no-modules-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 0.5rem;
  padding: 2rem 1.25rem;
  border-radius: 1rem;
  border: 1.5px dashed var(--border-color, #e2e8f0);
  background: var(--card-bg, #ffffff);
  color: var(--text-color, #0f172a);
}
.no-modules-icon { font-size: 2.2rem; line-height: 1; }
.no-modules-title { margin: 0; font-size: 1.05rem; font-weight: 800; }
.no-modules-desc { margin: 0; font-size: 0.88rem; color: var(--text-muted, #64748b); max-width: 340px; }
.launcher-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.85rem; }
@media (max-width: 480px) { .launcher-grid { grid-template-columns: 1fr; } }
.module-card { min-height: 126px; padding: 1rem; border-radius: 0.95rem; border: 1.5px solid var(--border-color, #e2e8f0); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); display: flex; flex-direction: column; justify-content: space-between; gap: 0.65rem; text-align: left; cursor: pointer; box-shadow: 0 3px 8px rgba(15, 23, 42, 0.05); transition: transform 0.12s, border-color 0.15s; }
.module-card:active { transform: scale(0.98); }
.module-card.accent-blue { border-left: 5px solid #2563eb; }
.module-card.accent-amber { border-left: 5px solid #d97706; }
.module-card.accent-purple { border-left: 5px solid #9333ea; }
.module-card.accent-green { border-left: 5px solid #16a34a; }
.module-card.accent-indigo { border-left: 5px solid #4f46e5; }
.card-top { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
.card-icon { font-size: 1.85rem; line-height: 1; }
.count-badge { padding: 0.25rem 0.65rem; border-radius: 9999px; font-size: 0.78rem; font-weight: 800; background: #dbeafe; color: #1d4ed8; white-space: nowrap; }
[data-theme="dark"] .count-badge { background: rgba(37, 99, 235, 0.25); color: #93c5fd; }
.card-title { margin: 0; font-size: 1.02rem; font-weight: 800; }
.card-desc { margin: 0.25rem 0 0; font-size: 0.8rem; color: var(--text-muted, #64748b); line-height: 1.35; }
.missing-pin-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(245, 158, 11, 0.14);
  border: 1px solid rgba(245, 158, 11, 0.4);
  color: #92400e;
}
[data-theme="dark"] .missing-pin-banner { color: #fcd34d; border-color: rgba(251, 191, 36, 0.45); }
.missing-pin-text { font-size: 0.84rem; font-weight: 700; line-height: 1.35; }
.missing-pin-cta {
  flex-shrink: 0;
  min-height: 36px;
  padding: 6px 12px;
  border: none;
  border-radius: 8px;
  background: #d97706;
  color: #ffffff;
  font-size: 0.82rem;
  font-weight: 800;
  cursor: pointer;
  white-space: nowrap;
}
</style>
