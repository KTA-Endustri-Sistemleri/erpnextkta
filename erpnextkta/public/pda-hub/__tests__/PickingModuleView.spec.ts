import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import PickingModuleView from "../views/PickingModuleView.vue";
import PdaApp from "../../line-replenishment-pda/PdaApp.vue";

vi.mock("../../line-replenishment-pda/utils/audio", () => ({
  playBeep: vi.fn(() => Promise.resolve()),
}));

import { playBeep } from "../../line-replenishment-pda/utils/audio";

function makeOrderDetails(overrides: Record<string, any> = {}) {
  return {
    name: "LRO-2026-0001",
    target_warehouse: "1501 - KTA",
    status: "Draft",
    company: "KTA",
    total_deficit_qty: 1100,
    can_skip_items: false,
    items: [
      {
        name: "ROW-10",
        item_code: "ITEM-A",
        item_name: "Kablo 1",
        uom: "Adet",
        deficit_qty: 500,
        picked_qty: 500,
        is_picked: 0,
        is_skipped: 0,
        is_fifo_override: 0,
        has_batch_no: 1,
        suggested_source_warehouse: "W1A-10-01 - KTA",
        suggested_batch_no: "BATCH-02",
        picked_source_warehouse: "",
        picked_batch_no: "",
      },
      {
        name: "ROW-02",
        item_code: "ITEM-A",
        item_name: "Kablo 1",
        uom: "Adet",
        deficit_qty: 500,
        picked_qty: 500,
        is_picked: 0,
        is_skipped: 0,
        is_fifo_override: 0,
        has_batch_no: 1,
        suggested_source_warehouse: "W1A-02-01 - KTA",
        suggested_batch_no: "BATCH-01",
        picked_source_warehouse: "",
        picked_batch_no: "",
      },
      {
        name: "ROW-NB",
        item_code: "ITEM-NB",
        item_name: "Etiket",
        uom: "Adet",
        deficit_qty: 100,
        picked_qty: 100,
        is_picked: 0,
        is_skipped: 0,
        is_fifo_override: 0,
        has_batch_no: 0,
        suggested_source_warehouse: "W1B-01-01 - KTA",
        suggested_batch_no: "",
        picked_source_warehouse: "",
        picked_batch_no: "",
      },
    ],
    ...overrides,
  };
}

function setupFrappeMock(
  orderDetails: any,
  scanResolver: (barcode: string, orderName?: string) => any,
  completeResult: any = "MAT-STE-2026-00099",
) {
  const callMock = vi.fn(async (opts: any) => {
    const method: string = opts.method || "";
    const run = async () => {
      if (method.endsWith("get_open_replenishment_orders")) {
        return {
          message: [
            {
              name: orderDetails.name,
              target_warehouse: orderDetails.target_warehouse,
              status: orderDetails.status,
              total_deficit_qty: orderDetails.total_deficit_qty,
            },
          ],
        };
      }
      if (method.endsWith("get_replenishment_order_details")) {
        return { message: structuredClone(orderDetails) };
      }
      if (method.endsWith("resolve_scanned_barcode")) {
        return {
          message: scanResolver(opts.args?.barcode, opts.args?.order_name),
        };
      }
      if (method.endsWith("complete_line_replenishment_picking")) {
        return { message: completeResult };
      }
      return { message: {} };
    };

    try {
      const res = await run();
      opts.callback?.(res);
      return res;
    } catch (err) {
      opts.error?.(err);
      throw err;
    }
  });

  window.frappe = {
    call: callMock,
    show_alert: vi.fn(),
    msgprint: vi.fn(),
    confirm: vi.fn((_msg: string, onYes: () => void) => onYes()),
  } as any;

  return callMock;
}

