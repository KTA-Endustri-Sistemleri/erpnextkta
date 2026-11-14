<template>
  <div class="mrp-app-container">
    <!-- Top Filter Bar -->
    <MrpFilterBar />

    <!-- In-memory Toolbar (Search, Quick Status Chips, Action Views, Exports) -->
    <MrpToolbar />

    <!-- Matrix Table (Frozen Left Identity + Horizontal Weekly Timeline + Accordions) -->
    <MrpMatrixTable />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useMrpState } from "./composables/useMrpState";
import MrpFilterBar from "./components/MrpFilterBar.vue";
import MrpToolbar from "./components/MrpToolbar.vue";
import MrpMatrixTable from "./components/matrix/MrpMatrixTable.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const { initMrpSettings, fetchMrpData } = useMrpState();

onMounted(async () => {
  await initMrpSettings();
  fetchMrpData();
});
</script>

<style>
/* Global App & Print Styles */
.mrp-app-container {
  padding-bottom: 10px;
  font-family: inherit;
  color: var(--text-color, #1e293b);
  background: var(--bg-color, #f8fafc);
  min-height: 100vh;
}

@media print {
  /* Print Optimization: Landscape, hide toolbar/filters, keep clean table */
  @page {
    size: landscape;
    margin: 10mm;
  }

  body {
    background: #ffffff !important;
  }

  .page-head,
  .mrp-filter-card,
  .mrp-toolbar,
  .mrp-chevron-btn,
  .mrp-modal-backdrop {
    display: none !important;
  }

  .mrp-app-container {
    padding: 0 !important;
    background: #ffffff !important;
  }

  .mrp-table-viewport {
    max-height: none !important;
    overflow: visible !important;
  }

  .mrp-th-fixed,
  .mrp-td-fixed {
    position: static !important;
    box-shadow: none !important;
  }

  .mrp-table th {
    background: #f1f5f9 !important;
    color: #000000 !important;
  }
}
</style>
