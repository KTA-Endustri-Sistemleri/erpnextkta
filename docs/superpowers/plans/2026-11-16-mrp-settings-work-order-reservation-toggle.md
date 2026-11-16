# KTA MRP Settings: İş Emri Rezervasyonlarını Stoktan Düşme Onay Kutusu Uygulama Planı

- **Hedef:** KTA MRP Settings içine `deduct_work_order_reservations` onay kutusunun eklenmesi, MRP motoru ve servisinin buna göre güncellenmesi, testlerinin yazılması ve dokümantasyon senkronizasyonu.
- **Şartname:** [`docs/superpowers/specs/2026-11-16-mrp-settings-work-order-reservation-toggle-design.md`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/docs/superpowers/specs/2026-11-16-mrp-settings-work-order-reservation-toggle-design.md)

---

## Görevler Listesi

- [x] **Görev 1: KTA MRP Settings Şemasının ve Ayar Okuyucusunun Güncellenmesi (`kta-mrp`)**
  - Dosyalar:
    - `erpnextkta/kta_mrp/doctype/kta_mrp_settings/kta_mrp_settings.json`
    - `erpnextkta/kta_mrp/mrp_engine/settings.py`
  - İşlem:
    - `kta_mrp_settings.json` içinde `sb_supply` altına `deduct_work_order_reservations` (Check, default="1") eklenmesi.
    - `settings.py` içinde `MrpSettings` dataclass'ına ve `get_mrp_settings()`, `resolve_mrp_settings()` fonksiyonlarına alanın eklenmesi.
  - Doğrulama: `test_settings.py` testlerinin yazılması ve geçmesi.

- [x] **Görev 2: MRP Hesaplama Motorunda Serbest Stok Mantığının Güncellenmesi (`kta-mrp`)**
  - Dosyalar:
    - `erpnextkta/kta_mrp/mrp_engine/service.py`
    - `erpnextkta/kta_mrp/tests/test_service.py`
  - İşlem:
    - `MaterialRequirementSummary` veri sınıfına `deduct_reservations: bool = True` eklenmesi ve `free_stock` özelliğinin buna göre hesaplanması.
    - `_build_single_material()` ve `_build_netting_input()` adımlarında `settings.deduct_work_order_reservations` parametresinin uygulanması.
  - Doğrulama: `test_service.py` içinde rezervasyon düşme aktif/pasif durumlarının doğrulanması.

- [x] **Görev 3: Çeviri ve Dokümantasyon Senkronizasyonu (`docs-i18n`)**
  - Dosyalar:
    - `erpnextkta/translations/tr.csv`
    - `erpnextkta/translations/en.csv`
    - `erpnextkta/translations/de.csv`
    - `erpnextkta/www/docs/mrp-settings.html`
    - `docs/mrp_settings.md`
  - İşlem:
    - Yeni etiket ve açıklama çevirilerinin sözlüklere eklenmesi.
    - MRP Ayarları kılavuz sayfalarına parametre açıklamasının eklenmesi.

- [x] **Görev 4: Koordinatör Kalite Kapısı ve Canlı Uygulama**
  - `bench migrate` ile şema güncellemesi.
  - `bench restart` ve `bench --site development.localhost clear-cache`.
  - Otomatik testlerin çalıştırılması ve onaylanması.
