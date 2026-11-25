import { reactive } from "vue";

export interface PdaToastAlert {
  id: number;
  message: string;
  indicator: string;
}

export interface PdaMsgprintState {
  show: boolean;
  title: string;
  message: string;
  indicator: string;
}

export interface PdaConfirmState {
  show: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel?: () => void;
}

export const overlayState = reactive<{
  freezing: boolean;
  freezeMessage: string;
  alerts: PdaToastAlert[];
  msgprint: PdaMsgprintState | null;
  confirm: PdaConfirmState | null;
}>({
  freezing: false,
  freezeMessage: "",
  alerts: [],
  msgprint: null,
  confirm: null,
});

export const runtimeLocaleState = reactive<{
  lang: string;
  messages: Record<string, string>;
}>({
  lang: "tr",
  messages: {},
});

let nextAlertId = 1;
let activeFreezeCount = 0;
let authExpiredCallback: (() => void) | undefined;

export function updateCsrfToken(token: string): void {
  if (typeof window !== "undefined") {
    window.csrf_token = token;
  }
}

export function setRuntimeTranslations(
  lang: string,
  messages?: Record<string, string>,
): void {
  const cleanLang = String(lang || "tr").trim() || "tr";
  const nextDict: Record<string, string> = { ...(messages || {}) };
  runtimeLocaleState.lang = cleanLang;
  runtimeLocaleState.messages = nextDict;
  if (typeof document !== "undefined") {
    document.documentElement.lang = cleanLang;
  }
  if (typeof window !== "undefined") {
    window.frappe = window.frappe || {};
    window.frappe._messages = nextDict;
    window.frappe.boot = window.frappe.boot || {};
    window.frappe.boot.__messages = nextDict;
  }
}

export function translate(txt: string, replace?: any[]): string {
  void runtimeLocaleState.lang;
  const win = typeof window !== "undefined" ? (window as any) : {};
  const raw =
    runtimeLocaleState.messages[txt] ??
    win.frappe?._messages?.[txt] ??
    win.frappe?.boot?.__messages?.[txt] ??
    txt;
  let msg = String(raw ?? "");
  if (Array.isArray(replace)) {
    replace.forEach((val, idx) => {
      msg = msg.replace(new RegExp(`\\{${idx}\\}`, "g"), String(val ?? ""));
    });
  }
  return msg;
}

