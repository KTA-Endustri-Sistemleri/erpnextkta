/**
 * App.vue — API akışları testleri.
 *
 * frappe.call mock'lanarak fetchWorkOrderByBarcode,
 * fetchJobCardByBarcode ve submitWorkCard fonksiyonları
 * deterministik olarak test edilir.
 *
 * withLoading içindeki setTimeout gecikmesini atlamak için
 * vi.useFakeTimers() kullanılır.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import App from '../App.vue';

const STUBS = {
  Teleport: true,
  Transition: true,
  StepWorkOrder: true,
  StepJobCard: true,
  StepOperation: true,
  StepWorkstation: true,
  StepUser: true,
  StepIndicator: true,
  StepJobCardSearch: true,
};

/**
 * Gerçek timer ortamında mount et (onMounted _msgCleaner setInterval için),
 * ardından _msgCleaner'ı temizle ve fake timer'a geç.
 */
async function mountApp() {
  vi.useRealTimers();
  const wrapper = mount(App, {
    global: { stubs: STUBS },
    attachTo: document.body,
  });
  await flushPromises();

  // setInterval _msgCleaner fake timer ile çakışmasın diye temizle
  if (window._msgCleaner) {
    clearInterval(window._msgCleaner);
    window._msgCleaner = null;
  }
  vi.useFakeTimers();
  // withLoading'in minMs (700ms) delay'ini tamamla ki loading=false olsun
  await vi.runAllTimersAsync();
  await flushPromises();
  wrapper.vm.loading = false; // Gerçek timer'dan kalan loading state'i sıfırla
  return wrapper;
}

/**
 * frappe.call'u mock'la:
 * - data varsa callback({message: data}) çağırır
 * - error varsa error handler'ı çağırır
 */
function mockFrappeCall(responses) {
  let callIndex = 0;
  frappe.call.mockImplementation(({ callback, error }) => {
    const resp = responses[callIndex] ?? responses[responses.length - 1];
    callIndex++;
    if (resp.error) {
      if (error) error(resp.error);
    } else {
      if (callback) callback({ message: resp.data });
    }
  });
  // Mock kurulduktan sonra önceki çağrıları sil
  frappe.call.mockClear();
}

afterEach(() => {
  vi.useRealTimers();
});

