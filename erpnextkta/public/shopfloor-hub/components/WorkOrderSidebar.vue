<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import type { WorkOrderSummary, WorkOrderViewMode } from '../types';

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    currentWorkOrder?: string | null;
    activeView?: WorkOrderViewMode;
  }>(),
  {
    currentWorkOrder: null,
    activeView: 'operations',
  }
);

const emit = defineEmits<{
  (e: 'select-work-order', name: string): void;
  (e: 'open-create-modal'): void;
}>();

interface FilterTab {
  value: string;
  label: string;
}

const statusFilter = ref<string>('');
const searchQuery = ref<string>('');
const workOrders = ref<WorkOrderSummary[]>([]);
const loading = ref<boolean>(false);
const error = ref<string | null>(null);

const filterTabs = computed<FilterTab[]>(() => {
  if (props.activeView === 'work_orders') {
    return [
      { value: '', label: __('Tümü') },
      { value: 'Draft', label: __('Taslak') },
      { value: 'Released', label: __('Serbest') },
    ];
  }
  return [
    { value: '', label: __('Tümü') },
    { value: 'In Process', label: __('Devam Eden') },
    { value: 'Not Started', label: __('Başlanmamış') },
  ];
});

watch(
  () => props.activeView,
  () => {
    statusFilter.value = '';
  }
);

async function fetchWorkOrders() {
  loading.value = true;
  error.value = null;
  try {
    const res = await new Promise<WorkOrderSummary[]>((resolve, reject) => {
      frappe.call({
        method: 'erpnextkta.kta_shopfloor.api.get_active_work_orders',
        args: {
          status: statusFilter.value || null,
          include_drafts: props.activeView === 'work_orders' ? 1 : 0,
          limit: 0,
        },
        quiet: true,
        callback: (r: { message?: WorkOrderSummary[] }) => resolve(r.message || []),
        error: (err: any) => reject(err),
      });
    });
    workOrders.value = Array.isArray(res) ? res : [];
  } catch (err: any) {
    console.error('get_active_work_orders error:', err);
    error.value = err?.message || __('İş Emirleri Yüklenemedi');
    workOrders.value = [];
  } finally {
    loading.value = false;
  }
}

const filteredWorkOrders = computed<WorkOrderSummary[]>(() => {
  let list = workOrders.value.filter(
    (wo) => !['Completed', 'Closed', 'Cancelled', 'Stopped'].includes(wo.status)
  );

  if (props.activeView === 'operations') {
    list = list.filter((wo) => wo.docstatus !== 0 && wo.status !== 'Draft');
    if (statusFilter.value === 'In Process') {
      list = list.filter((wo) => wo.status === 'In Process');
    } else if (statusFilter.value === 'Not Started') {
      list = list.filter((wo) => wo.status === 'Not Started');
    }
  } else {
    if (statusFilter.value === 'Draft') {
      list = list.filter((wo) => wo.docstatus === 0 || wo.status === 'Draft');
    } else if (statusFilter.value === 'Released') {
      list = list.filter(
        (wo) => wo.docstatus === 1 && ['Not Started', 'In Process'].includes(wo.status)
      );
    }
  }

  const q = (searchQuery.value || '').trim().toLowerCase();
  if (!q) return list;
  return list.filter((wo) => {
    const nameMatch = (wo.name || '').toLowerCase().includes(q);
    const itemMatch = (wo.production_item || '').toLowerCase().includes(q);
    const itemNameMatch = (wo.item_name || '').toLowerCase().includes(q);
    return nameMatch || itemMatch || itemNameMatch;
  });
});

function setStatusTab(tab: string) {
  statusFilter.value = tab;
  fetchWorkOrders();
}

function selectOrder(wo: WorkOrderSummary) {
  emit('select-work-order', wo.name);
}

function getProgressPercent(produced: number, qty: number): number {
  const t = Number(qty) || 0;
  if (t <= 0) return 0;
  return Math.min(100, Math.round(((Number(produced) || 0) / t) * 100));
}

onMounted(() => {
  fetchWorkOrders();
});

defineExpose({
  fetchWorkOrders,
});
</script>

