/* English comments as requested */

function _extract_and_clear_route_options() {
  const raw = frappe.route_options;
  if (!raw || typeof raw !== "object") {
    return null;
  }

  const doc = raw.doc || null;
  const tab = raw.tab || null;

  delete raw.doc;
  delete raw.tab;
  if (!Object.keys(raw).length) {
    frappe.route_options = null;
  }

  if (!doc && !tab) {
    return null;
  }
  return { doc, tab };
}

frappe.pages["stock-reco-dashboard"].on_page_load = function (wrapper) {
  frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Stok Uzlaştırma Panosu"),
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

// Dispatch route_options updates when navigating back to an already-mounted page
frappe.pages["stock-reco-dashboard"].on_page_show = function (_wrapper) {
  const routeOpts = _extract_and_clear_route_options();
  if (routeOpts) {
    window.dispatchEvent(
      new CustomEvent("kta-stock-reco-route", { detail: routeOpts })
    );
  }
};

async function load_vue(wrapper) {
  const $parent = $(wrapper).find(".layout-main-section");
  const routeOpts = _extract_and_clear_route_options();

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
  const vue_app = frappe.ui.setup_stock_reco_dashboard_vue(
    $parent,
    routeOpts
  );
  wrapper.__sr_dashboard_vue_app__ = vue_app;
}
