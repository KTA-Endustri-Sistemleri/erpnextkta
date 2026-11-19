# Tasarım Dokümanı: Work Cards & Alt Operasyon Analitiği (Work Cards & Sub-Operation Analytics)

**Tarih:** 2026-11-19  
**Durum:** Onaylandı (Opsiyon 1: Tam Rota Kontrol Listesi & Alt Operasyon Hiyerarşisi)  
**Yazar:** Tech Lead / docs-i18n  
**Hedef Kapsam:** `erpnextkta/kta_calisma_karti/**`, `erpnextkta/public/shopfloor-hub/**`, `docs/**`

---

## 1. Amaç ve Arka Plan (Intent & Problem Statement)

KTA kablo ve tesisat imalat süreçlerinde fiili üretim sahadaki operatörler tarafından
`Calisma Karti` (Çalışma Kartı) belgeleri üzerinden yürütülür. Standart ERPNext iş akışında
`Job Card` operasyon düzeyinde teyit alırken, KTA'nın sahadaki gerçek işleyişinde bir operasyon
(örneğin Kesim, Krimp, Enjeksiyon, Montaj, Kalite Test) çok sayıda alt adımdan
(`KTA Calisma Karti Alt Operasyonlari`) oluşur.

Mevcut Shopfloor Hub kokpitinde:
1. `Work Orders` (İş Emirleri listesi, malzeme uygunluğu ve serbest bırakma),
2. `Operations` (Job Card bazında standart ERPNext operasyon teyidi ve malzeme düşümü),
sekmeleri bulunmaktadır.

Ancak atölye şefleri, üretim mühendisleri ve vardiya liderleri için sahada açılmış ve
işlenmiş olan `Calisma Karti` kayıtlarını, bu kartlardaki alt operasyon bazlı parça işlemlerini,
harcanan net çalışma sürelerini, tüketilen hammaddeleri ve oluşan hurdaları tek ekrandan
özet ve hiyerarşik biçimde izleme imkanı bulunmamaktadır.

Kullanıcı tercihi doğrultusunda **Opsiyon 1 (Tam Rota Kontrol Listesi)** seçilmiştir.
Bu yaklaşımda, İş Emrinin planlanan rotasındaki tüm operasyonlar ve bunların altındaki tüm
alt operasyonlar eksiksiz bir ağaç olarak listelenir. Henüz kart açılmamış adımlar `0 Adet` ve
`⚪ Başlanmadı` rozetiyle gösterilir. Böylece ekran hem gerçekleşen kartların analitiğini hem de
kalan operasyonel adımların kontrol listesini (checklist) bir arada sunar.

---

## 2. Hedefler, Kapsam Dışı ve Anti-Hedefler

### 2.1 Hedefler (Goals)
1. **Üçüncü Üst Menü Sekmesi:** Shopfloor Hub üst gezinti çubuğuna (`ShopfloorNavbar.vue`)
   `[ 📇 Çalışma Kartları ]` (`work_cards`) sekmesinin eklenmesi.
2. **Tam Rota Kontrol Listesi & Ağaç Görünümü (Opsiyon 1):** Seçili `Work Order` için planlanan
   tüm operasyon ve alt operasyonların şablon sırasıyla listelenmesi. Henüz kart açılmamış
   alt adımların `0 Adet` ve `⚪ Başlanmadı` rozetiyle sunulması.
3. **Eksiksiz Alt Operasyon Kapsamı:** Tüketimi hesaplanan (`is_tuketim_hesaplanir == 1`) ve
   hesaplanmayan (`is_tuketim_hesaplanir == 0`) tüm alt adımların eksiksiz listelenmesi.
