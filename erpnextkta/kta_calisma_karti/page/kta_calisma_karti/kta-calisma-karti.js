frappe.pages['kta-calisma-karti'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: null,
    single_column: true,
  });

  // Developer mode'da hot reload
  if (frappe.boot.developer_mode) {
    // Eğer daha önce tanımlı değilse boş bir dizi olarak oluştur
    if (!Array.isArray(frappe.hot_update)) {
      frappe.hot_update = [];
    }

    // Bu sayfanın Vue loader'ını hot_update listesine ekle
    frappe.hot_update.push(() => load_vue(wrapper));
  }

  // Sayfa ilk yüklendiğinde Vue app'i mount et
  load_vue(wrapper);
};

// Sayfa her gösterildiğinde Vue'yu tekrar yüklemek istersen:
frappe.pages['kta-calismakarti'].on_page_show = (wrapper) => load_vue(wrapper);

// Vue app'i sayfaya yükleyen basit helper
async function load_vue(wrapper) {
  const $parent = $(wrapper).find('.layout-main-section');
  $parent.empty();

  // Bundle'ı yükle ve Vue app'i mount et
  await frappe.require('kta-calisma-karti.bundle.js');
  frappe.test_vue_app = frappe.ui.setup_vue($parent);
}
