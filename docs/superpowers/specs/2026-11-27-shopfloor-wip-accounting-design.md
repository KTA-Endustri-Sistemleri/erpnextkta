# Shopfloor Operasyon Bazlı Yarı Mamul (WIP) Muhasebeleştirme ve Değerleme Tasarım Belgesi

**Tarih:** 2026-11-27  
**Branch:** `feat/shopfloor-wip-accounting` (`main` üzerinden)  
**Durum:** Onaylandı  

---

## 1. Amaç ve Problem Tanımı

Shopfloor Hub üzerinde operasyon bazlı üretim teyitleri (`Material Consumption for Manufacture` ile ara/son operasyon hammadde tüketimi ve son operasyonda FG-only `Manufacture` ile mamul girişi) devreye alındığında, tüketim fişlerinde satır `expense_account` alanı boş bırakıldığı için ERPNext şirket varsayılanı olan `stock_adjustment_account` (`710.20 - Envanter Düzeltme Giderleri - KTA`) hesabını kullanmaktadır:

- **OP10/OP20 tüketiminde:** `710.20` BORÇ / `150` ALACAK
- **OP30 mamul girişinde:** `152` BORÇ / `710.20` ALACAK

Üretim tamamlanmadan (örneğin ay sonu kapanışında veya kısmi üretimlerde) tüketilmiş ama henüz nihai mamul olmamış yarı mamul bedeli bilanço (`151`) yerine gider/düzeltme (`710.20`) hesabında birikmekte ve muhasebenin yarı mamul stok bedelini net takip etmesini zorlaştırmaktadır.

Ayrıca mevcut `151.01.001` hesabı dış konsinye ambarına (`Stock` tipi) bağlı olduğu için bu hesaba **dokunulmamalıdır**.

---

## 2. Mimari Çözüm

### 2.1 `Company.custom_wip_consumption_account` Alanı ve Doğrulaması
- `Company` DocType'ına `stock_adjustment_account` alanından sonra **`custom_wip_consumption_account`** (`WIP Consumption Account`, `Link -> Account`) Custom Field'ı eklenir.
- `erpnextkta/overrides/company_wip_validation.py` (`doc_events["Company"]["validate"]`):
  - Seçilen hesabın aynı şirkete ait olduğu, grup olmadığı (`is_group == 0`) ve `account_type != "Stock"` olduğu doğrulanır (ERPNext `Stock Entry.validate_difference_account` `Stock` tipli hesaplara izin vermez ve konsinye stok hesabı korunur).
  - `get_validated_wip_consumption_account(company)` yardımcı fonksiyonu güvenli şekilde (`has_column` kontrollü) aktif WIP hesabını döner; boşsa mevcut ERPNext varsayılanı bozulmaz.

### 2.2 Otomatik Yevmiye Yönlendirmesi (`KTAStockEntry` + `BackflushService`)
- `KTAStockEntry.validate()` içinde (`super().validate()` öncesinde `_apply_wip_consumption_account`):
  - İş Emrine (`work_order`) bağlı `Material Consumption for Manufacture` fişlerinde çıkış (`s_warehouse`) satırlarına `expense_account = wip_account` atanır (`151` BORÇ / `150` ALACAK).
  - İş Emrine bağlı FG-only `Manufacture` fişlerinde (hiç `s_warehouse` satırı olmayıp yalnızca `t_warehouse` giriş satırları içeren) giriş satırlarına `expense_account = wip_account` atanır (`152` BORÇ / `151` ALACAK).
  - Hem hammadde çıkışı hem mamul girişi içeren klasik `Manufacture` fişlerine dokunulmaz.
  - `BackflushService.create_consumption_entry` ve `BackflushService.create_finished_goods_entry` de fiş oluştururken aynı hesabı satırlara yazar.
  - SAP CORS ile teyit iptal edildiğinde iki fiş de ters kayıtla iptal edildiğinden `151` bakiyesi birebir geri çekilir.

### 2.3 Geriye Dönük Açık Dönem Patch'i (`erpnextkta/patches/v4_6/backfill_shopfloor_wip_account.py`)
- Idempotent olarak `Company.custom_wip_consumption_account` alanını oluşturur.
- Şirkette `151.01` grup hesabı varsa altında `151.01.002 - ÜRETİM SÜRECİNDEKİ TÜKETİMLER (WIP)` (`root_type = "Asset"`, `account_type = ""`, `is_group = 0`) hesabını oluşturup `Company` üzerine bağlar (yoksa CI/test ortamında sessizce atlar).
- `from_date = "2026-11-23"` başlangıcı ve `Period Closing Voucher` / `Accounts Settings.acc_frozen_upto` korumasıyla yalnızca açık dönemdeki İş Emri bazlı `Material Consumption for Manufacture` ve FG-only `Manufacture` fişlerinin `tabStock Entry Detail.expense_account` ve `tabGL Entry` (`account` & `against`) kayıtlarını per-voucher savepoint içinde `stock_adjustment_account -> wip_account` olarak taşır.
- Her fiş sonrasında `SUM(debit) == SUM(credit)` dengesini doğrular ve `dry_run=True` önizlemesini destekler.

### 2.4 `KTA WIP Valuation Report` (`erpnextkta/kta_shopfloor/report/kta_wip_valuation_report/`)
- `Accounts User`, `Accounts Manager`, `Manufacturing Manager`, `System Manager` erişimli standart Frappe Script Report.
- `as_of_date` itibarıyla doğrudan `tabGL Entry` üzerinden her İş Emri için: Tüketim Bedeli, Mamule Devredilen Bedel, Kalan WIP Bedeli ve hesap kırılımını (`151` WIP vs kalan `710.20`) gösterir; `Stopped` durumdaki açık WIP bakiyelerini görsel olarak vurgular.
- Tamamen salt okunur (read-only) bir rapordur; geriye dönük açık dönem fişleri patch ile doğrudan `151` hesabına taşındığı için ayrı bir taslak virman `Journal Entry` aksiyonu veya endpoint'i içermez.

---

## 3. Doğrulama Planı

1. `erpnextkta.tests.test_wip_accounting` (hesap doğrulama, OP10 tüketim + OP30 üretim kapanışı, kısmi üretim bakiye tutarlılığı, klasik manufacture hariç tutma, CORS iptal, patch `dry_run` / `apply` / tarih kesimi / idempotency / patch sonrası iptal).
2. `erpnextkta.kta_shopfloor.tests.test_wip_valuation_report` (`as_of_date`, `only_open_wip`, hesap kırılımı, `wo_status` / `Stopped` vurgu ve özet kartları).
3. Mevcut regresyon testleri (`test_stock_entry_override`, `test_backflush_service`, `test_reversal_service`) ve `ruff check` / `ruff format --check`.
4. `old.kta-endustri.com.tr` üzerinde salt-okunur `backfill_shopfloor_wip_entries(dry_run=True)` doğrulaması.
5. `erpnextkta/www/docs/shopfloor-hub.html`, `docs/kta_shopfloor_hub_kilavuzu.md` ve `translations/{tr,en,de}.csv` güncellemesi.
