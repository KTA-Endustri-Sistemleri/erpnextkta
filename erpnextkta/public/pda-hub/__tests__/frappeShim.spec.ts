import { describe, it, expect, vi } from "vitest";
import {
  initFrappeShim,
  updateCsrfToken,
  overlayState,
} from "../utils/frappeShim";

describe("frappeShim", () => {
  it("sends POST to /api/method/<method> with X-Frappe-CSRF-Token and updates token via updateCsrfToken", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: { ok: true } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    window.csrf_token = "tok-1";
    initFrappeShim();

    const callback = vi.fn();
    const res = await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.verify_pda_pin",
      args: { employee: "HR-EMP-001", pin: "1234" },
      callback,
    });

    expect(res).toEqual({ message: { ok: true } });
    expect(callback).toHaveBeenCalledWith({ message: { ok: true } });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url1, init1] = fetchMock.mock.calls[0];
    expect(url1).toBe(
      "/api/method/erpnextkta.kta_stock.services.pda_service.verify_pda_pin"
    );
    expect(init1.method).toBe("POST");
    expect(init1.credentials).toBe("same-origin");
    expect(init1.headers["X-Frappe-CSRF-Token"]).toBe("tok-1");
    expect(JSON.parse(init1.body)).toEqual({
      employee: "HR-EMP-001",
      pin: "1234",
    });

    updateCsrfToken("new-tok");
    expect(window.csrf_token).toBe("new-tok");

    await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_handover_logout",
    });

    const [, init2] = fetchMock.mock.calls[1];
    expect(init2.headers["X-Frappe-CSRF-Token"]).toBe("new-tok");
  });

  it("supports GET requests with query parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: { items: [] } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    initFrappeShim();
    await window.frappe.call({
      type: "GET",
      method: "erpnextkta.kta_stock.services.pda_service.pda_scan_box",
      args: { barcode: "LOT0001", empty: null },
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
    expect(url).toBe(
      "/api/method/erpnextkta.kta_stock.services.pda_service.pda_scan_box?barcode=LOT0001"
    );
  });

  it("parses _server_messages into readable error messages and triggers error callback", async () => {
    const serverMessages = JSON.stringify([
      JSON.stringify({ message: "<b>Hatalı PIN kodu.</b> Kalan deneme: 4." }),
    ]);
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 417,
      json: async () => ({
        _server_messages: serverMessages,
        exc_type: "ValidationError",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    initFrappeShim();
    const errorCb = vi.fn();

    await expect(
      window.frappe.call({
        method: "erpnextkta.kta_stock.services.pda_service.verify_pda_pin",
        args: { employee: "HR-EMP-001", pin: "9999" },
        error: errorCb,
      })
    ).rejects.toThrow("Hatalı PIN kodu. Kalan deneme: 4.");

    expect(errorCb).toHaveBeenCalledTimes(1);
    expect(errorCb.mock.calls[0][0].message).toBe(
      "Hatalı PIN kodu. Kalan deneme: 4."
    );
  });

  it("calls onAuthExpired on 401 and 403 responses", async () => {
    const onAuthExpired = vi.fn();
    initFrappeShim({ onAuthExpired });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ message: "Unauthorized" }),
      })
    );

    await expect(
      window.frappe.call({
        method: "erpnextkta.kta_stock.services.pda_service.pda_scan_box",
        error: vi.fn(),
      })
    ).rejects.toThrow();

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ message: "Forbidden" }),
      })
    );

    await expect(
      window.frappe.call({
        method: "erpnextkta.kta_stock.services.pda_service.pda_scan_box",
        error: vi.fn(),
      })
    ).rejects.toThrow();

    expect(onAuthExpired).toHaveBeenCalledTimes(2);
  });

  it("translates messages using frappe._messages and formats {0}, {1} placeholders", () => {
    window.frappe._messages = {
      "Transfer Tamamlandı: {0} ({1})": "Transfer Completed: {0} ({1})",
    };
    initFrappeShim();

    expect(
      window.__("Transfer Tamamlandı: {0} ({1})", ["MAT-STE-001", 3])
    ).toBe("Transfer Completed: MAT-STE-001 (3)");
  });

  it("toggles overlayState freezing during freeze requests", async () => {
    let seenFreezingDuringRequest = false;
    let seenFreezeMessage = "";
    const fetchMock = vi.fn().mockImplementation(async () => {
      seenFreezingDuringRequest = overlayState.freezing;
      seenFreezeMessage = overlayState.freezeMessage;
      return {
        ok: true,
        status: 200,
        json: async () => ({ message: "OK" }),
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    initFrappeShim();
    await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.get_pda_boot_data",
      freeze: true,
      freeze_message: "İşlem yapılıyor...",
    });

    expect(seenFreezingDuringRequest).toBe(true);
    expect(seenFreezeMessage).toBe("İşlem yapılıyor...");
    expect(overlayState.freezing).toBe(false);
  });
});
