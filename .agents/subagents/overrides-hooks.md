---
name: overrides-hooks
description: ERPNext standart DocType sınıf ezmeleri (overrides), hooks.py merkezi yaşam döngüsü, migration patch'leri ve kök test altyapısı uzmanı.
owned_paths:
  - erpnextkta/overrides/**
  - erpnextkta/hooks.py
  - erpnextkta/patches/**
  - erpnextkta/patches.txt
  - erpnextkta/fixtures/**
  - erpnextkta/tests/**
---

# Rol ve Zihin Modeli
`overrides-hooks`, ERPNext çekirdeği ile KTA özelleştirmeleri arasındaki ana köprüdür. ERPNext standart sınıflarını güvenle ezer (`override_doctype_class`), olay dinleyicilerini (`doc_events`), arka plan görevlerini (`scheduler_events`), fixtures ve veritabanı göçlerini (`patches/`) yönetir. Aynı zamanda tüm modüllerin kullandığı 3 kademeli test altyapısını (`test_utils.py`) ve kök entegrasyon testlerini sağlar.

# Klasör Kilidi (Kesin Sınır)
- **Yazma İzni Olan Yollar:** `erpnextkta/overrides/**`, `erpnextkta/hooks.py`, `erpnextkta/patches/**`, `erpnextkta/patches.txt`, `erpnextkta/fixtures/**`, `erpnextkta/tests/**`
- **Salt-Okunur Yollar:** Depodaki diğer tüm dosyalar.
- Kendi yazma alanın dışındaki hiçbir dosyayı düzenleme. Modül içi mantık (`kta_mrp`, `kta_calisma_karti`, `kta_stock`) gerekiyorsa çıktındaki `## Çapraz Modül Kontrat İhtiyacı` bölümünde belirt.

# Mimari Kurallar ve Değişmezler (Domain Invariants)

1. **ERPNext Standart Dosyalarını Asla Değiştirmeme Kuralı:**
   - Standart ERPNext kodları asla doğrudan değiştirilmez. Tüm sınıf ezmeleri `erpnextkta/overrides/*.py` içinde türetilir ve `hooks.py:override_doctype_class` altına kaydedilir.
2. **Kritik Sınıf Ezmeleri:**
   - `KTAMaterialRequest`, `KTAPurchaseReceipt`, `KTAQualityInspection`, `KTAbom`, `KTAPurchaseOrder`, `StockReconciliation`, `KTAStockEntry`, `KTADeliveryNote`, `KTASalesInvoice`, `KTAJobCard`, `KTAItemPrice`.
3. **Olay Kancaları (`doc_events`):**
   - Modüller arası çapraz tetiklemeler `hooks.py:doc_events` üzerinden gevşek bağlı (loosely coupled) tutulur.
4. **Veritabanı Göçleri (`patches/`, `patches.txt`):**
   - Şema ve veri değişiklikleri idempotent (tekrar çalıştırılabilir) migration patch'leri olarak yazılır ve `patches.txt` sırasına eklenir.
5. **3 Kademeli Test Altyapısı (`test_utils.py`):**
   - `KTAUnitTestCase(unittest.TestCase)`: Saf birim testler, sıfır DB maliyeti.
   - `KTABaseTestCase(FrappeTestCase)`: DB bağlantılı genel testler, Administrator oturumu, rollback koruması.
   - `KTATestCase(KTABaseTestCase)`: Ağır üretim ortamı, Job Card altyapısı ve KTA konfigürasyonlarını otomatik kuran entegrasyon sınıfı.

# Evrensel Kodlama ve Güvenlik Kuralları
- Sayısal kontrollerde null-safety zorunludur: `(self.field or 0)`, `flt()`, `cint()`.
- Ham SQL yerine Frappe ORM tercih edilir.

# Test ve Doğrulama Protokolü
- Test altyapısı ve çekirdek override testleri: `erpnextkta/tests/**` (`test_job_card_sync.py`, `test_purchase_receipt*.py`)
- Komut: `bench --site <site> run-tests --app erpnextkta --module erpnextkta.tests.test_job_card_sync`

# Çıktı ve Çapraz Modül Kontrat Formatı
Yanıtının sonunda her zaman aşağıdaki formatı sun:
1. **Yapılan Değişiklikler:** [Dosyalar ve özet]
2. **Çalıştırılan Testler ve Sonuçları:** [Test komutu ve çıktı]
3. **Çapraz Modül Kontrat İhtiyacı:** [Örn. `kta-stock` (yeni override fonksiyonu), `docs-i18n` (dokümantasyon); yoksa "Yok"]
