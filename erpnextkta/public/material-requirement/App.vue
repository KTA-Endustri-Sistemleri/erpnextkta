<template>
  <div class="mrp-app-container">
    <!-- Unified Control Bar (Search, Status Chips, Horizon Tag, Popover Filters, Sort, Exports) -->
    <MrpToolbar />

    <!-- Matrix Table (Frozen Left Identity + Horizontal Weekly Timeline + Accordions) -->
    <MrpMatrixTable />

    <!-- Non-Modal Slide-over Right Detail Drawer -->
    <MrpDetailDrawer />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from "vue";
import { useMrpState } from "./composables/useMrpState";
import MrpToolbar from "./components/MrpToolbar.vue";
import MrpMatrixTable from "./components/matrix/MrpMatrixTable.vue";
import MrpDetailDrawer from "./components/drawer/MrpDetailDrawer.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const { initMrpSettings, fetchMrpData } = useMrpState();

const updateFrappeNavbarHeight = () => {
  if (typeof window === "undefined") return;
  const navbar = document.querySelector(".navbar");
  if (navbar) {
    const navH = navbar.getBoundingClientRect().height;
    if (navH > 0) {
      document.documentElement.style.setProperty("--navbar-height", `${Math.round(navH)}px`);
    }
  }
};

onMounted(async () => {
  updateFrappeNavbarHeight();
  window.addEventListener("resize", updateFrappeNavbarHeight);
  await initMrpSettings();
  fetchMrpData();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", updateFrappeNavbarHeight);
});
</script>

<style>
/* Page-Head'i tamamen yok et */
[data-page-route="material-requirement"] .page-head {
  display: none !important;
}

[data-page-route="material-requirement"] .page-toolbar:empty {
  display: none !important;
}

/* 1. Geniş Ekran Sağ Boşluk Giderme: Tüm Ata Taşıyıcıları %100 Genişliğe Açma */
[data-page-route="material-requirement"],
[data-page-route="material-requirement"] .container,
[data-page-route="material-requirement"] .container-fluid,
[data-page-route="material-requirement"] .page-body,
[data-page-route="material-requirement"] .page-body.container,
[data-page-route="material-requirement"] .page-wrapper,
[data-page-route="material-requirement"] .page-content,
[data-page-route="material-requirement"] .layout-main,
[data-page-route="material-requirement"] .layout-main-section-wrapper,
[data-page-route="material-requirement"] .layout-main-section,
#mrp-app-root {
  max-width: 100% !important;
  width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
  box-shadow: none !important;
  border: none !important;
  border-radius: 0 !important;
  background: transparent !important;
}

/* 2. Dikey Flex Zinciri ve Scrollbar'ların Ekrana Oturtulması */
body:has([data-page-route="material-requirement"]),
[data-page-route="material-requirement"],
[data-page-route="material-requirement"] .page-container,
[data-page-route="material-requirement"] .page-body,
[data-page-route="material-requirement"] .page-wrapper,
[data-page-route="material-requirement"] .page-content,
[data-page-route="material-requirement"] .layout-main {
  overflow: hidden !important;
  height: calc(100vh - var(--navbar-height, 48px)) !important;
  max-height: calc(100vh - var(--navbar-height, 48px)) !important;
}

[data-page-route="material-requirement"] .layout-main-section-wrapper,
[data-page-route="material-requirement"] .layout-main-section,
#mrp-app-root {
  display: flex !important;
  flex-direction: column !important;
  flex: 1 1 0% !important;
  min-height: 0 !important;
  height: 100% !important;
  max-height: 100% !important;
  overflow: hidden !important;
}

/* Semantic Light & Dark Theme CSS Variables */
:root,
[data-theme="light"] {
  --mrp-bg: var(--bg-color, #f0f2f5);
  --mrp-card-bg: var(--card-bg, #ffffff);
  --mrp-card-subtle: var(--control-bg, #f3f3f3);
  --mrp-text: var(--text-color, #171717);
  --mrp-text-muted: var(--text-muted, #7c7c7c);
  --mrp-border: var(--border-color, #ededed);
  --mrp-border-subtle: var(--border-color, #f3f3f3);
  --mrp-header-bg: #f8fafc;
  --mrp-current-week-header-bg: #eef2ff;
  --mrp-row-hover-bg: #f8faff;
  --mrp-cell-hover: rgba(99, 102, 241, 0.06);
  --mrp-cell-selected: rgba(99, 102, 241, 0.15);
  --mrp-table-zebra: rgba(255, 255, 255, 0.6);
  --mrp-glass-bg: rgba(255, 255, 255, 0.82);
  --mrp-glass-blur: blur(8px);
  --mrp-shadow: var(--card-shadow, 0 1px 3px rgba(0, 0, 0, 0.08));
}

[data-theme="dark"],
body.dark,
html.dark {
  --mrp-bg: var(--bg-color, #0c111b);
  --mrp-card-bg: var(--card-bg, #171717);
  --mrp-card-subtle: var(--control-bg, #232323);
  --mrp-text: var(--text-color, #f8f8f8);
  --mrp-text-muted: var(--text-muted, #c7c7c7);
  --mrp-border: var(--border-color, #282828);
  --mrp-border-subtle: var(--border-color, #1f1f1f);
  --mrp-header-bg: #1c1c1c;
  --mrp-current-week-header-bg: #1c1d32;
  --mrp-row-hover-bg: #212332;
  --mrp-cell-hover: rgba(129, 140, 248, 0.1);
  --mrp-cell-selected: rgba(129, 140, 248, 0.25);
  --mrp-table-zebra: rgba(255, 255, 255, 0.5);
  --mrp-glass-bg: rgba(23, 23, 23, 0.85);
  --mrp-glass-blur: blur(10px);
  --mrp-shadow: var(--card-shadow, 0 4px 6px -1px rgba(0, 0, 0, 0.4));
}

/* Viewport App Container */
.mrp-app-container {
  height: 100% !important;
  max-height: 100% !important;
  display: flex !important;
  flex-direction: column !important;
  flex: 1 1 0% !important;
  min-height: 0 !important;
  overflow: hidden !important;
  padding: 8px 12px !important;
  box-sizing: border-box !important;
  font-family: inherit;
  color: var(--mrp-text);
  background: var(--mrp-bg);
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
  .mrp-filter-popover,
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