describe("PickingModuleView (Approach A UX, Strict FIFO & Skip RBAC)", () => {
  beforeEach(() => {
    window.__ = (s: string, args?: any[]) => {
      if (!args || !args.length) return s;
      return args.reduce(
        (acc, val, idx) => acc.replace(`{${idx}}`, String(val)),
        s,
      );
    };
    vi.clearAllMocks();
    document.body.innerHTML = "";
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sorts pending cards in natural walk-order and removes manual controls from batch cards while preserving non-batch exception", async () => {
    const order = makeOrderDetails();
    setupFrappeMock(order, () => ({ item_code: null, batch_no: null, qty: 0 }));

    const wrapper = mount(PickingModuleView, { attachTo: document.body });
    await flushPromises();

    const cards = wrapper.findAll('[data-testid^="picking-card-"]');
    expect(cards).toHaveLength(3);
    // Natural walk order: W1A-02-01 (ROW-02) -> W1A-10-01 (ROW-10) -> W1B-01-01 (ROW-NB)
    expect(cards[0].attributes("data-testid")).toBe("picking-card-ROW-02");
    expect(cards[1].attributes("data-testid")).toBe("picking-card-ROW-10");
    expect(cards[2].attributes("data-testid")).toBe("picking-card-ROW-NB");

    // Batch-tracked card (ROW-02): NO checkbox, NO -/+ buttons, NO qty input, NO Tümünü Al
    const batchCard = cards[0];
    expect(batchCard.find('input[type="checkbox"]').exists()).toBe(false);
    expect(batchCard.find(".btn-step-dec").exists()).toBe(false);
    expect(batchCard.find(".btn-step-inc").exists()).toBe(false);
    expect(batchCard.find(".pda-picked-qty-input").exists()).toBe(false);
    expect(batchCard.find(".btn-pick-all").exists()).toBe(false);
    expect(batchCard.text()).toContain("W1A-02-01 - KTA");
    expect(batchCard.text()).toContain("500 Adet");
    expect(batchCard.text()).toContain("ITEM-A");
    expect(batchCard.text()).toContain("BATCH-01");
    expect(batchCard.find('[data-testid="card-skip-btn"]').exists()).toBe(false);

    // Non-batch card (ROW-NB): shows minimal qty input + Onayla button
    const nonBatchCard = cards[2];
    expect(nonBatchCard.find('[data-testid="non-batch-qty-input"]').exists()).toBe(true);
    expect(nonBatchCard.find('[data-testid="confirm-non-batch-btn"]').exists()).toBe(true);
    expect(nonBatchCard.find(".btn-pick-all").exists()).toBe(false);

    wrapper.unmount();
  });

  it("handles out-of-order exact match without false FIFO modal, blocks duplicate scans, and rejects bare item_code for batch items", async () => {
    const order = makeOrderDetails({
      items: [
        makeOrderDetails().items[1], // ROW-02: W1A-02-01, BATCH-01
        makeOrderDetails().items[0], // ROW-10: W1A-10-01, BATCH-02
      ],
    });
    const callMock = setupFrappeMock(order, (barcode) => {
      if (barcode === "BATCH-02") {
        return {
          item_code: "ITEM-A",
          batch_no: "BATCH-02",
          qty: 500,
          warehouse: "W1A-10-01 - KTA",
          has_batch_no: 1,
          available_balances: [{ warehouse: "W1A-10-01 - KTA", qty: 500 }],
        };
      }
      if (barcode === "ITEM-A") {
        return {
          item_code: "ITEM-A",
          batch_no: null,
          qty: 0,
          warehouse: null,
          has_batch_no: 1,
        };
      }
      return { item_code: null, batch_no: null, qty: 0 };
    });

    const wrapper = mount(PickingModuleView, { attachTo: document.body });
    await flushPromises();

    const scanInput = wrapper.find("#pda-barcode-input");

    // 1. Bare item_code scan rejected on batch-tracked item
    await scanInput.setValue("ITEM-A");
    await scanInput.trigger("keydown.enter");
    await flushPromises();
    expect(callMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: expect.stringContaining("resolve_scanned_barcode"),
        args: { barcode: "ITEM-A", order_name: "LRO-2026-0001" },
      }),
    );
    expect(playBeep).toHaveBeenLastCalledWith(false);
    expect(wrapper.text()).toContain("parti takiplidir");

    // 2. Out-of-order exact FIFO scan: BATCH-02 scanned before BATCH-01 -> picks ROW-10 silently without modal!
    await scanInput.setValue("BATCH-02");
    await scanInput.trigger("keydown.enter");
    await flushPromises();
    expect(document.body.querySelector('[data-testid="fifo-override-modal"]')).toBeNull();
    expect(playBeep).toHaveBeenLastCalledWith(true);
    expect(wrapper.find('[data-testid="tab-pending"]').text()).toContain("1");
    expect(wrapper.find('[data-testid="tab-picked"]').text()).toContain("1");

    // 3. Duplicate scan of BATCH-02 does NOT double qty or pick ROW-02
    await scanInput.setValue("BATCH-02");
    await scanInput.trigger("keydown.enter");
    await flushPromises();
    expect(playBeep).toHaveBeenLastCalledWith(false);
    expect(wrapper.text()).toContain("zaten okutuldu");
    expect(wrapper.find('[data-testid="tab-pending"]').text()).toContain("1");
    expect(wrapper.find('[data-testid="tab-picked"]').text()).toContain("1");

    wrapper.unmount();
  });

  it("opens FifoOverrideModal on different batch, supports cancel/confirm with real qty, and resets override state on undo", async () => {
    const order = makeOrderDetails({
      items: [
        {
          name: "ROW-01",
          item_code: "ITEM-A",
          item_name: "Kablo 1",
          uom: "Adet",
          deficit_qty: 100,
          picked_qty: 100,
          is_picked: 0,
          is_skipped: 0,
          is_fifo_override: 0,
          has_batch_no: 1,
          suggested_source_warehouse: "W1A-02-01 - KTA",
          suggested_batch_no: "BATCH-01",
        },
      ],
    });

    const callMock = setupFrappeMock(order, (barcode) => {
      if (barcode === "BATCH-ALT") {
        return {
          item_code: "ITEM-A",
          batch_no: "BATCH-ALT",
          qty: 140,
          warehouse: "W1C-04-02 - KTA",
          has_batch_no: 1,
          available_balances: [{ warehouse: "W1C-04-02 - KTA", qty: 140 }],
        };
      }
      return { item_code: null, batch_no: null, qty: 0 };
    });

    const wrapper = mount(PickingModuleView, { attachTo: document.body });
    await flushPromises();

    const scanInput = wrapper.find("#pda-barcode-input");
    await scanInput.setValue("BATCH-ALT");
    await scanInput.trigger("keydown.enter");
    await flushPromises();

    const modal = document.body.querySelector('[data-testid="fifo-override-modal"]');
    expect(modal).not.toBeNull();
    expect(modal?.textContent).toContain("BATCH-01");
    expect(modal?.textContent).toContain("BATCH-ALT");
    expect(modal?.textContent).toContain("W1C-04-02 - KTA");
    expect(modal?.textContent).toContain("140");

    // Cancel keeps item pending
    (
      document.body.querySelector('[data-testid="fifo-override-cancel-btn"]') as HTMLElement
    ).click();
    await flushPromises();
    expect(document.body.querySelector('[data-testid="fifo-override-modal"]')).toBeNull();
    expect(wrapper.find('[data-testid="tab-pending"]').text()).toContain("1");

    // Scan again and confirm override
    await scanInput.setValue("BATCH-ALT");
    await scanInput.trigger("keydown.enter");
    await flushPromises();
    (
      document.body.querySelector('[data-testid="fifo-override-confirm-btn"]') as HTMLElement
    ).click();
    await flushPromises();

    expect(document.body.querySelector('[data-testid="fifo-override-modal"]')).toBeNull();
    expect(wrapper.find('[data-testid="tab-pending"]').text()).toContain("0");
    expect(wrapper.find('[data-testid="tab-picked"]').text()).toContain("1");
    expect(wrapper.find('[data-testid="picking-ready-banner"]').exists()).toBe(true);

    // Switch to Toplanan tab & verify badge + undo reset
    await wrapper.find('[data-testid="tab-picked"]').trigger("click");
    const pickedCard = wrapper.find('[data-testid="picking-card-ROW-01"]');
    expect(pickedCard.find('[data-testid="fifo-override-badge"]').exists()).toBe(true);
    expect(pickedCard.text()).toContain("140 Adet");
    expect(pickedCard.text()).toContain("BATCH-ALT");

    // Click Undo (↩)
    await pickedCard.find('[data-testid="card-undo-btn"]').trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="tab-pending"]').text()).toContain("1");
    await wrapper.find('[data-testid="tab-pending"]').trigger("click");
    const restoredCard = wrapper.find('[data-testid="picking-card-ROW-01"]');
    expect(restoredCard.text()).toContain("BATCH-01");
    expect(restoredCard.text()).toContain("100 Adet");

    // Re-confirm override and complete transfer -> verify payload includes full box 140 & warehouse
    await scanInput.setValue("BATCH-ALT");
    await scanInput.trigger("keydown.enter");
    await flushPromises();
    (
      document.body.querySelector('[data-testid="fifo-override-confirm-btn"]') as HTMLElement
    ).click();
    await flushPromises();

    const completeBtn = wrapper.find('[data-testid="complete-transfer-btn"]');
    expect((completeBtn.element as HTMLButtonElement).disabled).toBe(false);
    await completeBtn.trigger("click");
    await flushPromises();

    const submitCall = callMock.mock.calls.find(([c]) =>
      String(c.method).endsWith("complete_line_replenishment_picking"),
    );
    expect(submitCall).toBeTruthy();
    const submittedItems = JSON.parse(submitCall![0].args.picked_items);
    expect(submittedItems).toEqual([
      expect.objectContaining({
        name: "ROW-01",
        is_picked: 1,
        is_skipped: 0,
        is_fifo_override: 1,
        picked_batch_no: "BATCH-ALT",
        picked_source_warehouse: "W1C-04-02 - KTA",
        picked_qty: 140,
      }),
    ]);

    wrapper.unmount();
  });

  it("enforces Stock Manager RBAC for skipping, keeps footer locked until all resolved, and switches to Cancel Order when all skipped", async () => {
    const order = makeOrderDetails({
      can_skip_items: true,
      items: [
        {
          name: "ROW-01",
          item_code: "ITEM-A",
          item_name: "Kablo 1",
          uom: "Adet",
          deficit_qty: 200,
          picked_qty: 200,
          is_picked: 0,
          is_skipped: 0,
          has_batch_no: 1,
          suggested_source_warehouse: "W1A-01-01 - KTA",
          suggested_batch_no: "BATCH-01",
        },
        {
          name: "ROW-02",
          item_code: "ITEM-B",
          item_name: "Kablo 2",
          uom: "Adet",
          deficit_qty: 300,
          picked_qty: 300,
          is_picked: 0,
          is_skipped: 0,
          has_batch_no: 1,
          suggested_source_warehouse: "W1A-02-01 - KTA",
          suggested_batch_no: "BATCH-02",
        },
      ],
    });

    const callMock = setupFrappeMock(
      order,
      () => ({ item_code: null, batch_no: null, qty: 0 }),
      "",
    );

    const wrapper = mount(PickingModuleView, { attachTo: document.body });
    await flushPromises();

    const completeBtn = wrapper.find('[data-testid="complete-transfer-btn"]');
    expect((completeBtn.element as HTMLButtonElement).disabled).toBe(true);

    // Skip ROW-01 via SkipItemModal
    await wrapper
      .find('[data-testid="picking-card-ROW-01"] [data-testid="card-skip-btn"]')
      .trigger("click");
    await flushPromises();
    expect(document.body.querySelector('[data-testid="skip-item-modal"]')).not.toBeNull();
    (
      document.body.querySelector('[data-testid="skip-item-confirm-btn"]') as HTMLElement
    ).click();
    await flushPromises();

    expect(wrapper.find('[data-testid="tab-skipped"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="tab-skipped"]').text()).toContain("1");
    // Footer remains disabled because ROW-02 is still pending
    expect((completeBtn.element as HTMLButtonElement).disabled).toBe(true);

    // Skip ROW-02 as well -> all skipped!
    await wrapper
      .find('[data-testid="picking-card-ROW-02"] [data-testid="card-skip-btn"]')
      .trigger("click");
    await flushPromises();
    (
      document.body.querySelector('[data-testid="skip-item-confirm-btn"]') as HTMLElement
    ).click();
    await flushPromises();

    expect((completeBtn.element as HTMLButtonElement).disabled).toBe(false);
    expect(completeBtn.text()).toContain("Emri İptal Et (Tümü Atlandı)");

    await completeBtn.trigger("click");
    await flushPromises();

    const submitCall = callMock.mock.calls.find(([c]) =>
      String(c.method).endsWith("complete_line_replenishment_picking"),
    );
    expect(submitCall).toBeTruthy();
    const submittedItems = JSON.parse(submitCall![0].args.picked_items);
    expect(submittedItems).toHaveLength(2);
    expect(submittedItems.every((r: any) => r.is_skipped === 1 && r.is_picked === 0)).toBe(
      true,
    );

    wrapper.unmount();
  });

  it("blocks disabled/target-warehouse/zero-balance batches and verifies PdaApp parity", async () => {
    const order = makeOrderDetails({
      items: [makeOrderDetails().items[1]],
    });
    setupFrappeMock(order, (barcode) => {
      if (barcode === "B-DISABLED") {
        return {
          item_code: "ITEM-A",
          batch_no: "B-DISABLED",
          qty: 0,
          warehouse: null,
          batch_disabled: true,
          has_batch_no: 1,
        };
      }
      if (barcode === "B-TARGET") {
        return {
          item_code: "ITEM-A",
          batch_no: "B-TARGET",
          qty: 0,
          warehouse: null,
          already_in_target: true,
          has_batch_no: 1,
        };
      }
      return {
        item_code: "ITEM-A",
        batch_no: "B-ZERO",
        qty: 0,
        warehouse: null,
        has_batch_no: 1,
      };
    });

    const wrapper = mount(PdaApp, { attachTo: document.body });
    await flushPromises();

    const scanInput = wrapper.find("#pda-barcode-input");

    await scanInput.setValue("B-DISABLED");
    await scanInput.trigger("keydown.enter");
    await flushPromises();
    expect(wrapper.text()).toContain("pasif durumdadır");

    await scanInput.setValue("B-TARGET");
    await scanInput.trigger("keydown.enter");
    await flushPromises();
    expect(wrapper.text()).toContain("hedef üretim hattında");

    await scanInput.setValue("B-ZERO");
    await scanInput.trigger("keydown.enter");
    await flushPromises();
    expect(wrapper.text()).toContain("kullanılabilir bakiyesi yok");

    wrapper.unmount();
  });

  it("handles unknown/out-of-order barcodes, ignores scans while modal open, confirms non-batch with tolerance guard, and undoes skipped rows", async () => {
    const order = makeOrderDetails({
      can_skip_items: true,
      items: [
        makeOrderDetails().items[1], // ROW-02: batch
        makeOrderDetails().items[2], // ROW-NB: non-batch, deficit 100
      ],
    });
    const callMock = setupFrappeMock(order, (barcode) => {
      if (barcode === "UNKNOWN") return { item_code: null, batch_no: null, qty: 0 };
      if (barcode === "OTHER-ITEM") return { item_code: "ITEM-X", batch_no: null, qty: 0 };
      if (barcode === "BATCH-ALT") {
        return {
          item_code: "ITEM-A",
          batch_no: "BATCH-ALT",
          qty: 500,
          warehouse: "W1C-01-01 - KTA",
          has_batch_no: 1,
        };
      }
      return { item_code: null, batch_no: null, qty: 0 };
    });

    const wrapper = mount(PickingModuleView, { attachTo: document.body });
    await flushPromises();

    const scanInput = wrapper.find("#pda-barcode-input");

    // Unknown barcode
    await scanInput.setValue("UNKNOWN");
    await scanInput.trigger("keydown.enter");
    await flushPromises();
    expect(wrapper.text()).toContain("Barkod tanınamadı");

    // Out-of-order item
    await scanInput.setValue("OTHER-ITEM");
    await scanInput.trigger("keydown.enter");
    await flushPromises();
    expect(wrapper.text()).toContain("bu ikmal emrinde yer almıyor");

    // Non-batch over-tolerance rejected, valid qty confirmed
    const nbCard = wrapper.find('[data-testid="picking-card-ROW-NB"]');
    await nbCard.find('[data-testid="non-batch-qty-input"]').setValue("150");
    expect(nbCard.text()).toContain("Tolerans Aşıldı");
    await nbCard.find('[data-testid="confirm-non-batch-btn"]').trigger("click");
    expect(wrapper.find('[data-testid="tab-picked"]').text()).toContain("0");

    await nbCard.find('[data-testid="non-batch-qty-input"]').setValue("110");
    await nbCard.find('[data-testid="confirm-non-batch-btn"]').trigger("click");
    expect(wrapper.find('[data-testid="tab-picked"]').text()).toContain("1");

    // Open FifoOverrideModal and verify background scan is ignored
    await scanInput.setValue("BATCH-ALT");
    await scanInput.trigger("keydown.enter");
    await flushPromises();
    expect(document.body.querySelector('[data-testid="fifo-override-modal"]')).not.toBeNull();

    const callsBefore = callMock.mock.calls.length;
    await scanInput.setValue("UNKNOWN");
    await scanInput.trigger("keydown.enter");
    await flushPromises();
    expect(callMock.mock.calls.length).toBe(callsBefore);

    (
      document.body.querySelector('[data-testid="fifo-override-cancel-btn"]') as HTMLElement
    ).click();
    await flushPromises();

    // Skip ROW-02 then undo from skipped tab
    await wrapper
      .find('[data-testid="picking-card-ROW-02"] [data-testid="card-skip-btn"]')
      .trigger("click");
    await flushPromises();
    (
      document.body.querySelector('[data-testid="skip-item-confirm-btn"]') as HTMLElement
    ).click();
    await flushPromises();
    expect(wrapper.find('[data-testid="tab-skipped"]').text()).toContain("1");

    await wrapper.find('[data-testid="tab-skipped"]').trigger("click");
    await wrapper
      .find('[data-testid="picking-card-ROW-02"] [data-testid="card-undo-btn"]')
      .trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="tab-pending"]').text()).toContain("1");
    expect(wrapper.find('[data-testid="tab-skipped"]').exists()).toBe(false);

    wrapper.unmount();
  });
});
