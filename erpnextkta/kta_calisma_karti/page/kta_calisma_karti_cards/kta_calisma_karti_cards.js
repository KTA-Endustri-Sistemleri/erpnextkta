/* English comments as requested */

frappe.pages["kta-calisma-karti-cards"].on_page_load = async function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Çalışma Kartlarım"),
    single_column: true
  });

  const $root = $(`<div id="app"></div>`);
  $(wrapper).find(".layout-main-section").append($root);

  await frappe.require("kta-calisma-karti-cards.bundle.js");
  if (frappe?.ui?.setup_vue) {
    frappe.ui.setup_vue($root);
  }
};
