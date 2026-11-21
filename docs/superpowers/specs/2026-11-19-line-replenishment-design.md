# KTA Hat İkmal Yönetimi (Line Replenishment Engine) Tasarım Dokümanı

**Tarih:** 2026-11-19  
**Durum:** Taslak (Draft) - Mimari Tasarım  
**Kapsam:** `kta_stock`, `kta_shopfloor`, `erpnextkta`  

---

## 1. Yönetici Özeti ve Problem Tanımı

### 1.1 Mevcut Durum ve Sorun
Kablo montaj ve tesisat üretim hatlarımızda, hammaddeler ana ambarlardan hat depolarına ikmal
edilmektedir. Mevcut işleyişte şu darboğazlar yaşanmaktadır:
1. **Reaktif İkmal Baskısı:** Üretim teyidi (Work Card) sırasında hat deposunda hammadde
   tükendiğinde operatör durmakta ve acil transfer talep etmektedir.
2. **Hatta Malzeme Bekleme Duruşları:** Hat depolarının stok durumu önceden taranmadığı için
   operatörler vardiya ortasında bekleme duruşlarına girmektedir.
3. **Manuel ve Parçalı Çekme:** Lojistik personeli hangi hatta ne kadar net hammadde açığı
   olduğunu tek bir merkezden toplu ve proaktif biçimde görememektedir.
4. **Hatlar Arası Dengesiz WIP ve Atıl Stok:** Bir hatta malzeme fazlası dururken kardeş
   hatta aynı malzeme tükendiğinde ana depodan tekrar çekim yapılmakta, bu da sahada atıl
   WIP stoklarının şişmesine ve ana ambarın erken tükenmesine yol açmaktadır.

### 1.2 Hat İkmal Yönetimi (Line Replenishment Engine) ile Çözüm
Proaktif hat ikmal metodolojisi uyarlanarak:
- Hat depolarındaki (`source_warehouse`) rezervasyon açıkları önceden hesaplanır.
- Kardeş üretim hatlarındaki serbest stoklar taranarak hatlar arası dengeleme önceliklendirilir.
- Depo ekibi vardiya öncesinde açık miktarını topluca görür ve ikmal emri başlatır.
- Ana ambardan veya kardeş hattan yönlendirilmiş toplama (guided picking) ve transfer yapılır.
- Üretim hattı vardiyaya başlamadan önce tüm gerekli komponentler hatta hazır edilir.

---

## 2. Amaç, Kapsam ve Temel Prensipler

### 2.1 Temel Hedefler (Goals)
* Hat depolarındaki anlık stok ve üretim rezervasyonlarını kıyaslayarak net açığı tespit etmek.
* **Akıllı Kaynak Tahsisi (Smart Sourcing & WIP Netting):** Açık tespit edildiğinde
  ana ambar (`110 HAMMADDE`) öncesinde kardeş hat depolarındaki (`150 ÜRETİM` altı) serbest
  stokları tarayıp hatlar arası dengeleme transferi (`Line-to-Line Transfer`) önermek.
* Kardeş hatlarda serbest stok yoksa ana ambardan FIFO (en eski parti/giriş) önerisi sunmak.
* Depocuya/kullanıcıya önerilen kaynak depoyu tek tıkla ana ambar (`110 HAMMADDE`) yapabilme
  inisiyatifi (manual override/fallback) sağlamak.
* **Zorunlu Tek Hedef Hat (Mandatory Single Target WIP Warehouse):** Kokpitte ve servislerde
  hedef WIP deposu seçimini zorunlu tekil tutarak karma çekimleri engellemek ve transferleri
  tek bir hatta kilitlemek.
* Depocuya mobil arayüzde barkod okutmalı, pratik ve hatasız yönlendirmeli toplama sağlamak.
* Sahada ambalaj/bobin bütünlüğü için kontrollü toleranslı fazla toplama (over-picking) sunmak.
* Toplama tamamlandığında arka planda tek adımda `Stock Entry (Material Transfer)` fişi üretmek.

