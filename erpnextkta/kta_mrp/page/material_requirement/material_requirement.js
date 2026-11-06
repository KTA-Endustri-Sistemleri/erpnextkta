frappe.pages["material-requirement"].on_page_load = async function (wrapper) {
  frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Hammadde İhtiyaç Planlama"),
    single_column: true
  });

  if (frappe.boot.developer_mode) {
    if (!Array.isArray(frappe.hot_update)) {
      frappe.hot_update = [];
    }
    frappe.hot_update.push(() => load_vue(wrapper));
  }

  load_vue(wrapper);
};

frappe.pages["material-requirement"].on_page_show = function (_wrapper) {
  // Keep empty to avoid remounting on page switch
};

async function load_vue(wrapper) {
  const $parent = $(wrapper).find(".layout-main-section");
  if (wrapper.__mrp_vue_app__) {
    wrapper.__mrp_vue_app__.unmount?.();
    wrapper.__mrp_vue_app__ = null;
  }
  $parent.empty();
  const $root = $('<div id="mrp-app-root"></div>').css({ width: "100%" });
  $parent.append($root);

  await frappe.require("material-requirement.bundle.js");
  if (frappe?.ui?.setup_mrp_vue) {
    wrapper.__mrp_vue_app__ = frappe.ui.setup_mrp_vue($root);
  }
}
