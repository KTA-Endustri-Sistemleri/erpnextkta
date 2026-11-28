import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import PdaHubApp from "../PdaHubApp.vue";

const STOCK_CATEGORY = {
  key: "stock",
  title: "Stock",
  icon: "📦",
  items: [
    {
      key: "picking",
      title: "Hat İkmal Toplama",
      subtitle: "Açık ikmal emirlerini okutarak topla ve hatta aktar",
      icon: "📦",
      accent: "accent-blue",
    },
    {
      key: "split",
      title: "Koli Bölme ve Etiketleme",
      subtitle: "Mevcut koliyi böl, yeni parti oluştur ve etiket bas",
      icon: "✂️",
      accent: "accent-amber",
    },
    {
      key: "merge",
      title: "Koli Birleştirme",
      subtitle: "Mevcut kolileri tek partide birleştir ve etiket bas",
      icon: "🔗",
      accent: "accent-purple",
    },
    {
      key: "transfer",
      title: "Depo Raf Transferi",
      subtitle: "Koli ve hedef raf okutarak raflar arası tam kutu taşı",
      icon: "🔄",
      accent: "accent-green",
    },
    {
      key: "lookup",
      title: "Stok ve Etiket Sorgula",
      subtitle: "Koli, raf veya ürün barkodu ile anlık bakiye görüntüle",
      icon: "🔍",
      accent: "accent-indigo",
    },
  ],
};

const QUALITY_CATEGORY = {
  key: "quality",
  title: "Quality",
  icon: "✅",
  items: [
    {
      key: "lookup",
      title: "Kalite Kontrol Sorgula",
      subtitle: "Parti kalite durumunu görüntüle",
      icon: "🔍",
      accent: "accent-indigo",
    },
  ],
};

function makeBoot(overrides: Record<string, any> = {}) {
  return {
    is_locked: true,
    current_user: "pda@example.com",
    active_operator: null,
    device_authorized: true,
    inactivity_timeout_sec: 120,
    operators: [
      {
        name: "EMP-0001",
        employee: "EMP-0001",
        employee_name: "Ali Yılmaz",
        department: "Depo",
        user_id: "ali@example.com",
        has_pin: true,
      },
      {
        name: "EMP-0002",
        employee: "EMP-0002",
        employee_name: "Veli Demir",
        department: "Kalite",
        user_id: "veli@example.com",
        has_pin: true,
      },
    ],
    open_picking_count: 2,
    menu_categories: [STOCK_CATEGORY],
    ...overrides,
  };
}

