# KTA MRP Settings: İş Emri Rezervasyonlarını Stoktan Düşme Onay Kutusu (Toggle) Tasarım Şartnamesi

- **Tarih:** 2026-11-16
- **Talep:** KTA MRP Settings içerisine, iş emri rezervasyonlarının stoktan düşülmesini açıp kapatmaya yarayan merkezi bir onay kutusu (checkbox) eklenmesi (Yaklaşım 2: Statik Global Ayar).
- **Yazar:** Coordinator (Tech Lead)
- **Uygulayıcı Ajanlar:** `kta-mrp`, `docs-i18n`

---

## 1. Amaç ve Kapsam

Mevcut MRP motoru ([`service.py`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/service.py)), serbest hammadde stok miktarını (`free_stock`) hesaplarken açık iş emirlerine tahsis edilmiş rezervasyonları (`Bin.reserved_qty_for_production`) fiziksel stoktan (`Bin.actual_qty`) otomatik olarak düşmektedir:

$$\text{free\_stock} = \text{actual\_qty} - \text{reserved\_qty}$$

İşletme senaryolarında üretim planlamacısı, bazı durumlarda iş emri rezervasyonlarının netting havuzunu tıkamamasını, fiziksel olarak rafta bulunan toplam mevcut stok (`actual_qty`) üzerinden ihtiyaç ve satınalma önerisi hesaplanmasını talep etmektedir.

Bu şartname, `KTA MRP Settings` altında tekil ve merkezi bir parametre ile bu davranışın konfigüre edilmesini sağlar.

---

## 2. Şema Değişikliği (`kta_mrp_settings.json`)

[`erpnextkta/kta_mrp/doctype/kta_mrp_settings/kta_mrp_settings.json`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_mrp/doctype/kta_mrp_settings/kta_mrp_settings.json):
- **Bölüm:** `sb_supply` ("Depo & Satınalma Parametreleri") altına `default_include_po` alanından sonra eklenir.
- **Alan Adı (fieldname):** `deduct_work_order_reservations`
- **Alan Tipi (fieldtype):** `Check`
- **Varsayılan Değer (default):** `"1"` (Mevcut davranışın devamlılığı ve geriye dönük uyumluluk için varsayılan aktiftir).
- **Etiket (label):** `İş Emri Rezervasyonlarını Stoktan Düş`
- **Açıklama (description):** `İşaretlendiğinde, kullanılabilir depolardaki mevcut stoktan açık iş emirleri için ayrılmış rezervasyon miktarı (reserved_qty_for_production) düşülerek net serbest stok hesaplanır. İşaret kaldırıldığında brüt mevcut stok doğrudan serbest kabul edilir.`

---

## 3. MRP Motoru ve Servis Mantığı

### 3.1 [`settings.py`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/settings.py)
- `MrpSettings` dataclass'ına yeni alan eklenir:
  ```python
  deduct_work_order_reservations: bool = True
  ```
- `get_mrp_settings()` ve `resolve_mrp_settings()` fonksiyonlarında değer okunur:
  ```python
  deduct_work_order_reservations=bool(cint(doc.get("deduct_work_order_reservations", 1)))
  ```

### 3.2 [`service.py`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/service.py)
- `MaterialRequirementSummary`:
  ```python
  @property
  def free_stock(self):
      effective_reserved = self.reserved if self.deduct_reservations else 0.0
      return self.actual - effective_reserved
  ```
- `NettingInput`:
  ```python
  effective_reserved = (
      stock.reserved if settings.deduct_work_order_reservations else 0.0
  )
  free_stock = stock.actual - effective_reserved
  ```
- `reserved_stock` kolonu matris tablosunda ve çekmecede plancıya şeffaf bilgi sağlamak amacıyla gösterilmeye devam eder, ancak ayar pasif olduğunda `free_stock` hesabından düşülmez.

---

## 4. Çeviri ve Dokümantasyon (`docs-i18n`)

- `tr.csv`:
  - `İş Emri Rezervasyonlarını Stoktan Düş` -> `İş Emri Rezervasyonlarını Stoktan Düş`
  - Açıklama metni
- `en.csv`:
  - `İş Emri Rezervasyonlarını Stoktan Düş` -> `Deduct Work Order Reservations from Stock`
  - `When checked, reserved quantity for open work orders is deducted from available warehouse stock to calculate net free stock. When unchecked, gross actual stock is considered free.`
- `de.csv`:
  - `İş Emri Rezervasyonlarını Stoktan Düş` -> `Fertigungsauftrags-Reservierungen vom Bestand abziehen`
  - `Wenn aktiviert, wird die für offene Fertigungsaufträge reservierte Menge vom verfügbaren Lagerbestand abgezogen, um den freien Nettobestand zu berechnen. Wenn deaktiviert, gilt der Brutto-Istbestand als frei.`
- Web Portalı Dokümantasyonu:
  - [`erpnextkta/www/docs/mrp-settings.html`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/www/docs/mrp-settings.html) tablosuna yeni parametre eklenir.

---

## 5. Doğrulama ve Kalite Kapısı

1. **Birim & Entegrasyon Testleri (`kta-mrp`):**
   - `test_settings.py`: Ayarın varsayılan `True` gelmesi ve `False` olarak güncellenebilmesi test edilir.
   - `test_service.py`: Ayar `True` iken `free_stock = 80` (100 actual - 20 reserved), ayar `False` iken `free_stock = 100` olduğu ve netting ihtiyaçlarının buna göre değiştiği test edilir.
2. **Sistem Entegrasyonu:**
   - `bench migrate` (KTA MRP Settings şemasını DB'ye senkronlar).
   - `bench restart` ve `bench --site <site> clear-cache`.
