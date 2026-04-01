# System Patterns — kta_calisma_karti

## Mimari Genel Bakış

```
Frontend (Vue 3 SPA)
    ↕  frappe.call() / frappe.realtime
Backend Facade: api.py          ← Tek stabil giriş noktası
    ↕ import
api_impl/ (implementasyon katmanı)
    ↕ frappe.get_doc / frappe.db
Frappe ORM → MariaDB
```

## Tasarım Desenleri

### 1. Facade Pattern (`api.py`)
```python
# api.py sadece re-export yapar
from .api_impl.cards import get_my_calisma_kartlari, get_calisma_karti_detail
from .api_impl.hurda import add_hurda, ...
```
- `api.py` dosyası sadece import ve re-export içermelidir. Asıl mantık `api_impl/` altında yer alır.
- Frontend tarafındaki metod isimleri `erpnextkta.kta_calisma_karti.api.*` şeklinde sabit kalmalıdır.

### 2. Vue Component Decomposition (Bileşen Parçalama)
- **Kural**: Bir Vue dosyası (özellikle `App.vue` veya ana görünümler) 500 satırı geçtiğinde veya mantıksal olarak ayrılabilir parçalar (liste kartı, filtre barı vb.) içerdiğinde mutlaka alt bileşenlere bölünmelidir.
- **Desen**:
  - `CkCard.vue`: Tekil veri gösterimi ve kart içi mantık.
  - `CkFilters.vue`: Arama/filtreleme UI ve state yönetimi.
  - `CkSkeleton.vue`: Yükleme durumu görseli (Shimmer efektli).
- **Fayda**: Kod okunabilirliği artar, stil kapsülleme (scoped CSS) daha verimli çalışır ve büyük dosyaların yönetimi kolaylaşır.

### 3. Role-Gate Pattern
```python
# Tüm write endpoint'lerinde:
if is_system_manager(): return  # tam yetki
if is_quality_user(): return    # QC yetki
emp = require_my_employee()
if doc.operator != emp: frappe.throw(...PermissionError)
```

### 3. Permlevel Bypass Pattern (QC)
```python
# kalite_kontrol alanı permlevel=1 → normal write izni işe yaramaz
_require_qc_role()          # ← sıkı kapı
doc.flags.ignore_permissions = True
doc.db_set("kalite_kontrol", val)  # güvenli bypass
```

### 4. Child Table Fieldname Discovery
```python
# first_child_table() — alan adı bilinmiyorsa deneme sırası
first_child_table(doc, ["hurdalar", "hurda", "calisma_karti_hurda"])

# get_child_table_fieldname() — meta üzerinden kesin bulma
meta = frappe.get_meta(parent_doc.doctype)
for df in meta.fields:
    if df.fieldtype == "Table" and df.options == child_doctype:
        return df.fieldname
```

### 5. Kümülatif Material Group Whitelist Pattern (v4)
Hammadde ve hurda listeleri, operasyonun iş akışındaki sırasına (`sequence`) göre kümülatif olarak genişletilir:

- **Alt Operasyon (Hammadde)**:
    - Akut Kısıt: Alt operasyonun kendi `allowed_material_groups` listesi doluysa **SADECE** o gruplar kullanılır.
    - Kümülatif Fallback: Liste boşsa, aynı ana operasyona bağlı olan ve sequence numarası mevcut olandan küçük/eşit olan **TÜM** alt operasyonların grupları + ana operasyonun grupları birleştirilir.
- **Hurda (Genel)**:
    - Aktif operasyondan önceki (sequence <= current) **TÜM** ana operasyonların ve bu ana operasyonlara bağlı **TÜM** alt operasyonların malzeme grupları serbest bırakılır.
- **Intersection**: Son liste, Work Order'ın `required_items` listesi ile bu izinli grupların kesişimidir.

### 8. Draft-First Lifecycle (v4)
- **Strateji**: Belgelerin veri girişi tamamlanmadan "Onaylı" (Submitted) olmasını engellemek için tüm yeni kayıtlar `docstatus: 0` (Taslak) olarak başlatılır.
- **Tetikleyici**: Belge sadece "Bitir" (Finish) aksiyonu sonucunda `doc.submit()` ile onaylanır. Diğer tüm ara işlemler (Başlat, Duraklat, Devam) Taslak belge üzerinde yürütülür.
- **Esneklik**: `islem_yap` metodu, hem taslak hem de onaylı belgelerde `db_set` kullanarak veri güncelleyebilir.

