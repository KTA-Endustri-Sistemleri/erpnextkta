frappe.pages["stock-requirements-list"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Stok İhtiyaç Listesi (MD04)"),
		single_column: true,
	});

	if (frappe.boot.developer_mode) {
		if (!Array.isArray(frappe.hot_update)) {
			frappe.hot_update = [];
		}
		frappe.hot_update.push(() => load_vue(wrapper));
	}

	load_vue(wrapper);
};

frappe.pages["stock-requirements-list"].on_page_show = function (_wrapper) {
	// keep empty — do not remount on show
};

async function load_vue(wrapper) {
	const $parent = $(wrapper).find(".layout-main-section");

	if (wrapper.__srl_vue_app__) {
		wrapper.__srl_vue_app__.unmount?.();
		wrapper.__srl_vue_app__ = null;
	}

	$parent.empty();

	await frappe.require("stock-requirements-list.bundle.js");

	const vue_app = frappe.ui.setup_stock_requirements_list_vue($parent);
	wrapper.__srl_vue_app__ = vue_app;
}
