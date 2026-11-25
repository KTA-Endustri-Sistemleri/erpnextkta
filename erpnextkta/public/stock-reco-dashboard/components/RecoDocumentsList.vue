<script setup lang="ts">
import type { StockRecoListRow } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  docs: StockRecoListRow[];
  selectedDocName: string | null;
  loading: boolean;
  statusFilter: string;
  search: string;
}>();

const emit = defineEmits<{
  (e: "select-doc", docName: string): void;
  (e: "update:statusFilter", value: string): void;
  (e: "update:search", value: string): void;
  (e: "refresh"): void;
}>();

const statusPills = [
  { value: "all", label: "Tümü" },
  { value: "draft", label: "Taslak" },
  { value: "submitted", label: "Onaylı" },
];

function onSearchInput(event: Event) {
  const target = event.target as HTMLInputElement | null;
  emit("update:search", target ? target.value : "");
}

function selectFilter(value: string) {
  if (props.statusFilter === value) return;
  emit("update:statusFilter", value);
}
</script>

<template>
  <aside class="rdl-card">
    <div class="rdl-head">
      <h3 class="rdl-title">📋 {{ __("Sayım Belgeleri") }}</h3>
      <button
        type="button"
        class="rdl-refresh-btn"
        :disabled="loading"
        :title="__('Belgeleri Yenile')"
        @click="emit('refresh')"
      >
        <span :class="{ spinning: loading }">🔄</span>
      </button>
    </div>

    <div class="rdl-filters">
      <div class="rdl-pills" role="tablist">
        <button
          v-for="pill in statusPills"
          :key="pill.value"
          type="button"
          class="rdl-pill"
          :class="{ active: statusFilter === pill.value }"
          @click="selectFilter(pill.value)"
        >
          {{ __(pill.label) }}
        </button>
      </div>

      <div class="rdl-search-wrap">
        <input
          type="text"
          class="rdl-search-input"
          :value="search"
          :placeholder="__('Belge No veya Depo Ara...')"
          @input="onSearchInput"
        />
        <button
          v-if="search"
          type="button"
          class="rdl-clear-btn"
          :title="__('Temizle')"
          @click="emit('update:search', '')"
        >
          ✕
        </button>
      </div>
    </div>

    <div class="rdl-list-wrap">
      <div v-if="loading && docs.length === 0" class="rdl-empty">
        <div class="rdl-spinner">⏳</div>
        <span>{{ __("Sayım belgeleri yükleniyor...") }}</span>
      </div>

      <div v-else-if="docs.length === 0" class="rdl-empty">
        <span>📭</span>
        <span>{{ __("Eşleşen sayım belgesi bulunamadı.") }}</span>
      </div>

      <button
        v-for="doc in docs"
        v-else
        :key="doc.name"
        type="button"
        class="rdl-row"
        :class="{ active: selectedDocName === doc.name }"
        @click="emit('select-doc', doc.name)"
      >
        <div class="rdl-row-top">
          <span class="rdl-doc-name">{{ doc.name }}</span>
          <span
            class="rdl-status-pill"
            :class="doc.docstatus === 0 ? 'status-draft' : 'status-submitted'"
          >
            {{ doc.docstatus === 0 ? __("Taslak") : __("Onaylı") }}
          </span>
        </div>

        <div class="rdl-row-wh">
          🏢 {{ doc.set_warehouse || __("Çoklu Depo") }}
        </div>

        <div class="rdl-row-bottom">
          <span class="rdl-date">📅 {{ doc.posting_date }}</span>
          <span class="rdl-count-badge">
            {{ doc.positive_item_count }} / {{ doc.item_count }} {{ __("Kalem") }}
          </span>
        </div>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.rdl-card { display: flex; flex-direction: column; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; overflow: hidden; box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04); height: 100%; min-height: 480px; max-height: calc(100vh - 210px); }
