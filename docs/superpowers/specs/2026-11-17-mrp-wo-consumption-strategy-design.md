# KTA MRP Settings: İş Emri Malzeme Tüketim Stratejisi Tasarım Şartnamesi

- **Tarih:** 2026-11-17
- **Talep:** KTA MRP Settings içerisine, iş emirlerinin hammadde ihtiyacını anlık stoktan peşin düşmek yerine fabrikanın haftalık kapasite planı doğrultusunda zaman fazlı tüketmesini sağlayan strateji seçim listesi (Select) eklenmesi.
- **Yazar:** Coordinator (Tech Lead)
- **Uygulayıcı Uzman Ajanlar:** `kta-mrp`, `docs-i18n`

---

## 1. Amaç ve Kapsam

### 1.1 Mevcut Durum ve Problem (Zaman Kayması / Time-Warp Tuzağı)
Mevcut MRP motorunda iki zıt mekanizma aynı anda çalışmaktadır:
1. **Stok Tarafı:** İş emirleri açıldığı anda ERPNext reçetedeki tüm bileşenleri `tabBin.reserved_qty_for_production` alanına yazar. MRP motoru serbest stok hesabında (`free_stock = actual - reserved`), açılmış olan tüm iş emirlerinin hammaddesini **"Bugün (W0)"** ambar stokundan peşin düşer.
2. **Haftalık Plan Tarafı (`demand.py`):** Açık iş emirleri çift sayımı önlemek adına haftalık üretim planından düşülür (`material_driving_qty = max(0, planned - work_orders)`).

**Operasyonel Sakınca:**
Özellikle kablo montaj hatlarında (ör. `C4000İW` grubundaki `8750301805` ve `8750716444` ürünleri):
- İmalat süresi (`custom_manufacturing_lead_days`) **14 gün (2 hafta)**,
- Grup haftalık montaj kapasitesi **7.000 adet**tir.
- 38 hammadde kaleminin 36'sı (%95) ortaktır.

Bir iş emri açıldığında üretimin tamamlanıp satışa hazır hale gelmesi asgari 2 hafta sürerken ve haftalık 7.000 kapasite kısıtı nedeniyle üretim haftalara yayılmak zorundayken; hammaddeyi iş emri açıldığı gün yok saymak:
- Hammadde ihtiyacını ve satın alma siparişini (Suggested PO) **en az 2 hafta yapay olarak erkene çekmekte**,
- Tedarikçilere erken ve panik sipariş önerilmesine yol açmakta,
- Aynı terminalleri/kabloları paylaşan kardeş ürünlerin hammadde erişimini kilitlemektedir.
- Ayrıca iş emrinin `planned_start_date` tarihi operasyonel gecikmeler nedeniyle geçmişte kaldığında statik planlama çökmektedir.

### 1.2 Hedeflenen Çözüm (Kapasiteye Dağıtılmış Tüketim Modeli)
Kapasite Planlama Raporu (`capacity.py`), satış siparişlerini, açık iş emirlerini ve geçmişten sarkan işleri (backlog) haftalık 7.000 tavanını aşmayacak şekilde ileriye doğru kusursuz dengeler (`capacity.plan`). KTA'da malzeme çıkışı önceden değil, mamul tamamlandığında (`Manufacture` fişi ile - Backflush) ambar stoğundan düşülmektedir.

Bu şartname ile `KTA MRP Settings` altına bir **Select** alanı eklenerek planlamacıya iki stratejik tercih sunulur:
1. `Anlık Stok Rezervasyonu (Klasik)`
2. `Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)`

---

## 2. Şema Değişikliği (`kta_mrp_settings.json`)

Dosya: [`erpnextkta/kta_mrp/doctype/kta_mrp_settings/kta_mrp_settings.json`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_mrp/doctype/kta_mrp_settings/kta_mrp_settings.json)

- **Bölüm:** `sb_supply` ("Depo & Satınalma Parametreleri") altına `default_include_po` alanından sonra eklenir.
- **Alan Adı (fieldname):** `wo_consumption_strategy`
- **Alan Tipi (fieldtype):** `Select`
- **Seçenekler (options):**
  ```
  Anlık Stok Rezervasyonu (Klasik)
  Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)
  ```
- **Varsayılan Değer (default):** `Anlık Stok Rezervasyonu (Klasik)` (Mevcut davranışın devamlılığı ve geriye dönük tam uyumluluk için).
- **Etiket (label):** `İş Emri Malzeme Tüketim Stratejisi`
- **Açıklama (description):** `İş emirlerinin hammadde ihtiyacının nasıl karşılanacağını belirler. 'Anlık Stok Rezervasyonu' modunda açık iş emirlerinin tüm reçetesi bugünkü serbest stoktan peşin düşülür. 'Kapasiteye Dağıtılmış Tüketim' modunda ise iş emirleri ambar stokunu peşin kilitlemez; fabrikanın haftalık kapasite planındaki üretim hızına göre zaman fazlı olarak tüketilir (2 haftalık erken satın alma baskısını ve kardeş ürün malzeme kilitlenmelerini önler).`

---

## 3. Ayar ve Motor Mimarisi