<template>
  <aside class="wo-sidebar">
    <!-- Header -->
    <div class="sidebar-header">
      <div class="sidebar-title-group">
        <span class="sidebar-icon">📋</span>
        <div>
          <h2 class="sidebar-title">{{ activeView === 'work_orders' ? __('İş Emirleri') : __('Aktif İş Emirleri') }}</h2>
          <span class="sidebar-count">{{ __('{0} Kayıt', [filteredWorkOrders.length]) }}</span>
        </div>
      </div>
      <button
        type="button"
        class="btn-sidebar-refresh"
        :title="__('Listeyi Yenile')"
        :disabled="loading"
        @click="fetchWorkOrders"
      >
        <span :class="{ spinning: loading }">↻</span>
      </button>
    </div>

    <!-- Primary Create Action (Work Orders View Only) -->
    <div v-if="activeView === 'work_orders'" class="sidebar-create-action">
      <button
        type="button"
        class="btn-create-work-order"
        @click="emit('open-create-modal')"
      >
        + {{ __('Yeni İş Emri Aç') }}
      </button>
    </div>

    <!-- Search Box above Filter Tabs -->
    <div class="sidebar-search-box">
      <span class="search-icon">🔍</span>
      <input
        v-model="searchQuery"
        type="text"
        class="sidebar-search-input"
        :placeholder="__('İş Emri veya Ürün Ara…')"
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

    <!-- Status Tabs -->
    <div class="sidebar-tabs">
      <button
        v-for="tab in filterTabs"
        :key="tab.value"
        type="button"
        class="sidebar-tab"
        :class="{ active: statusFilter === tab.value }"
        @click="setStatusTab(tab.value)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Scrollable Cards List -->
    <div class="sidebar-body">
      <div v-if="loading && workOrders.length === 0" class="sidebar-state-box">
        <div class="sidebar-spinner" />
        <span>{{ __('Yükleniyor…') }}</span>
      </div>

      <div v-else-if="error" class="sidebar-state-box error-box">
        <span>⚠️ {{ error }}</span>
        <button type="button" class="btn-retry" @click="fetchWorkOrders">
          {{ __('Tekrar Dene') }}
        </button>
      </div>

      <div v-else-if="filteredWorkOrders.length === 0" class="sidebar-state-box">
        <span class="empty-icon">📭</span>
        <strong>{{ __('Kayıt Yok') }}</strong>
        <p>{{ __('Aramanıza veya bu statüye uygun iş emri bulunamadı.') }}</p>
      </div>

      <div v-else class="sidebar-list">
        <div
          v-for="wo in filteredWorkOrders"
          :key="wo.name"
          class="wo-sidebar-card"
          :class="{ selected: currentWorkOrder === wo.name }"
          @click="selectOrder(wo)"
        >
          <div class="wo-card-top">
            <div class="wo-name-group">
              <span class="wo-name">{{ wo.name }}</span>
              <span v-if="currentWorkOrder === wo.name" class="active-badge">
                {{ __('Seçili') }}
              </span>
            </div>
            <span
              class="status-pill"
              :class="'status-' + (wo.status || '').toLowerCase().replace(/\s+/g, '-')"
            >
              {{ __(wo.status) }}
            </span>
          </div>

          <div class="wo-card-item">
            <span class="item-code">{{ wo.production_item }}</span>
            <span
              v-if="wo.item_name && wo.item_name !== wo.production_item"
              class="item-name"
            >
              {{ wo.item_name }}
            </span>
          </div>

          <div class="wo-card-progress">
            <div class="progress-labels">
              <span><strong>{{ wo.produced_qty }}</strong> / {{ wo.qty }} {{ __('Adet') }}</span>
              <span>%{{ getProgressPercent(wo.produced_qty, wo.qty) }}</span>
            </div>
            <div class="mini-progress-track">
              <div
                class="mini-progress-bar"
                :style="{ width: getProgressPercent(wo.produced_qty, wo.qty) + '%' }"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.wo-sidebar {
  width: 350px; min-width: 350px; max-width: 350px; height: 100%;
  background: var(--card-bg, #ffffff); border-right: 1px solid var(--border-color, #e2e8f0);
  display: flex; flex-direction: column; box-sizing: border-box; font-family: inherit; color: var(--text-color, #0f172a);
}
[data-theme='dark'] .wo-sidebar {
  background: var(--ck-glass-bg, #1c2127); border-right-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12));
}
.sidebar-header {
  display: flex; align-items: center; justify-content: space-between; padding: 1.1rem 1.15rem;
  border-bottom: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc);
}
.sidebar-title-group { display: flex; align-items: center; gap: 0.6rem; }
.sidebar-icon { font-size: 1.4rem; }
.sidebar-title { margin: 0; font-size: 1.05rem; font-weight: 800; color: var(--text-color, #0f172a); }
.sidebar-count { font-size: 0.72rem; color: var(--text-muted, #64748b); font-weight: 600; }
.btn-sidebar-refresh {
  background: transparent; border: 1px solid var(--border-color, #cbd5e1); border-radius: 0.4rem;
  width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--text-muted, #475569); font-size: 1rem; transition: all 0.2s;
}
.btn-sidebar-refresh:hover:not(:disabled) { background: #e2e8f0; color: #0f172a; }
.spinning { display: inline-block; animation: spin 0.8s linear infinite; }

.sidebar-create-action {
  padding: 0.65rem 0.85rem 0.15rem;
  background: var(--bg-color, #f8fafc);
}
.btn-create-work-order {
  width: 100%;
  padding: 0.55rem 0.9rem;
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 0.45rem;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  transition: background-color 0.15s ease, box-shadow 0.15s ease;
}
.btn-create-work-order:hover {
  background: #1d4ed8;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25);
}
[data-theme='dark'] .btn-create-work-order {
  background: #3b82f6;
}
[data-theme='dark'] .btn-create-work-order:hover {
  background: #2563eb;
}

.sidebar-search-box { position: relative; padding: 0.6rem 0.85rem 0.35rem; background: var(--bg-color, #f8fafc); }
.search-icon { position: absolute; left: 1.45rem; top: 50%; transform: translateY(-50%); font-size: 0.85rem; opacity: 0.55; pointer-events: none; }
.sidebar-search-input {
  width: 100%; height: 36px; padding: 0 1.85rem 0 2rem; font-size: 0.82rem; border-radius: 0.45rem;
  border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a);
  outline: none; box-sizing: border-box; transition: border-color 0.2s, box-shadow 0.2s;
}
.sidebar-search-input:focus { border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15); }
.btn-clear-search { position: absolute; right: 1.35rem; top: 50%; transform: translateY(-50%); background: none; border: none; font-size: 0.8rem; color: #94a3b8; cursor: pointer; padding: 0.2rem; }
.btn-clear-search:hover { color: #0f172a; }

.sidebar-tabs { display: flex; gap: 0.3rem; padding: 0.4rem 0.85rem 0.65rem; border-bottom: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); }
.sidebar-tab {
  flex: 1; padding: 0.35rem 0.4rem; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.4rem; font-size: 0.72rem; font-weight: 700; color: var(--text-muted, #64748b);
  cursor: pointer; text-align: center; transition: all 0.15s; white-space: nowrap;
}
.sidebar-tab.active { background: #2563eb; color: #ffffff; border-color: #2563eb; }

.sidebar-body { flex: 1; overflow-y: auto; padding: 0.85rem; }
.sidebar-state-box {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 3rem 1rem; text-align: center; gap: 0.5rem; color: var(--text-muted, #64748b); font-size: 0.85rem;
}
.sidebar-spinner { width: 26px; height: 26px; border: 3px solid rgba(37, 99, 235, 0.2); border-radius: 50%; border-top-color: #2563eb; animation: spin 0.8s linear infinite; }
.empty-icon { font-size: 2.2rem; }
.btn-retry { padding: 0.35rem 0.75rem; background: #2563eb; color: #ffffff; border: none; border-radius: 0.4rem; font-size: 0.75rem; font-weight: 600; cursor: pointer; }

.sidebar-list { display: flex; flex-direction: column; gap: 0.65rem; }
.wo-sidebar-card {
  padding: 0.75rem 0.85rem; background: var(--card-bg, #ffffff); border: 1.5px solid var(--border-color, #e2e8f0);
  border-radius: 0.65rem; cursor: pointer; transition: all 0.15s ease-in-out; display: flex; flex-direction: column; gap: 0.45rem;
}
.wo-sidebar-card:hover { border-color: #93c5fd; transform: translateX(2px); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04); }
.wo-sidebar-card.selected { border-color: #2563eb; background: rgba(37, 99, 235, 0.05); box-shadow: 0 0 0 1px #2563eb; }

.wo-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}
.wo-name-group {
  min-width: 0;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  overflow: hidden;
}
.wo-name {
  font-weight: 800;
  font-size: 0.88rem;
  color: #2563eb;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.active-badge {
  font-size: 0.58rem;
  font-weight: 800;
  background: #2563eb;
  color: #ffffff;
  padding: 0.08rem 0.32rem;
  border-radius: 9999px;
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
}
.status-pill {
  padding: 0.12rem 0.45rem;
  border-radius: 9999px;
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
}
.status-draft { background: #fef3c7; color: #b45309; }
.status-in-process { background: #dbeafe; color: #1d4ed8; }
.status-not-started { background: #f1f5f9; color: #475569; }
.status-completed { background: #dcfce7; color: #15803d; }
[data-theme='dark'] .status-draft { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
[data-theme='dark'] .status-in-process { background: rgba(59, 130, 246, 0.2); color: #93c5fd; }
[data-theme='dark'] .status-not-started { background: rgba(148, 163, 184, 0.18); color: #cbd5e1; }
[data-theme='dark'] .status-completed { background: rgba(34, 197, 94, 0.2); color: #4ade80; }

.wo-card-item { display: flex; flex-direction: column; gap: 0.1rem; }
.item-code { font-size: 0.82rem; font-weight: 700; color: var(--text-color, #0f172a); }
.item-name { font-size: 0.74rem; color: var(--text-muted, #64748b); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.wo-card-progress { display: flex; flex-direction: column; gap: 0.2rem; margin-top: 0.15rem; }
.progress-labels { display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-muted, #64748b); }
.mini-progress-track { height: 5px; background: #e2e8f0; border-radius: 9999px; overflow: hidden; }
[data-theme='dark'] .mini-progress-track { background: rgba(255, 255, 255, 0.1); }
.mini-progress-bar { height: 100%; background: #16a34a; border-radius: 9999px; transition: width 0.3s ease; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