describe("PdaHubApp", () => {
  beforeEach(() => {
    window.csrf_token = "initial-csrf";
    window.__ = (s: string) => s;
    window.__KTA_PDA_BOOT__ = makeBoot({ menu_categories: [] });
    localStorage.removeItem("kta_pda_theme");
    localStorage.removeItem("kta_pda_sound");
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.lang = "tr";
    document.body.innerHTML = "";
  });

  afterEach(() => {
    Object.defineProperty(window, "scrollY", { value: 0, configurable: true });
    localStorage.removeItem("kta_pda_theme");
    localStorage.removeItem("kta_pda_sound");
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.lang = "tr";
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("unlocks via PIN and transitions from PinLockScreen to LauncherHome, then navigates to PickingModuleView", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("verify_pda_pin")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            message: {
              ok: true,
              user: "ali@example.com",
              employee: "EMP-0001",
              employee_name: "Ali Yılmaz",
              csrf_token: "unlocked-csrf",
              menu_categories: [STOCK_CATEGORY],
              open_picking_count: 2,
            },
          }),
        };
      }
      if (url.includes("get_pda_boot_data")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            message: makeBoot({ is_locked: false, open_picking_count: 3 }),
          }),
        };
      }
      if (url.includes("get_open_replenishment_orders")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ message: [] }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({ message: {} }),
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(PdaHubApp);
    await wrapper.find('[data-testid="operator-card"]').trigger("click");
    for (const d of ["1", "2", "3", "4"]) {
      await wrapper.find(`[data-testid="pin-key-${d}"]`).trigger("click");
    }
    await flushPromises();

    expect(window.csrf_token).toBe("unlocked-csrf");
    expect(wrapper.find('[data-testid="module-card-picking"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="inactivity-timer"]').text()).toBe("02:00");
    expect(wrapper.find('[data-testid="pda-subbar"]').exists()).toBe(false);

    await wrapper.find('[data-testid="module-card-picking"]').trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="pda-subbar"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="topbar-back-btn"]').exists()).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("get_open_replenishment_orders"),
      expect.any(Object),
    );

    await wrapper.find('[data-testid="topbar-back-btn"]').trigger("click");
    expect(wrapper.find('[data-testid="pda-subbar"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="module-card-picking"]').exists()).toBe(true);
    wrapper.unmount();
  });

  it("handles handover logout button and inactivity auto-lock", async () => {
    vi.useFakeTimers();
    window.__KTA_PDA_BOOT__ = makeBoot({
      is_locked: false,
      active_operator: {
        name: "EMP-0001",
        employee: "EMP-0001",
        employee_name: "Ali Yılmaz",
        department: "Depo",
        user_id: "ali@example.com",
        has_pin: true,
      },
      inactivity_timeout_sec: 10,
    });

    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("pda_handover_logout")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            message: { ok: true, csrf_token: "locked-csrf" },
          }),
        };
      }
      return { ok: true, status: 200, json: async () => ({ message: {} }) };
    });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(PdaHubApp);
    expect(wrapper.find('[data-testid="handover-btn"]').exists()).toBe(true);

    await vi.advanceTimersByTimeAsync(10_500);
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("pda_handover_logout"),
      expect.any(Object),
    );
    expect(window.csrf_token).toBe("locked-csrf");
    expect(wrapper.find('[data-testid="operator-card"]').exists()).toBe(true);
    wrapper.unmount();
  });

  it("uses two-row header + subbar without overflow, opens drawer, and resets menu state on handover", async () => {
    let activePinOperator = "EMP-0001";
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("verify_pda_pin")) {
        const body = init?.body ? JSON.parse(String(init.body)) : {};
        activePinOperator = body.employee || activePinOperator;
        const isOpB = activePinOperator === "EMP-0002";
        return {
          ok: true,
          status: 200,
          json: async () => ({
            message: {
              ok: true,
              user: isOpB ? "veli@example.com" : "ali@example.com",
              employee: activePinOperator,
              employee_name: isOpB ? "Veli Demir" : "Ali Yılmaz",
              csrf_token: isOpB ? "csrf-b" : "csrf-a",
              menu_categories: isOpB ? [] : [STOCK_CATEGORY],
              open_picking_count: isOpB ? 0 : 2,
            },
          }),
        };
      }
      if (url.includes("get_pda_boot_data")) {
        const isOpB = activePinOperator === "EMP-0002";
        return {
          ok: true,
          status: 200,
          json: async () => ({
            message: makeBoot({
              is_locked: false,
              current_user: isOpB ? "veli@example.com" : "ali@example.com",
              menu_categories: isOpB ? [] : [STOCK_CATEGORY],
              open_picking_count: isOpB ? 0 : 2,
            }),
          }),
        };
      }
      if (url.includes("pda_handover_logout")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            message: { ok: true, csrf_token: "csrf-locked" },
          }),
        };
      }
      if (url.includes("get_open_replenishment_orders")) {
        return { ok: true, status: 200, json: async () => ({ message: [] }) };
      }
      return { ok: true, status: 200, json: async () => ({ message: {} }) };
    });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(PdaHubApp);

    // 1) Operator A (Stock category only) unlocks -> Row 1 has no breadcrumb or back button, subbar hidden on home
    await wrapper.findAll('[data-testid="operator-card"]')[0].trigger("click");
    for (const d of ["1", "2", "3", "4"]) {
      await wrapper.find(`[data-testid="pin-key-${d}"]`).trigger("click");
    }
    await flushPromises();

    const topbar = wrapper.find(".pda-topbar");
    expect(topbar.find('[data-testid="topbar-menu-btn"]').exists()).toBe(true);
    expect(topbar.find('[data-testid="topbar-brand"]').exists()).toBe(true);
    expect(topbar.find('[data-testid="topbar-breadcrumb"]').exists()).toBe(false);
    expect(topbar.find('[data-testid="topbar-back-btn"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="pda-subbar"]').exists()).toBe(false);

    // Select "split" -> subbar appears with Back + Breadcrumb
    await wrapper.find('[data-testid="module-card-split"]').trigger("click");
    const subbar = wrapper.find('[data-testid="pda-subbar"]');
    expect(subbar.exists()).toBe(true);
    expect(subbar.find('[data-testid="topbar-back-btn"]').text()).toContain("Geri");
    expect(subbar.find('[data-testid="topbar-breadcrumb"]').text()).toBe(
      "Stock › Koli Bölme",
    );

    // Open drawer and switch to "picking"
    await wrapper.find('[data-testid="topbar-menu-btn"]').trigger("click");
    const drawer = document.body.querySelector('[data-testid="pda-menu-drawer"]');
    expect(drawer).not.toBeNull();

    const pickingDrawerBtn = document.body.querySelector(
      '[data-testid="drawer-item-picking"]',
    ) as HTMLElement;
    pickingDrawerBtn.click();
    await flushPromises();

    expect(document.body.querySelector('[data-testid="pda-menu-drawer"]')).toBeNull();
    expect(wrapper.find('[data-testid="topbar-breadcrumb"]').text()).toBe(
      "Stock › Hat İkmal Toplama",
    );

    // Clicking subbar back button returns to home and hides subbar
    await wrapper.find('[data-testid="topbar-back-btn"]').trigger("click");
    expect(wrapper.find('[data-testid="pda-subbar"]').exists()).toBe(false);

    // 2) Handover -> Operator B (no authorized modules)
    await wrapper.find('[data-testid="handover-btn"]').trigger("click");
    await flushPromises();

    const opCards = wrapper.findAll('[data-testid="operator-card"]');
    expect(opCards).toHaveLength(2);
    await opCards[1].trigger("click");
    for (const d of ["5", "6", "7", "8"]) {
      await wrapper.find(`[data-testid="pin-key-${d}"]`).trigger("click");
    }
    await flushPromises();

    expect(wrapper.find('[data-testid="no-authorized-modules"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="module-card-split"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("shows subbar inside multi-category folder and clears category selection on subbar back", async () => {
    window.__KTA_PDA_BOOT__ = makeBoot({
      is_locked: false,
      active_operator: {
        name: "EMP-0001",
        employee: "EMP-0001",
        employee_name: "Ali Yılmaz",
        department: "Depo",
        user_id: "ali@example.com",
        has_pin: true,
      },
      menu_categories: [STOCK_CATEGORY, QUALITY_CATEGORY],
    });

    const wrapper = mount(PdaHubApp);
    expect(wrapper.find('[data-testid="pda-subbar"]').exists()).toBe(false);

    await wrapper.find('[data-testid="category-card-stock"]').trigger("click");
    expect(wrapper.find('[data-testid="pda-subbar"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="topbar-breadcrumb"]').text()).toBe(
      "Ana Modüller › Stock",
    );

    await wrapper.find('[data-testid="topbar-back-btn"]').trigger("click");
    expect(wrapper.find('[data-testid="pda-subbar"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="category-card-stock"]').exists()).toBe(true);
    wrapper.unmount();
  });

  it("applies stored dark theme, navigates to PdaSettingsView via drawer, and syncs live translations on unlock/handover", async () => {
    localStorage.setItem("kta_pda_theme", "dark");
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("verify_pda_pin")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            message: {
              ok: true,
              user: "ali@example.com",
              employee: "EMP-0001",
              employee_name: "Ali Yılmaz",
              csrf_token: "csrf-en",
              menu_categories: [STOCK_CATEGORY],
              open_picking_count: 1,
              lang: "en",
              messages: {
                Menü: "Menu",
                Ayarlar: "Settings",
                Geri: "Back",
                Devret: "Handover",
              },
            },
          }),
        };
      }
      if (url.includes("pda_get_settings_data")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            message: {
              has_employee: true,
              employee: "EMP-0001",
              employee_name: "Ali Yılmaz",
              department: "AMBAR - KTA",
              has_pin: true,
              can_manage_operator_pins: false,
              authorized_printers: [],
              printer_preferences: { printer: null, fallback_printer: null, disabled: 1 },
              user_language: "en",
              manageable_operators: [],
            },
          }),
        };
      }
      if (url.includes("pda_handover_logout")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            message: {
              ok: true,
              csrf_token: "csrf-tr",
              lang: "tr",
              messages: { "PDA Terminal Kilidi": "PDA Terminal Kilidi" },
            },
          }),
        };
      }
      if (url.includes("get_pda_boot_data")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            message: makeBoot({ is_locked: false, open_picking_count: 1 }),
          }),
        };
      }
      return { ok: true, status: 200, json: async () => ({ message: {} }) };
    });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(PdaHubApp);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    await wrapper.findAll('[data-testid="operator-card"]')[0].trigger("click");
    for (const d of ["1", "2", "3", "4"]) {
      await wrapper.find(`[data-testid="pin-key-${d}"]`).trigger("click");
    }
    await flushPromises();

    expect(document.documentElement.lang).toBe("en");
    expect(wrapper.find('[data-testid="topbar-menu-btn"]').text()).toContain("Menu");
    expect(wrapper.find('[data-testid="handover-btn"]').text()).toContain("Handover");

    await wrapper.find('[data-testid="topbar-menu-btn"]').trigger("click");
    const settingsBtn = document.body.querySelector(
      '[data-testid="drawer-item-settings"]',
    ) as HTMLElement;
    expect(settingsBtn).not.toBeNull();
    settingsBtn.click();
    await flushPromises();

    expect(wrapper.find('[data-testid="pda-subbar"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="topbar-back-btn"]').text()).toContain("Back");
    expect(wrapper.find('[data-testid="topbar-breadcrumb"]').text()).toBe("Settings");
    expect(wrapper.find('[data-testid="own-pin-card"]').exists()).toBe(true);

    await wrapper.find('[data-testid="handover-btn"]').trigger("click");
    await flushPromises();
    expect(document.documentElement.lang).toBe("tr");
    expect(wrapper.find('[data-testid="operator-card"]').exists()).toBe(true);
    wrapper.unmount();
  });

  it("auto-hides subbar on downward scroll and restores it on upward scroll or near top", async () => {
    Object.defineProperty(window, "scrollY", { value: 0, configurable: true });
    window.__KTA_PDA_BOOT__ = makeBoot({
      is_locked: false,
      active_operator: {
        name: "EMP-0001",
        employee: "EMP-0001",
        employee_name: "Ali Yılmaz",
        department: "Depo",
        user_id: "ali@example.com",
        has_pin: true,
      },
      menu_categories: [STOCK_CATEGORY],
    });

    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("get_open_replenishment_orders")) {
        return { ok: true, status: 200, json: async () => ({ message: [] }) };
      }
      return { ok: true, status: 200, json: async () => ({ message: {} }) };
    });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(PdaHubApp);
    await wrapper.find('[data-testid="module-card-picking"]').trigger("click");
    await flushPromises();

    const shell = wrapper.find(".pda-hub-shell");
    const subbar = wrapper.find('[data-testid="pda-subbar"]');
    expect(subbar.exists()).toBe(true);
    expect(subbar.classes()).not.toContain("is-hidden");
    expect((shell.element as HTMLElement).style.getPropertyValue("--pda-sticky-top")).toBe("100px");

    const triggerScroll = async (y: number) => {
      Object.defineProperty(window, "scrollY", { value: y, configurable: true });
      window.dispatchEvent(new Event("scroll"));
      await flushPromises();
    };

    // Scroll down past 48px -> subbar hides, sticky top shifts to 56px
    await triggerScroll(80);
    expect(subbar.classes()).toContain("is-hidden");
    expect((shell.element as HTMLElement).style.getPropertyValue("--pda-sticky-top")).toBe("56px");

    // Scroll back up (lastY - currentY > 4) -> subbar reappears, sticky top restores to 100px
    await triggerScroll(60);
    expect(subbar.classes()).not.toContain("is-hidden");
    expect((shell.element as HTMLElement).style.getPropertyValue("--pda-sticky-top")).toBe("100px");

    // Scroll down again, then return near top (<= 24px) -> subbar reappears
    await triggerScroll(120);
    expect(subbar.classes()).toContain("is-hidden");
    expect((shell.element as HTMLElement).style.getPropertyValue("--pda-sticky-top")).toBe("56px");

    await triggerScroll(16);
    expect(subbar.classes()).not.toContain("is-hidden");
    expect((shell.element as HTMLElement).style.getPropertyValue("--pda-sticky-top")).toBe("100px");

    wrapper.unmount();
  });
});
