frappe.pages['create-calisma-karti'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: null,
    single_column: true,
  });

  // Developer mode'da hot reload
  if (frappe.boot.developer_mode) {
    if (!Array.isArray(frappe.hot_update)) {
      frappe.hot_update = [];
    }

    // Bu sayfanın Vue loader'ını hot_update listesine ekle
    frappe.hot_update.push(() => load_vue(wrapper));
  }

  // Sayfa ilk yüklendiğinde Vue app'i mount et
  load_vue(wrapper);
};

// ❌ BURADA TEKRAR MOUNT ETMEK UYARIYI TETİKLİYOR
// Eğer gerçekten gerek yoksa tamamen kaldır:
frappe.pages['kta-calisma-karti'].on_page_show = (wrapper) => {
  // load_vue(wrapper); // BUNU ARTIK ÇALIŞTIRMAYALIM
  // İleride istersen burada sadece Vue'ya bir "page-show" event'i emit edebiliriz.
};

async function load_vue(wrapper) {
  const $parent = $(wrapper).find('.layout-main-section');
  const $page_header = $(wrapper).find('.page-head-content');

  // ⬇️ Daha önce mount ettiysek önce unmount et
  if (wrapper.__kta_ck_vue_app__) {
    // Vue 3 createAppInstance:
    // unmount fonksiyonu varsa çağır
    wrapper.__kta_ck_vue_app__.unmount?.();
    wrapper.__kta_ck_vue_app__ = null;
  }

  // Sonra DOM'u temizle
  $parent.empty();
  $page_header.empty();

  // 🔥 Teleport için sabit bir hedef div oluştur
  // Her load_vue çağrısında yeniden yaratılacak
  const $teleport_target = $('<div class="kta-ck-header"></div>').css({width: "100%"});
  $teleport_target.appendTo($page_header);

  await frappe.require('create-calisma-karti.bundle.js');

  const vue_app = frappe.ui.setup_vue($parent);
  wrapper.__kta_ck_vue_app__ = vue_app;
  frappe.test_vue_app = vue_app;
}

