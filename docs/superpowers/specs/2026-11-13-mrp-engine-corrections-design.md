# KTA MRP Motoru ve Satın Alma Raporu İyileştirmeleri Tasarım Dokümanı

**Tarih:** 2026-11-13  
**Durum:** Onay Bekliyor  
**Kapsam:** `erpnextkta/kta_mrp/mrp_engine/` ve `erpnextkta/kta_mrp/report/recommended_purchase_orders/`

---

## 1. Amaç ve Arka Plan (Intent & Why)

KTA Endüstri Sistemleri üretim operasyonlarında **yarı mamul (sub-assembly) kullanılmamakta**, tüm kablo gruplama operasyonları tek bir **mono reçete (BOM)** üzerinde sıralı operasyonlar (`OP10 Kablo Kesme`, `OP30 Montaj`, `OP30 Enjeksiyon`, `OP40 Form Verme + Test`) olarak tanımlanmaktadır. 

Ayrıca ERPNext üzerinde tüm iş emirleri standart olarak **`skip_transfer = 1`** parametresi ile açılmaktadır. Bu parametre nedeniyle hammaddeler ara ambarlara (WIP) transfer edilmemekte, doğrudan `Hammadde Ambarı` üzerinde `Bin.reserved_qty_for_production` hanesinde rezerve tutulmakta ve sadece nihai montaj tamamlandığında `Stock Entry (Manufacture)` fişi ile stoktan düşülmektedir.

Mevcut MRP motoru bu kurguya uyum sağlamak için serbest stoğu `free_stock = actual - reserved` olarak almakta ve talep tarafında açık iş emirlerini plandan düşmektedir (`max(0, planned - work_orders)`). Ancak yapılan analizlerde, motorun kapasite dengeleme, tedarikçi termin ötelemesi ve kotalı dağıtım fonksiyonlarında 6 kritik eksiklik/hata tespit edilmiştir:
1. Kapasite dengeleme algoritmasında (`leveling.py`) kapasite dolduğunda açık iş emirlerinin unutulması (`item_carry_over_wo` eksikliği) ve 5.000 adetlik iş emirlerinin buharlaşarak mükerrer hammadde satın alma önerisi üretmesi.
2. Önerilen Satın Alma Siparişleri (RPO) raporunda kotalı tedarikçilerin bireysel termin sürelerinin (`lead_time_days`) yok sayılması ve tüm siparişin tek satırda varsayılan tedarikçiyle gösterilmesi.
3. RPO raporunda teslim süresi bugünü aşan siparişlerin geçmiş haftalara düşmesi ve geçmiş kolonlar açması (Acil Sipariş uyarısı eksikliği).
4. Kotalı tedarikçilerde net ihtiyaç küçük olduğunda dahi kotaya bölünmesi ve her tedarikçiye ayrı ayrı MOQ uygulanarak ambara ihtiyacın katbekat fazlası stok yığılması (kamçı etkisi).
5. Standart `Item.safety_stock` (Satın Alma sekmesi) alanının netting formülünde hesaba katılmaması.
6. Tedarikçi kartlarında ülke alanı `Turkey` unutulmuş olan yurt dışı tedarikçilerin yanlışlıkla yerli sayılma riski.

Bu tasarım dokümanı, bu 6 konuyu çözüme kavuşturacak mimari ve mantıksal mühendislik adımlarını belirler.

---

## 2. Hedefler, Kapsam Dışı ve Kısıtlar

### Hedefler (Goals)
* Kapasite aşımında açık iş emirlerinin haftadan haftaya taşınarak (`carry-over`) tam olarak korunması ve hiçbir açık iş emrinin plandan düşülmeden buharlaşmamasını sağlamak.
* RPO raporunda çoklu tedarikçiye sahip ürünleri her tedarikçinin kendi satırında ve kendi teslim süresi kadar geriye öteleyerek doğru sipariş haftasını göstermek.
* Teslim süresi geçmişe düşen (termin süresi aşılmış) siparişleri mevcut planlama haftasına kilitleyip kırmızı rozetle *"Acil Sipariş"* olarak işaretlemek.
* Net ihtiyaç miktarı tedarikçilerin MOQ toplamından küçükse kotayı bölmeyip tek bir öncelikli tedarikçiye yönlendirmek.
* `Item.safety_stock` alanını motora bağlamak (varsayılanı `0` tutarak bugünkü sisteme sıfır riskle uyum sağlamak).
* `Supplier.country != Company.country` ve `supplier_group == 'YD-Hammadde'` hibrit kuralı ile yerli/ithal ayrımını hatasız kılmak.

