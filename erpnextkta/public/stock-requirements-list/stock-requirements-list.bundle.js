import { createApp } from "vue";
import VueApp from "./App.vue";

function setup_stock_requirements_list_vue($wrapper) {
	const app = createApp(VueApp);
	app.mount($wrapper.get(0));
	return app;
}

frappe.ui.setup_stock_requirements_list_vue = setup_stock_requirements_list_vue;

export default setup_stock_requirements_list_vue;