4. **Metriklerin Güvenli Agregasyonu:**
   - **Tüketim Hesaplaması:** `tabCalisma Karti Alt Operasyon Kayitlari` tablosundaki
     `adet`, `adet_2`, `adet_3` alanları toplanır (`docstatus != 2` ve
     `quality_inspection_status NOT IN ('Reddedildi', 'Rejected', 'Red')`).
   - **Mükerrerliksiz Süre Hesabı:** Çok adımlı kartlarda süre mükerrerliğini önlemek için
     Operasyon ve İş Emri özetlerinde tekil `Calisma Karti.net_calisma_suresi` değerleri toplanır.
   - **Akıllı Hurda Eşleştirmesi:** `tabCalisma Karti Hurda` tablosundaki `parca_no` değeri
     ilgili alt operasyonun hammadde yuvalarıyla eşleşiyorsa o alt operasyona atanır;
     eşleşmeyen veya genel hurdalar Operasyon özet seviyesinde gösterilir.
5. **Kart Bazlı Detay Açılımı (Drilldown):** Her alt operasyon kartının altında, o adıma katkı
   sağlayan tekil `Calisma Karti` listesi (kart adı, operatör adı, durum, süre, adet).

### 2.2 Kapsam Dışı (Non-Goals)
- Bu sekme üzerinden yeni `Calisma Karti` oluşturulması veya mevcut kartların düzenlenmesi
  (Bu sekme salt izleme, analiz ve mutabakat görünümüdür).
- ERPNext stok rezervasyon mantığının bu sekmeden tetiklenmesi (Stok hareketleri `Operations`
  sekmesindeki teyit mekanizması üzerinden yürütülür).

### 2.3 Anti-Hedefler (Anti-Goals)
- Tüketim hesabı yapılmayan veya henüz kart açılmamış operasyonları gizlemek (Kullanıcı
  tüm üretim rotasını kontrol listesi olarak eksiksiz izlemek istemektedir).
- Bir kartın birden fazla alt operasyon kaydı içermesi durumunda aynı kart süresini her
  kayıt için ayrı ayrı toplayıp operasyon veya iş emri toplam süresini şişirmek.

---

## 3. Ağaç Kapsamı ve Rota Şablonu Kararı

### Opsiyon 1: Tam Rota Kontrol Listesi (SEÇİLEN)
- **Kapsam:** Seçili `Work Order`'a ait rota şablonundaki tüm operasyonlar ve bu operasyonlara
  bağlı tüm standart alt operasyonlar (`KTA Calisma Karti Alt Operasyonlari`) ağaçta yer alır.
- **Henüz Kart Açılmamış Adımlar:**
  - Kart listesi boş (`cards: []`),
  - İşlem adedi `0 Adet`,
  - Durum rozeti: `⚪ Başlanmadı` (`Not Started`),
  - Tüketim ve hurda miktarları `0`.
- **Avantajı:** Üretim mühendisi veya atölye şefi iş emrinin ne kadarının tamamlandığını,
  hangi adımların henüz başlamadığını tek bakışta görür.

---

## 4. Veri Modeli ve Mimari (Data Model & Architecture)

### 4.1 İlişki ve Eşleşme Zinciri
İş Emri ile Çalışma Kartı alt operasyonları arasındaki ilişki köprüsü şu zincirle kurulur:
1. `Work Order` -> Bağlı `Job Card` listesi (`work_order = wo.name`).
2. `Job Card.operation` -> `KTA Operation ERPNext Mappings` alt tablosu üzerinden
   `KTA Calisma Karti Operasyonlari` ana belgesine eşleşir.
3. `KTA Calisma Karti Operasyonlari` -> Bağlı `KTA Calisma Karti Alt Operasyonlari`
   tanımlarını içerir (`parent_operation = op.name`).
4. Fiili gerçekleşmeler: `Calisma Karti` belgesinin `custom_work_order = wo.name` ve
   `is_karti = jc.name` alanları üzerinden toplanır.

