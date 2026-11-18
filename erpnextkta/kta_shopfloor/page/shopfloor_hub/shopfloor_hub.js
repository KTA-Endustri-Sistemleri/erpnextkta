// Copyright (c) 2026, KTA and Contributors
// See license.txt

frappe.pages["shopfloor_hub"].on_page_load = function (wrapper) {
  frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Shopfloor Hub"),
    single_column: true,
  });

  $(wrapper).find(".page-head").hide();

  $(wrapper)
    .find(
      ".page-body, .content.page-container.no-list-sidebar, .layout-main-section"
    )
    .css({
      width: "100%",
      "max-width": "100%",
      padding: "0",
      margin: "0",
    });

  frappe.dom.set_style(
    `
    [data-page-route="shopfloor_hub"] .page-head,
    #page-shopfloor_hub .page-head {
      display: none !important;
    }
    [data-page-route="shopfloor_hub"] .page-body,
    [data-page-route="shopfloor_hub"] .content.page-container.no-list-sidebar,
    [data-page-route="shopfloor_hub"] .layout-main-section,
    #page-shopfloor_hub .page-body,
    #page-shopfloor_hub .content.page-container.no-list-sidebar,
    #page-shopfloor_hub .layout-main-section {
      width: 100% !important;
      max-width: 100% !important;
      padding: 0 !important;
      margin: 0 !important;
    }
  `,
    "shopfloor-hub-fullwidth"
  );

  if (frappe.boot.developer_mode) {
    if (!Array.isArray(frappe.hot_update)) {
      frappe.hot_update = [];
    }
    frappe.hot_update.push(() => load_vue(wrapper));
  }

  load_vue(wrapper);
};

frappe.pages["shopfloor_hub"].on_page_show = function (wrapper) {
  $(wrapper).find(".page-head").hide();
  $(wrapper)
    .find(
      ".page-body, .content.page-container.no-list-sidebar, .layout-main-section"
    )
    .css({
      width: "100%",
      "max-width": "100%",
      padding: "0",
      margin: "0",
    });
};

// Backwards compatibility alias for kta_co11n route
frappe.pages["kta_co11n"] = frappe.pages["shopfloor_hub"];

async function load_vue(wrapper) {
  const $parent = $(wrapper).find(".layout-main-section");

  if (wrapper.__shopfloor_hub_vue_app__) {
    wrapper.__shopfloor_hub_vue_app__.unmount?.();
    wrapper.__shopfloor_hub_vue_app__ = null;
  }
  if (wrapper.__kta_co11n_vue_app__) {
    wrapper.__kta_co11n_vue_app__.unmount?.();
    wrapper.__kta_co11n_vue_app__ = null;
  }

  $parent.empty();

  try {
    await frappe.require("shopfloor-hub.bundle.js");
  } catch (_e) {
    await frappe.require("kta-co11n.bundle.js");
  }

  const setup_fn =
    frappe.ui.setup_shopfloor_hub_vue || frappe.ui.setup_kta_co11n_vue;
  if (setup_fn) {
    const vue_app = setup_fn($parent);
    wrapper.__shopfloor_hub_vue_app__ = vue_app;
  }
}
