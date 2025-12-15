import { createApp } from "vue";
import VueApp from "./App.vue";

function setup_stock_reco_dashboard_vue($wrapper) {
  const app = createApp(VueApp);
  app.mount($wrapper.get(0));
  return app;
}

// Do NOT override frappe.ui.setup_vue globally
frappe.ui.setup_stock_reco_dashboard_vue = setup_stock_reco_dashboard_vue;

export default setup_stock_reco_dashboard_vue;