function stripHtml(raw: string): string {
  return raw.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

export function parseFrappeError(payload: any, fallback: string): string {
  if (!payload) return fallback;
  if (typeof payload === "string") return stripHtml(payload) || fallback;

  if (payload._server_messages) {
    try {
      const parsed = JSON.parse(payload._server_messages);
      if (Array.isArray(parsed) && parsed.length > 0) {
        const msgs = parsed
          .map((item: any) => {
            if (typeof item === "string") {
              try {
                const inner = JSON.parse(item);
                return stripHtml(String(inner?.message || item));
              } catch {
                return stripHtml(item);
              }
            }
            return stripHtml(String(item?.message || item));
          })
          .filter(Boolean);
        if (msgs.length > 0) return msgs.join(" ");
      }
    } catch {
      /* ignore parse errors and try fallback fields */
    }
  }

  if (payload.message && typeof payload.message === "string") {
    return stripHtml(payload.message) || fallback;
  }
  if (payload.exc_type && payload.exception) {
    return stripHtml(String(payload.exception)) || fallback;
  }
  return fallback;
}

function showMsgprint(opts: string | Record<string, any>): void {
  if (typeof opts === "string") {
    overlayState.msgprint = {
      show: true,
      title: translate("Bilgi"),
      message: stripHtml(opts),
      indicator: "blue",
    };
    return;
  }
  overlayState.msgprint = {
    show: true,
    title: String(opts.title || translate("Bilgi")),
    message: stripHtml(String(opts.message || "")),
    indicator: String(opts.indicator || "blue"),
  };
}

function showAlert(
  opts: string | { message: string; indicator?: string },
  seconds = 5
): void {
  const message =
    typeof opts === "string" ? opts : String(opts?.message || "");
  const indicator =
    typeof opts === "string" ? "blue" : String(opts?.indicator || "blue");
  const id = nextAlertId++;
  overlayState.alerts.push({ id, message: stripHtml(message), indicator });
  setTimeout(() => {
    const idx = overlayState.alerts.findIndex((a) => a.id === id);
    if (idx !== -1) overlayState.alerts.splice(idx, 1);
  }, Math.max(1000, seconds * 1000));
}

function showConfirm(
  message: string,
  onConfirm: () => void,
  onCancel?: () => void
): void {
  overlayState.confirm = {
    show: true,
    title: translate("Onay"),
    message: stripHtml(message),
    onConfirm,
    onCancel,
  };
}

function escapeHtml(str: string): string {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function buildGetUrl(baseUrl: string, args: Record<string, any>): string {
  const params = new URLSearchParams();
  Object.entries(args || {}).forEach(([k, v]) => {
    if (v === null || v === undefined) return;
    params.append(k, typeof v === "object" ? JSON.stringify(v) : String(v));
  });
  const qs = params.toString();
  return qs ? `${baseUrl}?${qs}` : baseUrl;
}

async function frappeCall(opts: Record<string, any>): Promise<any> {
  const httpMethod = String(opts?.type || "POST").toUpperCase();
  const baseUrl = `/api/method/${opts.method}`;
  const args = opts?.args || {};
  const url = httpMethod === "GET" ? buildGetUrl(baseUrl, args) : baseUrl;

  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Frappe-CSRF-Token":
      (typeof window !== "undefined" && window.csrf_token) || "",
  };
  const fetchInit: RequestInit = {
    method: httpMethod,
    credentials: "same-origin",
    headers,
  };
  if (httpMethod !== "GET") {
    headers["Content-Type"] = "application/json";
    fetchInit.body = JSON.stringify(args);
  }

  if (opts?.freeze) {
    activeFreezeCount += 1;
    overlayState.freezing = true;
    overlayState.freezeMessage =
      opts.freeze_message || translate("İşlem yapılıyor...");
  }

  try {
    const response = await fetch(url, fetchInit);
    let data: any = null;
    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (response.status === 401 || response.status === 403) {
      authExpiredCallback?.();
    }

    if (!response.ok || data?.exc || data?.exc_type) {
      const msg = parseFrappeError(
        data,
        translate("Sunucu isteği sırasında bir hata oluştu.")
      );
      const err: any = new Error(msg);
      err.status = response.status;
      err._server_messages = data?._server_messages;
      err.response = data;
      opts?.error?.(err);
      if (!opts?.error && !opts?.quiet) {
        showMsgprint({ title: translate("Hata"), message: msg, indicator: "red" });
      }
      throw err;
    }

    opts?.callback?.(data);
    return data;
  } catch (err: any) {
    if (!err?.status && !err?.response) {
      const msg = err?.message || translate("Bağlantı hatası oluştu.");
      opts?.error?.(err);
      if (!opts?.error && !opts?.quiet) {
        showMsgprint({ title: translate("Hata"), message: msg, indicator: "red" });
      }
    }
    throw err;
  } finally {
    if (opts?.freeze) {
      activeFreezeCount = Math.max(0, activeFreezeCount - 1);
      if (activeFreezeCount === 0) {
        overlayState.freezing = false;
        overlayState.freezeMessage = "";
      }
    }
  }
}

export function initFrappeShim(options?: { onAuthExpired?: () => void }): void {
  authExpiredCallback = options?.onAuthExpired;
  if (typeof window === "undefined") return;

  window.__ = translate;
  const existing = window.frappe || {};
  const initialLang =
    String(
      existing.boot?.lang ||
        (typeof document !== "undefined" && document.documentElement.lang) ||
        "tr",
    ).trim() || "tr";
  const initialMessages = {
    ...(existing.boot?.__messages || {}),
    ...(existing._messages || {}),
  };
  runtimeLocaleState.lang = initialLang;
  runtimeLocaleState.messages = initialMessages;

  window.frappe = {
    ...existing,
    boot: { ...(existing.boot || {}), __messages: runtimeLocaleState.messages },
    _messages: runtimeLocaleState.messages,
    call: frappeCall,
    msgprint: showMsgprint,
    show_alert: showAlert,
    confirm: showConfirm,
    utils: { ...(existing.utils || {}), escape_html: escapeHtml },
    dom: existing.dom || {
      set_style(css: string) {
        if (!css) return null;
        const s = document.createElement("style");
        s.appendChild(document.createTextNode(css));
        document.head.appendChild(s);
        return s;
      },
    },
    set_route(...args: any[]) {
      const route = args.join("/");
      if (route) window.location.assign(`/app/${route}`);
    },
  };
}
