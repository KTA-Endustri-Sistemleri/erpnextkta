/* English comments as requested */

frappe.pages["stock-reco-dashboard"].on_page_load = function (wrapper) {
  frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Stock Reconciliation Dashboard"),
    single_column: true,
  });

  // Developer mode hot reload support
  if (frappe.boot.developer_mode) {
    if (!Array.isArray(frappe.hot_update)) {
      frappe.hot_update = [];
    }
    frappe.hot_update.push(() => load_vue(wrapper));
  }

  load_vue(wrapper);
};

// Do NOT remount on show
frappe.pages["stock-reco-dashboard"].on_page_show = function (_wrapper) {
  // keep empty
};

async function load_vue(wrapper) {
  const $parent = $(wrapper).find(".layout-main-section");

  // Unmount previous Vue app if any
  if (wrapper.__sr_dashboard_vue_app__) {
    wrapper.__sr_dashboard_vue_app__.unmount?.();
    wrapper.__sr_dashboard_vue_app__ = null;
  }

  // Clear DOM
  $parent.empty();

  // Load bundle
  await frappe.require("stock-reco-dashboard.bundle.js");

  // Mount via your injected setup
  const vue_app = frappe.ui.setup_stock_reco_dashboard_vue($parent);
  wrapper.__sr_dashboard_vue_app__ = vue_app;
}