### 2.2 Kapsam Dışı (Non-Goals)
* Satın alma siparişi veya fason transferi süreçlerinin bu ekrandan yönetilmesi.
* Doğrudan hammadde sarfiyatı (Backflush) yapılması (sarfiyat Work Card teyitlerine aittir).
* Birden fazla hedef hatta ait malzemelerin tek bir emirde karma toplanması (operasyonel
  karışıklık ve yanlış teslimat riski nedeniyle kesinlikle kapsam dışıdır).

---

## 3. Mimari Kararlar ve İş Akışı

### 3.1 Modül Sorumluluk Ayrımı ve Sahiplik Modeli
ERPNext depo mimarisine ve KTA modüler yapısına tam uyum sağlamak amacıyla kesin modüler
ayrım yapılmıştır:

1. **`kta_stock` Modülü (Sahip ve İcra Makamı):**
   - `KTA Line Replenishment Order` ve `KTA Line Replenishment Item` DocType'larının tek sahibidir.
   - FIFO raf/parti tahsis motoru, kaynak depo önceliklendirmesi ve dengeleme mantığını yürütür.
   - Depocu mobil el terminali arayüzünü (`Line Replenishment Picking`) barındırır.
   - Toplama tamamlandığında resmi `Stock Entry (Material Transfer)` fişini üretir ve onaylar.

2. **`kta_shopfloor` Modülü (Talep ve Analitik Sağlayıcı):**
   - Yalnızca üretim rezervasyon açıklarını hesaplayan analitik talep motorunu sağlar
     (`reservation_deficit_service`).
   - Tekil seçilen hat bazlı iş emri operasyonlarını, terminleri ve gereksinimleri tarar.
   - İkmal ihtiyacını `kta_stock` modülüne hatta özel ikmal talebi olarak besler.
   - Masaüstü Hat İkmal Kokpiti (`Line Replenishment Hub`) analiz ve başlatma ekranını sunar.

### 3.2 İhtiyaç ve Açık Hesaplama Motoru (`kta_shopfloor: reservation_deficit_service`)
İkmal ihtiyacı aşağıdaki formülle tespit edilir:
1. Analiz edilecek hedef hat deposu (`target_warehouse`) kullanıcı tarafından zorunlu tekil
   olarak seçilir (karma liste taraması engellenmiştir).
2. Seçilen hedef hattın aktif iş emirlerine ait üretim rezervasyonları taranır.
3. `tabBin` üzerindeki `reserved_qty_for_production` ile `actual_qty` karşılaştırılır.
4. `Net Açık = reserved_qty_for_production - actual_qty`
5. Yalnızca `Net Açık > 0` olan kalemler o hatta özel ikmal havuzuna dahil edilir.

```text
+-----------------------------+      +------------------+
| reserved_qty_for_production |  -   |    actual_qty    | = Net Acik (Deficit Qty)
+-----------------------------+      +------------------+
                                               |
                                               v  (Deficit > 0 ise)
                                     +----------------------+
                                     | Hat Ikmal Havuzu     |
                                     | (Tek Hedef WIP Icin) |
                                     +----------------------+
```

### 3.3 Akıllı Kaynak Tahsisi ve Hat İçi Serbest Stok Dengelemesi (Smart Sourcing & WIP Netting)
Net açık hesaplandıktan sonra sistem doğrudan ana depoya gitmez. Aşağıdaki hiyerarşi işletilir:

1. **Kardeş Üretim Depolarının Taranması (`150 ÜRETİM` Grubu):**
   - Hedef hat deposu (örn. `1501 KESMELER`) için açık saptandığında, sistem aynı grup altındaki
     kardeş üretim ambarlarını (örn. `1503 RATIONAL`, `1509 BOSCH`, `1505 MONTAJ` vb.) tarar.
2. **Serbest Stok Formülü:**
   `Serbest Stok = actual_qty - reserved_qty_for_production`
3. **Hatlar Arası Dengeleme Transferi Önceliği:**
   - Eğer kardeş hatta `Serbest Stok > 0` ise, ikmal emrinde öncelikli kaynak olarak kardeş hat
     deposu önerilir (`suggested_source_warehouse = 1503`).
   - Böylece üretim sahasındaki atıl hammadde birikmesi önlenir, WIP şişmesi engellenir ve
     ana ambar stoklarının erken tükenmesinin önüne geçilir.
