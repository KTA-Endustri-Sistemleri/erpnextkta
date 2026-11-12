# Design Dokümanı: KTA Tooling (Kalıp, Aplikasyon & Üretim Araçları) Yönetimi

* **Tarih:** 2026-11-12
* **Durum:** Faz 1 Tamamlandı (Commit: `ac4304b`), Faz 2 Genişletilmiş Mimari Tasarımı (KTA Tooling)
* **İlgili Branch:** `feat/enjeksiyon-kalip-no`
* **Kapsam:** İki Parçalı Uygulama Planı:
  - **Faz 1 (Tamamlandı):** Enjeksiyon kalıp ana verisi (`KTA Enjeksiyon Kalibi`), 46 kalıp otomatik aktarımı, Link alanları, backend doğrulamaları ve 320px responsive UI ergonomisi.
  - **Faz 2 (KTA Tooling):** Enjeksiyon kalıpları ile krimp aplikasyon kalıplarını tek bir kurumsal **`KTA Tooling`** ana veri çatısı altında birleştirme; `930-Tools` (`933-Injection Molds`, `934-Crimp Applicators`) Item Group senkronizasyonu; takım yatırımı & müşteri geri ödemesi; kalıphane kritik yedek parça listesi; çift makine tandem çalışma & kısmi arıza yönetimi; göz sayısı oranlı vuruş sayacı; varsayılan BOM akıllı eşlemesi ve Seçenek C canlı darboğaz kilidi (Concurrency Guard).

---

## 1. Giriş ve İhtiyaç Analizi (Intent & The Why)

Kablo gruplama (wire harness) fabrikalarında üretimin ana darboğazını ve ürün kalitesini belirleyen iki temel üretim takımı (tooling) ailesi bulunur:
1. **Krimp Aplikasyon Kalıpları (Crimp Applicators / Mini-Applicators):** Preslere takılan, terminalleri kabloya çakan yüksek hassasiyetli kalıplar (Örn: `Kalıp 287`, `Kalıp 1026`).
2. **Plastik Enjeksiyon Kalıpları (Injection Molds):** Gromet, konnektör gövdesi ve aşırı kalıplama (overmolding) yapan enjeksiyon kalıpları (Örn: `8718645633`, `8710506150`).

Her iki takım türünün de kurumsal fabrika operasyonundaki kaderi ve iş modeli **birebir aynıdır**:
- **Kısıtlar Teorisi (TOC):** Fabrikada 16 enjeksiyon makinesi veya onlarca krimp presi boş olsa dahi üretim ancak fiziksel kalıp/aplikatör kopyası (`available_qty / mevcut_adet`) kadar yapılabilir.
- **Kalıp Yatırımı ve Geri Ödeme (Tooling Investment & Reimbursement):** Otomotiv ve beyaz eşya ana sanayisinde (Bosch, Siemens, OEM) kalıplar ve aplikatörler müşteri adına yaptırılır ve yatırım bedelleri daha sonra müşteriye fatura edilir veya parça fiyatı içinde amorti edilir. Bu nedenle takımların ERPNext'te kurumsal bir `Item` (`930-Tools` hiyerarşisinde) karşılığı olması finansal ve operasyonel bir zorunluluktur.
- **Tandem / Çift Makine Çalışma:** Operatörler aynı iş emrinde yan yana duran iki tezgahı (iki enjeksiyon makinesi veya çift krimp) eş zamanlı çalıştırabilmektedir.
- **Kalıphane Ömür, Vuruş (Stroke) ve Yedek Parça Takibi:** Her iki takım ailesinde de mekanik aşınma baskı/vuruş sayısına bağlıdır (örn: krimpte 100.000 vuruşta bıçak/örs değişimi, enjeksiyonda 50.000 vuruşta kalıphane bakımı). Kritik yedek parçaların (bıçak, örs, lokma, itici pim, meme rezistansı) raf stoğu takım kartından izlenmelidir.

Bu nedenlerle mimari, yalnızca enjeksiyonla sınırlı kalmayıp global endüstri standardı olan **`KTA Tooling` (Kalıp & Aplikasyon Yönetimi)** çatısı altına genişletilmiştir.

---

