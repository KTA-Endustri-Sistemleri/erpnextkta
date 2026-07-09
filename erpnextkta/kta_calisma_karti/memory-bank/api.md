# API Reference — kta_calisma_karti

Frontend method path prefix: `erpnextkta.kta_calisma_karti.api.`

## Liste & Detay

| Fonksiyon | Parametreler | Döner | Yetki |
|-----------|-------------|-------|-------|
| `get_my_calisma_kartlari` | `order_by`, `start`, `page_length`, `customer_group` | `[{name, operator, durum, ...}]` | Herkese açık (filtreli) | |
| `get_calisma_karti_detail` | `name` | `{name, hurdalar, duruslar, alt_operasyon_kayitlari[{..., alt_operasyon_title, alt_operasyon_sequence}], max_kart_suresi_dk, kart_uyari_suresi_dk, ...}` | Operator | |

## Oluşturma

| Fonksiyon | Parametreler | Döner | Yetki |
|-----------|-------------|-------|-------|
| `create_calisma_karti` | `is_karti`, `operasyon`, `is_istasyonu`, `custom_work_order?`, `operator?` | CK dict | Manufacturing User | [Test Doğrulandı] |
| `get_operations_for_job_card` | `job_card` | `[{name, calisma_karti_op, customer_group, sequence}]` — JC'ye göre filtrelenmiş | Herkese açık | |

## Barkod

| Fonksiyon | Parametreler | Döner | Yetki |
|-----------|-------------|-------|-------|
| `get_job_card_by_barcode` | `barcode` | JC + WO payload | JC read |
| `get_work_order_by_barcode` | `barcode` | WO payload | WO read |

## Hurda

| Fonksiyon | Parametreler | Yetki |
|-----------|-------------|-------|
| `get_hurda_nedeni_options` | `parent_cost_center?` | Herkese açık |
| `search_allowed_hurda_items` | `doctype, txt, searchfield, start, page_len, filters{calisma_karti}` | Operator |
| `add_hurda` | `name, parca_no, hurda_nedeni, miktar, birim, depo?` | Operator | [Test Doğrulandı] |
| `update_hurda` | `name, rowname, parca_no, hurda_nedeni, miktar, birim, depo?` | Operator | |
| `delete_hurda` | `name, rowname` | Operator | [Test Doğrulandı] |

## Kalite Kontrol

> **Not:** `update_kalite_kontrol` hâlâ sadece QC/QM/SM rolleri ile sınırlıdır.  
> IDC ve barkod CRUD işlemleri için operatör de kendi kartına erişebilir.

| Fonksiyon | Parametreler | Yetki |
|-----------|-------------|-------|
| `update_kalite_kontrol` | `name, kalite_kontrol` | KTA Kalite / QM / SM |
| `search_allowed_idc_items` | `doctype, txt, searchfield, start, page_len, filters{calisma_karti}` | Kart okuma yetkisi olan herkes |
| `add_idc_olcumu` | `name, item_code, yukseklik_mm=0, cekme_n=0` | Operator / SM / QC |
| `update_idc_olcumu` | `name, rowname, item_code, yukseklik_mm=0, cekme_n=0` | Operator / SM / QC |
| `delete_idc_olcumu` | `name, rowname` | Operator / SM / QC |
| `add_barkod_kaydi` | `name, barcode` | KTA Kalite / QM / SM |
| `update_barkod_kaydi` | `name, rowname, barcode` | KTA Kalite / QM / SM |
| `delete_barkod_kaydi` | `name, rowname` | KTA Kalite / QM / SM |
| `get_qc_templates_for_ck` | `ck_name` | `{templates: [], default_template, item_code}` | Herkese açık |
| `get_template_details` | `template_name` | `[{specification, numeric, min, max, ...}]` | Herkese açık |
| `submit_kta_quality_inspection`| `ck_name, template_name, readings, sample_size=1, intent="approve"` | MAT-QA link + status (Draft) | KTA Kalite / QM / SM | [Test Doğrulandı] |

