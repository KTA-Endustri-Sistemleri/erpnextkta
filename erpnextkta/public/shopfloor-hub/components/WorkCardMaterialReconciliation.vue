<script setup lang="ts">
import { ref, computed } from 'vue';
import type { MaterialReconciliationItem } from '../types';

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    items?: MaterialReconciliationItem[];
  }>(),
  {
    items: () => [],
  }
);

const isOpen = ref<boolean>(true);
const searchQuery = ref<string>('');
type FilterType = 'all' | 'over' | 'progress' | 'matched' | 'none';
const activeFilter = ref<FilterType>('all');
const expandedItems = ref<Record<string, boolean>>({});

function getItemKey(item: MaterialReconciliationItem): string {
  return `${item.item_code}-${item.operation || ''}`;
}

function isItemExpanded(item: MaterialReconciliationItem): boolean {
  return !!expandedItems.value[getItemKey(item)];
}

function toggleItemExpanded(item: MaterialReconciliationItem): void {
  const key = getItemKey(item);
  expandedItems.value[key] = !expandedItems.value[key];
}

function toggleOpen() {
  isOpen.value = !isOpen.value;
}

const countOver = computed(
  () => (props.items || []).filter((i) => i.status === 'Plan Aşımı').length
);
const countProgress = computed(
  () => (props.items || []).filter((i) => i.status === 'Devam Ediyor').length
);
const countMatched = computed(
  () => (props.items || []).filter((i) => i.status === 'Tamamlandı').length
);
const countNone = computed(
  () => (props.items || []).filter((i) => i.status === 'Tüketim Yok').length
);

function matchesFilter(
  item: MaterialReconciliationItem,
  filter: FilterType
): boolean {
  if (filter === 'all') return true;
  if (filter === 'over') return item.status === 'Plan Aşımı';
  if (filter === 'progress') return item.status === 'Devam Ediyor';
  if (filter === 'matched') return item.status === 'Tamamlandı';
  if (filter === 'none') return item.status === 'Tüketim Yok';
  return true;
}

const filteredItems = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  return (props.items || []).filter((item) => {
    const matchesSearch =
      !q ||
      (item.item_code && item.item_code.toLowerCase().includes(q)) ||
      (item.item_name && item.item_name.toLowerCase().includes(q)) ||
      (item.operation && item.operation.toLowerCase().includes(q));

    const matchesStatus = matchesFilter(item, activeFilter.value);
    return matchesSearch && matchesStatus;
  });
});

function formatQty(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(Number(value))) {
    return '0';
  }
  const n = Number(value);
  if (n === 0) return '0';
  return parseFloat(n.toFixed(4)).toString();
}

function formatVariance(variance: number | null | undefined): string {
  const v = Number(variance || 0);
  if (v > 0) {
    return `+${parseFloat(v.toFixed(4)).toString()}`;
  }
  return parseFloat(v.toFixed(4)).toString();
}

function getVarianceClass(variance: number | null | undefined): string {
  const v = Number(variance || 0);
  if (v > 0) return 'variance-over';
  if (v < 0) return 'variance-under';
  return 'variance-exact';
}

function getStatusBadgeClass(status: string): string {
  switch (status) {
    case 'Plan Aşımı':
      return 'badge-status-over';
    case 'Devam Ediyor':
      return 'badge-status-progress';
    case 'Tamamlandı':
      return 'badge-status-matched';
    case 'Tüketim Yok':
      return 'badge-status-none';
    case 'Reçete Dışı':
      return 'badge-status-extra';
    default:
      return 'badge-status-default';
  }
}

function formatStatusBadge(status: string): string {
  const iconMap: Record<string, string> = {
    'Plan Aşımı': '🔴',
    'Devam Ediyor': '🟡',
    'Tamamlandı': '🟢',
    'Tüketim Yok': '⚪',
    'Reçete Dışı': '🟣',
  };
  const icon = iconMap[status] || '⚪';
  const labelMap: Record<string, string> = {
    'Plan Aşımı': __('Plan Aşımı'),
    'Devam Ediyor': __('Devam Ediyor'),
    'Tamamlandı': __('%100 Eşleşti'),
    'Tüketim Yok': __('Tüketim Yok'),
    'Reçete Dışı': __('Reçete Dışı'),
  };
  return `${icon} ${labelMap[status] || __(status)}`;
}
</script>

