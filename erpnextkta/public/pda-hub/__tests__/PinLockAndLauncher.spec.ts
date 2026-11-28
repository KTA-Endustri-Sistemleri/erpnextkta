import { describe, it, expect, vi } from "vitest";
import { ref, defineComponent } from "vue";
import { mount, flushPromises } from "@vue/test-utils";
import PinLockScreen from "../components/PinLockScreen.vue";
import LauncherHome from "../components/LauncherHome.vue";
import PdaMenuDrawer from "../components/PdaMenuDrawer.vue";
import { useInactivityLock } from "../composables/useInactivityLock";
import type { PdaMenuCategory, PdaOperator } from "../types";

const stockCategory: PdaMenuCategory = {
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

const qualityCategory: PdaMenuCategory = {
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

const sampleOperators: PdaOperator[] = [
  {
    employee: "HR-EMP-0001",
    name: "HR-EMP-0001",
    employee_name: "Ali Yılmaz",
    department: "AMBAR - KTA",
    user_id: "ali@example.com",
    has_pin: true,
  },
  {
    employee: "HR-EMP-0002",
    name: "HR-EMP-0002",
    employee_name: "Ayşe Demir",
    department: "Sevk",
    user_id: "ayse@example.com",
    has_pin: false,
  },
];

describe("PinLockScreen.vue", () => {
  it("opens 4-digit keypad on operator selection, calls verify_pda_pin, and emits unlocked", async () => {
    window.frappe.call = vi.fn(({ method, args, callback }) => {
      expect(method).toBe(
        "erpnextkta.kta_stock.services.pda_service.verify_pda_pin"
      );
      expect(args).toEqual({ employee: "HR-EMP-0001", pin: "2580" });
      callback?.({
        message: {
          ok: true,
          user: "ali@example.com",
          employee: "HR-EMP-0001",
          employee_name: "Ali Yılmaz",
          csrf_token: "fresh-csrf-123",
        },
      });
      return Promise.resolve();
    });

    const wrapper = mount(PinLockScreen, {
      props: { operators: sampleOperators },
    });

    const cards = wrapper.findAll("[data-testid='operator-card']");
    expect(cards).toHaveLength(2);
    expect(cards[0].text()).toContain("Ali Yılmaz");
    expect(cards[1].text()).toContain("PIN Yok");

    await cards[0].trigger("click");
    expect(wrapper.find("[data-testid='pin-keypad']").exists()).toBe(true);

    for (const digit of ["2", "5", "8", "0"]) {
      await wrapper.find(`[data-testid='pin-key-${digit}']`).trigger("click");
    }
    await flushPromises();

    const emitted = wrapper.emitted("unlocked");
    expect(emitted).toBeTruthy();
    expect(emitted![0][0]).toEqual({
      response: {
        ok: true,
        user: "ali@example.com",
        employee: "HR-EMP-0001",
        employee_name: "Ali Yılmaz",
        csrf_token: "fresh-csrf-123",
      },
      operator: sampleOperators[0],
    });
  });

  it("shows error message and clears entered digits on PIN rejection", async () => {
    window.frappe.call = vi.fn(({ error }) => {
      error?.(new Error("Hatalı PIN kodu. Kalan deneme hakkı: 4."));
      return Promise.reject(new Error("Hatalı PIN kodu. Kalan deneme hakkı: 4."));
    });

    const wrapper = mount(PinLockScreen, {
      props: { operators: sampleOperators },
    });

    await wrapper.findAll("[data-testid='operator-card']")[0].trigger("click");
    for (const digit of ["1", "1", "1", "1"]) {
      await wrapper.find(`[data-testid='pin-key-${digit}']`).trigger("click");
    }
    await flushPromises();

    expect(wrapper.emitted("unlocked")).toBeFalsy();
    expect(wrapper.find("[data-testid='pin-error']").text()).toContain(
      "Hatalı PIN kodu"
    );
    expect(
      wrapper.findAll("[data-testid='pin-dot'].filled")
    ).toHaveLength(0);
  });
});

describe("LauncherHome.vue", () => {
  it("renders all 5 module cards with open picking count badge and emits select", async () => {
    const wrapper = mount(LauncherHome, {
      props: {
        menuCategories: [stockCategory],
        openPickingCount: 7,
        operatorName: "Ali Yılmaz",
      },
    });

    const pickingCard = wrapper.find("[data-testid='module-card-picking']");
    const splitCard = wrapper.find("[data-testid='module-card-split']");
    const mergeCard = wrapper.find("[data-testid='module-card-merge']");
    const transferCard = wrapper.find("[data-testid='module-card-transfer']");
    const lookupCard = wrapper.find("[data-testid='module-card-lookup']");

    expect(pickingCard.exists()).toBe(true);
    expect(splitCard.exists()).toBe(true);
    expect(mergeCard.exists()).toBe(true);
    expect(transferCard.exists()).toBe(true);
    expect(lookupCard.exists()).toBe(true);
    expect(pickingCard.text()).toContain("7");

    await splitCard.trigger("click");
    expect(wrapper.emitted("select")).toEqual([["split"]]);
  });

  it("renders category cards for multiple categories and empty state for zero categories", async () => {
    const multiWrapper = mount(LauncherHome, {
      props: {
        menuCategories: [stockCategory, qualityCategory],
        selectedCategoryKey: null,
        openPickingCount: 4,
        operatorName: "Ali Yılmaz",
      },
    });

    const stockCard = multiWrapper.find("[data-testid='category-card-stock']");
    const qualityCard = multiWrapper.find("[data-testid='category-card-quality']");
    expect(stockCard.exists()).toBe(true);
    expect(qualityCard.exists()).toBe(true);
    expect(multiWrapper.find("[data-testid='module-card-split']").exists()).toBe(false);

    await stockCard.trigger("click");
    expect(multiWrapper.emitted("select-category")).toEqual([["stock"]]);

    const emptyWrapper = mount(LauncherHome, {
      props: {
        menuCategories: [],
        openPickingCount: 0,
        operatorName: "Ali Yılmaz",
      },
    });
    const emptyEl = emptyWrapper.find("[data-testid='no-authorized-modules']");
    expect(emptyEl.exists()).toBe(true);
    expect(emptyEl.text()).toContain("Yetkili Modül Bulunamadı");
  });

  it("shows missing-pin banner when showMissingPinBanner is true and emits open-settings on CTA click", async () => {
    const wrapperWithBanner = mount(LauncherHome, {
      props: {
        menuCategories: [stockCategory],
        openPickingCount: 2,
        operatorName: "Ali Yılmaz",
        showMissingPinBanner: true,
      },
    });
    expect(wrapperWithBanner.find("[data-testid='missing-pin-banner']").exists()).toBe(true);
    await wrapperWithBanner.find("[data-testid='missing-pin-cta']").trigger("click");
    expect(wrapperWithBanner.emitted("open-settings")).toHaveLength(1);

    const wrapperWithoutBanner = mount(LauncherHome, {
      props: {
        menuCategories: [stockCategory],
        openPickingCount: 2,
        operatorName: "Ali Yılmaz",
        showMissingPinBanner: false,
      },
    });
    expect(wrapperWithoutBanner.find("[data-testid='missing-pin-banner']").exists()).toBe(false);
  });
});

describe("PdaMenuDrawer.vue", () => {
  it("renders in body teleport, handles picking badge, Ana Modüller button, screen selection, Escape and backdrop", async () => {
    document.body.innerHTML = "";
    const singleWrapper = mount(PdaMenuDrawer, {
      props: {
        isOpen: true,
        categories: [stockCategory],
        activeScreen: "split",
        selectedCategoryKey: "stock",
        openPickingCount: 5,
      },
    });

    const drawerEl = document.body.querySelector("[data-testid='pda-menu-drawer']");
    expect(drawerEl).not.toBeNull();
    expect(drawerEl?.textContent).toContain("5");
    expect(
      document.body.querySelector("[data-testid='drawer-all-modules-btn']")
    ).toBeNull();

    const transferBtn = document.body.querySelector(
      "[data-testid='drawer-item-transfer']"
    ) as HTMLElement;
    expect(transferBtn).not.toBeNull();
    transferBtn.click();
    await flushPromises();
    expect(singleWrapper.emitted("select-screen")).toEqual([["transfer"]]);
    expect(singleWrapper.emitted("close")).toHaveLength(1);

    const settingsGroup = document.body.querySelector(
      "[data-testid='drawer-settings-group']"
    ) as HTMLElement;
    expect(settingsGroup).not.toBeNull();
    expect(settingsGroup.textContent).toContain("AYARLAR");

    const settingsBtn = document.body.querySelector(
      "[data-testid='drawer-item-settings']"
    ) as HTMLElement;
    expect(settingsBtn).not.toBeNull();
    settingsBtn.click();
    await flushPromises();
    expect(singleWrapper.emitted("select-utility")).toEqual([["settings"]]);
    expect(singleWrapper.emitted("close")).toHaveLength(2);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    await flushPromises();
    expect(singleWrapper.emitted("close")).toHaveLength(3);

    const backdrop = document.body.querySelector(
      "[data-testid='drawer-backdrop']"
    ) as HTMLElement;
    backdrop.click();
    await flushPromises();
    expect(singleWrapper.emitted("close")).toHaveLength(4);
    singleWrapper.unmount();

    const multiWrapper = mount(PdaMenuDrawer, {
      props: {
        isOpen: true,
        categories: [stockCategory, qualityCategory],
        activeScreen: "home",
        selectedCategoryKey: "stock",
        openPickingCount: 5,
      },
    });
    const allModulesBtn = document.body.querySelector(
      "[data-testid='drawer-all-modules-btn']"
    ) as HTMLElement;
    expect(allModulesBtn).not.toBeNull();
    allModulesBtn.click();
    await flushPromises();
    expect(multiWrapper.emitted("select-all-modules")).toHaveLength(1);
    expect(multiWrapper.emitted("close")).toHaveLength(1);
    multiWrapper.unmount();
  });
});

describe("useInactivityLock", () => {
  it("locks after 300s of inactivity and resets timer on user interaction", async () => {
    vi.useFakeTimers();
    try {
      const onLock = vi.fn();
      const enabled = ref(true);

      const Harness = defineComponent({
        setup() {
          const state = useInactivityLock({
            timeoutMs: 300_000,
            enabled,
            onLock,
          });
          return { state };
        },
        template: "<div />",
      });

      const wrapper = mount(Harness);

      await vi.advanceTimersByTimeAsync(250_000);
      expect(onLock).not.toHaveBeenCalled();

      window.dispatchEvent(new Event("pointerdown"));
      await vi.advanceTimersByTimeAsync(250_000);
      expect(onLock).not.toHaveBeenCalled();

      await vi.advanceTimersByTimeAsync(50_000);
      expect(onLock).toHaveBeenCalledTimes(1);

      wrapper.unmount();
    } finally {
      vi.useRealTimers();
    }
  });
});
