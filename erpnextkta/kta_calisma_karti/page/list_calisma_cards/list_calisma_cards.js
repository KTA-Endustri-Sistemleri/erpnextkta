/* English comments as requested */

frappe.pages["list-calisma-cards"].on_page_load = async function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Çalışma Kartlarım",
    single_column: true
  });

  $(wrapper)
    .find(".page-content .row.layout-main .col-md-12.layout-main-section-wrapper")
    .addClass("p-0");

  // Developer mode hot reload support
  if (frappe.boot.developer_mode) {
    if (!Array.isArray(frappe.hot_update)) {
      frappe.hot_update = [];
    }
    frappe.hot_update.push(() => load_vue(wrapper));
  }

  const $root = $(`<div id="app"></div>`);
  $(wrapper).find(".layout-main-section").append($root);

  await frappe.require("list-calisma-cards.bundle.js");
  if (frappe?.ui?.setup_vue) {
    frappe.ui.setup_vue($root);
  }
};
