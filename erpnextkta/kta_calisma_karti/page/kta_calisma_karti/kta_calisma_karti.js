frappe.pages['kta_calisma_karti'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'Test Vue',
    single_column: true,
  });

  // hot reload when in developer mode
  if (frappe.boot.developer_mode) {
    frappe.hot_update ??= frappe.hot_update;
    frappe.hot_update.push(() => load_vue(wrapper));
  }
};
frappe.pages['kta_calisma_karti'].on_page_show = (wrapper) => load_vue(wrapper);

// Simple callback function to load Vue in the page
async function load_vue(wrapper) {
  const $parent = $(wrapper).find('.layout-main-section');
  $parent.empty();

  // Require the bundle and mount the Vue app
  await frappe.require('kta_calisma_karti.bundle.js');
  frappe.test_vue_app = frappe.ui.setup_vue($parent);
}