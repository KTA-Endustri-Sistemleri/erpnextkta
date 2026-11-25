import { vi, beforeEach } from "vitest";

beforeEach(() => {
  window.csrf_token = "test-csrf-token";
  window.__KTA_PDA_BOOT__ = undefined;
  window.frappe = {
    boot: { __messages: {} },
    _messages: {},
    dom: {
      set_style: vi.fn(),
    },
  };
  window.__ = (txt, replace) => {
    let out = String(txt ?? "");
    if (Array.isArray(replace)) {
      replace.forEach((val, idx) => {
        out = out.replace(new RegExp(`\\{${idx}\\}`, "g"), String(val ?? ""));
      });
    }
    return out;
  };
  vi.restoreAllMocks();
});
