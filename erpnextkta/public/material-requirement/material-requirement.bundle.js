import { createApp } from 'vue';
import MrpAppVue from './App.vue';

function setup_mrp_vue(wrapper) {
  const app = createApp(MrpAppVue);
  app.config.globalProperties.__ = window.__ || ((s) => s);
  app.mount(wrapper.get ? wrapper.get(0) : wrapper);
  return app;
}

frappe.ui.setup_mrp_vue = setup_mrp_vue;
export default setup_mrp_vue;