### 4.2 Malzeme Tüketim Formülü ve Kalite Filtresi
Her bir `Calisma Karti` belgesinin alt tablosu olan `Calisma Karti Alt Operasyon Kayitlari`
(`tabCalisma Karti Alt Operasyon Kayitlari` / kısaca `aok`) 3 hammadde yuvası barındırır:
- **Yuva 1:** `hammadde`, `boyut_1_mm`, `islem_adedi_1`, `adet`, `uom`
- **Yuva 2:** `hammadde_2`, `boyut_2_mm`, `islem_adedi_2`, `adet_2`, `uom_2`
- **Yuva 3:** `hammadde_3`, `boyut_3_mm`, `islem_adedi_3`, `adet_3`, `uom_3`

Tüketim hesaplaması şu kurallara göre derlenir:
1. **Belge ve Kalite Filtresi:** Sadece `docstatus != 2` (iptal edilmemiş) ve
   `quality_inspection_status NOT IN ('Reddedildi', 'Rejected', 'Red')` olan satırlar dahil edilir.
2. **Tüketim Alanı:** Her yuva için veritabanındaki `adet`, `adet_2`, `adet_3` alanları toplanır.
3. `is_tuketim_hesaplanir == 0` ise hammadde tüketim miktarı aranmaz veya `0` sayılır;
   yalnızca `islem_adedi` ve süre izlenir.
4. Kablo ve uzunluk bazlı hammaddeler (`boyut_X_mm > 0`):
   $\text{Tüketim (Metre)} = \frac{\text{boyut\_X\_mm} \times \text{adet\_X}}{1000}$
5. Diskret / parça bazlı bileşenler (`boyut_X_mm == 0` veya boş):
   Doğrudan `adet_X` değeri kümülatif tüketim olarak alınır.

### 4.3 Hurda Eşleştirme Kuralı (Scrap Association)
`tabCalisma Karti Hurda` tablosundaki kayıtlar şu mantıkla gruplanır:
1. **Alt Operasyon Hurda Eşleşmesi:** Hurda kaydındaki `parca_no` değeri, o operasyonun alt
   operasyonunda tanımlı hammadde kodlarından (`hammadde`, `hammadde_2`, `hammadde_3`) biriyle
   eşleşiyorsa, ilgili alt operasyonun `scraps` listesine dahil edilir.
2. **Operasyon Seviyesinde Genel Hurda:** `parca_no` herhangi bir alt operasyon hammaddesiyle
   doğrudan eşleşmiyorsa veya genel/ayrıştırılamayan bir ıskarta ise, Operasyon seviyesindeki
   `unmatched_scraps` listesinde kümülatif olarak gösterilir.

### 4.4 Mükerrerliksiz Çalışma Süresi Hesabı (Duration Aggregation)
Tek bir `Calisma Karti` belgesinde birden fazla alt operasyon kaydı (`aok` satırı) bulunabilir:
1. Alt operasyon bazındaki süre: O alt operasyon satırını içeren kartların `net_calisma_suresi`
   değerlerinin paylaştırılmış veya satır bazlı süresidir.
2. **Operasyon ve İş Emri Seviyesi Toplam Süresi:** Çift sayımı (double-counting) kesin olarak
   önlemek amacıyla, o operasyona veya iş emrine ait tekil `Calisma Karti` belgelerinin
   `net_calisma_suresi` değerleri bir kez toplanır:
   $$\text{Toplam Süre} = \sum_{ck \in \text{Unique Cards}} ck.\text{net\_calisma\_suresi}$$

---

## 5. Backend Servis Tasarımı (Backend Service Design)

### 5.1 Servis Dosya Yolu ve API
- **Servis Yolu:** `erpnextkta/kta_calisma_karti/services/work_card_analytics_service.py`
- **Çekirdek Fonksiyon:** `get_work_order_card_analytics(work_order: str) -> dict`
- **Exposed API:** `erpnextkta.kta_calisma_karti.api.get_work_order_card_analytics`
  (`@frappe.whitelist()`)