### 9. Cancelled Status Priority (UI)
- **Kural**: Belgenin `docstatus` değeri `2` (Cancelled) ise, frontend üzerindeki diğer tüm durum hesaplama mantığı baypas edilir.
- **Görünüm**: İptal edilen belgeler her zaman Gri ("İptal Edildi") olarak ve inaktif aksiyon butonlarıyla gösterilir.
- **Veri Kaynağı**: Detay ve Liste API'leri mutlaka `docstatus` alanını içermelidir.

### 6. Realtime Event Pattern
```python
# Her yazma işlemi sonrası (create.py, qc.py, ...):
publish_calisma_karti_changed(docname, reason="create:calisma_karti")
# →
frappe.publish_realtime("kta_calisma_karti:list_changed", ...)
frappe.publish_realtime(f"kta_calisma_karti:doc_changed:{docname}", ...)
```

Frontend'de:
```js
frappe.realtime.on("kta_calisma_karti:list_changed", handler)
```

### 7. Vardiya Sonu Akıllı Kapatma Deseni (Smart Shift-End)
Sistem, operatörlerin açık unuttuğu kartları her vardiya sonunda (16:00 ve 00:00) otomatik olarak kapatır.
- **Kapatma Zamanı**:
    - **Duruşta Olanlar**: Kartın fiilen durdurulduğu an (`durus_baslangic`) bitiş saati olarak kabul edilir.
    - **Çalışıyor Olanlar**: Vardiyanın resmi bitiş saati (**16:00** veya **00:00**) bitiş saati olarak kabul edilir.
- **Tetikleyici**: `hooks.py` içinde birleştirilmiş cron tanımı (`15 0,16 * * *`) ile günde iki kez çalışır.
- **Süre Sınırı**: 430 dakikalık net çalışma süresi sınırı, kart kapandıktan sonra kümülatif olarak `doc.update_durum()` tarafından uygulanır.
- **⚠️ Boundary Rule (Kritik)**: `_shift_name_by_now()` fonksiyonu `(start, end]` mantığı kullanır:
    - `time(0,0) < t <= time(8,0)` → 3. Vardiya
    - `time(8,0) < t <= time(16,0)` → 1. Vardiya
    - `time(16,0) < t` veya `t == time(0,0)` → 2. Vardiya
    - Tam sınır saati (16:00, 00:00, 08:00) her zaman **biten vardiyaya** aittir. `[start, end)` kullanılmamalıdır!

### 8. Server-Side Filtering Pattern
Büyük liste verileri içeren (Çalışma Kartları) Vue frontend ekranlarında, `computed` tabanlı tarayıcı düzeyinde döngülerden (client-side data arrays filtering) kaçınılır. Ara yüz sadece arama(`search_term`), durum(`durum`, `qc_filter`) parametrelerini backend'e gönderir. Süzme ve paginasyon işlemleri (SQL `WHERE` ve `LIMIT/OFFSET`) arka tarafta (`frappe.get_all` parametreleri ve `or_filters`) yapılır.

## Bileşen İlişkileri

```
Calisma Karti (Ana DocType)
  ├── hurdalar              → Calisma Karti Hurda
  ├── duruslar              → Operasyon Duruslari
  ├── idc_olcumleri         → Calisma Karti IDC Olcumleri
  ├── barkod_kayitlari      → Calisma Karti Barkod Kayitlari
  └── alt_operasyon_kayitlari → Calisma Karti Alt Operasyon Kayitlari

Bağlı ERPNext Doktipleri:
  is_karti   → Job Card → BOM (hurda ve IDC filtresi için)
  custom_work_order → Work Order → BOM
  is_istasyonu → Workstation
  operator   → Employee
  operasyon  → KTA Calisma Karti Operasyonlari (customer_group ile)
```

## Kritik Implementasyon Yolları

### CK Oluşturma:
`create_calisma_karti() → JC yükle → WO çöz → Status kontrol (docstatus=1, Not Started/In Process) → doc.insert() → publish_realtime → Departman tag ekle`

### 9. Operasyon → JC Eşleştirme Pattern
```
get_operations_for_job_card(job_card)
  → jc.operation + jc.production_item okunur
  → Tüm KTA Operasyonları + mapping satırları tek sorguda çekilir
  → Prio-1: erpnext_operation == jc.operation AND production_item == jc.production_item → döndür
  → Prio-2: erpnext_operation == jc.operation AND production_item boş → döndür
  → Prio-3: Hiç mapping satırı olmayan KTA operasyonları → döndür
```

### 10. Koşullu Autoname Pattern (KTA Operasyonlari)
```python
def autoname(self):
    op = self.calisma_karti_op.strip()
    cg = (self.customer_group or "").strip()
    self.name = f"{op}-{cg}" if cg else op
    # Generic: "Kablo Kesme" | Spec: "Kablo Kesme-BOSCH"
```