### Kapsam Dışı (Non-Goals)
* Mono reçete yapısını değiştirmek veya çok seviyeli yarı mamul takibine geçmek (KTA'nın bilinçli mono-reçete tercihi aynen korunacaktır).
* `skip_transfer = 1` iş akışını değiştirmek.
* Günlük granülaritede kova sistemi kurmak (Pazartesiye sabitlenmiş haftalık kova standardı korunacaktır).

---

## 3. Mimari ve Detaylı Tasarım

### 3.1. `leveling.py`: İş Emri Devri (Carry-Over Fix)
* **Dosya:** [leveling.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/leveling.py)
* **Fonksiyon:** `forward_scheduling`
* **Değişiklik:** Satır 127-130 arasındaki `else` bloğuna (mevcut haftada kapasite dolduğunda devreye giren kısım) eksik olan iş emri devri eklenecektir:
  ```python
  else:
      for i in items_in_group:
          item_carry_over[i] += item_week_demand[i].get(week, 0)
          item_carry_over_kanban[i] += item_week_kanban[i].get(week, 0)
          item_carry_over_wo[i] += item_week_wo[i].get(week, 0)  # <-- EKLENECEK
  ```
* **Etki:** `MFG-WO-2026-05434` gibi mevcut haftada kapasiteye sığmayan iş emirleri bir sonraki haftanın kapasitesine aktarılacak, `wo_plan` içinde eksiksiz yer alacak ve `demand.py`'de plandan düşülerek 55 hammaddenin mükerrer satın alınması engellenecektir.

---

### 3.2. `recommended_purchase_orders.py`: Çoklu Tedarikçi ve Bireysel Termin Ötelemesi
* **Dosya:** [recommended_purchase_orders.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/report/recommended_purchase_orders/recommended_purchase_orders.py)
* **Mevcut Durum:** `shift_by_lead_time(material)` fonksiyonu sadece `material.lead_time_days` değerini kullanmakta ve `material.supplier` üzerinden tek satır üretmektedir.
* **Yeni Tasarım:**
  1. `material.netting.planned_orders_by_supplier` sözlüğü kontrol edilir.
  2. Eğer birden fazla tedarikçi varsa, her tedarikçi için ayrı bir satır üretilir:
     * `supplier`: Tedarikçi adı
     * `lead_time_days`: O tedarikçiye özel teslim süresi (`s.get("lead_time_days")`)
     * `moq`, `paket`: O tedarikçiye özel parti şartları
     * Sipariş haftaları: O tedarikçinin teslim süresi kadar geriye ötelenmiş haftalar.
  3. Tek tedarikçili ürünlerde mevcut tek satır düzeni devam eder.

---

### 3.3. `recommended_purchase_orders.py`: Geçmişe Düşen Siparişler (Action Messages)
* **Dosya:** [recommended_purchase_orders.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/report/recommended_purchase_orders/recommended_purchase_orders.py)
* **Mevcut Durum:** İhtiyaç haftası eksi teslim süresi bugünden önceye düşerse, geçmiş haftalar için kolonlar açılmakta (`2026_w41` vb.).
* **Yeni Tasarım:**
  * Minimum sipariş haftası raporun başlangıç haftasına (Mevcut Hafta / `from_date` Pazartesisi) eşitlenir:
    ```python
    order_week = week_key(order_date)
    if order_week < first_valid_week:
        is_past_due = True
        target_week = first_valid_week
    else:
        target_week = order_week
    ```
  * Rapora `is_past_due` alanı eklenir. Rapor görselinde bu satırlar kırmızı gösterge ve *"Acil / Gecikmiş Sipariş"* uyarısı alır. Rapor sadece geçerli planlama ufkundaki haftaları listeler.

---

### 3.4. `netting.py`: Küçük İhtiyaçlarda MOQ Bölünmesinin Engellenmesi
* **Dosya:** [netting.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/netting.py#L121-L131)
* **Fonksiyon:** `_net_week`
* **Yeni Tasarım:**
  * Kotalı dağılım (`Kotalı Dağılım (% Paylaşım)`) stratejisinde:
    ```python
    total_moq_sum = sum(flt(s.get("moq") or 0) for s in suppliers)
    if shortage < total_moq_sum and len(suppliers) > 1:
        # Net ihtiyaç tedarikçilerin MOQ toplamından küçükse, kotayı bölüp kat kat sipariş üretme!
        # En yüksek kotaya sahip (veya 1. sıradaki) ana tedarikçiye ver:
        primary_s = max(suppliers, key=lambda s: flt(s.get("quota_share") or 0))
        # Sipariş sadece primary_s için lot_size uygulanarak açılır.
    else:
        # Normal kotalı bölüşüm uygulanır.
    ```
* **Etki:** 100 adetlik ihtiyaç için iki tedarikçiye ayrı ayrı 500'er adet (toplam 1.000 adet) sipariş açılması engellenir; tek bir 500 adetlik sipariş açılarak kamçı etkisi önlenir.

---

### 3.5. `netting.py` & `service.py`: Emniyet Stoğu Altyapısı
* **Dosyalar:** [netting.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/netting.py), [service.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/service.py)
* **Tasarım:**
  1. `service.py` içinde `load_supply_context`:
     `Item` kartındaki standart `safety_stock` alanı okunur (`terms.safety_stock = flt(item_doc.safety_stock or 0)`).
  2. `net_material()` fonksiyonu `safety_stock=0` parametresi alır.
  3. `_net_week` içinde net açık hesabı güncellenir:
     $$\text{shortage} = \max(0, \text{demand} + \text{safety\_stock} - \text{available})$$
  4. Stok bakiyesi `safety_stock` altına inmeden önce sipariş önerisi üretilir. Değer `0` iken bugünkü davranışın birebir aynısı korunur.

---

### 3.6. `supply.py`: Hibrit Yerli / Yurt Dışı Sınıflandırması
* **Dosya:** [supply.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/supply.py)
* **Tasarım:**
  Tedarikçi yurt dışı / ithalat kontrolü için tek merkezli yardımcı fonksiyon tanımlanır:
  ```python
  def is_foreign_supplier(supplier_doc, company_country="Turkey"):
      if not supplier_doc:
          return False
      if supplier_doc.supplier_group == "YD-Hammadde":
          return True
      if supplier_doc.country and supplier_doc.country != company_country:
          return True
      return False
  ```
* **Etki:** Kart açılırken ülke alanı `Turkey` unutulan Stocko, TDK, Alpha Therm gibi 140 hammaddeye sahip tedarikçiler güvenle yurt dışı / ithalat statüsünde işlem görür.

---

## 4. Test ve Doğrulama Planı

1. **Birim Testleri (Unit Tests):**
   * `test_leveling.py`: Kapasite aşımında iş emirlerinin devredildiği ve `wo_plan` toplamının tam eşleştiği test senaryosu.
   * `test_netting.py`: Küçük ihtiyaçta MOQ bölüşüm engeli testi ve `safety_stock > 0` iken erken sipariş tetikleme testi.
   * `test_recommended_purchase_orders.py`: Çoklu tedarikçili ürünün 2 satır halinde kendi lead time'ları ile ötelenmesi ve geçmişe düşen siparişin mevcut haftaya kilitlenmesi testi.
2. **Entegrasyon / Canlı Veri Testi:**
   * `8750301805` ürünü üzerinden MRP çalıştırılıp açık 8.280 adetlik iş emrinin tamamının düşüldüğü ve 55 hammadde için 5.000 adetlik mükerrer satın alma önerisinin sıfırlandığı teyit edilecek.
3. **Frontend / Rapor Doğrulaması:**
   * Malzeme İhtiyaç ve Önerilen Satın Alma Siparişleri raporlarının UI üzerinden doğru çalıştığı doğrulanacak.