## Alt Operasyon

docs> **Not:** `hammadde`, `boyut_x_mm`, `islem_adedi_x`, `note` opsiyonel. `islem_adedi` varsayılan `0`.  
> `hammadde`, `hammadde_2`, `hammadde_3` girilirse `_assert_hammadde_allowed()` ile material group kısıtı uygulanır. UOM arka planda otomatik çekilir.

| Fonksiyon | Parametreler | Yetki |
|-----------|-------------|-------|
| `add_alt_operasyon_kaydi` | `calisma_karti, alt_operasyon, hammadde(1-3)=None, boyut_(1-3)_mm=0, islem_adedi_(1-3)=0, note=None` | Operator / SM / QC | [Test Doğrulandı] |
| `update_alt_operasyon_kaydi` | `calisma_karti, row_id, alt_operasyon, hammadde(1-3)=None, boyut_(1-3)_mm=0, islem_adedi_(1-3)=0, note=None` | Operator / SM / QC | |
| `delete_alt_operasyon_kaydi` | `calisma_karti, row_id` | Operator / SM / QC | [Test Doğrulandı] |
| `search_allowed_hammadde_items` | `filters{calisma_karti, alt_operasyon}` — sub-op grubu tanımlıysa o grup; boşsa sequence çözümlemesi | Herkese açık (Link search) |

## Realtime Events

| Event | Tetikleyici | Dinleyen |
|-------|------------|---------|
| `kta_calisma_karti:list_changed` | her create/update/qc sonrası | list SPA |
| `kta_calisma_karti:doc_changed:{name}` | aynı, docname ile | view SPA |

## Dahili Hooklar & Zamanlanmış Görevler (Internal Hooks & Scheduled Tasks)

Bu fonksiyonlar `hooks.py`, DocType controller veya Frappe Scheduler üzerinden otomatik tetiklenir:

| Fonksiyon | Tetikleyici / Zamanlayıcı | Açıklama |
|-----------|------------|----------|
| `sync_stock_entry_to_calisma_karti` | `Stock Entry` (on_update) | SE'den yapılan manuel değişiklikleri CK'ya senkronize eder. |
| `sync_calisma_karti_hurdalar_to_se` | `Calisma Karti` (on_update / after_submit) | CK tablosundaki değişiklikleri SE'ye senkronize eder. |
| `on_stock_entry_trash` | `Stock Entry` (on_trash) | SE silindiğinde CK üzerindeki linki temizler. |
| `get_dashboard_data` | `override_doctype_dashboards` (User) | User dashboard yapısına `Calisma Karti`'ni bağlar. |
| `get_open_count` | Whitelisted API (User dashboard) | Kullanıcıya bağlı Employee'ler üzerinden açık Çalışma Kartı sayısı ve isim listesini döner. |
| `auto_close_timed_out_cards` | Cron (`15 0,16 * * *`) | Vardiya sonlarında açık kalan kartları (duruşta ise duruş başlangıcında, çalışıyorsa vardiya sonu saatinde) kapatır. |
| `delete_old_unstarted_cards` | Cron (`0 4 * * *`) | +24 saattir `Hazır` statüsünde kalmış ve hiç başlatılmamış kartları `frappe.delete_doc` ile siler. |
| `submit_draft_calisma_kartlari` | Cron (`30 1 * * 0`) | Pazar günü açık/taslak kalan ve bitirilmiş olan kartları otomatik submit eder. |
| `send_daily_calisma_karti_error_report` | Cron (`30 8 * * *`) | Ayarlar aktif ise dün 5 saatin altında net çalışma süresine sahip operatörleri amirlere e-posta ile raporlar. |

## Sabitler (_helpers.py)

```python
HURDA_PARENT_COST_CENTER = "Malzeme Sarfları - KTA"

QC_ALLOWED_ROLES = {"KTA Kalite Kullanıcısı", "Quality Manager", "System Manager"}
QC_ALLOWED_VALUES = {"Onay Bekliyor", "Onaylandı", "Reddedildi"}
```
