<script setup lang="ts">
import { computed } from "vue";
import type { SortDirection } from "../../reports/tableSort";

const props = withDefaults(
  defineProps<{
    label: string;
    sortKey: string;
    activeKey: string;
    sortDir: SortDirection;
    align?: "left" | "right";
  }>(),
  { align: "left" }
);

const emit = defineEmits<{ (e: "sort", key: string): void }>();

const isActive = computed(() => props.activeKey === props.sortKey);
const ariaSort = computed(() =>
  isActive.value ? (props.sortDir === "asc" ? "ascending" : "descending") : "none"
);
</script>

<template>
  <th
    class="sortable-th"
    :class="{ 'text-right': align === 'right', 'is-active': isActive }"
    :aria-sort="ariaSort"
  >
    <button type="button" class="sort-btn" @click="emit('sort', sortKey)">
      <span>{{ label }}</span>
      <span class="sort-icon" :class="{ muted: !isActive }" aria-hidden="true">
        {{ isActive ? (sortDir === "asc" ? "▲" : "▼") : "⇅" }}
      </span>
    </button>
  </th>
</template>

<style scoped>
.sortable-th {
  text-align: left;
  padding: 0.65rem 0.7rem;
  background: var(--bg-color, #f8fafc);
  color: var(--text-muted, #64748b);
  font-weight: 700;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  white-space: nowrap;
}
[data-theme="dark"] .sortable-th {
  background: rgba(255, 255, 255, 0.04);
}
.sortable-th.text-right {
  text-align: right;
}
.sort-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: transparent;
  border: none;
  padding: 0;
  font: inherit;
  color: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.15s ease;
}
.sortable-th.text-right .sort-btn {
  justify-content: flex-end;
  width: 100%;
}
.sort-btn:hover {
  color: var(--text-color, #0f172a);
}
[data-theme="dark"] .sort-btn:hover {
  color: #f8fafc;
}
.sortable-th.is-active .sort-btn {
  color: #2563eb;
}
[data-theme="dark"] .sortable-th.is-active .sort-btn {
  color: #60a5fa;
}
.sort-icon {
  font-size: 0.68rem;
  line-height: 1;
}
.sort-icon.muted {
  opacity: 0.45;
}
</style>