4. **Ana Depo Fallback (Kullanıcı İnisiyatifi):**
   - Kardeş hatlarda serbest stok yoksa veya yetersizse, kalan miktar için ana ambar
     (`110 HAMMADDE`) kaynak gösterilir.
   - Depo personeli ya da hat lideri, ekrandaki tek bir buton/aksiyon ile kaynak depoyu
     dilediği zaman ana ambara (`110 HAMMADDE`) çevirebilir (manual override).

```text
[ Net Acik Saptandi ] -> Hedef: 1501 KESMELER (Tekil WIP)
          |
          v
[ Kardes Hatlari Tara (150 URETIM Alt Grubu) ]
          |
          +---> Serbest Stok Var mi? (actual_qty - reserved_qty_for_production > 0)
          |           |
          |           |-- EVET --> [ Oncelikli Oneri: Dengeleme Transferi (1503 -> 1501) ]
          |           |
          |           +-- HAYIR -> [ Ana Ambar: 110 HAMMADDE (FIFO Parti Tahsisi) ]
          |
          +---> [ Fallback: Istenirse Tek Tikla 110 HAMMADDE Secilebilir ]
```

### 3.4 Parti ve Raf Tahsis Motoru (FIFO / `kta_stock`)
Seçilen kaynak depoya (kardeş hat veya ana ambar) göre parti tahsisi yapılır:
- İlgili kalemin partili stokları FIFO kuralına göre (en eski parti / SKT / giriş tarihi) sıralanır.
- Stokta bulunan raf adresi (`Bin Location`) ve parti numarası depocuya önerilir.
- Sahadaki ambalaj bütünlüğü (ör. 500m bobin, 1000 adetlik paket) nedeniyle depocu alternatif
  parti okutabilir ve belirlenen tolerans dahilinde fazla toplama (over-picking) yapabilir.

### 3.5 İki Aşamalı Belge ve Stok Akışı
Süreç iki temel aşamadan oluşur:
1. **Aşama 1 - Hat İkmal Emri Oluşturma (`KTA Line Replenishment Order`):**
   Sistem veya depo amiri `KTA Line Replenishment Order` dokümanını taslak (`Draft`) açar.
   Emir, tekil `target_warehouse` hedefine kilitlenir. Akıllı kaynak tahsisi ile belirlenen
   kaynak depo, önerilen parti ve miktarlar satırlara işlenir.
2. **Aşama 2 - Mobil Toplama ve Otomatik Transfer (`Stock Entry`):**
   Depocu el terminalinden partiyi/rafı okutarak toplar (`picked_qty`, `picked_batch_no`).
   Toplama tamamlandığında emrin statüsü `Completed` olur; arka planda otomatik olarak
   tekil hedef hatta kilitli `Stock Entry (Material Transfer)` üretilir, submit edilir
   (`docstatus=1`) ve emirle bağlanır.

### 3.6 Tetikleme Modeli (Hibrit)
- **Periyodik Arka Plan Cron:** Vardiya değişimlerinden önce (ör. 07:00, 15:00, 23:00)
  tanımlı her bir WIP deposu için ayrı ayrı açık taraması yapar ve taslak ikmal emirlerini
  hat bazlı ambar havuzuna düşürür.
- **Anlık Masaüstü Kokpit:** Depo amiri veya hat lideri gün içinde dilediği an kokpiti açıp
  hedef WIP deposunu seçerek anlık açık analizi yapabilir ve tek tıkla ikmal emri başlatabilir.

### 3.7 Zorunlu Tek WIP Deposu Kuralı (Mandatory Single Target WIP Warehouse)
Hat İkmal Kokpiti'nde ve arka plan servislerinde `target_warehouse` (Hedef WIP Deposu) seçimi
kesinlikle **zorunlu tekildir (Mandatory Single-Select)**.

#### Kuralın Operasyonel Gerekçeleri ve Mimari Kazanımları:
1. **Operasyonel Kargaşanın Önlenmesi:**
   Depo bazlı ayrıştırma olmadan tüm hatların karma liste halinde çekilmesi sahada malzeme
   karışıklığına, yanlış hatta teslimat riskine ve hat duruşlarına neden olur. Bu sebeple
   çoklu hat/depo seçimi kesin olarak engellenmiştir.