### 5.2 JSON Yanıt Şeması (Response Contract)
```json
{
  "work_order": "MFG-WO-2026-00001",
  "production_item": "KBL-001-XYZ",
  "item_name": "Standart Kablo Demeti",
  "qty": 100.0,
  "summary": {
    "total_cards": 5,
    "completed_cards": 4,
    "in_progress_cards": 1,
    "total_duration_mins": 340.5,
    "total_scrap_qty": 3.0
  },
  "operations": [
    {
      "operation_name": "Kesim ve Krimp",
      "job_card": "PO-0001-1",
      "status": "In Process",
      "total_duration_mins": 210.0,
      "unmatched_scraps": [
        {
          "item_code": "GEN-SCRAP-01",
          "qty": 1.0,
          "uom": "Adet",
          "reason": "Genel Hat Ayar Firesi"
        }
      ],
      "sub_operations": [
        {
          "sub_op_id": "Kesim ve Krimp-Otomatik Kesim",
          "title": "Otomatik Kesim",
          "sequence": 10,
          "status": "Devam Ediyor",
          "status_badge": "🔵 Devam Ediyor",
          "is_tuketim_hesaplanir": 1,
          "total_process_qty": 100.0,
          "total_duration_mins": 120.0,
          "consumptions": [
            {
              "item_code": "RAW-CBL-0.5-RED",
              "item_name": "Kırmızı Kablo 0.50mm2",
              "total_qty": 150.0,
              "uom": "Metre"
            }
          ],
          "scraps": [
            {
              "item_code": "RAW-CBL-0.5-RED",
              "qty": 2.0,
              "uom": "Metre",
              "reason": "Başlangıç Fire / Ayar"
            }
          ],
          "cards": [
            {
              "card_name": "CK-2026-00120",
              "operator": "Ahmet Yılmaz",
              "durum": "Tamamlandı",
              "net_calisma_suresi": 60.0,
              "islem_adedi": 50.0,
              "creation": "2026-11-19 09:30:00"
            }
          ]
        },
        {
          "sub_op_id": "Kesim ve Krimp-Manuel Lehim",
          "title": "Manuel Lehimleme",
          "sequence": 15,
          "status": "Başlanmadı",
          "status_badge": "⚪ Başlanmadı",
          "is_tuketim_hesaplanir": 1,
          "total_process_qty": 0.0,
          "total_duration_mins": 0.0,
          "consumptions": [],
          "scraps": [],
          "cards": []
        },
        {
          "sub_op_id": "Kesim ve Krimp-Görsel Kontrol",
          "title": "Görsel Kontrol ve Temizlik",
          "sequence": 20,
          "status": "Tamamlandı",
          "status_badge": "🟢 Tamamlandı",
          "is_tuketim_hesaplanir": 0,
          "total_process_qty": 100.0,
          "total_duration_mins": 35.0,
          "consumptions": [],
          "scraps": [],
          "cards": [
            {
              "card_name": "CK-2026-00125",
              "operator": "Ayşe Demir",
              "durum": "Tamamlandı",
              "net_calisma_suresi": 35.0,
              "islem_adedi": 100.0,
              "creation": "2026-11-19 11:15:00"
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 6. Frontend Bileşen Mimarisi (Frontend Architecture)

### 6.1 ShopfloorNavbar.vue Entegrasyonu
`ShopfloorNavbar.vue` bileşeni 3 sekmeli yapıya güncellenir:
```typescript
export type WorkOrderViewMode = "work_orders" | "operations" | "work_cards";