<template>
  <div class="material-reconciliation-section">
    <!-- Başlık ve Özet Çubuğu -->
    <div
      class="recon-header"
      role="button"
      tabindex="0"
      :aria-expanded="isOpen"
      @click="toggleOpen"
      @keydown.enter.space.prevent="toggleOpen"
    >
      <div class="header-left">
        <span class="recon-icon" aria-hidden="true">⚖️</span>
        <h4 class="recon-title">
          {{ __('Hammadde Tüketim ve Fire Mutabakatı') }}
        </h4>
        <span class="chip-total">
          {{ items.length }} {{ __('Kalem') }}
        </span>
        <div class="summary-chips">
          <span
            v-if="countOver > 0"
            class="chip-pill chip-over"
            :title="__('Plan Aşımı')"
          >
            🔴 {{ countOver }} {{ __('Plan Aşımı') }}
          </span>
          <span
            v-if="countProgress > 0"
            class="chip-pill chip-progress"
            :title="__('Devam Ediyor')"
          >
            🟡 {{ countProgress }} {{ __('Devam Ediyor') }}
          </span>
          <span
            v-if="countMatched > 0"
            class="chip-pill chip-matched"
            :title="__('%100 Eşleşti')"
          >
            🟢 {{ countMatched }} {{ __('%100 Eşleşti') }}
          </span>
        </div>
      </div>

      <div class="header-right">
        <button
          type="button"
          class="btn-toggle"
          :title="isOpen ? __('Daralt') : __('Genişlet')"
          @click.stop="toggleOpen"
        >
          <span class="toggle-arrow" aria-hidden="true">
            {{ isOpen ? '▲' : '▼' }}
          </span>
        </button>
      </div>
    </div>

    <!-- Mutabakat Gövdesi -->
    <div v-if="isOpen" class="recon-body">
      <!-- Filtre ve Arama Çubuğu -->
      <div class="recon-toolbar">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input
            v-model="searchQuery"
            type="text"
            class="search-input"
            :placeholder="__('Hammadde veya operasyon ara…')"
          />
          <button
            v-if="searchQuery"
            type="button"
            class="btn-clear-search"
            @click="searchQuery = ''"
          >
            ✕
          </button>
        </div>

        <div class="filter-pills">
          <button
            type="button"
            class="filter-pill"
            :class="{ active: activeFilter === 'all' }"
            @click="activeFilter = 'all'"
          >
            {{ __('Tümü') }} ({{ items.length }})
          </button>
          <button
            type="button"
            class="filter-pill pill-over"
            :class="{ active: activeFilter === 'over' }"
            @click="activeFilter = 'over'"
          >
            {{ __('Plan Aşımı') }} ({{ countOver }})
          </button>
          <button
            type="button"
            class="filter-pill pill-progress"
            :class="{ active: activeFilter === 'progress' }"
            @click="activeFilter = 'progress'"
          >
            {{ __('Devam Ediyor') }} ({{ countProgress }})
          </button>
          <button
            type="button"
            class="filter-pill pill-matched"
            :class="{ active: activeFilter === 'matched' }"
            @click="activeFilter = 'matched'"
          >
            {{ __('%100 Eşleşti') }} ({{ countMatched }})
          </button>
          <button
            type="button"
            class="filter-pill pill-none"
            :class="{ active: activeFilter === 'none' }"
            @click="activeFilter = 'none'"
          >
            {{ __('Tüketim Yok') }} ({{ countNone }})
          </button>
        </div>
      </div>

      <!-- Mutabakat Tablosu -->
      <div v-if="filteredItems.length > 0" class="table-container">
        <table class="reconciliation-table">
          <thead>
            <tr>
              <th class="th-item">{{ __('Hammadde Kodu ve Adı') }}</th>
              <th class="th-op text-center">{{ __('Operasyon') }}</th>
              <th class="th-uom text-center">{{ __('Birim') }}</th>
              <th class="th-qty text-right">{{ __('Planlanan (BOM)') }}</th>
              <th class="th-qty text-right">{{ __('Kartlardan Tüketilen') }}</th>
              <th class="th-qty text-right">{{ __('Hurda / Fire') }}</th>
              <th class="th-qty text-right">{{ __('Toplam Harcanan') }}</th>
              <th class="th-qty text-right">{{ __('Sapma / Fark') }}</th>
              <th class="th-status text-center">{{ __('Durum') }}</th>
              <th class="th-operators text-center">{{ __('Operatörler') }}</th>
            </tr>
          </thead>
          <tbody>
            <template
              v-for="item in filteredItems"
              :key="getItemKey(item)"
            >
              <tr
                class="recon-row"
                :class="{ 'row-expanded': isItemExpanded(item) }"
              >
                <td class="td-item">
                  <div
                    class="item-cell"
                    :title="item.item_name || item.item_code"
                  >
                    <span class="item-code-text">{{ item.item_code }}</span>
                    <span
                      v-if="item.item_name"
                      class="item-name-text"
                      :title="item.item_name"
                    >
                      {{ item.item_name }}
                    </span>
                  </div>
                </td>
                <td
                  class="td-op"
                  :title="item.operation ? __(item.operation) : undefined"
                >
                  <span
                    v-if="item.operation"
                    class="op-tag"
                    :title="__(item.operation)"
                  >
                    {{ item.operation.slice(0, 4) }}
                  </span>
                  <span v-else class="text-muted">—</span>
                </td>
                <td class="td-uom text-center">
                  <span class="uom-pill">{{ item.stock_uom }}</span>
                </td>
                <td class="td-qty text-right font-mono">
                  {{ formatQty(item.planned_qty) }}
                </td>
                <td class="td-qty text-right font-mono">
                  {{ formatQty(item.consumed_qty) }}
                </td>
                <td
                  class="td-qty text-right font-mono"
                  :class="{ 'text-scrap': (item.scrap_qty || 0) > 0 }"
                >
                  {{ formatQty(item.scrap_qty) }}
                </td>
                <td class="td-qty text-right font-mono font-semibold">
                  {{ formatQty(item.total_spent) }}
                </td>
                <td
                  class="td-qty text-right font-mono font-semibold"
                  :class="getVarianceClass(item.variance)"
                >
                  {{ formatVariance(item.variance) }}
                </td>
                <td class="td-status text-center">
                  <span
                    class="status-badge"
                    :class="getStatusBadgeClass(item.status)"
                  >
                    {{ formatStatusBadge(item.status) }}
                  </span>
                </td>
                <td class="td-operators text-center">
                  <button
                    v-if="item.operators && item.operators.length > 0"
                    type="button"
                    class="btn-op-pill"
                    :class="{ active: isItemExpanded(item) }"
                    :aria-expanded="isItemExpanded(item)"
                    :title="
                      isItemExpanded(item)
                        ? __('Operatör Dağılımını Gizle')
                        : __('Operatör Dağılımını Göster')
                    "
                    @click.stop="toggleItemExpanded(item)"
                  >
                    <span class="pill-icon" aria-hidden="true">🧑‍🔧</span>
                    <span class="pill-label">
                      {{ item.operators.length }} {{ __('Operatör') }}
                    </span>
                    <span class="pill-arrow" aria-hidden="true">
                      {{ isItemExpanded(item) ? '▲' : '▼' }}
                    </span>
                  </button>
                  <span v-else class="text-muted">—</span>
                </td>
              </tr>

              <!-- Operatör Tüketim Dağılımı Satırı -->
              <tr
                v-if="
                  isItemExpanded(item) &&
                  item.operators &&
                  item.operators.length > 0
                "
                class="recon-breakdown-row"
              >
                <td colspan="10" class="td-breakdown">
                  <div class="op-breakdown-container">
                    <div class="op-breakdown-header">
                      <div class="op-breakdown-title-box">
                        <span class="op-breakdown-icon" aria-hidden="true">
                          🧑‍🔧
                        </span>
                        <h5 class="op-breakdown-title">
                          {{ __('Bu Malzemeyi Tüketen Operatörler') }}
                        </h5>
                        <span class="op-count-chip">
                          {{ item.operators.length }} {{ __('Operatör') }}
                        </span>
                      </div>
                      <div class="op-breakdown-meta">
                        <span class="meta-item-code font-mono">
                          {{ item.item_code }}
                        </span>
                        <span v-if="item.item_name" class="meta-item-name">
                          — {{ item.item_name }}
                        </span>
                      </div>
                    </div>

                    <div class="op-table-responsive">
                      <table class="op-detail-table">
                        <thead>
                          <tr>
                            <th class="th-op-name">
                              {{ __('Operatör Adı') }}
                            </th>
                            <th class="th-op-qty text-right">
                              {{ __('Tüketilen Miktar') }}
                            </th>
                            <th class="th-op-share">
                              {{ __('Tüketim Payı') }}
                            </th>
                            <th class="th-op-cards text-center">
                              {{ __('Kart Sayısı') }}
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr
                            v-for="op in item.operators"
                            :key="op.operator"
                            class="op-detail-row"
                          >
                            <td class="td-op-name">
                              <div class="op-name-cell">
                                <span class="op-avatar-icon" aria-hidden="true">
                                  👤
                                </span>
                                <div class="op-text-group">
                                  <span class="op-main-name font-semibold">
                                    {{ op.operator_name || op.operator }}
                                  </span>
                                  <span
                                    v-if="
                                      op.operator_name &&
                                      op.operator !== op.operator_name
                                    "
                                    class="op-code-sub font-mono"
                                  >
                                    {{ op.operator }}
                                  </span>
                                </div>
                              </div>
                            </td>
                            <td class="td-op-qty text-right font-mono font-semibold">
                              {{ formatQty(op.consumed_qty) }} {{ item.stock_uom }}
                            </td>
                            <td class="td-op-share">
                              <div class="op-share-container">
                                <div class="share-bar-track">
                                  <div
                                    class="share-bar-fill"
                                    :style="{
                                      width: `${Math.min(
                                        100,
                                        Math.max(0, op.percentage || 0)
                                      )}%`,
                                    }"
                                  ></div>
                                </div>
                                <span class="share-label font-mono">
                                  {{ op.percentage }}%
                                </span>
                              </div>
                            </td>
                            <td class="td-op-cards text-center">
                              <span class="card-count-tag">
                                📇 {{ op.card_count }} {{ __('Kart') }}
                              </span>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Filtre Sonucu Boş Durumu -->
      <div v-else class="empty-reconciliation-box">
        <span class="empty-icon" aria-hidden="true">🔍</span>
        <span class="empty-text">
          {{ __('Kriterlere uygun mutabakat kalemi bulunamadı.') }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.material-reconciliation-section {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  margin-bottom: 0.85rem;
  transition: border-color 0.15s ease;
}

[data-theme='dark'] .material-reconciliation-section {
  background: var(--ck-glass-bg, #1a202c);
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.08));
}