### 11. Standart Kalite Entegrasyon Pattern (MAT-QA)
```
QcToggle (Vue) → get_qc_templates_for_ck() 
  → (Şablon varsa) QualityInspectionModal.vue 
  → submit_kta_quality_inspection() 
      → frappe.new_doc("Quality Inspection")
      → Reference: Job Card (ck.is_karti)
      → ck.quality_inspection = qa.name
      → ck.kalite_kontrol = "Onaylandı" / "Reddedildi"
      → publish_realtime
```

### 11.5. Makine Günlük Bakım Workflow Deseni
Operatörün işe başlamadan veya iş sırasında makine kontrolü yapmasını sağlar:
- **Fetch**: `Bakim Talimati` (PTR.BT.049) içeriği HTML olarak çekilir.
- **UI**: `frappe.ui.Dialog` içinde talimat metni + Asset seçimi + Onay kutusu.
- **Record**: `Makine Gunluk Bakim Formu` (Submittable) oluşturulur ve `Calisma Karti`'ne referans verilir.
- **Validation**: Backend veya Frontend'de zorunlu tutulabilir (opsiyonel).

### 11.6. Test Masası Doğrulama Deseni (Planlanan)
Yüksek riskli operasyonlar için (Board testi vb.) uygulanan kalite güvence deseni:
- **Trigger**: `KTA Calisma Karti Operasyonlari.board_dogrulamasi_gerektirir == 1`.
- **Entity**: `Test Masasi Dogrulama Kaydi`.
- **Enforcement**: Kart bitirilirken (`Bitis`) bu kaydın varlığı ve onaylı olması kontrol edilebilir (Faz 2).

### 11.7. Birleşik Geliştirme ve Build İş Akışı
Modülün frontend ve backend bileşenlerinin senkronize kalmasını sağlayan iş akışı:
- **Kapsam**: `kta_calisma_karti/` ve `public/create|list|view-calisma-karti/` klasörleri.
- **Kural**: Frontend tarafındaki her `*.vue`, `*.ts` veya `*.css` değişikliği sonrası derleme zorunludur.
- **Komut**: `bench build --app erpnextkta --production`.

### 11.8. Modern SPA UI & Tema Deseni
KTA Çalışma Kartı arayüzü, endüstriyel cihazlarda yüksek performans veren bir Glassmorphism (Cam Efekti) mimarisi kullanır:
- **Tema Değişkenleri**: Renk kodları asla hardcode yazılmaz. `App.vue` kök dizininde `:root` ve `[data-theme="dark"]` içinde tanımlanan akıllı değişkenler (`var(--ck-glass-bg)`, `var(--ck-success-bg)`) kullanılır.
- **Performanslı Animasyon**: Sub-view değişimlerinde Vue'nun `<Transition mode="out-in">` elementi kullanılarak, sadece `opacity` ve `transform` manipüle edilir; işlemci tüketen CSS hesaplamalarından (layout thrashing) kaçınılır.
- **Akıllı Bileşen Durumu**: Semantic statüler (örn: Kalite için "Onaylandı", "Reddedildi"), Vue componentlerinde Computed Property yardımıyla saptanır ve ana konteynıra (`is-accepted`, `is-rejected`) CSS sınıfı olarak CSS Cascade avantajı kullanılarak geçirilir.

## Bileşen İlişkileri

