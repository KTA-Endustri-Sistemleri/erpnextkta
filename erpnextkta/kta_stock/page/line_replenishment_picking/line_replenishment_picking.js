// Copyright (c) 2026, KTA and Contributors
// See license.txt

frappe.pages["line-replenishment-picking"].on_page_load = function (wrapper) {
  frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Line Replenishment Picking"),
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
    [data-page-route="line-replenishment-picking"] .page-head,
    [data-page-route="line_replenishment_picking"] .page-head,
    #page-line-replenishment-picking .page-head,
    #page-line_replenishment_picking .page-head {
      display: none !important;
    }
    [data-page-route="line-replenishment-picking"] .page-body,
    [data-page-route="line-replenishment-picking"] .content.page-container.no-list-sidebar,
    [data-page-route="line-replenishment-picking"] .layout-main-section,
    [data-page-route="line_replenishment_picking"] .page-body,
    [data-page-route="line_replenishment_picking"] .content.page-container.no-list-sidebar,
    [data-page-route="line_replenishment_picking"] .layout-main-section,
    #page-line-replenishment-picking .page-body,
    #page-line-replenishment-picking .content.page-container.no-list-sidebar,
    #page-line-replenishment-picking .layout-main-section,
    #page-line_replenishment_picking .page-body,
    #page-line_replenishment_picking .content.page-container.no-list-sidebar,
    #page-line_replenishment_picking .layout-main-section {
      width: 100% !important;
      max-width: 100% !important;
      padding: 0 !important;
      margin: 0 !important;
    }
  `,
    "line-replenishment-picking-fullwidth"
  );

  if (frappe.boot.developer_mode) {
    if (!Array.isArray(frappe.hot_update)) {
      frappe.hot_update = [];
    }
    frappe.hot_update.push(() => load_vue(wrapper));
  }

  load_vue(wrapper);
};

frappe.pages["line-replenishment-picking"].on_page_show = function (wrapper) {
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

// Backwards compatibility route alias
frappe.pages["line_replenishment_picking"] =
  frappe.pages["line-replenishment-picking"];

async function load_vue(wrapper) {
  const $parent = $(wrapper).find(".layout-main-section");

  if (wrapper.__line_replenishment_pda_vue_app__) {
    wrapper.__line_replenishment_pda_vue_app__.unmount?.();
    wrapper.__line_replenishment_pda_vue_app__ = null;
  }

  $parent.empty();

  await frappe.require("line-replenishment-pda.bundle.js");

  const setup_fn = frappe.ui.setup_line_replenishment_pda_vue;
  if (setup_fn) {
    const vue_app = setup_fn($parent);
    wrapper.__line_replenishment_pda_vue_app__ = vue_app;
  }
}