const tabs: NavTab[] = [
  { id: 'work_orders', icon: '⚡', label: 'Work Orders' },
  { id: 'operations', icon: '📋', label: 'Operations' },
  { id: 'work_cards', icon: '📇', label: 'Work Cards' },
];
```

### 6.2 Ana Panel: WorkCardAnalyticsPanel.vue
- `erpnextkta/public/shopfloor-hub/components/WorkCardAnalyticsPanel.vue` konumunda yer alır.
- Seçili iş emri değiştikçe backend API'sini asenkron çağırır (`get_work_order_card_analytics`).
- Üstte özet metrik kartları: Toplam Çalışma Kartı, Tamamlanan Kart, Toplam Süre, Toplam Hurda.
- Ortada operasyon bazlı tam rota listesi.
- Tüketimi hesaplanmayan adımlar için görsel rozet (`[ 🔍 Tüketimsiz Operasyon / Hizmet Adımı ]`).
- Başlanmamış alt operasyonlar için `⚪ Başlanmadı` rozeti ve sıfır adet gösterimi.

### 6.3 Alt Bileşen: WorkCardSubOperationCard.vue
- Her alt operasyonu akordeon stili katlanabilir bir kart olarak görüntüler.
- Başlık satırı: Alt operasyon adı, işlem adedi, durum rozeti (`⚪ Başlanmadı`, `🔵 Devam Ediyor`,
  `🟢 Tamamlandı`), toplam süre rozeti, tüketim rozeti.
- Gövde bölümü:
  - Tüketilen malzemeler listesi (Kod, Adı, Miktar, Birim),
  - Hurda kayıtları listesi (Kod, Neden, Miktar),
  - Katkı sağlayan `Calisma Karti` tablosu (Kart No, Operatör, Statü, Süre, İşlem Adedi).

### 6.4 Çok Dilli Sözlük Anahtarları (Title Case Standardı)
Aşağıdaki anahtarlar `tr.csv`, `en.csv` ve `de.csv` dosyalarına eklenir:
- `"Work Cards"` -> TR: `"Çalışma Kartları"`, DE: `"Arbeitskarten"`
- `"Sub-Operation Analytics"` -> TR: `"Alt Operasyon Analitiği"`, DE: `"Unteroperationsanalytik"`
- `"No Material Consumption"` -> TR: `"Tüketimsiz İşlem"`, DE: `"Kein Materialverbrauch"`
- `"Process Count"` -> TR: `"İşlem Adedi"`, DE: `"Bearbeitungsmenge"`
- `"Net Work Duration"` -> TR: `"Net Çalışma Süresi"`, DE: `"Nettoarbeitszeit"`
- `"Contributing Cards"` -> TR: `"Katkı Sağlayan Kartlar"`, DE: `"Beteiligte Karten"`
- `"Not Started"` -> TR: `"Başlanmadı"`, DE: `"Nicht Begonnen"`
- `"Unassigned Scraps"` -> TR: `"Eşleşmeyen Hurdalar"`, DE: `"Nicht Zugewiesener Ausschuss"`

---

## 7. Güvenlik, Hata Yönetimi ve Gizlilik

1. **SQL Enjeksiyonu Önleme:** Tüm sorgular Frappe ORM (`frappe.db.get_all`) veya
   parametrik `frappe.db.sql(..., values, as_dict=True)` kullanılarak çalıştırılacaktır.
2. **Defensive Null-Safety:**
   - Süre veya adet alanları boş (`None`) gelebilir; tüm toplamlar `flt(val or 0)` ile
     güvenliğe alınacaktır.
3. **Gizlilik ve Ticari Veri Politikası:**
   - Analitik ekranında veya kod tabanında hiçbir ticari birim fiyat veya özel firma unvanı
     yer almayacaktır. Yalnızca operasyonel adet, süre ve teknik malzeme kodları sergilenecektir.

---

## 8. Uygulama ve Doğrulama Adımları

1. **Backend Servisi ve Testler:**
   - `work_card_analytics_service.py` modülü kodlanacak,
   - `erpnextkta/kta_calisma_karti/tests/test_work_card_analytics.py` testleri yazılacak.
2. **Frontend Entegrasyonu ve Derleme:**
   - `ShopfloorNavbar.vue`, `types.ts`, `App.vue` güncellenecek,
   - `WorkCardAnalyticsPanel.vue` ve `WorkCardSubOperationCard.vue` eklenecek,
   - `bench build --app erpnextkta --production` komutuyla derlenecektir.
3. **Dokümantasyon:**
   - `erpnextkta/www/docs/` altındaki ilgili portal sayfaları güncellenecektir.