## 2. Hedefler, Kapsam Dışı ve Anti-Hedefler

### Hedefler (Goals)
* **Birleşik `KTA Tooling` Ana Veri Modeli:**
  - Enjeksiyon kalıplarını (`Injection Mold`) ve Krimp aplikatörlerini (`Crimp Applicator`) ortak bir varlık çatısında yönetmek.
  - Faz 1'deki 46 kalıp kaydını sıfır veri kaybıyla `KTA Tooling` modeline taşımak (`tool_type: "Injection Mold"`).
* **`930-Tools` Item Group Entegrasyonu:**
  - Mevcut `930-Tools` hiyerarşisi altına `933-Injection Molds` ve `934-Crimp Applicators` gruplarının eklenmesi.
  - `KTA Tooling` kaydedildiğinde aynı kodla (`Item.item_code == tool_code`) arka planda otomatik `Item` oluşturulması ve senkronize edilmesi (`stock_uom: Adet`, `is_purchase_item: 1`, `is_sales_item: 1`).
  - Mülkiyet (`KTA Özkaynağı`, `Müşteri Mülkiyeti`, `Müşteri Yatırımı / Geri Ödemeli`), müşteri bağlantısı ve yatırım/geri ödeme durumunun takibi.
* **Kalıp & Aplikasyon Bileşenleri (Kritik Yedek Parça Listesi):**
  - `KTA Tooling` altında bıçak, lokma, itici pim, rezistans gibi yedek parçaların listelenmesi, takım başına kullanım adedi ve kalıphanedeki anlık raf stoğunun tek ekranda gösterilmesi.
* **BOM Operasyonunda Tooling Tanımı:** `BOM Operation` üzerinde `custom_tool_code` (1. Takım) ve opsiyonel `custom_tool_code_2` (2. Takım) alanlarıyla gereken kalıp/aplikatörün mühendislik aşamasında tanımlanması.
* **Varsayılan BOM'lara Akıllı Eşleme:** Ürünlerin aktif ve varsayılan BOM'larındaki (`is_default = 1, docstatus = 1`) operasyonlara takımları bağlayan otomatik eşleme patch'i.
* **İş Kartına (Job Card) Otomatik Aktarım:** İş Emri oluşturulduğunda BOM Operasyonundaki takımların Job Card'a taşınması.
* **Tek Kartta Çift Makine Desteği:** Operatörün `create-calisma-karti` sihirbazında 1. Makineyi zorunlu seçmesi, opsiyonel toggle ile 2. Makineyi (`is_istasyonu_2`) ekleyebilmesi.
* **Alt İşlem - Makine Eşleştirmesi:** Çift makine çalışan kartlarda alt işlem eklenirken (`alt_operasyon_kayitlari`), işlemin hangi makinede (`Makine 1` veya `Makine 2`) yapıldığının seçilmesi. Tek makine varsa otomatik Makine 1 atanması.
* **Kısmi Arıza / Makine Serbest Bırakma (Senaryo B):** İki makineden birinde arıza çıktığında operatörün arızalı makineyi karttan düşürüp takımını canlı kilit havuzunda anında boşa çıkarması; o ana kadar girilmiş üretim ve ölçüm kayıtlarının korunması ve sağlam makineyle kesintisiz üretime devam edebilmesi.
* **Göz Sayısı (Cavity) Oranlı Vuruş Sayacı:** Enjeksiyonda kalıbın göz sayısına (`goz_sayisi`) göre her vardiya sonunda girilen üretilen parça adedinin `islem_adedi / goz_sayisi` olarak takımın kümülatif `total_stroke_count` sayacına otomatik eklenmesi; krimpte `islem_adedi` kadar vuruş sayılması; bakım eşiği (`maintenance_stroke_period`) kontrolü.
* **Çift Makinede Hurda Girişi:** Çift makineli kartlarda hurda giriş penceresinde hangi tezgahtan (`is_istasyonu` / `is_istasyonu_2`) fire çıktığının seçilebilmesi.
* **Canlı Darboğaz Kilidi (Seçenek C) & Admin Override:** 
  - *Sihirbaz Bilgilendirmesi:* Kart açılışında takım başka bir aktif kartta meşgulse operatöre anlık durum/uyarı rozeti gösterilmesi.
  - *Alt İşlem Sert Kilidi:* Alt işlem kaydedilirken, takımın açık kartlardaki aktif kullanım sayısı `>= available_qty` ise kaydın kullanıcı dostu hata ile engellenmesi.
  - *Admin Override:* Vardiyada açık unutulan kartların kilitlerinin yetkili amirler ("KTA Çalışma Kartı Yöneticisi") tarafından güvenli log kaydıyla zorla serbest bırakılabilmesi.