.recon-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1.15rem;
  background: rgba(100, 116, 139, 0.03);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  cursor: pointer;
  user-select: none;
  gap: 0.75rem;
}

[data-theme='dark'] .recon-header {
  background: rgba(255, 255, 255, 0.02);
  border-bottom-color: var(--ck-glass-border, rgba(255, 255, 255, 0.08));
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
}

.recon-icon {
  font-size: 1.15rem;
}

.recon-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-color, #0f172a);
}

.chip-total {
  font-size: 0.75rem;
  font-weight: 700;
  background: rgba(59, 130, 246, 0.1);
  color: var(--primary, #2563eb);
  padding: 0.2rem 0.55rem;
  border-radius: 9999px;
}

[data-theme='dark'] .chip-total {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.summary-chips {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.chip-pill {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.18rem 0.5rem;
  border-radius: 9999px;
  display: inline-flex;
  align-items: center;
}

.chip-over {
  background: rgba(239, 68, 68, 0.1);
  color: #b91c1c;
}

[data-theme='dark'] .chip-over {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.chip-progress {
  background: rgba(234, 179, 8, 0.15);
  color: #a16207;
}

[data-theme='dark'] .chip-progress {
  background: rgba(234, 179, 8, 0.25);
  color: #fde047;
}

.chip-matched {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

[data-theme='dark'] .chip-matched {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.header-right {
  display: flex;
  align-items: center;
}

.btn-toggle {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.35rem 0.5rem;
  color: var(--text-muted, #64748b);
  border-radius: 4px;
}

.btn-toggle:hover {
  background: rgba(100, 116, 139, 0.1);
  color: var(--text-color, #0f172a);
}

.toggle-arrow {
  font-size: 0.75rem;
}

.recon-body {
  padding: 0.85rem 1.15rem 1.15rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.recon-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 240px;
  flex: 1;
  max-width: 380px;
}

.search-icon {
  position: absolute;
  left: 0.65rem;
  font-size: 0.8rem;
  color: var(--text-muted, #94a3b8);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.4rem 1.8rem 0.4rem 2rem;
  font-size: 0.82rem;
  border-radius: 6px;
  border: 1px solid var(--border-color, #cbd5e1);
  background: var(--input-bg, #ffffff);
  color: var(--text-color, #0f172a);
  outline: none;
}

[data-theme='dark'] .search-input {
  background: rgba(0, 0, 0, 0.2);
  border-color: rgba(255, 255, 255, 0.12);
  color: #f1f5f9;
}

.search-input:focus {
  border-color: var(--primary, #3b82f6);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.btn-clear-search {
  position: absolute;
  right: 0.5rem;
  background: transparent;
  border: none;
  font-size: 0.75rem;
  color: var(--text-muted, #94a3b8);
  cursor: pointer;
  padding: 0.1rem 0.25rem;
}

.filter-pills {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.filter-pill {
  border: 1px solid var(--border-color, #cbd5e1);
  background: var(--card-bg, #ffffff);
  color: var(--text-muted, #64748b);
  font-size: 0.76rem;
  font-weight: 600;
  padding: 0.3rem 0.65rem;
  border-radius: 9999px;
  cursor: pointer;
  transition: all 0.15s ease;
}

[data-theme='dark'] .filter-pill {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.1);
  color: #94a3b8;
}

.filter-pill:hover {
  background: rgba(100, 116, 139, 0.08);
  color: var(--text-color, #0f172a);
}

.filter-pill.active {
  background: var(--primary, #2563eb);
  border-color: var(--primary, #2563eb);
  color: #ffffff;
}

[data-theme='dark'] .filter-pill.active {
  background: #3b82f6;
  border-color: #3b82f6;
  color: #ffffff;
}

.table-container {
  overflow-x: auto;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 6px;
}

[data-theme='dark'] .table-container {
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.08));
}

.reconciliation-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
  text-align: left;
}

.reconciliation-table thead {
  background: rgba(100, 116, 139, 0.06);
}

[data-theme='dark'] .reconciliation-table thead {
  background: rgba(255, 255, 255, 0.04);
}

.reconciliation-table th {
  padding: 0.45rem 0.55rem;
  font-size: 0.73rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--text-muted, #475569);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  white-space: nowrap;
}

[data-theme='dark'] .reconciliation-table th {
  color: #94a3b8;
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

.reconciliation-table td {
  padding: 0.45rem 0.55rem;
  border-bottom: 1px solid var(--border-color, #f1f5f9);
  color: var(--text-color, #0f172a);
  vertical-align: middle;
}

[data-theme='dark'] .reconciliation-table td {
  border-bottom-color: rgba(255, 255, 255, 0.04);
  color: #e2e8f0;
}

.td-item,
.th-item {
  width: 180px;
  max-width: 180px;
}

.td-op,
.th-op {
  width: 70px;
  max-width: 70px;
  text-align: center;
}

.recon-row:hover td {
  background: rgba(59, 130, 246, 0.03);
}

[data-theme='dark'] .recon-row:hover td {
  background: rgba(255, 255, 255, 0.02);
}

.item-cell {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  max-width: 100%;
  overflow: hidden;
}

.item-code-text {
  font-family: monospace;
  font-weight: 700;
  font-size: 0.82rem;
  color: var(--text-color, #0f172a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

[data-theme='dark'] .item-code-text {
  color: #f1f5f9;
}

.item-name-text {
  font-size: 0.72rem;
  color: var(--text-muted, #64748b);
  max-width: 175px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.op-tag {
  display: inline-block;
  font-size: 0.74rem;
  background: rgba(100, 116, 139, 0.08);
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  font-weight: 600;
}

.uom-pill {
  font-size: 0.72rem;
  background: rgba(100, 116, 139, 0.08);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.text-scrap {
  color: #dc2626;
  font-weight: 600;
}

[data-theme='dark'] .text-scrap {
  color: #f87171;
}

.variance-over {
  color: #dc2626;
}

[data-theme='dark'] .variance-over {
  color: #f87171;
}

.variance-under {
  color: #2563eb;
}

[data-theme='dark'] .variance-under {
  color: #60a5fa;
}

.variance-exact {
  color: #16a34a;
}

[data-theme='dark'] .variance-exact {
  color: #4ade80;
}

.status-badge {
  display: inline-block;
  padding: 0.18rem 0.55rem;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
}

.badge-status-over {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

[data-theme='dark'] .badge-status-over {
  background: rgba(239, 68, 68, 0.22);
  color: #f87171;
}

.badge-status-progress {
  background: rgba(234, 179, 8, 0.18);
  color: #a16207;
}

[data-theme='dark'] .badge-status-progress {
  background: rgba(234, 179, 8, 0.28);
  color: #fde047;
}

.badge-status-matched {
  background: rgba(34, 197, 94, 0.14);
  color: #15803d;
}

[data-theme='dark'] .badge-status-matched {
  background: rgba(34, 197, 94, 0.22);
  color: #4ade80;
}

.badge-status-none {
  background: rgba(100, 116, 139, 0.1);
  color: var(--text-muted, #64748b);
}

[data-theme='dark'] .badge-status-none {
  background: rgba(255, 255, 255, 0.06);
  color: #94a3b8;
}

.badge-status-extra {
  background: rgba(147, 51, 234, 0.12);
  color: #7e22ce;
}

[data-theme='dark'] .badge-status-extra {
  background: rgba(147, 51, 234, 0.22);
  color: #c084fc;
}

.badge-status-default {
  background: rgba(100, 116, 139, 0.1);
  color: var(--text-muted, #64748b);
}

.empty-reconciliation-box {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1.5rem;
  background: rgba(100, 116, 139, 0.04);
  border: 1px dashed var(--border-color, #cbd5e1);
  border-radius: 6px;
  color: var(--text-muted, #64748b);
  font-size: 0.82rem;
}

[data-theme='dark'] .empty-reconciliation-box {
  border-color: rgba(255, 255, 255, 0.1);
}

.text-left {
  text-align: left;
}

.text-center {
  text-align: center;
}

.text-right {
  text-align: right;
}

.font-mono {
  font-family: monospace;
}

.font-semibold {
  font-weight: 600;
}

.text-muted {
  color: var(--text-muted, #64748b);
}

/* Operatörler Butonu / Kolonu */
.td-operators {
  white-space: nowrap;
}

.btn-op-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.22rem 0.55rem;
  font-size: 0.73rem;
  font-weight: 600;
  border-radius: 9999px;
  border: 1px solid rgba(59, 130, 246, 0.25);
  background: rgba(59, 130, 246, 0.08);
  color: var(--primary, #2563eb);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-op-pill:hover {
  background: rgba(59, 130, 246, 0.16);
  border-color: rgba(59, 130, 246, 0.4);
}

.btn-op-pill.active {
  background: var(--primary, #2563eb);
  border-color: var(--primary, #2563eb);
  color: #ffffff;
}

[data-theme='dark'] .btn-op-pill {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.3);
  color: #93c5fd;
}

[data-theme='dark'] .btn-op-pill:hover {
  background: rgba(59, 130, 246, 0.25);
  border-color: rgba(59, 130, 246, 0.45);
}

[data-theme='dark'] .btn-op-pill.active {
  background: #3b82f6;
  border-color: #3b82f6;
  color: #ffffff;
}

.pill-icon {
  font-size: 0.78rem;
  line-height: 1;
}

.pill-label {
  line-height: 1.2;
}

.pill-arrow {
  font-size: 0.65rem;
  opacity: 0.85;
}

.row-expanded td {
  background: rgba(59, 130, 246, 0.04) !important;
  border-bottom-color: transparent !important;
}

[data-theme='dark'] .row-expanded td {
  background: rgba(59, 130, 246, 0.08) !important;
}

/* Operatör Kırılımı Detay Alanı */
.recon-breakdown-row {
  background: rgba(248, 250, 252, 0.7);
}

[data-theme='dark'] .recon-breakdown-row {
  background: rgba(15, 23, 42, 0.5);
}

.td-breakdown {
  padding: 0.5rem 1rem 1rem !important;
  border-bottom: 2px solid var(--border-color, #e2e8f0) !important;
}

[data-theme='dark'] .td-breakdown {
  border-bottom-color: rgba(255, 255, 255, 0.08) !important;
}

.op-breakdown-container {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}

[data-theme='dark'] .op-breakdown-container {
  background: rgba(30, 41, 59, 0.6);
  border-color: rgba(255, 255, 255, 0.08);
}

.op-breakdown-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.65rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color, #f1f5f9);
  flex-wrap: wrap;
  gap: 0.5rem;
}

[data-theme='dark'] .op-breakdown-header {
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

.op-breakdown-title-box {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.op-breakdown-icon {
  font-size: 0.95rem;
}

.op-breakdown-title {
  margin: 0;
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-color, #0f172a);
}

[data-theme='dark'] .op-breakdown-title {
  color: #f1f5f9;
}

.op-count-chip {
  font-size: 0.7rem;
  font-weight: 700;
  background: rgba(59, 130, 246, 0.1);
  color: var(--primary, #2563eb);
  padding: 0.12rem 0.45rem;
  border-radius: 9999px;
}

[data-theme='dark'] .op-count-chip {
  background: rgba(59, 130, 246, 0.2);
  color: #93c5fd;
}

.op-breakdown-meta {
  font-size: 0.74rem;
  color: var(--text-muted, #64748b);
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.meta-item-code {
  font-weight: 700;
  color: var(--text-color, #334155);
}

[data-theme='dark'] .meta-item-code {
  color: #cbd5e1;
}

.op-table-responsive {
  overflow-x: auto;
}

.op-detail-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
}

.op-detail-table th {
  padding: 0.45rem 0.65rem;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--text-muted, #64748b);
  background: rgba(100, 116, 139, 0.04);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

[data-theme='dark'] .op-detail-table th {
  background: rgba(255, 255, 255, 0.02);
  border-bottom-color: rgba(255, 255, 255, 0.06);
  color: #94a3b8;
}

.op-detail-table td {
  padding: 0.45rem 0.65rem;
  border-bottom: 1px solid var(--border-color, #f8fafc);
  color: var(--text-color, #0f172a);
  vertical-align: middle;
}

[data-theme='dark'] .op-detail-table td {
  border-bottom-color: rgba(255, 255, 255, 0.03);
  color: #e2e8f0;
}

.op-detail-row:hover td {
  background: rgba(59, 130, 246, 0.03);
}

[data-theme='dark'] .op-detail-row:hover td {
  background: rgba(255, 255, 255, 0.02);
}

.op-name-cell {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.op-avatar-icon {
  font-size: 0.85rem;
}

.op-text-group {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.op-main-name {
  color: var(--text-color, #0f172a);
}

[data-theme='dark'] .op-main-name {
  color: #f1f5f9;
}

.op-code-sub {
  font-size: 0.68rem;
  color: var(--text-muted, #94a3b8);
}

.op-share-container {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  max-width: 220px;
}

.share-bar-track {
  flex: 1;
  height: 6px;
  background: rgba(100, 116, 139, 0.15);
  border-radius: 9999px;
  overflow: hidden;
}

[data-theme='dark'] .share-bar-track {
  background: rgba(255, 255, 255, 0.1);
}

.share-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #2563eb);
  border-radius: 9999px;
  transition: width 0.3s ease;
}

[data-theme='dark'] .share-bar-fill {
  background: linear-gradient(90deg, #60a5fa, #3b82f6);
}

.share-label {
  font-size: 0.72rem;
  font-weight: 700;
  min-width: 44px;
  text-align: right;
  color: var(--text-color, #334155);
}

[data-theme='dark'] .share-label {
  color: #cbd5e1;
}

.card-count-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.15rem 0.45rem;
  background: rgba(100, 116, 139, 0.08);
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted, #475569);
}

[data-theme='dark'] .card-count-tag {
  background: rgba(255, 255, 255, 0.06);
  color: #cbd5e1;
}
</style>