[data-theme="dark"] .rdl-card { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12)); }
.rdl-head { display: flex; justify-content: space-between; align-items: center; padding: 0.85rem 1rem; border-bottom: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .rdl-head { background: rgba(255, 255, 255, 0.03); }
.rdl-title { margin: 0; font-size: 0.94rem; font-weight: 800; color: var(--text-color, #0f172a); }
.rdl-refresh-btn { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #cbd5e1); border-radius: 0.4rem; padding: 0.3rem 0.5rem; cursor: pointer; font-size: 0.85rem; }
[data-theme="dark"] .rdl-refresh-btn { background: rgba(255, 255, 255, 0.06); border-color: rgba(255, 255, 255, 0.16); color: #f8fafc; }
.rdl-refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.spinning { display: inline-block; animation: rdl-spin 1s linear infinite; }
@keyframes rdl-spin { to { transform: rotate(360deg); } }
.rdl-filters { padding: 0.75rem 0.9rem; display: flex; flex-direction: column; gap: 0.6rem; border-bottom: 1px solid var(--border-color, #e2e8f0); }
.rdl-pills { display: flex; gap: 0.35rem; }
.rdl-pill { flex: 1; padding: 0.35rem 0.5rem; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--bg-color, #f8fafc); color: var(--text-muted, #64748b); font-size: 0.76rem; font-weight: 700; cursor: pointer; transition: all 0.15s; }
[data-theme="dark"] .rdl-pill { background: rgba(255, 255, 255, 0.04); border-color: rgba(255, 255, 255, 0.14); color: #94a3b8; }
.rdl-pill.active { background: #2563eb; border-color: #2563eb; color: #ffffff; }
.rdl-search-wrap { position: relative; display: flex; align-items: center; }
.rdl-search-input { width: 100%; padding: 0.42rem 1.75rem 0.42rem 0.65rem; border-radius: 0.45rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-size: 0.8rem; box-sizing: border-box; }
[data-theme="dark"] .rdl-search-input { background: #14181d; border-color: rgba(255, 255, 255, 0.16); color: #f8fafc; }
.rdl-clear-btn { position: absolute; right: 0.45rem; background: transparent; border: none; color: var(--text-muted, #64748b); cursor: pointer; font-size: 0.8rem; }
.rdl-list-wrap { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }
.rdl-empty { padding: 2.5rem 1rem; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 0.4rem; font-size: 0.82rem; color: var(--text-muted, #64748b); }
.rdl-spinner { font-size: 1.5rem; }
.rdl-row { width: 100%; text-align: left; background: transparent; border: none; border-bottom: 1px solid var(--border-color, #e2e8f0); padding: 0.75rem 0.95rem; cursor: pointer; display: flex; flex-direction: column; gap: 0.3rem; transition: background-color 0.15s; color: inherit; }
.rdl-row:hover { background: rgba(37, 99, 235, 0.05); }
.rdl-row.active { background: rgba(37, 99, 235, 0.1); border-left: 3px solid #2563eb; padding-left: calc(0.95rem - 3px); }
.rdl-row-top { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
.rdl-doc-name { font-family: monospace; font-size: 0.84rem; font-weight: 800; color: var(--text-color, #0f172a); }
.rdl-status-pill { padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 700; white-space: nowrap; }
.status-draft { background: #fef3c7; color: #b45309; border: 1px solid #fde68a; }
.status-submitted { background: #dcfce7; color: #15803d; border: 1px solid #86efac; }
[data-theme="dark"] .status-draft { background: rgba(245, 158, 11, 0.2); border-color: rgba(251, 191, 36, 0.35); color: #fcd34d; }
[data-theme="dark"] .status-submitted { background: rgba(34, 197, 94, 0.2); border-color: rgba(74, 222, 128, 0.35); color: #86efac; }
.rdl-row-wh { font-size: 0.78rem; color: var(--text-muted, #475569); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rdl-row-bottom { display: flex; justify-content: space-between; align-items: center; font-size: 0.73rem; color: var(--text-muted, #64748b); }
.rdl-count-badge { font-weight: 700; background: var(--bg-color, #f1f5f9); padding: 0.1rem 0.45rem; border-radius: 0.35rem; }
[data-theme="dark"] .rdl-count-badge { background: rgba(255, 255, 255, 0.08); }
</style>