```
Calisma Karti (Ana DocType)
  ├── hurdalar              → Calisma Karti Hurda
  ├── duruslar              → Operasyon Duruslari
  ├── idc_olcumleri         → Calisma Karti IDC Olcumleri
  ├── barkod_kayitlari      → Calisma Karti Barkod Kayitlari
  ├── alt_operasyon_kayitlari → Calisma Karti Alt Operasyon Kayitlari
  └── quality_inspection    → ERPNext Quality Inspection (Link)

## Kalite Kontrol (QC) Akış Örüntüleri

### 12. Draft & Auto-Submit Akışı
QI belgeleri `submit_kta_quality_inspection` ile oluşturulduğunda **docstatus=0** (Draft) olarak kaydedilir. Bu, operatörün kartı bitirene kadar kalite verilerini güncellemesine imkan tanır. Nihai onay (Submit), `Calisma Karti` "Bitir"ildiğinde (`_handle_bitis` -> `_submit_linked_quality_inspection`) otomatik olarak yapılır.

### 13. Kullanıcı Girdisini Koruma (`manual_inspection`)
ERPNext'in sunucu taraflı otomatik Accepted/Rejected hesaplamasının kullanıcı girdisini ezmesini önlemek için her ölçüm satırı için `manual_inspection: 1` ayarı eklenir.

### 14. Alan Eşleme (Reading Mapping)
- **Numerik**: `reading_1` kullanılır.
- **Metin/Yorum**: `reading_value` kullanılır.

### 16. Agresif Modal Susturma (Sıkıyönetim Modu)
Frontend sihirbazı açıkken, Frappe'nin standart ve kafa karıştırıcı hata modallarının kullanıcı deneyimini bozmasını önlemek için uygulanan desen:
- **Override**: `frappe.msgprint` fonksiyonu geçici olarak yakalanır ve sadece 'başarı' mesajlarının geçmesine izin verilir.
- **Poll & Clear**: Her 250ms'de bir `frappe.messages` kuyruğu zorla temizlenerek arka planda kalan bildirimlerin popup açması engellenir.
- **Local Error UI**: Yakalanan hatalar, bileşen içindeki `wizard-error-alert` kutusuna animasyonlu (`shake`) şekilde yansıtılır.

### 17. Smart Prefix Barkod Çözümleme
Kullanıcı girişini kolaylaştırmak için uygulanan örüntü:
- `2026-X` formatındaki girişler otomatik olarak `MFG-WO-2026-X` haline getirilir.
- `JOBX` veya sayısal ID'ler `PO-JOBX` veya ilgili `PO-` önekleriyle zenginleştirilir.
- Bu işlem hem frontend (`App.vue`) hem de backend (`barcode.py`) düzeyinde normalize edilir.

### 18. QI Statü Senkronizasyonu ve Restorasyon Deseni
Kalite belgesi (QI) ile Çalışma Kartı (CK) arasındaki derin entegrasyonu yöneten desendir:
- **Linkage Protection**: Bir karta QI belgesi bağlandığı anda, hem Backend (`qc.py`) hem de Frontend (`useCalismaKartiUi.ts`) seviyesinde manuel kalite güncellemeleri kilitlenir. Tek veri kaynağı QI belgesi olur.
- **Dynamic Restoration**: QI statüsü "Rejected" durumundan "Accepted" durumuna döndüğünde, kartın genel durumu (`durum` alanı) körü körüne eski haline getirilmez. Bunun yerine `ck.get_durum()` metodu tetiklenerek, kartın o anki zaman kayıtlarına (Çalışıyor, Duruşta, Hazır) göre en güncel ve doğru statü otomatik olarak hesaplanıp restore edilir.
### 20. 1:1 Çift Yönlü Hurda Senkronizasyon Deseni (Bidirectional Sync)
Her `Calisma Karti` ile bir `Stock Entry` (Scrap for Manufacturing) arasında 1:1 ilişki kuran ve veri tutarlılığını her iki yönde koruyan desendir:
- **Kaynak (Source)**: `scrap_stock_entry` alanı kart üzerindeki tekil bağlantıdır.
- **Döngü Koruması**: `frappe.flags.syncing_hurda_from_se` ve `syncing_hurda_from_card` bayrakları ile bitmeyen güncellemeler engellenir.
- **Konsolidasyon Yok**: Operatör bazlı takip için İş Emri seviyesinde birleştirme yapılmaz; her kart kendi belgesini yönetir.
- **ID Eşleme**: Karta eklenen her hurda satırı, SE'deki karşılığının ID'sini (`stock_entry_detail_id`) saklar.

### 21. Controller-Level After-Submit Sync Deseni
Frappe'nin standart "Onaylı belgede değişiklik yapılamaz" kuralını bypass ederek senkronizasyonun devam etmesini sağlayan desendir:
- **Tetikleyici**: Controller içindeki `on_update_after_submit` metodu.
- **Uygulama**: `ck_doc.save(ignore_permissions=True)` çağrısı ile onaylı kartlar üzerinde alt tablo güncellemeleri yapılır.
- **Bypass Flag**: `doc.flags.ignore_validate_update_after_submit = True` kullanılarak standart validation'lar aşılır (sadece hurda tablosu için).

### 22. DB-Level Field Protection Pattern (Work Order Restoration)
ERPNext'in standart `Stock Entry` validasyonlarının `job_card` yoksa `work_order` alanını temizlemesini engellemek için kullanılır:
- **Mekanizma**: `se_doc.save()` veya `insert()` işleminden hemen sonra `frappe.db.set_value` ile veriyi doğrudan DB'ye zorla yazma.
- **Gerekçe**: Bellekteki (in-memory) döküman objesi validasyon sırasında alanı boşaltsa dahi, işlem bitiminde DB seviyesinde veri restore edilmiş olur.
### 23. Modal Teleportation Pattern (Vue 3)
Modalların (Hurda, Kalite vb.) `sticky` elementler veya farklı `stacking context` (z-index) yaratan konteynırlar tarafından perdelenmesini önlemek için kullanılan desendir:
- **Uygulama**: Modal template'i `<Teleport to="body">` ile sarmalanır.
- **Fayda**: Modal, DOM ağacında en üst seviyeye (body) taşınarak, uygulama içindeki hiyerarşiden bağımsız olarak her zaman en üst katmanda renders edilmesi garanti altına alınır.

### 24. Vue Reactivity State Leakage Koruma Deseni (Asenkron Sızıntı)
Vue'nun SPA (Single Page Application) yapısında, router üzerinden geçiş yapıldığında component unmount edilmeyebilir (özellikle aynı route, farklı referans ile). Asenkron işlemler esnasında state sızıntısını önlemek için uygulanan ZORUNLU desendir:
- **Sorun**: Örneğin Kalite kontrol şablonunu getirmek için atılan `await getQcTemplates()` isteği 500ms sürerken, kullanıcı "Geri" tuşuyla sayfalar arasında gezinip farklı bir karta (Kart 2) geçerse; API'den dönen cevap Kart 1'e ait olmasına rağmen, ekran aktif olan Kart 2 üzerinde açılır. "Kendiliğinden bambaşka karta belge oluştu ve kafasına göre parametre koydu" hatasının kök nedenidir.
- **Çözüm**: Her asenkron ağ (network) işleminin başında `const currentDocname = docname.value` hafızaya alınır. `await` satırından hemen sonra `if (docname.value !== currentDocname) return;` kontrolü yapılarak işlem derhal **iptal edilir**. Modal submit işlemleri de döküman adını argüman olarak doğrudan hafızadan sabitlemelidir.

### 25. Pessimistic Locking & State Bypass Koruması (Yarış Durumu)
Çoklu tıklama (Double Submit) veya UI atlatma (Bypass) durumlarında veritabanı tutarlılığını korumak için uygulanan backend desenidir:
- **Yarış Durumu (Race Condition)**: `islem_yap` API'si (Başlat, Duraklat, Bitiş) çağrıldığında kart durumu belleğe alınır. Art arda iki istek gelirse, okunan bellekteki değer (örneğin `tamamlanan_miktar = 10`) her iki işlemde de 10 olarak baz alınır ve üzerine eklenir; data kaybı yaşanır.
- **Çözüm**: Kritik yazma işlemlerinde (Status, Miktar) `frappe.get_doc("Calisma Karti", docname, for_update=True)` kullanılarak satır MySQL seviyesinde kilitlenmeli veya Redis cache ile 5 saniyelik debounce/cooldown (Rate Limiting) uygulanmalıdır.
- **State Bypass**: Vue UI, kart "Bitmiş" veya "Reddedildi" olduğunda form girişlerini gizleyebilir ancak art niyetli/gecikmeli HTTP istekleri (Hurda API'si, Barkod Kaydı API'si, IDC API'si) doğrudan backend'e ulaşabilir. Bu child-table API'lerinin hepsi **en başta** `frappe.db.get_value("Calisma Karti", ck_name, ["docstatus", "durum"])` ile kartın yetki ve statü denetimini taze biçimde yapmak zorundadır.

### 26. Operasyonel Miktar Kısıtı Doğrulama Deseni (Planlanan/Konfigürasyonel)
Alt operasyonlara girilen üretim miktarlarında zorunlu üst kısıt (Upper Bound Limit) kontrolünün tek tip değil, operasyon tipine göre ayrıştığı dinamik validasyon desenidir:
- **Son Kontrol ve Paketleme Operasyonu**: Girilen miktar, Work Order'daki (İş Emri) **üretilmesi hedeflenen (qty)** miktardan büyük **Olamaz**.
- **IDC ve Soket Basma Operasyonları**: Girilen miktar, Work Order'ın BOM'undaki (Ürün Ağacı) ilgili bileşenin **sarf (tüketim) miktarına** bakılarak doğrulanır.
- **Tolerans (Overproduction)**: Endüstriyel üretimde sıfır hata toleransı mümkün olmayabilir (%10 Üretim Fazlası Payı). Bu durum ciddi konfigürasyon gerektirir (`KTA Calisma Karti Settings` içinde global % tolerans veya `KTA Calisma Karti Operasyonlari` DocType'ına "Miktar Kısıt Tipi" [None, WorkOrder, BOM] ve "Tolerans Yüzdesi" eklenerek modellenmelidir).

