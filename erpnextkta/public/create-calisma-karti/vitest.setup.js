import { vi, beforeEach } from 'vitest';

/**
 * Her test öncesi temiz bir frappe global mock oluşturur.
 * frappe.call(config) şeklinde çağrılır; config.callback({ message }) beklenir.
 */
function createFrappeMock() {
  return {
    // Varsayılan: boş listeyle başarılı yanıt
    call: vi.fn(({ callback }) => {
      if (callback) callback({ message: [] });
    }),
    set_route: vi.fn(),
    msgprint: vi.fn(),
    messages: [],
  };
}

// İlk global kurulum
global.frappe = createFrappeMock();

beforeEach(() => {
  const mock = createFrappeMock();
  global.frappe = mock;
  // window.frappe da erişilebilir olsun (App.vue window.frappe kullanıyor)
  Object.defineProperty(window, 'frappe', {
    value: mock,
    writable: true,
    configurable: true,
  });
  // _msgCleaner interval'ını temizle
  if (window._msgCleaner) {
    clearInterval(window._msgCleaner);
    window._msgCleaner = null;
  }
});
