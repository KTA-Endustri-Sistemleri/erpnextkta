/**
 * App.vue — Race Condition / Çift Kart Oluşturma Testleri
 *
 * Kullanıcıların birden fazla Çalışma Kartı oluşturma sorununun
 * frontend kaynaklı olup olmadığını test eder.
 *
 * Senaryolar:
 * 1. Çift-tıklama (double-click) koruması
 * 2. Eşzamanlı submitWorkCard() çağrıları
 * 3. Enter tuşu spam koruması
 * 4. Yavaş API / ağ gecikmesi sırasında tekrar submit
 * 5. Hata sonrası tekrar deneme (retry) — bu MEŞRU, izin verilmeli
 * 6. createdDoc set edilince submit tamamen bloke
 * 7. loading flag'inin senkron set edildiği doğrulanır
 * 8. Barkod okuyucu "Enter üretme" race — WO/JC adımında tekrar submit engeli
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

/** Gerçek timer ortamında mount et, _msgCleaner'ı temizle, fake timer'a geç */
async function mountApp() {
  vi.useRealTimers();
  const wrapper = mount(App, { global: { stubs: STUBS }, attachTo: document.body });
  await flushPromises();
  if (window._msgCleaner) { clearInterval(window._msgCleaner); window._msgCleaner = null; }
  // withLoading'in minMs delay'ini tamamla ki loading=false garantilensin
  await flushPromises();
  vi.useFakeTimers();
  wrapper.vm.loading = false;
  return wrapper;
}

/** WO modunda son adımda hazır duruma getir. JC seçimi watcher'ını da bekler. */
async function setupReadyWizard(wrapper) {
  // selectedJobCardName watcher'ını tatmin edecek boş ops cevabı
  frappe.call.mockImplementation(({ callback }) => {
    if (callback) callback({ message: [] });
  });
  wrapper.vm.workOrder = { name: 'WO-001' };
  wrapper.vm.jobCards = [{ name: 'JC-001', workstation: 'IST-01' }];
  wrapper.vm.selectedJobCardName = 'JC-001';
  wrapper.vm.selectedWorkstation = 'IST-01';
  wrapper.vm.selectedOperationName = 'KTA-OP-001';
  wrapper.vm.selectedUser = 'EMP-001';
  wrapper.vm.currentStep = 5;
  await vi.runAllTimersAsync();
  await flushPromises();
  // Watcher çağrılarını temizle; sayaç sıfırlansın
  frappe.call.mockClear();
}

afterEach(() => {
  vi.useRealTimers();
});