2. **Tek Hat Lojistik Rotası:**
   Depo çekme ve dağıtım rotası tek bir fiziksel hatta odaklanır. Lojistik personeli çekme
   arabasını tek bir hedef hat için hazırlar, gereksiz dolaşımı ve çapraz taşımayı engeller.
3. **Hat Liderine Net Teslimat ve Kabul:**
   Her hat lideri yalnızca kendi hattına ait Çekme Listesi'ni (Pull List) teslim alır ve
   onaylar. Hatlar arası zimmet ve malzeme kabul belirsizlikleri tamamen ortadan kalkar.
4. **Atomik Stok Fişi Güvencesi:**
   Oluşturulan `KTA Line Replenishment Order` ve arka plandaki `Stock Entry (Material Transfer)`
   tek bir `target_warehouse` hedefine kilitlenir. Tek bir transfer fişinde çoklu hedef
   depo karmaşası yaşanmaz, ERPNext stok hareketleri atomik ve tam izlenebilir kalır.

---

## 4. Veri Modeli ve Şema Tasarımı

DocType isimleri Frappe standartlarına uygun şekilde tekil ve İngilizce tanımlanmıştır.
DocType'lar kesin olarak `kta_stock` modülü altında konumlandırılmıştır.

### 4.1 `KTA Line Replenishment Order` (Parent DocType)
Modül: `kta_stock`  
İsim Formatı: `LRO-.YYYY.-.#####`

| Alan Adı | Tip | Açıklama |
|---|---|---|
| `naming_series` | Select | Seri no (`LRO-.YYYY.-`) |
| `target_warehouse` | Link (Warehouse) | Hedef hat deposu (Zorunlu tekil, değiştirilemez) |
| `posting_date` | Date | Belge tarihi |
| `posting_time` | Time | Belge saati |
| `status` | Select | `Draft`, `In Progress`, `Completed`, `Cancelled` |
| `sourcing_strategy` | Select | `Smart Sourcing (WIP First)`, `Main Warehouse Only` |
| `stock_entry` | Link (Stock Entry)| Otomatik oluşan transfer fişi referansı |
| `company` | Link (Company) | Şirket bilgisi |
| `total_deficit_qty` | Float | Toplam açık miktarı |
| `total_picked_qty` | Float | Toplam toplanan miktar |
| `items` | Table | İkmal satırları (`KTA Line Replenishment Item`) |
| `remarks` | Small Text | Açıklama ve notlar |

### 4.2 `KTA Line Replenishment Item` (Child DocType)
Modül: `kta_stock`  
Parent: `KTA Line Replenishment Order`

| Alan Adı | Tip | Açıklama |
|---|---|---|
| `item_code` | Link (Item) | Malzeme kodu |
| `item_name` | Data | Malzeme adı |
| `uom` | Link (UOM) | Birim |
| `reserved_qty` | Float | Hat deposundaki rezervasyon |
| `line_actual_qty` | Float | Hat deposundaki mevcut fiziksel stok |
| `deficit_qty` | Float | Hesaplanan net açık miktarı |
| `sourcing_type` | Select | `Line Transfer` / `Central Warehouse` |
| `free_stock_qty` | Float | Kardeş hatta bulunan serbest stok miktarı |
| `suggested_source_warehouse`| Link (Warehouse) | Önerilen kaynak depo (Kardeş hat veya 110) |
| `suggested_batch_no` | Link (Batch) | FIFO ile önerilen parti no |
| `picked_qty` | Float | Fiilen toplanan transfer miktarı |
| `picked_source_warehouse` | Link (Warehouse) | Fiilen toplanan kaynak ambar/raf |
| `picked_batch_no` | Link (Batch) | Fiilen toplanan parti no |
| `is_picked` | Check | Satır toplandı bayrağı |

---

## 5. Kullanıcı Deneyimi ve Arayüz Mimarisi

İki farklı kullanıcı profili için çift yüzlü mimari uygulanır:

```text
[ Hedef WIP Deposu Secimi (Zorunlu Tekil) ]
                    |
                    v
[ 1. Hat Ikmal Kokpiti (kta_shopfloor) ] -----(Emir)-----> [ KTA Line Replenishment Order ]
   (Tek Hatta Ozel Net Rezervasyon Acigi)                         (Hedef Depoya Kilitli)
                                                                       |
                                                                       v
                                                           [ 2. Hat Ikmal Toplama ]
                                                            (Line Replenishment Picking)
                                                                       |
                                                                       v
                                                           [ Stock Entry: Transfer ]
                                                            (Tek Hedef Depoya Atomik)
```

### 5.1 Hat İkmal Kokpiti (Line Replenishment Hub - Desk)
- Planlamacı ve depo amirinin kullandığı analiz ekranıdır.
- `target_warehouse` (Hedef WIP Deposu) seçimi **zorunlu tekildir (Mandatory Single-Select)**.
- Depo seçimi yapılmadan analiz çalıştırılamaz; tüm hatların karma liste halinde çekilmesi
  operasyonel riskleri önlemek adına kesinlikle engellenmiştir.
- Kullanıcı tek bir WIP deposu (ör. `1501 KESMELER - KTA`) seçtiğinde, sistem yalnızca o WIP
  deposunun aktif iş emirlerindeki net rezervasyon açıklarını hesaplar.
- O hatta özel Çekme Listesi (Pull List) üretir.
- Kaynak önerilerini (Kardeş Hat vs. Ana Ambar) gösterir; kullanıcının tek tıkla kaynak depoyu
  `110 HAMMADDE` ambarına çekmesine imkan tanır (manual override).
- Seçilen kalemler için hedefe kilitli tekil `KTA Line Replenishment Order` üretir.

### 5.2 Hat İkmal Toplama (Line Replenishment Picking - PDA / Mobil)
- Depocunun sahada el terminalinde (PDA) kullanacağı basit, ergonomik arayüzdür.
- Açık emirleri listeler; depocu emri seçip kaynak raf/depo adresine yönlendirilir.
- Kaynak kardeş hat ise hat adresini, ana ambar ise ana ambar rafını gösterir.
- `KTA Stock Label` barkodu veya parti barkodu okutulduğunda parti ve miktar doğrulanır.
- Tolerans dahilinde fazla toplama veya alternatif parti seçimi anında onaylanır.
- Toplama bittiğinde "Transferi Tamamla" butonuyla resmi stok fişi (`Stock Entry`) oluşur.

---

## 6. Güvenlik, Hata Yönetimi ve Toleranslar

### 6.1 Fazla Toplama (Over-Picking) Toleransı
- Bobin, makara ve kapalı kutu ürünlerde malzeme bölünemez.
- Kalem bazında tanımlı tolerans oranı (ör. %10) veya tam paket katsayısı kadar
  fazla toplama sistem tarafından kabul edilir.
- Kabul edilen fazla miktar hat deposuna aktarılır ve sonraki teyitler için rezervde kalır.

### 6.2 Barkod ve Parti Doğrulama
- Depocu önerilen partiden farklı bir parti okuttuğunda:
  1. Partinin aynı kaleme ait olup olmadığı kontrol edilir.
  2. Partinin blokeli, karantinada veya SKT'si geçmiş olup olmadığı doğrulanır.
  3. Koşullar uygunsa alternatif parti `picked_batch_no` alanına işlenir.

### 6.3 İptal ve Ters Kayıt (Rollback)
- `In Progress` durumundaki emirler doğrudan iptal edilebilir.
- `Completed` olmuş ve `Stock Entry` fişi oluşmuş emirlerde iptal işlemi, ilgili `Stock Entry`
  fişinin Frappe standartlarında iptal edilmesi (`cancel`) ile eş zamanlı yürütülür.

---

## 7. Modüller Arası Entegrasyon ve Sorumluluk Matrisi

| Modül / Ajan | Sorumluluk Alanı |
|---|---|
| `kta_shopfloor` | Tekil hat rezervasyon açığı analizi, Hat İkmal Kokpiti arayüzü |
| `kta_stock` | Emir DocType sahipliği, akıllı kaynak (WIP netting), PDA toplama, Transfer fişi |
| `overrides-hooks` | Cron zamanlaması (`hooks.py`), DocType izin ve hook entegrasyonu |
| `docs-i18n` | Son kullanıcı portal rehberi (`/docs/`) ve TR/EN/DE çevirileri |