### Kapsam Dışı (Non-Goals)
* **İş Emri / Job Card Tamamlanan Adet Algoritması:** Job Card adet tamamlama mantığına (`doc.total_completed_qty = doc.for_quantity`) dokunulmayacaktır. Karmaşık set/oran hesaplamaları ERPNext stok hareketlerini riske atmamak adına kapsam dışıdır.
* PLC/IoT sayaç entegrasyonu.
* İki ayrı Job Card veya iki ayrı Çalışma Kartı açılması.

### Anti-Hedefler (Anti-Goals)
* Operatöre iki makine için iki ayrı Çalışma Kartı açtırmak veya iki kez barkod okutmak kesinlikle yasaktır (Tek Kart Prensibi).
* Kalite ölçüm formunu karmaşıklaştırmak veya operatöre gereksiz mükerrer form doldurtmak yasaktır.
* ERPNext çekirdeğindeki `Job Card.workstation reqd: 1` kuralını bozmak yasaktır (BOM ve Job Card'da şemsiye istasyonlar `30-0800 Enjeksiyon istasyonu` korunacaktır).

---

## 3. Kısıtlar ve Teknik İlkeler (Constraints)

1. **ERPNext Şemsiye İstasyon Kuralı:** BOM ve Job Card seviyesinde ana istasyon `30-0800 Enjeksiyon istasyonu` kalır. Fiili 16 makine (`30-0801` – `30-0816`) Çalışma Kartı (`is_istasyonu` ve `is_istasyonu_2`) seviyesinde seçilir.
2. **Takım Stok/Kopya Sayısı (`available_qty / mevcut_adet`):** Bir takımın fabrikadaki fiziksel kopya sayısı `KTA Tooling.available_qty` alanında tutulur (varsayılan: 1).
3. **Eşzamanlılık Tanımı:** Açık bir kart (`docstatus < 2`, `bitis_saati is not set`), üzerinde kayıtlı olan alt işlemlerdeki her takımdan 1 adet kullanım hakkı tüketir. Kart tamamlandığında (`bitis_saati` set edildiğinde) takım anında serbest kalır. Kart duruşta olsa bile takım tezgahta takılı olduğu için meşgul sayılır.
4. **Çift Makine Farklı İstasyon Kuralı:** Operatör `is_istasyonu_2` alanına `is_istasyonu` ile aynı makineyi seçemez (`is_istasyonu != is_istasyonu_2`).

---

## 4. Değerlendirilen Yaklaşımlar ve Karar

| Kriter | Yaklaşım 1 (Seçilen: Global KTA Tooling + 930 Item Hiyerarşisi) | Yaklaşım 2 (Reddedilen: Ayrı DocType'lar: Kalıp & Aplikasyon) | Yaklaşım 3 (Reddedilen: Saf Item Kullanımı) |
| :--- | :--- | :--- | :--- |
| **Operatör Deneyimi** | **Mükemmel (Bağlama Göre Filtreli Hafif Liste)** | Orta (Çift form ve kafa karışıklığı) | Kötü (On binlerce item içinde arama) |
| **ERPNext Muhasebe / Satın Alma** | **Tam Entegre (930-Tools Hiyerarşisi)** | Parçalı | Tam uyumlu ama yavaş |
| **Genişletilebilirlik** | **Yüksek (Hotmelt, Bıçak, Fikstür eklenebilir)** | Düşük (Her araca ayrı DocType gerekir) | Yüksek ama şema şişer |
| **Bakım & Geliştirme Maliyeti** | **Düşük (Tek ortak çekirdek mantık)** | Yüksek (İki ayrı modül bakımı) | Orta |
| **Darboğaz Takibi** | **Canlı ve Net (Seçenek C)** | Dağınık | Zor |

**Karar:** Hem otomotiv küresel standartlarına hem KTA ERPNext altyapısına tam uyum sağlayan **Yaklaşım 1 (KTA Tooling)** seçilmiştir.

---

## 5. Detaylı Teknik Tasarım

### A. Faz 1: Kalıp Master ve Seçim Altyapısı (Tamamlandı)
* `KTA Enjeksiyon Kalibi` DocType oluşturuldu.
* 46 kalıp `extract_enjeksiyon_kaliplari.py` yamasıyla aktarıldı.
* Alt operasyon ve enjeksiyon ölçüm tablolarında `kalip_no` Link alanına dönüştürüldü.
* `_assert_enjeksiyon_kalip_valid` doğrulaması devreye alındı.
* 320px ve altı ekranlar için dikey yığınlanan butonlar ve kalıp çipleri entegre edildi.

---

### B. Faz 2: KTA Tooling Detaylı Mimarisi ve Veri Akışı

```mermaid
flowchart TD
    subgraph Kurumsal["1. Kurumsal Takım & Demirbaş Yönetimi (KTA Tooling)"]
        G930["Item Group: 930-Tools"] --> G933["933-Injection Molds"]
        G930 --> G934["934-Crimp Applicators"]
        TOOL["KTA Tooling (Takım / Kalıp / Aplikasyon Master)"]
        TOOL <-->|Otomatik 1-e-1 Senkron| ITM["Item (933 veya 934)"]
        TOOL --> TYPE{"tool_type"}
        TYPE -->|Injection Mold| T_ENJ["Enjeksiyon Kalıbı (Göz Sayısı, QI Şablonu)"]
        TYPE -->|Crimp Applicator| T_KRM["Krimp Aplikasyon Kalıbı (Terminal, Kesit, Besleme)"]
        TOOL --> FIN["Yatırım & Mülkiyet (Bosch / Geri Ödemeli)"]
        TOOL --> COUNTER["Kümülatif Vuruş Sayacı (Stroke Counter)"]
        TOOL --> SPARES["Kritik Yedek Parça Listesi (Bıçak, Lokma, Rezistans)"]
    end

    subgraph Muhendislik["2. Mühendislik & BOM"]
        BOM["Varsayılan BOM (is_default: 1, docstatus: 1)"]
        BOM -->|custom_tool_code| K1["1. Takım (Zorunlu)"]
        BOM -.->|custom_tool_code_2| K2["2. Takım (Opsiyonel)"]
    end

    subgraph Planlama["3. Planlama & İş Kartı"]
        WO["Work Order"] --> JC["Job Card"]
        K1 -.->|Otomatik Kopyalama| JC
        K2 -.->|Otomatik Kopyalama| JC
    end

    subgraph Sihirbaz["4. create-calisma-karti Sihirbazı"]
        JC --> WIZ["Kart Açılışı"]
        WIZ --> WS1["1. Makine / İstasyon"]
        WIZ -->|Toggle: + 2. Makine| WS2["2. Makine / İstasyon (is_istasyonu_2)"]
        WIZ --> CHECK1["Seçenek C: Canlı Meşguliyet Uyarısı (Soft Badge)"]
    end

    subgraph CalismaKarti["5. KTA Çalışma Kartı"]
        WIZ --> CK["Calisma Karti"]
        CK --> SUB1["Alt İşlem 1 (Makine 1 + Takım 1)"]
        CK --> SUB2["Alt İşlem 2 (Makine 2 + Takım 2 veya Takım 1 Kopya)"]
        SUB1 --> HARDLOCK["Seçenek C: Kesin Darboğaz Kilidi (Hard Gate)"]
        SUB2 --> HARDLOCK
        SUB1 --> M1["3/3 Ölçüm (Başlangıç/Ara/Bitiş) -> 3 Enerji Puanı"]
        SUB2 --> M2["3/3 Ölçüm (Başlangıç/Ara/Bitiş) -> 3 Enerji Puanı"]
        SUB1 --> T1["Reçete Oranlı Tüketim (kg/adet)"]
        SUB2 --> T2["Reçete Oranlı Tüketim (kg/adet)"]
        SUB1 -.->|Vardiya Sonu Adet| COUNTER
        SUB2 -.->|Vardiya Sonu Adet| COUNTER
        CK -.->|Kısmi Arıza (Senaryo B)| REL["2. Makineyi Serbest Bırak (Kayıtlar Korunur, Takım Boşa Çıkar)"]
        CK -.->|Fire Girişi| SCRAP["Hurda Girişi (Makine 1 / Makine 2 Seçimli)"]
    end
```

#### 1. Veri Modeli Genişletmeleri

##### a. `Item Group` ve `Item` Entegrasyonu
* `930-Tools` Alt Grupları:
  - `933-Injection Molds` (`parent_item_group`: `930-Tools`, `is_group`: 0)
  - `934-Crimp Applicators` (`parent_item_group`: `930-Tools`, `is_group`: 0)
* `KTA Tooling` Kaydedildiğinde Otomatik `Item` Açılması/Senkronizasyonu:
  - `item_code`: `{tool_code}` (örn: `8718645633` veya `KLP-0287`)
  - `item_name`: `{tool_name}`
  - `item_group`: `tool_type == 'Injection Mold'` ise `933-Injection Molds`, `tool_type == 'Crimp Applicator'` ise `934-Crimp Applicators`
  - `stock_uom`: `Adet`
  - `is_stock_item`: Müşteri mülkiyetinde `0`, KTA mülkiyetinde `1`
  - `is_purchase_item`: 1 (kalıpçı/revizyon masrafları için)
  - `is_sales_item`: 1 (müşteri yatırım faturaları için)

##### b. `KTA Tooling` Alanları
* **Temel Bilgiler:**
  - `tool_code` (Data, Unique, Mandatory, Title Case: "Takım / Kalıp Kodu")
  - `tool_name` (Data, Mandatory, Title Case: "Takım / Kalıp Adı")
  - `tool_type` (Select: `Injection Mold`, `Crimp Applicator`, `Cutting Die`, `Assembly Fixture`, Title Case: "Takım Tipi", Mandatory)
  - `available_qty` (Int, Default: 1, Title Case: "Mevcut Takım Adedi")
  - `disabled` (Check, Default: 0, Title Case: "Devre Dışı")
  - `description` (Small Text, Title Case: "Açıklama")
* **Mülkiyet & Finansman:**
  - `ownership_type` (Select: `KTA Özkaynağı`, `Müşteri Mülkiyeti (Doğrudan)`, `Müşteri Yatırımı (Geri Ödemeli / Tooling Reimbursement)`)
  - `customer` (Link: `Customer`, Title Case: "Müşteri", depends_on: Müşteri seçildiğinde)
  - `linked_item_code` (Link: `Item`, Read Only, Title Case: "Bağlı Ürün Kodu")
  - `total_investment_amount` (Currency, Title Case: "Toplam Yatırım Tutarı")
  - `reimbursement_status` (Select: `Faturalandı`, `Geri Ödeme Bekliyor`, `Amorti Ediliyor`, `Tamamlandı`, Title Case: "Geri Ödeme Durumu")
* **Ömür & Bakım:**
  - `total_stroke_count` (Int, Default: 0, Read Only, Title Case: "Toplam Baskı Adedi (Vuruş)")
  - `maintenance_stroke_period` (Int, Default: 50000, Title Case: "Bakım Periyodu (Vuruş)")
* **Tipe Özel Parametreler (Şartlı):**
  - *Enjeksiyon İçin (`tool_type == 'Injection Mold'`):*
    - `cavity_count` (Int, Default: 1, Title Case: "Göz Sayısı / Cavity", reqd: 1)
    - `default_quality_template` (Link: `Quality Inspection Template`, Title Case: "Varsayılan Kalite Şablonu")
  - *Krimp İçin (`tool_type == 'Crimp Applicator'`):*
    - `linked_terminal` (Link: `Item`, Title Case: "Bağlı Terminal / Kontak No")
    - `wire_cross_section_range` (Data, Title Case: "Kablo Kesit Aralığı (mm²)", örn: `0.50 - 1.00 mm²`)
    - `feed_type` (Select: `Yandan Besleme (Side-feed)`, `Arkadan Besleme (End-feed)`, Title Case: "Besleme Tipi")
* **Kritik Bileşenler & Yedek Parçalar Child Table (`KTA Tooling Spare Part`):**
  - `spare_part` (Link: `Item`, Title Case: "Yedek Parça")
  - `qty_in_tool` (Int, Default: 1, Title Case: "Takımdaki Adet")
  - `min_shelf_qty` (Int, Default: 1, Title Case: "Kritik Raf Stoğu")
  - `current_stock` (Float, Read Only, Title Case: "Depo Stoğu")

##### c. `tabBOM Operation` & `tabJob Card`
* `custom_tool_code` (Link: `KTA Tooling`, Title Case: "1. Takım / Kalıp Kodu")
* `custom_tool_code_2` (Link: `KTA Tooling`, Title Case: "2. Takım / Kalıp Kodu")

##### d. `tabCalisma Karti` & Child Tables
* `tabCalisma Karti`:
  - `is_istasyonu_2` (Link: `Workstation`, Title Case: "2. İş İstasyonu")
* `tabCalisma Karti Alt Operasyon Kayitlari`:
  - `kalip_no` -> Link: `KTA Tooling` (Title Case: "Takım / Kalıp No")
  - `is_istasyonu` (Link: `Workstation`, Title Case: "İş İstasyonu")
* `tabCalisma Karti Enjeksiyon Olcumleri`:
  - `kalip_no` -> Link: `KTA Tooling`

---

#### 2. Sihirbaz Arayüzü (`create-calisma-karti`)
* `StepWorkstation.vue`:
  - 1. Makine seçimi (mevcut alan).
  - "İkinci Makinede Çalışılacak mı?" switch/toggle butonu.
  - Açıldığında `2. İş İstasyonu` açılır listesi (1. makine hariç filtrelenir).
  - Job Card'da tanımlı takım/kalıp ekranda gösterilir. Takım başka bir kartta aktifse sarı rozet çıkar:
    `⚠️ {Takım Kodu} şu anda {Makine} tezgahında {Operatör} tarafından kullanılmaktadır (Mevcut: {aktif}/{mevcut_adet}).`

---

#### 3. Alt Operasyon ve Kısmi Arıza Yönetimi (Senaryo B)
* **Makine ve Takım Seçimi:**
  Kartta `is_istasyonu_2` tanımlıysa formda `is_istasyonu` seçimi görünür (`[Makine 1, Makine 2]`).
  Operasyona göre takım arama filtresi dinamik uygulanır:
  - Enjeksiyon (OP40): `tool_type: "Injection Mold"`
  - Krimp (OP10/OP20): `tool_type: "Crimp Applicator"`
* **Kısmi Arıza / Makine Serbest Bırakma API (`release_machine_from_card`):**
  - Çift makineli bir kartta bir makine arızalandığında operatör "2. Makineyi Serbest Bırak" diyebilir.
  - O ana kadar girilmiş olan üretim adedi ve ölçüm kayıtları **kesinlikle korunur**.
  - Sistem karttaki `is_istasyonu_2` değerini temizler ve arızalı makinedeki takım/kalıp kilidini canlı kilit havuzunda serbest bırakır.
  - Kart sağlam makine (`is_istasyonu`) ile normal üretime devam eder.

---

#### 4. Vuruş Sayacı Mantığı (Göz Sayısı Oranlı)
Operatör vardiya sonunda alt işlem satırına üretilen adedi (`islem_adedi_1`) girip güncellediğinde:
```python
import math

def update_tool_stroke_counter(tool_code: str, delta_qty: int) -> None:
    """Takımın tipine ve göz sayısına göre vuruş/stroke sayacını günceller."""
    if not tool_code or delta_qty <= 0:
        return
    tool_doc = frappe.get_doc("KTA Tooling", tool_code)
    
    if tool_doc.tool_type == "Injection Mold":
        cavity = tool_doc.cavity_count or 1
        stroke_delta = math.ceil(delta_qty / cavity)
    else:
        # Krimp ve diğer takımlarda 1 adet = 1 vuruş
        stroke_delta = delta_qty

    frappe.db.sql(
        """
        UPDATE `tabKTA Tooling`
        SET total_stroke_count = COALESCE(total_stroke_count, 0) + %s
        WHERE name = %s
        """,
        (stroke_delta, tool_code),
    )
```

---

#### 5. Canlı Darboğaz Kilidi (Seçenek C) & Admin Override Mantığı (`concurrency.py`)
```python
def assert_tooling_concurrency(tool_code: str, current_card_name: str | None = None) -> None:
    """Verilen takımın fabrikadaki mevcut adet sınırını aşıp aşmadığını denetler."""
    if not tool_code:
        return

    available_qty = frappe.db.get_value("KTA Tooling", tool_code, "available_qty") or 1

    active_usages = frappe.db.sql(
        """
        SELECT ck.name as card_name, ck.operator, ck.is_istasyonu, ao.is_istasyonu as sub_ws
        FROM `tabCalisma Karti Alt Operasyon Kayitlari` ao
        JOIN `tabCalisma Karti` ck ON ck.name = ao.parent
        WHERE ao.kalip_no = %(tool_code)s
          AND ck.docstatus < 2
          AND (ck.bitis_saati IS NULL OR ck.bitis_saati = '')
          AND ck.name != %(current_card)s
        GROUP BY ck.name, ao.kalip_no
        """,
        {"tool_code": tool_code, "current_card": current_card_name or ""},
        as_dict=True,
    )

    if len(active_usages) >= available_qty:
        conflict = active_usages[0]
        ws_info = conflict.sub_ws or conflict.is_istasyonu or _("Bilinmeyen Makine")
        frappe.throw(
            _(
                "Takım/Kalıp {0} şu anda {1} numaralı çalışma kartında ({2} operatörü, {3} makinesi) "
                "kullanımdadır. Fabrikadaki mevcut adet: {4}."
            ).format(tool_code, conflict.card_name, conflict.operator, ws_info, available_qty),
            frappe.ValidationError,
        )

@frappe.whitelist()
def admin_force_release_tool(card_name: str, tool_code: str) -> dict:
    """Yetkili amirler (KTA Çalışma Kartı Yöneticisi) için açık kalmış kart kilitlerini zorla kaldırma yetkisi."""
    frappe.only_for("KTA Çalışma Kartı Yöneticisi")
    frappe.logger("calisma_karti").info(f"Takım {tool_code} kilit devri yapıldı. Kart: {card_name}, Yetkili: {frappe.session.user}")
    return {"status": "success", "message": _("Takım kilidi başarıyla kaldırıldı.")}
```

---

#### 6. Faz 1'den Faz 2'ye Yumuşak Veri Göçü (Migration Patch)
* `migrate_enjeksiyon_kalip_to_kta_tooling.py`:
  - Mevcut 46 `KTA Enjeksiyon Kalibi` kaydı `KTA Tooling` (`tool_type: "Injection Mold"`) tablosuna kopyalanır.
  - Alt operasyon ve ölçüm child table tanımlarındaki `options` değeri `KTA Tooling` olarak güncellenir.
  - Veri kaybı veya yabancı anahtar uyumsuzluğu riski sıfırlanır.

---

## 6. İnşa Eden Geliştiriciye Bırakılan Detaylar (What's Left to the Builder)

* `Job Card` oluşturulurken `BOM Operation`'daki `custom_tool_code` ve `custom_tool_code_2` alanlarının otomatik kopyalanması için `before_insert` veya Work Order hook'unun eklenmesi.
* `KTA Tooling` kaydedilirken `Item` kaydının oluşturulması veya güncellenmesi için `after_insert` / `on_update` hook'u.
* Mevcut açık çalışma kartları için geriye dönük uyumluluk (kartta `is_istasyonu_2` yoksa eski tek makineli akışın pürüzsüz devam etmesi).
* Alt operasyon silindiğinde veya güncellendiğinde takım meşguliyetinin anında güncellenmesi.
* Çift makineli kartlarda `useHurdaDialogs.ts` formuna `is_istasyonu` seçim kutusunun entegre edilmesi.
* Sözlük dosyalarına (`tr.csv`, `en.csv`, `de.csv`) yeni hata mesajları ve etiketlerin eklenmesi.