// ──────────────────────────────────────────────────────────────────────────────
// fetchWorkOrderByBarcode
// ──────────────────────────────────────────────────────────────────────────────
describe('fetchWorkOrderByBarcode', () => {
  it('başarılı: workOrder state güncellenir ve step 2\'ye geçer', async () => {
    const WO_DATA = { name: 'MFG-WO-001', production_item: 'ITEM-A', qty: 10 };

    const wrapper = await mountApp();
    // 1. çağrı: get_work_order_by_barcode → WO döner
    // 2. çağrı: frappe.client.get_list → JC listesi döner
    mockFrappeCall([
      { data: WO_DATA },
      { data: [{ name: 'JC-001', workstation: 'IST-01' }] },
    ]);

    wrapper.vm.workOrderBarcode = 'MFG-WO-001';
    const p = wrapper.vm.fetchWorkOrderByBarcode();
    await vi.runAllTimersAsync();
    await flushPromises();
    await p;

    expect(wrapper.vm.workOrder).toMatchObject({ name: 'MFG-WO-001' });
    expect(wrapper.vm.currentStep).toBe(2);
    expect(wrapper.vm.errorMessage).toBeNull();
  });

  it('API hata döndürünce errorMessage set, workOrder null kalır', async () => {
    const wrapper = await mountApp();
    mockFrappeCall([{ error: { message: 'Work Order MFG-001 not found' } }]);

    wrapper.vm.workOrderBarcode = 'MFG-WO-999';
    const p = wrapper.vm.fetchWorkOrderByBarcode();
    await vi.runAllTimersAsync();
    await flushPromises();
    await p.catch(() => {});

    expect(wrapper.vm.workOrder).toBeNull();
    expect(wrapper.vm.errorMessage).toBeTruthy();
  });

  it('boş barkod ile çağrılınca hiçbir şey yapılmaz', async () => {
    const wrapper = await mountApp();
    frappe.call.mockClear(); // mountApp'teki fetchUsers çağrısını sıfırla
    wrapper.vm.workOrderBarcode = '   ';
    await wrapper.vm.fetchWorkOrderByBarcode();
    expect(frappe.call).not.toHaveBeenCalled();
  });

  it('smart prefix: "2026-00123" → "MFG-WO-2026-00123" gönderilir', async () => {
    const wrapper = await mountApp();
    mockFrappeCall([
      { data: { name: 'MFG-WO-2026-00123' } },
      { data: [] },
    ]);

    wrapper.vm.workOrderBarcode = '2026-00123';
    const p = wrapper.vm.fetchWorkOrderByBarcode();
    await vi.runAllTimersAsync();
    await flushPromises();
    await p.catch(() => {});

    // workOrderBarcode değeri prefix eklenmiş olmalı
    expect(wrapper.vm.workOrderBarcode).toBe('MFG-WO-2026-00123');
    // frappe.call'un ilk çağrısı doğru args ile yapılmalı
    const firstCall = frappe.call.mock.calls[0][0];
    expect(firstCall.args.barcode).toBe('MFG-WO-2026-00123');
  });

  it('tek JC varsa otomatik seçilir', async () => {
    const wrapper = await mountApp();
    mockFrappeCall([
      { data: { name: 'MFG-WO-001' } },
      { data: [{ name: 'JC-ONLY', workstation: 'IST-01' }] },
    ]);

    wrapper.vm.workOrderBarcode = 'MFG-WO-001';
    const p = wrapper.vm.fetchWorkOrderByBarcode();
    await vi.runAllTimersAsync();
    await flushPromises();
    await p.catch(() => {});

    expect(wrapper.vm.selectedJobCardName).toBe('JC-ONLY');
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// fetchJobCardByBarcode
// ──────────────────────────────────────────────────────────────────────────────
describe('fetchJobCardByBarcode', () => {
  it('başarılı: jobCards, workOrder ve currentStep güncellenir', async () => {
    const JC_DATA = {
      job_card: 'JC-001',
      work_order: 'WO-001',
      workstation: 'IST-01',
      production_item: 'ITEM-X',
      for_quantity: 5,
      customer_group: 'Grup A',
      customer_groups: ['Grup A'],
    };

    const wrapper = await mountApp();
    wrapper.vm.setSearchMode('JC');
    await flushPromises();

    // 1: get_job_card_by_barcode, 2: get_operations_for_job_card
    mockFrappeCall([
      { data: JC_DATA },
      { data: [{ name: 'OP-001', calisma_karti_op: 'Kaynak' }] },
    ]);

    wrapper.vm.jobCardBarcode = 'JC-001';
    const p = wrapper.vm.fetchJobCardByBarcode();
    await vi.runAllTimersAsync();
    await flushPromises();
    await p.catch(() => {});

    expect(wrapper.vm.selectedJobCardName).toBe('JC-001');
    expect(wrapper.vm.workOrder).toMatchObject({ name: 'WO-001' });
    expect(wrapper.vm.selectedWorkstation).toBe('IST-01');
    expect(wrapper.vm.currentStep).toBe(2);
  });

  it('smart prefix: "JOB16115" → "PO-JOB16115" gönderilir', async () => {
    const wrapper = await mountApp();
    wrapper.vm.setSearchMode('JC');
    mockFrappeCall([
      { data: { job_card: 'PO-JOB16115', work_order: 'WO-01' } },
      { data: [] },
    ]);

    wrapper.vm.jobCardBarcode = 'JOB16115';
    const p = wrapper.vm.fetchJobCardByBarcode();
    await vi.runAllTimersAsync();
    await flushPromises();
    await p.catch(() => {});

    expect(wrapper.vm.jobCardBarcode).toBe('PO-JOB16115');
  });

  it('API null döndürünce errorMessage set edilir', async () => {
    const wrapper = await mountApp();
    wrapper.vm.setSearchMode('JC');
    mockFrappeCall([{ data: null }]);

    wrapper.vm.jobCardBarcode = 'JC-NOTEXIST';
    const p = wrapper.vm.fetchJobCardByBarcode();
    await vi.runAllTimersAsync();
    await flushPromises();
    await p.catch(() => {});

    expect(wrapper.vm.errorMessage).toBeTruthy();
    expect(wrapper.vm.selectedJobCardName).toBeNull();
  });

  it('boş barkod ile hiçbir şey yapılmaz', async () => {
    const wrapper = await mountApp();
    frappe.call.mockClear();
    wrapper.vm.setSearchMode('JC');
    wrapper.vm.jobCardBarcode = '';
    await wrapper.vm.fetchJobCardByBarcode();
    expect(frappe.call).not.toHaveBeenCalled();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// submitWorkCard
// ──────────────────────────────────────────────────────────────────────────────
describe('submitWorkCard', () => {
  /**
   * selectedJobCardName set edilince watcher fetchOperationsForJobCard çağırır.
   * Bu nedenle mock listesine operasyon yanıtını da ekliyoruz (ilk sıraya).
   */
  async function setupReadyWizard(wrapper, submitResponse) {
    // Önce mock'u kur: 1. ops fetch (watcher), 2. submit çağrısı
    frappe.call.mockImplementation(({ callback }) => {
      if (callback) callback({ message: submitResponse ?? [] });
    });
    frappe.call.mockClear();

    wrapper.vm.workOrder = { name: 'WO-001' };
    wrapper.vm.jobCards = [{ name: 'JC-001', workstation: 'IST-01' }];
    // selectedJobCardName watch → fetchOperationsForJobCard tetiklenir
    wrapper.vm.selectedJobCardName = 'JC-001';
    wrapper.vm.selectedWorkstation = 'IST-01';
    wrapper.vm.selectedOperationName = 'KTA-OP-001';
    wrapper.vm.selectedUser = 'EMP-001';
    wrapper.vm.currentStep = 5;
    await vi.runAllTimersAsync();
    await flushPromises();
    // Watcher çağrılarını sıfırla; sadece submit çağrısı sayılsın
    frappe.call.mockClear();
  }

  it('başarılı: createdDoc set edilir', async () => {
    const wrapper = await mountApp();
    const DOC = { name: 'CK-0001', _is_existing: false };
    await setupReadyWizard(wrapper);

    frappe.call.mockImplementation(({ callback }) => {
      if (callback) callback({ message: DOC });
    });

    const p = wrapper.vm.submitWorkCard();
    await vi.runAllTimersAsync();
    await flushPromises();
    await p;

    expect(wrapper.vm.createdDoc).toMatchObject({ name: 'CK-0001' });
    expect(wrapper.vm.errorMessage).toBeNull();
  });

  it('mevcut kart: _is_existing=true olarak gelir', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    frappe.call.mockImplementation(({ callback }) => {
      if (callback) callback({ message: { name: 'CK-0001', _is_existing: true } });
    });

    const p = wrapper.vm.submitWorkCard();
    await vi.runAllTimersAsync();
    await flushPromises();
    await p;

    expect(wrapper.vm.createdDoc._is_existing).toBe(true);
  });

  it('API hatasında errorMessage set, createdDoc null kalır', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    frappe.call.mockImplementation(({ error }) => {
      if (error) error({ message: 'Yetki yetersiz.' });
    });

    const p = wrapper.vm.submitWorkCard();
    await vi.runAllTimersAsync();
    await flushPromises();
    await p.catch(() => {});

    expect(wrapper.vm.createdDoc).toBeNull();
    expect(wrapper.vm.errorMessage).toBeTruthy();
  });

  it('step geçersizken submit çağrılınca frappe.call yapılmaz', async () => {
    const wrapper = await mountApp();
    frappe.call.mockClear();
    wrapper.vm.currentStep = 5;
    wrapper.vm.selectedUser = null;
    await flushPromises();

    await wrapper.vm.submitWorkCard();
    expect(frappe.call).not.toHaveBeenCalled();
  });

  it('zaten createdDoc varken tekrar submit yapılmaz', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);
    frappe.call.mockClear();
    wrapper.vm.createdDoc = { name: 'CK-MEVCUT' };
    await flushPromises();

    await wrapper.vm.submitWorkCard();
    expect(frappe.call).not.toHaveBeenCalled();
  });
});