### 3.1 `settings.py` Güncellemesi
[`erpnextkta/kta_mrp/mrp_engine/settings.py`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/settings.py):
- `MrpSettings` sınıfına `wo_consumption_strategy: str = "Anlık Stok Rezervasyonu (Klasik)"` alanı eklenir.
- Yardımcı property:
  ```python
  @property
  def is_capacity_leveled_consumption(self) -> bool:
      return self.wo_consumption_strategy == "Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)"
  ```
- Geriye dönük uyumluluk:
  Eğer `is_capacity_leveled_consumption` aktif ise `deduct_work_order_reservations = False` olarak işletilir.
  Klasik modda ise mevcut `deduct_work_order_reservations` değeri baz alınır.

### 3.2 `demand.py` Güncellemesi
[`erpnextkta/kta_mrp/mrp_engine/demand.py`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/demand.py):
- `ProductionPlan.material_driving_qty` metoduna strateji desteği eklenir:
  ```python
  def material_driving_qty(self, item_code, week, capacity_leveled: bool = False):
      planned = self.planned.get(item_code, {}).get(week, 0) or 0
      if planned <= 0:
          return 0
      if capacity_leveled:
          # Kapasiteye göre dengelenmiş toplam haftalık üretim adedi hammadde talebini doğurur.
          # İş emirleri zaten bu planın içinde zaman fazlı olarak yer almaktadır.
          return planned
      # Klasik mod: Hammaddesi stoktan peşin rezerve edildiği için plandan düşülür.
      return max(0, planned - (self.work_orders.get(item_code, {}).get(week, 0) or 0))
  ```

### 3.3 `service.py` Güncellemesi
[`erpnextkta/kta_mrp/mrp_engine/service.py`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/service.py):
- `_build_single_material()` fonksiyonunda:
  ```python
  if settings.is_capacity_leveled_consumption:
      effective_reserved = 0.0  # Stoktan peşin düşülmez, zaman fazlı tüketilir
  else:
      effective_reserved = stock.reserved if settings.deduct_work_order_reservations else 0.0

  free_stock = stock.actual - effective_reserved
  ```
- `get_material_requirements_data()` fonksiyonunda `material_driving_qty` çağrılırken `capacity_leveled=settings.is_capacity_leveled_consumption` parametresi aktarılır.

---

## 4. İki Modun Matematiksel Karşılaştırması

| Kriter | 1. Anlık Stok Rezervasyonu (Klasik) | 2. Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı) |
|---|---|---|
| **Serbest Stok (`free_stock`)** | `actual_qty - reserved_qty` | `actual_qty` (Fiziksel ambar stoğu) |
| **Haftalık Brüt Talep** | `planned - work_orders` | `planned` (Kapasite planındaki toplam üretim) |
| **İş Emri Hammadde Tüketimi** | W0'da (Bugün) peşin düşülür | Kapasiteye göre üretileceği haftalarda erir |
| **2 Hafta Erken Çekme Etkisi** | Var (Tedarikçiye erken sipariş) | Yok (JIT / Tam zamanında ihtiyaç) |
| **Ortak Hammadde Paylaşımı** | Açık iş emri olan ürün tüm stoğu kilitler | Her iki ürün haftalık kapasite payı kadar tüketir |
| **Gecikmiş (Backlog) İş Emri** | Bugüne yığılır | Haftalık 7.000 tavanına göre ileriye dengelenir |

---

## 5. Doğrulama ve Test Kriterleri

1. **Birim Testleri (`kta-mrp`):**
   - `test_settings.py`: Yeni strateji alanının varsayılanı ("Anlık Stok Rezervasyonu (Klasik)"), get ve resolve fonksiyonlarında doğru okunması.
   - `test_service.py`:
     - Klasik mod testi: `free_stock = actual - reserved`, `material_driving_qty = planned - wo`.
     - Kapasite modu testi: `free_stock = actual`, `material_driving_qty = planned`, iş emrinin haftalık plana yayılması ve malzeme ihtiyacının haftalara dengeli yansıması.
2. **Dokümantasyon ve i18n (`docs-i18n`):**
   - `tr.csv`, `en.csv`, `de.csv` dosyalarına etiket ve seçenek çevirilerinin işlenmesi:
     - TR: `İş Emri Malzeme Tüketim Stratejisi`, `Anlık Stok Rezervasyonu (Klasik)`, `Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)`
     - EN: `Work Order Material Consumption Strategy`, `Instant Stock Reservation (Classic)`, `Capacity-Leveled Consumption (Time-Phased)`
     - DE: `Materialverbrauchsstrategie für Fertigungsaufträge`, `Sofortige Bestandsreservierung (Klassisch)`, `Kapazitätsorientierter Verbrauch (Zeitphasenorientiert)`
   - `erpnextkta/www/docs/mrp-settings.html` ve `docs/mrp_settings.md` dokümanlarına stratejinin mantığının ve kullanım rehberinin eklenmesi.
3. **Kalite Kapısı:**
   - `bench migrate`
   - `bench build --app erpnextkta --production`
   - `bench restart` ve `clear-cache`
   - Test modüllerinin hatasız geçmesi (`test_settings`, `test_service`, `test_netting`).
