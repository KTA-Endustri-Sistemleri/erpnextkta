// Copyright (c) 2026, KTA and Contributors
// See license.txt

import { createApp } from 'vue';
import App from './App.vue';

function setup_shopfloor_hub_vue($wrapper) {
  const app = createApp(App);
  app.mount($wrapper.get(0));
  return app;
}

if (typeof window !== 'undefined') {
  window.frappe = window.frappe || {};
  window.frappe.ui = window.frappe.ui || {};
  window.frappe.ui.setup_shopfloor_hub_vue = setup_shopfloor_hub_vue;
  window.frappe.ui.setup_kta_co11n_vue = setup_shopfloor_hub_vue; // Geriye dönük uyumluluk
}

export default setup_shopfloor_hub_vue;