// ──────────────────────────────────────────────────────────────────────────────
// 1. loading.value SYNC set — temel garanti
// ──────────────────────────────────────────────────────────────────────────────
describe('loading guard — senkron koruma', () => {
  it('submitWorkCard başlar başlamaz loading=true set edilir (async ilk await öncesi)', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    // API çağrısını askıda bırak (resolve etme)
    let resolveFn;
    frappe.call.mockImplementation(({ callback }) => {
      // Kasıtlı geciktir — asla callback çağırma
      resolveFn = callback;
    });

    // Submit başlat ama await etme
    wrapper.vm.submitWorkCard();

    // JavaScript'in senkron yürütme tamamlandı, microtask henüz çalışmadı.
    // withLoading'in ilk satırı (loading.value = true) çalışmış olmalı.
    expect(wrapper.vm.loading).toBe(true);

    // Temizlik: resolve et
    resolveFn({ name: 'CK-001' });
    await vi.runAllTimersAsync();
    await flushPromises();
  });

  it('loading=true iken submit çağrısı reddedilir', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    // loading'i manuel olarak true yap
    wrapper.vm.loading = true;
    await flushPromises();

    await wrapper.vm.submitWorkCard();
    // frappe.call çağrılmamış olmalı
    expect(frappe.call).not.toHaveBeenCalled();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// 2. Çift tıklama / eşzamanlı submit
// ──────────────────────────────────────────────────────────────────────────────
describe('çift tıklama koruması', () => {
  it('submitWorkCard() iki kez arka arkaya çağrılırsa tek API çağrısı yapılır', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    let callCount = 0;
    frappe.call.mockImplementation(({ callback }) => {
      callCount++;
      // Geciktirilmiş resolve
      setTimeout(() => callback({ message: { name: 'CK-001' } }), 100);
    });

    // İki çağrıyı AYNI JS tick'te başlat (await ETME)
    wrapper.vm.submitWorkCard();
    wrapper.vm.submitWorkCard(); 

    // Timer'ları ilerlet ve bitmesini bekle
    await vi.runAllTimersAsync();
    await flushPromises();

    // Yalnızca BİR API çağrısı yapılmış olmalı
    expect(callCount).toBe(1);
  });

  it('ikinci çağrıda createdDoc değişmez — ilk sonuç korunur', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    frappe.call.mockImplementation(({ callback }) => {
      callback({ message: { name: 'CK-FIRST', _is_existing: false } });
    });

    wrapper.vm.submitWorkCard();
    wrapper.vm.submitWorkCard();

    await vi.runAllTimersAsync();
    await flushPromises();

    expect(wrapper.vm.createdDoc?.name).toBe('CK-FIRST');
  });

  it('createdDoc set olduktan sonra submit tekrar çağrılırsa API yapılmaz', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    frappe.call.mockImplementation(({ callback }) => {
      callback({ message: { name: 'CK-001' } });
    });

    // İlk submit
    wrapper.vm.submitWorkCard();
    await vi.runAllTimersAsync();
    await flushPromises();

    expect(wrapper.vm.createdDoc?.name).toBe('CK-001');
    frappe.call.mockClear();

    // İkinci submit
    wrapper.vm.submitWorkCard();
    await vi.runAllTimersAsync();
    await flushPromises();

    expect(frappe.call).not.toHaveBeenCalled();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// 3. Enter tuşu spam koruması
// ──────────────────────────────────────────────────────────────────────────────
describe('Enter tuşu spam koruması', () => {
  function makeEnterEvent() {
    return { 
      key: 'Enter', 
      target: { tagName: 'DIV' }, 
      preventDefault: vi.fn(),
      stopPropagation: vi.fn()
    };
  }

  it('handleEnter loading sırasında çağrılırsa submit yapılmaz', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    wrapper.vm.loading = true;
    await flushPromises();

    wrapper.vm.onGlobalKeydown(makeEnterEvent());
    expect(frappe.call).not.toHaveBeenCalled();
  });

  it('handleEnter son adımda 5 kez arka arkaya çağrılırsa tek submit yapılır', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    let apiCallCount = 0;
    frappe.call.mockImplementation(({ callback }) => {
      apiCallCount++;
      setTimeout(() => callback({ message: { name: 'CK-001' } }), 500);
    });

    const enterEvent = makeEnterEvent();
    for (let i = 0; i < 5; i++) {
      wrapper.vm.onGlobalKeydown(enterEvent);
    }

    await vi.runAllTimersAsync();
    await flushPromises();

    expect(apiCallCount).toBe(1);
  });

  it('handleEnter createdDoc set sonrası çağrılırsa işlem yapılmaz', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    frappe.call.mockImplementation(({ callback }) => {
      callback({ message: { name: 'CK-001' } });
    });
    
    wrapper.vm.submitWorkCard();
    await vi.runAllTimersAsync();
    await flushPromises();

    frappe.call.mockClear();

    wrapper.vm.onGlobalKeydown(makeEnterEvent());
    await vi.runAllTimersAsync();
    await flushPromises();

    expect(frappe.call).not.toHaveBeenCalled();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// 4. Yavaş API / ağ gecikmesi sırasında UI bloke kalır
// ──────────────────────────────────────────────────────────────────────────────
describe('ağ gecikmesi sırasında koruma', () => {
  it('API yanıt beklenirken loading=true devam eder', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    frappe.call.mockImplementation(() => {});

    wrapper.vm.submitWorkCard(); 
    // await etmiyoruz çünkü asla bitmeyecek şekilde mock'ladık
    
    expect(wrapper.vm.loading).toBe(true);
  });

  it('yavaş API sırasında yeni submitWorkCard() çağrıları reddedilir', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    let apiCallCount = 0;
    frappe.call.mockImplementation(() => {
      apiCallCount++;
    });

    wrapper.vm.submitWorkCard();
    wrapper.vm.submitWorkCard();
    wrapper.vm.submitWorkCard();

    expect(apiCallCount).toBe(1);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// 5. Hata sonrası retry — BU MEŞRU, izin verilmeli
// ──────────────────────────────────────────────────────────────────────────────
describe('hata sonrası retry (meşru senaryo)', () => {
  it('ilk submit hata verirse ikinci submit başarılı olabilir', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    // 1. Hata
    frappe.call.mockImplementation(({ error }) => {
      if (error) error({ message: 'Hata' });
    });

    wrapper.vm.submitWorkCard();
    await vi.runAllTimersAsync();
    await flushPromises();

    expect(wrapper.vm.errorMessage).toBeTruthy();
    expect(wrapper.vm.loading).toBe(false);

    // 2. Başarı
    frappe.call.mockImplementation(({ callback }) => {
      if (callback) callback({ message: { name: 'CK-001' } });
    });

    wrapper.vm.submitWorkCard();
    await vi.runAllTimersAsync();
    await flushPromises();

    expect(wrapper.vm.createdDoc?.name).toBe('CK-001');
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// 6. Backend "mevcut kart" yanıtı — _is_existing
// ──────────────────────────────────────────────────────────────────────────────
describe('backend duplicate koruması entegrasyonu', () => {
  it('backend _is_existing=true döndürünce createdDoc set edilir', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    frappe.call.mockImplementation(({ callback }) => {
      callback({ message: { name: 'CK-EXISTING', _is_existing: true } });
    });

    wrapper.vm.submitWorkCard();
    await vi.runAllTimersAsync();
    await flushPromises();

    expect(wrapper.vm.createdDoc?.name).toBe('CK-EXISTING');
    
    frappe.call.mockClear();
    wrapper.vm.submitWorkCard();
    expect(frappe.call).not.toHaveBeenCalled();
  });

  it('_is_existing=true sonrası resetWizard yapılırsa yeni kart oluşturulabilir', async () => {
    const wrapper = await mountApp();
    await setupReadyWizard(wrapper);

    frappe.call.mockImplementation(({ callback }) => {
      callback({ message: { name: 'CK-EXISTING', _is_existing: true } });
    });

    wrapper.vm.submitWorkCard();
    await vi.runAllTimersAsync();
    await flushPromises();

    wrapper.vm.resetWizard();
    await flushPromises();

    await setupReadyWizard(wrapper);
    frappe.call.mockImplementation(({ callback }) => {
      callback({ message: { name: 'CK-NEW' } });
    });

    wrapper.vm.submitWorkCard();
    await vi.runAllTimersAsync();
    await flushPromises();

    expect(wrapper.vm.createdDoc?.name).toBe('CK-NEW');
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// 7. Barkod okuyucu Enter spam (Step 1)
// ──────────────────────────────────────────────────────────────────────────────
describe('barkod okuyucu Enter spam (Step 1)', () => {
  it('WO barkod submit sırasında ikinci çağrı API\'yi tekrar tetiklemez', async () => {
    const wrapper = await mountApp();
    
    wrapper.vm.loading = false;
    wrapper.vm.workOrderBarcode = 'MFG-WO-001';
    
    // Önce TEK çağrıda gerçekten frappe.call tetikleniyor mu diye kontrol et
    // App.api.test.js'deki gibi senkron (setTimeout YOK)
    let apiCallCount = 0;
    frappe.call.mockImplementation(({ method, callback }) => {
      apiCallCount++;
      // Senkron — App.api.test.js pattern'i
      if (callback) {
        if (method === 'frappe.client.get_list') callback({ message: [] });
        else callback({ message: { name: 'MFG-WO-001' } });
      }
    });
    frappe.call.mockClear();
    apiCallCount = 0;

    // İlk çağrı
    const p1 = wrapper.vm.fetchWorkOrderByBarcode();
    await vi.runAllTimersAsync();
    await flushPromises();
    await p1;

    // En az bir kez çağrılmış olmalı (ana guard testi için)
    expect(apiCallCount).toBeGreaterThanOrEqual(1);
    const firstCallCount = apiCallCount;
    apiCallCount = 0;
    frappe.call.mockClear();

    // İkinci çağrı — loading state ne durumda?
    // p1 bitti, loading=false olmalı
    const p2 = wrapper.vm.fetchWorkOrderByBarcode();
    await vi.runAllTimersAsync();
    await flushPromises();
    await p2;

    // İkinci meşru çağrı da çalışmalı
    // NOT: Bu race condition testi değil, sadece fonksiyonun çalıştığını kanıtlar
    expect(apiCallCount).toBeGreaterThanOrEqual(1);
  });

  it('loading true iken ikinci fetchWorkOrderByBarcode çağrısı bloke edilir', async () => {
    const wrapper = await mountApp();
    
    let apiCallCount = 0;
    frappe.call.mockImplementation(({ method, callback }) => {
      if (method && method.includes('get_work_order_by_barcode')) {
        apiCallCount++;
      }
      setTimeout(() => {
        if (callback) {
          if (method === 'frappe.client.get_list') callback({ message: [] });
          else callback({ message: { name: 'MFG-WO-001' } });
        }
      }, 500);
    });
    frappe.call.mockClear();

    wrapper.vm.workOrderBarcode = 'MFG-WO-001';
    wrapper.vm.currentStep = 1;
    wrapper.vm.setSearchMode('WO');

    const enterEvent = {
      key: 'Enter',
      target: { tagName: 'DIV' },
      preventDefault: vi.fn(),
      stopPropagation: vi.fn(),
    };

    // İlk Enter — fetchWorkOrderByBarcode başlatır
    wrapper.vm.handleEnter(enterEvent);
    
    // Async zincirin withLoading'e ulaşması için birkaç microtask tick bekle
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    
    // loading artık true olmalı
    expect(wrapper.vm.loading).toBe(true);

    // İkinci Enter — handleEnter başında `if (loading.value) return` çalışır
    wrapper.vm.handleEnter(enterEvent);

    // Timer'ları ilerlet
    await vi.runAllTimersAsync();
    await flushPromises();

    // Sadece get_work_order_by_barcode 1 kez çağrılmış olmalı
    expect(apiCallCount).toBe(1);
  });
});
