import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import PackageSplitView from "../views/PackageSplitView.vue";
import PackageMergeView from "../views/PackageMergeView.vue";
import MaterialTransferView from "../views/MaterialTransferView.vue";
import StockLookupView from "../views/StockLookupView.vue";
import PdaHubApp from "../PdaHubApp.vue";

vi.mock("../../line-replenishment-pda/utils/audio", () => ({
  playBeep: vi.fn(() => Promise.resolve()),
}));

import { playBeep } from "../../line-replenishment-pda/utils/audio";

function makeBoxPayload(overrides: Record<string, any> = {}) {
  return {
    item_code: "ITEM-001",
    item_name: "Test Kablo",
    stock_uom: "Nos",
    batch_no: "KTA26112101",
    base_lot: "KTA2611",
    is_standard_batch: true,
    label_name: "LBL-0001",
    label_type: "Package",
    sut_barcode: "SUT-100",
    expiry_date: "2027-12-31",
    total_qty: 500,
    balances: [{ warehouse: "170-W1F-01-01 - KTA", qty: 500 }],
    ...overrides,
  };
}

describe("Task 6 Warehouse Modules", () => {
  beforeEach(() => {
    window.__ = (s: string, args?: any[]) => {
      if (!args || !args.length) return s;
      return args.reduce(
        (acc, val, idx) => acc.replace(`{${idx}}`, String(val)),
        s,
      );
    };
    window.frappe = {
      call: vi.fn(),
      show_alert: vi.fn(),
      msgprint: vi.fn(),
      confirm: vi.fn(),
    } as any;
    vi.clearAllMocks();
    document.body.innerHTML = "";
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("PackageSplitView", () => {
    it("scans a box, validates live remaining qty, locks invalid splits, and submits partial split", async () => {
      const box = makeBoxPayload();
      const splitResp = {
        ok: true,
        stock_entry: "MAT-STE-2026-00010",
        base_lot: "KTA26112101",
        source_batch: "KTA26112101",
        source_warehouse: "170-W1F-01-01 - KTA",
        remaining_qty: 300,
        created_batches: [
          { batch_no: "KTA26112101-A", qty: 200, label_name: "LBL-0002" },
        ],
        source_label_name: "LBL-0001",
        source_label_reprinted: true,
        queued_reprint_count: 1,
      };

      const callMock = vi.fn(async (opts: any) => {
        if (opts.method.endsWith("pda_scan_box")) {
          return { message: box };
        }
        if (opts.method.endsWith("pda_package_split")) {
          return { message: splitResp };
        }
        return { message: {} };
      });
      window.frappe.call = callMock;

      const wrapper = mount(PackageSplitView);
      const scanInput = wrapper.find("#pda-barcode-input");
      await scanInput.setValue("SUT-100");
      await scanInput.trigger("keydown.enter");
      await flushPromises();

      expect(callMock).toHaveBeenCalledWith(
        expect.objectContaining({
          method: "erpnextkta.kta_stock.services.pda_service.pda_scan_box",
          args: { barcode: "SUT-100" },
        }),
      );
      expect(wrapper.find('[data-testid="split-box-card"]').exists()).toBe(true);
      expect(wrapper.text()).toContain("ITEM-001");
      expect(wrapper.text()).toContain("KTA26112101");

      const submitBtn = wrapper.find('[data-testid="split-submit-btn"]');
      const qtyInput = wrapper.find('[data-testid="split-qty-input-0"]');

      // <= 0 locks submit
      await qtyInput.setValue("0");
      expect((submitBtn.element as HTMLButtonElement).disabled).toBe(true);

      // > balance locks submit
      await qtyInput.setValue("600");
      expect((submitBtn.element as HTMLButtonElement).disabled).toBe(true);

      // Standard 7+4 full qty single split locks submit
      await qtyInput.setValue("500");
      expect((submitBtn.element as HTMLButtonElement).disabled).toBe(true);

      // Valid partial split calculates remaining qty live and unlocks submit
      await qtyInput.setValue("200");
      expect((submitBtn.element as HTMLButtonElement).disabled).toBe(false);
      expect(wrapper.find('[data-testid="split-remaining-qty"]').text()).toContain("300");

      await submitBtn.trigger("click");
      await flushPromises();

      expect(callMock).toHaveBeenCalledWith(
        expect.objectContaining({
          method: "erpnextkta.kta_stock.services.pda_service.pda_package_split",
          args: {
            item_code: "ITEM-001",
            source_warehouse: "170-W1F-01-01 - KTA",
            source_batch: "KTA26112101",
            split_qtys: [200],
            reprint_source_label: 1,
          },
        }),
      );
      expect(playBeep).toHaveBeenCalledWith(true);
      expect(wrapper.find('[data-testid="split-success-card"]').exists()).toBe(true);
      expect(wrapper.text()).toContain("MAT-STE-2026-00010");
      expect(wrapper.text()).toContain("KTA26112101-A");

      await wrapper.find('[data-testid="split-reset-btn"]').trigger("click");
      expect(wrapper.find('[data-testid="split-box-card"]').exists()).toBe(false);
      wrapper.unmount();
    });

    it("supports multi-warehouse source selection, adding split rows, and unchecking source reprint", async () => {
      const box = makeBoxPayload({
        is_standard_batch: false,
        total_qty: 700,
        balances: [
          { warehouse: "WH-A - KTA", qty: 300 },
          { warehouse: "WH-B - KTA", qty: 400 },
        ],
      });
      const callMock = vi.fn(async (opts: any) => {
        if (opts.method.endsWith("pda_scan_box")) return { message: box };
        return {
          message: {
            ok: true,
            stock_entry: "MAT-STE-2026-00011",
            base_lot: "KTA26112101",
            source_batch: "KTA26112101",
            source_warehouse: "WH-B - KTA",
            remaining_qty: 100,
            created_batches: [
              { batch_no: "KTA26112101-A", qty: 150 },
              { batch_no: "KTA26112101-B", qty: 150 },
            ],
          },
        };
      });
      window.frappe.call = callMock;

      const wrapper = mount(PackageSplitView);
      const scanInput = wrapper.find("#pda-barcode-input");
      await scanInput.setValue("SUT-100");
      await scanInput.trigger("keydown.enter");
      await flushPromises();

      const whSelect = wrapper.find('[data-testid="split-source-select"]');
      expect(whSelect.exists()).toBe(true);
      await whSelect.setValue("WH-B - KTA");

      await wrapper.find('[data-testid="split-add-row-btn"]').trigger("click");
      await wrapper.find('[data-testid="split-qty-input-0"]').setValue("150");
      await wrapper.find('[data-testid="split-qty-input-1"]').setValue("150");
      expect(wrapper.find('[data-testid="split-remaining-qty"]').text()).toContain("100");

      const reprintCheckbox = wrapper.find('input[type="checkbox"]');
      await reprintCheckbox.setValue(false);

      await wrapper.find('[data-testid="split-submit-btn"]').trigger("click");
      await flushPromises();

      expect(callMock).toHaveBeenCalledWith(
        expect.objectContaining({
          method: "erpnextkta.kta_stock.services.pda_service.pda_package_split",
          args: {
            item_code: "ITEM-001",
            source_warehouse: "WH-B - KTA",
            source_batch: "KTA26112101",
            split_qtys: [150, 150],
            reprint_source_label: 0,
          },
        }),
      );
      wrapper.unmount();
    });
  });

  describe("MaterialTransferView", () => {
    it("focuses target rack after box scan, enforces full box qty, transfers, plays beep, and resets", async () => {
      const box = makeBoxPayload();
      const transferResp = {
        ok: true,
        stock_entry: "MAT-STE-2026-00025",
        item_code: "ITEM-001",
        batch_no: "KTA26112101",
        qty: 500,
        source_warehouse: "170-W1F-01-01 - KTA",
        target_warehouse: "170-W1F-02-04 - KTA",
        owner: "pda@example.com",
      };

      const callMock = vi.fn(async (opts: any) => {
        if (opts.method.endsWith("pda_scan_box")) {
          return { message: box };
        }
        if (opts.method.endsWith("pda_material_transfer")) {
          return { message: transferResp };
        }
        return { message: {} };
      });
      window.frappe.call = callMock;

      const wrapper = mount(MaterialTransferView, { attachTo: document.body });
      const scanInput = wrapper.find("#pda-barcode-input");
      await scanInput.setValue("SUT-100");
      await scanInput.trigger("keydown.enter");
      await flushPromises();

      expect(wrapper.find('[data-testid="transfer-box-card"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="one-box-one-batch-badge"]').text()).toContain(
        "1 Kutu = 1 Parti",
      );
      expect(wrapper.text()).toContain("500");

      const targetInput = wrapper.find('[data-testid="transfer-target-input"]');
      expect(document.activeElement).toBe(targetInput.element);

      await targetInput.setValue("170-W1F-02-04");
      await wrapper.find('[data-testid="transfer-submit-btn"]').trigger("click");
      await flushPromises();

      expect(callMock).toHaveBeenCalledWith(
        expect.objectContaining({
          method: "erpnextkta.kta_stock.services.pda_service.pda_material_transfer",
          args: {
            item_code: "ITEM-001",
            batch_no: "KTA26112101",
            source_warehouse: "170-W1F-01-01 - KTA",
            target_warehouse_barcode: "170-W1F-02-04",
            qty: 500,
          },
        }),
      );
      expect(playBeep).toHaveBeenCalledWith(true);
      expect(wrapper.find('[data-testid="transfer-success-banner"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="transfer-success-banner"]').text()).toContain(
        "MAT-STE-2026-00025",
      );
      expect(wrapper.find('[data-testid="transfer-box-card"]').exists()).toBe(false);
      wrapper.unmount();
    });
  });

  describe("StockLookupView", () => {
    it("renders batch, warehouse, and item lookup responses cleanly", async () => {
      const batchResp = { ...makeBoxPayload(), kind: "batch" };
      const warehouseResp = {
        kind: "warehouse",
        warehouse: "170-W1F-02-04 - KTA",
        warehouse_name: "170-W1F-02-04",
        company: "KTA",
        items: [
          {
            item_code: "ITEM-002",
            item_name: "Konnektör",
            stock_uom: "Nos",
            actual_qty: 1200,
            reserved_qty: 100,
          },
        ],
      };
      const itemResp = {
        kind: "item",
        item_code: "ITEM-003",
        item_name: "Terminal",
        stock_uom: "Nos",
        has_batch_no: 1,
        total_qty: 850,
        warehouses: [
          { warehouse: "170-W1F-01-01 - KTA", qty: 850, reserved_qty: 50 },
        ],
        batches: [
          {
            warehouse: "170-W1F-01-01 - KTA",
            batch_no: "KTA26112109",
            qty: 850,
            is_standard_batch: true,
          },
        ],
      };

      const callMock = vi
        .fn()
        .mockResolvedValueOnce({ message: batchResp })
        .mockResolvedValueOnce({ message: warehouseResp })
        .mockResolvedValueOnce({ message: itemResp });
      window.frappe.call = callMock;

      const wrapper = mount(StockLookupView);
      const scanInput = wrapper.find("#pda-barcode-input");

      // 1. Batch lookup
      await scanInput.setValue("SUT-100");
      await scanInput.trigger("keydown.enter");
      await flushPromises();
      expect(wrapper.find('[data-testid="lookup-batch-card"]').exists()).toBe(true);
      expect(wrapper.text()).toContain("KTA26112101");
      expect(wrapper.text()).toContain("LBL-0001");

      // 2. Warehouse lookup
      await scanInput.setValue("170-W1F-02-04");
      await scanInput.trigger("keydown.enter");
      await flushPromises();
      expect(wrapper.find('[data-testid="lookup-warehouse-card"]').exists()).toBe(true);
      expect(wrapper.text()).toContain("ITEM-002");
      expect(wrapper.text()).toContain("1200");

      // 3. Item lookup
      await scanInput.setValue("ITEM-003");
      await scanInput.trigger("keydown.enter");
      await flushPromises();
      expect(wrapper.find('[data-testid="lookup-item-card"]').exists()).toBe(true);
      expect(wrapper.text()).toContain("850");
      expect(wrapper.text()).toContain("KTA26112109");
      wrapper.unmount();
    });
  });

  describe("PackageMergeView", () => {
    it("merges 2 same-lot boxes directly without modal and shows result card", async () => {
      const box1 = makeBoxPayload({
        batch_no: "KTA26112101",
        base_lot: "KTA2611",
        total_qty: 200,
        balances: [{ warehouse: "170-W1F-01-01 - KTA", qty: 200 }],
      });
      const box2 = makeBoxPayload({
        batch_no: "KTA26112102",
        base_lot: "KTA2611",
        sut_barcode: "SUT-101",
        total_qty: 300,
        balances: [{ warehouse: "170-W1F-01-01 - KTA", qty: 300 }],
      });
      const mergeResp = {
        ok: true,
        stock_entry: "MAT-STE-2026-00050",
        item_code: "ITEM-001",
        base_lot: "KTA2611",
        target_batch: "KTA26112103",
        target_warehouse: "170-W1F-01-01 - KTA",
        total_qty: 500,
        is_mixed_lot: false,
        remarks: "Aynı ana lot",
        source_batches: ["KTA26112101", "KTA26112102"],
        target_label_name: "LBL-0005",
        quality_ref: null,
        owner: "pda@example.com",
      };

      const callMock = vi.fn(async (opts: any) => {
        if (opts.method.endsWith("pda_scan_box")) {
          return { message: opts.args.barcode === "SUT-100" ? box1 : box2 };
        }
        if (opts.method.endsWith("pda_package_merge")) {
          return { message: mergeResp };
        }
        return { message: {} };
      });
      window.frappe.call = callMock;

      const wrapper = mount(PackageMergeView);
      expect(wrapper.find('[data-testid="merge-empty-hint"]').exists()).toBe(true);

      const scanInput = wrapper.find("#pda-barcode-input");
      await scanInput.setValue("SUT-100");
      await scanInput.trigger("keydown.enter");
      await flushPromises();

      await scanInput.setValue("SUT-101");
      await scanInput.trigger("keydown.enter");
      await flushPromises();

      expect(wrapper.find('[data-testid="merge-box-row-0"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="merge-box-row-1"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="merge-lot-status"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="merge-mixed-warning"]').exists()).toBe(false);

      await wrapper.find('[data-testid="merge-submit-btn"]').trigger("click");
      await flushPromises();

      expect(
        document.body.querySelector('[data-testid="mixed-lot-confirm-modal"]'),
      ).toBeNull();
      expect(callMock).toHaveBeenCalledWith(
        expect.objectContaining({
          method: "erpnextkta.kta_stock.services.pda_service.pda_package_merge",
          args: {
            source_boxes: [
              {
                batch_no: "KTA26112101",
                warehouse: "170-W1F-01-01 - KTA",
                qty: 200,
              },
              {
                batch_no: "KTA26112102",
                warehouse: "170-W1F-01-01 - KTA",
                qty: 300,
              },
            ],
            target_warehouse_barcode: null,
            allow_mixed_lots: 0,
          },
        }),
      );
      expect(playBeep).toHaveBeenCalledWith(true);
      expect(wrapper.find('[data-testid="merge-result-card"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="merge-result-card"]').text()).toContain(
        "MAT-STE-2026-00050",
      );
      expect(wrapper.find('[data-testid="merge-result-card"]').text()).toContain(
        "KTA26112103",
      );
      wrapper.unmount();
    });

    it("opens mixed-lot modal on different base lots, respects cancel, and submits allow_mixed_lots=1 on confirm", async () => {
      document.body.innerHTML = "";
      const box1 = makeBoxPayload({
        batch_no: "KTA26112101",
        base_lot: "KTA2611",
        total_qty: 100,
        balances: [{ warehouse: "WH-A - KTA", qty: 100 }],
      });
      const box2 = makeBoxPayload({
        batch_no: "KTA26120001",
        base_lot: "KTA2612",
        sut_barcode: "SUT-200",
        total_qty: 250,
        balances: [{ warehouse: "WH-B - KTA", qty: 250 }],
      });
      const mixedResp = {
        ok: true,
        stock_entry: "MAT-STE-2026-00051",
        item_code: "ITEM-001",
        base_lot: "KTA2611",
        target_batch: "KTA26112199",
        target_warehouse: "WH-A - KTA",
        total_qty: 350,
        is_mixed_lot: true,
        remarks: "Karma Lot",
        source_batches: ["KTA26112101", "KTA26120001"],
        quality_ref: "KARMA LOT",
      };

      const callMock = vi.fn(async (opts: any) => {
        if (opts.method.endsWith("pda_scan_box")) {
          return { message: opts.args.barcode === "SUT-100" ? box1 : box2 };
        }
        if (opts.method.endsWith("pda_package_merge")) {
          return { message: mixedResp };
        }
        return { message: {} };
      });
      window.frappe.call = callMock;

      const wrapper = mount(PackageMergeView);
      const scanInput = wrapper.find("#pda-barcode-input");
      await scanInput.setValue("SUT-100");
      await scanInput.trigger("keydown.enter");
      await flushPromises();

      await scanInput.setValue("SUT-200");
      await scanInput.trigger("keydown.enter");
      await flushPromises();

      expect(wrapper.find('[data-testid="merge-mixed-warning"]').exists()).toBe(true);

      await wrapper.find('[data-testid="merge-submit-btn"]').trigger("click");
      await flushPromises();

      const modal = document.body.querySelector('[data-testid="mixed-lot-confirm-modal"]');
      expect(modal).not.toBeNull();
      expect(callMock).not.toHaveBeenCalledWith(
        expect.objectContaining({
          method: "erpnextkta.kta_stock.services.pda_service.pda_package_merge",
        }),
      );

      (
        document.body.querySelector(
          '[data-testid="mixed-lot-cancel-btn"]',
        ) as HTMLElement
      ).click();
      await flushPromises();

      expect(
        document.body.querySelector('[data-testid="mixed-lot-confirm-modal"]'),
      ).toBeNull();
      expect(wrapper.find('[data-testid="merge-box-row-1"]').exists()).toBe(true);

      await wrapper.find('[data-testid="merge-submit-btn"]').trigger("click");
      await flushPromises();
      (
        document.body.querySelector(
          '[data-testid="mixed-lot-confirm-btn"]',
        ) as HTMLElement
      ).click();
      await flushPromises();

      expect(callMock).toHaveBeenCalledWith(
        expect.objectContaining({
          method: "erpnextkta.kta_stock.services.pda_service.pda_package_merge",
          args: expect.objectContaining({
            allow_mixed_lots: 1,
          }),
        }),
      );
      expect(wrapper.find('[data-testid="merge-result-card"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="merge-result-card"]').text()).toContain(
        "KARMA LOT",
      );
      wrapper.unmount();
    });

    it("rejects box with different item_code and plays error beep", async () => {
      const box1 = makeBoxPayload({ item_code: "ITEM-001", batch_no: "KTA26112101" });
      const boxDiff = makeBoxPayload({
        item_code: "ITEM-999",
        batch_no: "KTA26112109",
        sut_barcode: "SUT-999",
      });

      window.frappe.call = vi.fn(async (opts: any) => ({
        message: opts.args.barcode === "SUT-100" ? box1 : boxDiff,
      }));

      const wrapper = mount(PackageMergeView);
      const scanInput = wrapper.find("#pda-barcode-input");
      await scanInput.setValue("SUT-100");
      await scanInput.trigger("keydown.enter");
      await flushPromises();

      await scanInput.setValue("SUT-999");
      await scanInput.trigger("keydown.enter");
      await flushPromises();

      expect(playBeep).toHaveBeenLastCalledWith(false);
      expect(wrapper.find('[data-testid="merge-box-row-0"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="merge-box-row-1"]').exists()).toBe(false);
      expect(wrapper.text()).toContain("Farklı ürün kodlarına ait koliler birleştirilemez.");
      wrapper.unmount();
    });
  });

  describe("PdaHubApp Module Routing", () => {
    it("routes launcher cards to PackageSplitView, PackageMergeView, MaterialTransferView, and StockLookupView", async () => {
      window.__KTA_PDA_BOOT__ = {
        is_locked: false,
        current_user: "pda@example.com",
        active_operator: {
          name: "EMP-0001",
          employee: "EMP-0001",
          employee_name: "Ali Yılmaz",
          department: "Depo",
          user_id: "pda@example.com",
          has_pin: true,
        },
        device_authorized: true,
        inactivity_timeout_sec: 300,
        operators: [],
        open_picking_count: 0,
        menu_categories: [
          {
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
          },
        ],
      };

      const wrapper = mount(PdaHubApp);

      await wrapper.find('[data-testid="module-card-split"]').trigger("click");
      expect(wrapper.findComponent(PackageSplitView).exists()).toBe(true);

      await wrapper.find('[data-testid="topbar-back-btn"]').trigger("click");
      await wrapper.find('[data-testid="module-card-merge"]').trigger("click");
      expect(wrapper.findComponent(PackageMergeView).exists()).toBe(true);

      await wrapper.find('[data-testid="topbar-back-btn"]').trigger("click");
      await wrapper.find('[data-testid="module-card-transfer"]').trigger("click");
      expect(wrapper.findComponent(MaterialTransferView).exists()).toBe(true);

      await wrapper.find('[data-testid="topbar-back-btn"]').trigger("click");
      await wrapper.find('[data-testid="module-card-lookup"]').trigger("click");
      expect(wrapper.findComponent(StockLookupView).exists()).toBe(true);

      wrapper.unmount();
    });
  });
});
