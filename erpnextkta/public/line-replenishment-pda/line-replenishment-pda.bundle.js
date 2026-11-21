// Copyright (c) 2026, KTA and Contributors
// See license.txt

import { createApp } from "vue";
import PdaApp from "./PdaApp.vue";

function setup_line_replenishment_pda_vue($parent) {
  const mountEl = $parent && $parent.get ? $parent.get(0) : $parent;
  const app = createApp(PdaApp);
  app.mount(mountEl);
  return app;
}

if (typeof window !== "undefined") {
  window.frappe = window.frappe || {};
  window.frappe.ui = window.frappe.ui || {};
  window.frappe.ui.setup_line_replenishment_pda_vue =
    setup_line_replenishment_pda_vue;
}

export default setup_line_replenishment_pda_vue;
