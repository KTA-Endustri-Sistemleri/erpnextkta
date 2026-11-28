import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import PdaSettingsView from "../views/PdaSettingsView.vue";
import { initFrappeShim, translate } from "../utils/frappeShim";

vi.mock("../../line-replenishment-pda/utils/audio", () => ({
  playBeep: vi.fn(() => Promise.resolve()),
}));

import { playBeep } from "../../line-replenishment-pda/utils/audio";

function makeSettingsData(overrides: Record<string, any> = {}) {
  return {
    has_employee: true,
    employee: "HR-EMP-0001",
    employee_name: "Ali Yılmaz",
    department: "AMBAR - KTA",
    has_pin: false,
    can_manage_operator_pins: false,
    authorized_printers: [
      { name: "ZEBRA-01", printer_name: "Ambar Etiket 1", ip: "10.0.0.10", port: 9100 },
      { name: "ZEBRA-02", printer_name: "Ambar Etiket 2", ip: "10.0.0.11", port: 9100 },
    ],
    printer_preferences: { printer: "ZEBRA-01", fallback_printer: null, disabled: 0 },
    user_language: "tr",
    manageable_operators: [],
    ...overrides,
  };
}

describe("PdaSettingsView.vue", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.lang = "tr";
    initFrappeShim();
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.lang = "tr";
    vi.restoreAllMocks();
  });

  it("renders initial PIN setup form when has_pin=false and emits pin-updated", async () => {
    const callMock = vi.fn(async (opts: any) => {
      if (opts.method.endsWith("pda_get_settings_data")) {
        return { message: makeSettingsData({ has_pin: false }) };
      }
      if (opts.method.endsWith("pda_update_own_pin")) {
        return { message: { ok: true, employee: "HR-EMP-0001", has_pin: true } };
      }
      return { message: {} };
    });
    window.frappe.call = callMock;
    window.frappe.show_alert = vi.fn();

    const wrapper = mount(PdaSettingsView);
    await flushPromises();

    expect(wrapper.find('[data-testid="pin-mode-current"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="save-own-pin-btn"]').text()).toContain("PIN Oluştur");

    await wrapper.find('[data-testid="own-new-pin-input"]').setValue("4829");
    await wrapper.find('[data-testid="own-confirm-pin-input"]').setValue("4829");
    await wrapper.find('[data-testid="save-own-pin-btn"]').trigger("click");
    await flushPromises();

    expect(callMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "erpnextkta.kta_stock.services.pda_service.pda_update_own_pin",
        args: {
          mode: "initial",
          new_pin: "4829",
          confirm_pin: "4829",
          current_pin: undefined,
          account_password: undefined,
        },
      }),
    );
    expect(wrapper.emitted("pin-updated")).toHaveLength(1);
    wrapper.unmount();
  });

  it("toggles between current_pin and account_password modes when has_pin=true", async () => {
    const callMock = vi.fn(async (opts: any) => {
      if (opts.method.endsWith("pda_get_settings_data")) {
        return { message: makeSettingsData({ has_pin: true }) };
      }
      if (opts.method.endsWith("pda_update_own_pin")) {
        return { message: { ok: true, employee: "HR-EMP-0001", has_pin: true } };
      }
      return { message: {} };
    });
    window.frappe.call = callMock;
    window.frappe.show_alert = vi.fn();

    const wrapper = mount(PdaSettingsView);
    await flushPromises();

    expect(wrapper.find('[data-testid="pin-mode-current"]').exists()).toBe(true);
    await wrapper.find('[data-testid="pin-mode-password"]').trigger("click");
    await wrapper.find('[data-testid="own-password-input"]').setValue("MyPass123!");
    await wrapper.find('[data-testid="own-new-pin-input"]').setValue("9012");
    await wrapper.find('[data-testid="own-confirm-pin-input"]').setValue("9012");
    await wrapper.find('[data-testid="save-own-pin-btn"]').trigger("click");
    await flushPromises();

    expect(callMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "erpnextkta.kta_stock.services.pda_service.pda_update_own_pin",
        args: expect.objectContaining({
          mode: "account_password",
          account_password: "MyPass123!",
          new_pin: "9012",
          confirm_pin: "9012",
        }),
      }),
    );
    wrapper.unmount();
  });

  it("renders employeeless info hint and handles RBAC admin reset (empty and populated)", async () => {
    const callMock = vi
      .fn()
      .mockResolvedValueOnce({
        message: makeSettingsData({
          has_employee: false,
          employee: null,
          can_manage_operator_pins: true,
          manageable_operators: [],
        }),
      });
    window.frappe.call = callMock;

    const emptyAdminWrapper = mount(PdaSettingsView);
    await flushPromises();
    expect(emptyAdminWrapper.find('[data-testid="own-pin-card"]').text()).toContain(
      "aktif personel kartı bulunmadığından",
    );
    expect(emptyAdminWrapper.find('[data-testid="admin-pin-reset-card"]').text()).toContain(
      "başka aktif PDA operatörü bulunamadı",
    );
    emptyAdminWrapper.unmount();

    const adminCallMock = vi.fn(async (opts: any) => {
      if (opts.method.endsWith("pda_get_settings_data")) {
        return {
          message: makeSettingsData({
            has_pin: true,
            can_manage_operator_pins: true,
            manageable_operators: [
              {
                name: "HR-EMP-0002",
                employee: "HR-EMP-0002",
                employee_name: "Ayşe Demir",
                department: "AMBAR - KTA",
                user_id: "ayse@example.com",
                has_pin: true,
              },
            ],
          }),
        };
      }
      if (opts.method.endsWith("pda_admin_reset_operator_pin")) {
        return {
          message: { ok: true, employee: "HR-EMP-0002", employee_name: "Ayşe Demir", has_pin: true },
        };
      }
      return { message: {} };
    });
    window.frappe.call = adminCallMock;
    window.frappe.show_alert = vi.fn();

    const adminWrapper = mount(PdaSettingsView);
    await flushPromises();

    await adminWrapper.find('[data-testid="admin-target-operator"]').setValue("HR-EMP-0002");
    await adminWrapper.find('[data-testid="admin-new-pin-input"]').setValue("3344");
    await adminWrapper.find('[data-testid="admin-confirm-pin-input"]').setValue("3344");
    await adminWrapper.find('[data-testid="admin-reset-pin-btn"]').trigger("click");
    await flushPromises();

    expect(adminCallMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "erpnextkta.kta_stock.services.pda_service.pda_admin_reset_operator_pin",
        args: {
          target_employee: "HR-EMP-0002",
          new_pin: "3344",
          confirm_pin: "3344",
        },
      }),
    );
    adminWrapper.unmount();
  });

  it("saves Zebra printers, validates distinct primary/fallback, tests printer, and switches theme/sound/language live", async () => {
    const callMock = vi.fn(async (opts: any) => {
      if (opts.method.endsWith("pda_get_settings_data")) {
        return { message: makeSettingsData() };
      }
      if (opts.method.endsWith("pda_save_printer_preferences")) {
        return {
          message: { ok: true, printer: "ZEBRA-01", fallback_printer: "ZEBRA-02", disabled: 0 },
        };
      }
      if (opts.method.endsWith("pda_test_printer_connection")) {
        return {
          message: { ok: true, printer: "ZEBRA-01", online: true, status: "Ready", message: "Online" },
        };
      }
      if (opts.method.endsWith("pda_update_user_language")) {
        return {
          message: {
            ok: true,
            lang: "en",
            messages: { "Zebra Yazıcı Tercihleri": "Zebra Printer Preferences" },
          },
        };
      }
      return { message: {} };
    });
    window.frappe.call = callMock;
    window.frappe.show_alert = vi.fn();

    const wrapper = mount(PdaSettingsView);
    await flushPromises();

    // Same printer validation blocks RPC
    await wrapper.find('[data-testid="printer-fallback-select"]').setValue("ZEBRA-01");
    await wrapper.find('[data-testid="save-printer-btn"]').trigger("click");
    expect(callMock).not.toHaveBeenCalledWith(
      expect.objectContaining({
        method: "erpnextkta.kta_stock.services.pda_service.pda_save_printer_preferences",
      }),
    );

    // Distinct fallback saves & tests connection
    await wrapper.find('[data-testid="printer-fallback-select"]').setValue("ZEBRA-02");
    await wrapper.find('[data-testid="save-printer-btn"]').trigger("click");
    await flushPromises();
    expect(callMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "erpnextkta.kta_stock.services.pda_service.pda_save_printer_preferences",
        args: { printer: "ZEBRA-01", fallback_printer: "ZEBRA-02" },
      }),
    );

    await wrapper.find('[data-testid="test-printer-btn"]').trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="printer-test-status"]').text()).toContain("Ready");

    // Theme switch
    await wrapper.find('[data-testid="theme-dark-btn"]').trigger("click");
    expect(localStorage.getItem("kta_pda_theme")).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    await wrapper.find('[data-testid="theme-light-btn"]').trigger("click");
    expect(localStorage.getItem("kta_pda_theme")).toBe("light");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);

    // Sound toggle (mute does not play beep; unmute plays test beep)
    await wrapper.find('[data-testid="sound-toggle-btn"]').trigger("click");
    expect(localStorage.getItem("kta_pda_sound")).toBe("0");
    expect(playBeep).not.toHaveBeenCalled();

    await wrapper.find('[data-testid="sound-toggle-btn"]').trigger("click");
    expect(localStorage.getItem("kta_pda_sound")).toBe("1");
    expect(playBeep).toHaveBeenCalledWith(true);

    // Zero-reload live language switch
    await wrapper.find('[data-testid="lang-btn-en"]').trigger("click");
    await flushPromises();
    expect(callMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "erpnextkta.kta_stock.services.pda_service.pda_update_user_language",
        args: { language: "en" },
      }),
    );
    expect(translate("Zebra Yazıcı Tercihleri")).toBe("Zebra Printer Preferences");
    expect(wrapper.find('[data-testid="printer-settings-card"]').text()).toContain(
      "Zebra Printer Preferences",
    );
    wrapper.unmount();
  });
});
