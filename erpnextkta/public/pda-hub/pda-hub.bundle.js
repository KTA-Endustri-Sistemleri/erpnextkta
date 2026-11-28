// Copyright (c) 2026, KTA and Contributors
// See license.txt

import { createApp } from "vue";
import PdaHubApp from "./PdaHubApp.vue";
import { initFrappeShim } from "./utils/frappeShim";

initFrappeShim();

export function mountPdaHub(targetSelector = "#pda-app") {
  const el =
    typeof targetSelector === "string"
      ? document.querySelector(targetSelector)
      : targetSelector;
  if (!el) return null;
  const app = createApp(PdaHubApp);
  app.mount(el);
  return app;
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      mountPdaHub("#pda-app");
    });
  } else {
    mountPdaHub("#pda-app");
  }
}
