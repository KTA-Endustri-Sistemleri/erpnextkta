/* English comments as requested */

frappe.pages["view-calisma-karti"].on_page_load = async function (wrapper) {
  frappe.ui.make_app_page({
    parent: wrapper,
    title: "Çalışma Kartı",
    single_column: true
  });

  // Developer mode hot reload support
  if (frappe.boot.developer_mode) {
    if (!Array.isArray(frappe.hot_update)) {
      frappe.hot_update = [];
    }
    frappe.hot_update.push(() => load_vue(wrapper));
  }

  const $root = $(`<div id="app"></div>`);
  $(wrapper).find(".layout-main-section").append($root);

  await frappe.require("view-calisma-karti.bundle.js");
  if (frappe?.ui?.setup_vue) {
    frappe.ui.setup_vue($root);
  }
};
