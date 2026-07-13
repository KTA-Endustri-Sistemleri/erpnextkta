# KTA Kablo Üretim ve Montaj Yönetimi: Graph Tabanlı Sanal Yarımamül Mimarisi

Bu doküman, üretim sahasındaki karmaşık kablaj (Wire Harness) operasyonlarını (Doppel, Seal, Çoklu Soketleme, Enjeksiyon, Makaron, Shaping, Paketleme vb.) standart ERPNext Ürün Ağacı (BOM) yapısını bozmadan, tamamen paralel bir "Düğüm-Bağlantı (Node-Edge)" mantığıyla dijitalleştirmek için hazırlanmış kapsamlı bir mimari implementasyon planıdır.

## ✅ Çözülmüş Kararlar (Resolved Decisions)

> [!NOTE]  
> - **Geriye Dönük Uyumluluk:** Yeni yapı sadece yeni açılacak iş emirlerinden itibaren geçerlidir.
> - **Kapsam:** En tepe düzey detay **İş Emri (Work Order)**'dir. Aynı iş emrine açılmış tüm çalışma kartları havuzu ortaklaşa görebilir, farklı iş emirleri birbirini asla göremez.
> - **Kavite / Pin Takibi:** Soketleme işlemlerinde zorunludur. Tam bir "Pin-to-Pin" altyapısı kurulacaktır.
> - **Tüketim Mantığı:** Birleştirme (Tip 3/4 vb.) işlemlerinde kaynak WIP'lerin statüsü zorla "Tüketildi" yapılmaz. Tüketim miktarı `KTA Calisma Karti Hammadde Kayitlari` üzerinden toplanır. Adet 0 veya altına düştüğünde WIP, havuz listesinden dinamik olarak gizlenir.
> - **Görsel Gruplama (Aggregation):** Özellikleri tamamen aynı olan (etiketi aynı olan) WIP'ler havuz ekranına (UI) gönderilirken tek bir satırda gruplanır ve kapasiteleri toplanır (Örn: `WIP-1,WIP-2` -> 1000 Adet). Arka planda tüketim yapılırken bu gruplanmış liste parçalanır (split) ve kalan kapasitelerine göre veritabanına ayrı tüketim satırları olarak işlenerek izlenebilirlik sağlanır.
> - **WIP Kapasite Kontrolü:** Alt operasyon girildiğinde, sistem kaynak WIP'in üretim kapasitesini (Örn: OP10'da doğan miktar) denetler. Tüketilecek toplam miktar bu kapasiteyi aşamaz. Aşarsa, İş Emri limitinden bağımsız olarak işlem red edilir. Ayrıca havuz miktarları `islem_adedi = base_capacity - max_consumed` formülüyle hesaplanıp her yön için dinamik yönetilir.
> - **Modülerlik:** Kodda hiçbir operasyon ismi/ID'si hardcode edilmeyecektir. Graph motorunun davranışı, `KTA Çalışma Kartı Alt Operasyonları` tablosundaki **Sanal Yarımamül Davranışı + Alt Parametre** ikilisinden okunacaktır.
> - **Allowed Materials:** Her operasyonun tüketebileceği malzemeler `Allowed Materials` üzerinden kısıtlanacaktır.

---

## Tam Davranış Tipi Kütüphanesi (Behavior Registry)

Sistemin çekirdeğini oluşturan **10 ana davranış tipi**. Benzer işlemler tek çatı altında toplanmış, davranışın nüansı **Alt Parametre** ile ayrıştırılmıştır. Python motoru hiçbir zaman operasyon adına bakmaz — sadece bu iki alana bakar.

> [!IMPORTANT]
> **Çok Damarlı Kablo Desteği:** Üretimde yaygın olarak kullanılan çok damarlı kablolar (multi-core) Tip 9 sayesinde modellenir. OP10'da kablo tek bir T1/T2 çifti olarak doğar; OP20 Manto Sıyırma işleminde Tip 9 çalışarak o ucu N bağımsız damara (Damar-1, Damar-2… Damar-N) böler. Sonrasında her damara ayrı ayrı terminal, seal veya makaron işlemi uygulanabilir.

| # | Davranış Tipi | Alt Parametre | Graph Üzerindeki Etkisi | Tüketilen Malzeme Örnekleri | Tipik Operasyon |
|---|---|---|---|---|---|
| 1 | **Temel Kablo Oluşturur** | `doppel: Evet / Hayır` | `Hayır` → 1 Merkez + T1/T2 uçları. `Evet` → N kablo anında birleşik (V şekilli) WIP olarak doğar. | Kablo (+ Terminal if Doppel) | OP10 |
| 2 | **Uca / Düğüme Bileşen Ekler** | `uç_durumu: Kapatır / Açık Bırakır / Beklemede / Kapalı Düğüme Ekler` | `Kapatır` → T1/T2 "Dolu". `Açık Bırakır` → Uç açık kalır. `Beklemede` → Bileşen pasif eklenir, ısıtma beklenir. `Kapalı Düğüme Ekler` → Zaten "Dolu" bir düğüme ek bileşen takılır (kapak, klıps), uç durumu değişmez. | Terminal / Seal / Makaron / Tülle / Kapak / Klıps | OP11, OP20 |
| 3 | **Düğümleri Birleştirir** | `birlesim_tipi: Terminal / Lehim / Perçin` | N bağımsız WIP'i "Tüketildi" yapar ve bir birleşim düğümünde birleştirir, yeni büyük WIP doğar. `Terminal` → bir terminal malzemesi ile. `Lehim` → kalay ile kalıcı eletriksel birleşim. `Perçin` → mekanik kalıcı birleşim. | Terminal / Kalay / Perçin | OP11 (Doppel), OP20 (Lehim, Perçinleme) |
| 4 | **Soketler** | *(yok, Pin zorunlu)* | Operatörden Pin numarası alarak N WIP ucunu soket düğümüne bağlar, kaynak WIP'leri tüketir. | Soket, Plastik Gövde | OP30 |
| 5 | **Enjeksiyon** | *(yok)* | Seçilen birleşim noktasını "Kalıplanmış (Molded)" statüsüne çeker; artık müdahale edilemez. | Plastik Granül | OP40 |
| 6 | **Yapısal Değişikliksiz İşlem** | `wip_durumu: Açık Bırakır / Tamamlandı Kapatır` | `Açık Bırakır` → Gruplama damgası vurur, WIP aktif kalır. `Tamamlandı Kapatır` → Malzeme tüketir ve WIP'i kapatır. | Bağcık / Bant / Etiket / Ambalaj | OP50 (Shaping), OP60 (Paketleme) |
| 7 | **Doğrulama / Test** | *(yok)* | WIP'e test sonucu (OK/NOK) ve timestamp kaydeder. Yapısal değişiklik yoktur. | Yok | OP50 (Pushback, Elektriksel Test) |
| 8 | **Bileşeni Aktifleştirir** | `test_zorunlu: Evet / Hayır` | "Beklemede" düğümü "Kalıcı/Aktif" yapar. `test_zorunlu: Evet` → Motor önce `test_ok: true` damgasını doğrular; NOK veya yoksa reddeder. `test_zorunlu: Hayır` → Test kontrolü atlanır, direkt aktifleştirilir (OP11 senaryosu). | Yok (ısı/enerji) | OP11 (Makaron Geçir + Isıt), OP50 (Test Sonrası Makaron Isıtma) |
| 9 | **Ucu Böler** | `damar_sayisi: N` | Seçilen T1 veya T2 uç düğümünü N adet bağımsız alt düğüme (Damar-1, Damar-2… Damar-N) dönüştürür. Her alt düğüm bağımsız olarak Tip 2 işlemine tabi tutulabilir. Orijinal T1/T2 düğümü artık sadece bir kapsayıcı (container) olur. | Yok (mekanik işlem) | OP20 (Manto Sıyırma) |
| 10 | **Alt Montaj (Sub-Assembly)** | `cikti_tipi: Yeni WIP / Mevcut WIP'e Ekle` | Kablo dışı birden fazla parçayı (düğme, kapak, yay, mikro switch vb.) bir araya getirerek birleşik bir Alt Montaj düğümü oluşturur. `Yeni WIP` → Yeni bağımsız bir WIP olarak havuza düşer. `Mevcut WIP'e Ekle` → Mevcut bir WIP'in belirli bir noktasına bağlanır. | Plastik Bileşenler, Yay, Vida, Switch | OP20 (Anahtar Alt Montajı, Anahtar Düğme Kapak Birleştirme) |

> [!TIP]
> **Örnek 1A — Makaron → Soket → Test → Isıtma (Test Zorunlu)**
> ```
> [Makaron Geçir]    Tip 2, Beklemede      → Bileşen pasif eklendi
>       ↓
> [Soketle]           Tip 4                 → Pin bazlı bağlantı tamamlandı
>       ↓
> [Pushback]          Tip 7                 → test_ok: true damgası vuruldu
>       ↓
> [Makaron Isıt]      Tip 8, test_zorunlu=E → OK ise Kalıcı/Aktif | NOK ise reddedilir
> ```

> [!TIP]
> **Örnek 1B — Makaron → Hemen Isıtma (Test Zorunsuz, OP11 Senaryosu)**
> ```
> [Makaron Geçir]    Tip 2, Beklemede      → Bileşen pasif eklendi
>       ↓
> [Makaron Isıt]      Tip 8, test_zorunlu=H → Test kontrolü atlanır, direkt Kalıcı/Aktif
> ```

> [!TIP]
> **Örnek 2 — Çok Damarlı Kablo (Tip 1 → 9 → 2 × N)**
> ```
> [OP10 Kesme]        Tip 1 → Merkez + T1 (Sol Uç) + T2 (Sağ Uç) yaratıldı
>       ↓
> [OP20 Manto Sıyır]  Tip 9, damar_sayisi=5 → T1, Damar-1-Sol … Damar-5-Sol'a bölündü
>       ↓
> [OP11 Terminal]     Tip 2, Kapatır → Damar-1-Sol'a terminal basıldı
>                     Tip 2, Kapatır → Damar-2-Sol'a terminal basıldı
>                     ...                (her damara ayrı işlem)
>       ↓
> [OP11 Terminal]     Tip 2, Kapatır → T2 (Sağ Uç) kapatıldı (tek damar ise)
> ```

---

## Önerilen Değişiklikler (Proposed Changes)

### 1. Veritabanı ve Şema (Database Layer)

#### [NEW] `KTA Sanal Yarimamul` (Doctype)
- **WIP ID** (Data, Unique)
- **İş Emri** (Link → Work Order) — En tepe izolasyon anahtarı
- **Çalışma Kartı** (Link → Calisma Karti)
- **Graph State** (Long Text / JSON) — Tüm düğümler, bağlantılar, malzemeler
- **Status** (Select: Aktif / Tüketildi / Tamamlandı)
- **Is Graph Based** (Check) — Yeni iş emirleri için 1, eski için 0

#### [MODIFY] `KTA Calisma Karti Alt Operasyonlari`
- **Sanal Yarımamül Davranışı** (Select) — 9 ana davranış tipinden biri.
- **Davranış Alt Parametresi** (Select) — Seçilen tipe göre dinamik olarak değişen alt seçenek (Örn: "Kapatır / Açık Bırakır / Beklemede").

#### [MODIFY] `KTA Calisma Karti Hammadde Kayitlari`
- `yon` (Sol/Orta/Sağ) → **Hedef Node ID** olarak dönüştürülür (eski kayıtlar için `yon` korunur).

---

### 2. Backend Motoru (Python Graph Engine)

#### [NEW] `erpnextkta/kta_calisma_karti/api_impl/wip_graph_engine.py`

```python
# 10 ana handler — alt parametre handler içinde işlenir
BEHAVIOR_HANDLERS = {
    "Temel Kablo Oluşturur":           create_base_wire,         # alt: doppel
    "Uca / Düğüme Bileşen Ekler":    attach_component,         # alt: uç_durumu
    "Düğümleri Birleştirir":           merge_wips,               # alt: birlesim_tipi
    "Soketler":                        plug_into_socket,         # pin zorunlu
    "Enjeksiyon":                      apply_injection_mold,
    "Yapısal Değişikliksiz İşlem":    process_no_structure,     # alt: wip_durumu
    "Doğrulama / Test":                record_test_result,
    "Bileşeni Aktifleştirir":          activate_pending_component, # alt: test_zorunlu
    "Ucu Böler":                       split_endpoint,           # alt: damar_sayisi
    "Alt Montaj (Sub-Assembly)":       create_sub_assembly,      # alt: cikti_tipi
}

# Ana Fonksiyonlar:
# - attach_component(wip_id, node_id, component, uc_durumu):
#     Kapatır → ucu kapatır | Açık Bırakır → açık bırakır | Beklemede → pasif ekler
#     Kapalı Düğüme Ekler → Zaten "Dolu" düğüme ek bileşen taklar (durum değişmez)
# - merge_wips(wip_ids, node_ids, material, birlesim_tipi):
#     Terminal → terminal düğümü | Lehim → Lehim düğümü | Perçin → Perçin düğümü
# - activate_pending_component(wip_id, node_id, test_zorunlu):
#     Evet → test_ok kontrol eder, yoksa reddeder | Hayır → direkt aktifleştirir
# - split_endpoint(wip_id, node_id, damar_sayisi):
#     T1/T2'yi N alt damara böler, orijinal `container` olur
# - create_sub_assembly(component_list, cikti_tipi):
#     Yeni WIP → bağımsız alt montaj WIP'i | Mevcut WIP'e Ekle → mevcut WIP'e bağlanır

def process_no_structure(wip_id, materials, wip_durumu):
    consume_materials(wip_id, materials)
    if wip_durumu == "Tamamlandı Kapatır":
        finalize_wip(wip_id)
    # "Açık Bırakır" ise WIP aktif kalmaya devam eder
```

#### [MODIFY] `alt_operasyon.py`
- `get_work_order_pool`: `is_graph_based=1` iş emirleri için Graph State'ten açık uçları listeler; eski iş emirleri için mevcut doğrusal mantık çalışmaya devam eder.

---

### 3. Frontend (Vue.js)

#### [MODIFY] `AltOperasyonView.vue`
- WIP kartları Graph State'e göre dinamik render edilir.
- **"Beklemede" düğüm:** Sarı/turuncu gösterilir, Isıtma butonu test OK olmadan devre dışıdır.
- **"Kalıcı/Aktif" düğüm:** Yeşil gösterilir.
- **"Kalıplanmış" düğüm:** Gri/kilitli gösterilir.
- **Test sonucu:** OK/NOK rozeti WIP kartında görünür.

#### [NEW] `NodeSelectorModal.vue` — Açık uç seçimi (T1 mi T2 mi?)
#### [NEW] `SocketPinModal.vue` — Pin/kavite numarası girişi
#### [NEW] `InjectionMoldModal.vue` — Kalıplanacak birleşim noktası seçimi

---

### 4. UI/UX ve Rendering (Vue.js Çoklu-Ağaç Mimarisi)
- **Çoklu Yarımamül (Multi-WIP) Gösterimi:** `CkGraphViewerModal.vue` içerisinde birden fazla grafik yan yana/alt alta (horizontal-tree) render edilirken, ortak "Birleşim" düğümleri (örneğin uçlar veya Doppel birleşimleri) tespit edilerek `sharedLeftNode` veya `sharedRightNode` mantığıyla ayrıştırılır. Kalan grafikler arasına süslü parantez (`{`, `}`) çizilerek görsel gruplama yapılır.
- **Sıyırma Boyutları (Stripping Lengths):** Fiziksel bir malzeme kodu (`hammadde`) taşımayan sıyırma işlemleri (`boyut_mm > 0`), backend'de graph motoruna aktarılırken `t.get("hammadde") or t.get("boyut_mm")` kuralı ile filtreden geçirilir. Frontend'de bu boyutlar "Uç (T1)" veya "Uç (T2)" içerisinde `{{ boyut_mm }}mm (Sıyırma)` formatında gösterilir.
- **Kablo Merkezi Görünümü:** Veritabanındaki `Kablo Merkezi` düğüm tipi, arayüzde görsel sadelik amacıyla `Kablo` olarak render edilir.

---

## Doğrulama Planı

### Otomatik Testler
- `test_b1_standard_wire()` — Küt, Tek Taraf, Çift Taraf üretimini doğrula
- `test_b1_auto_doppel()` — Makine Doppel: baştan birleşik WIP
- `test_b2_close()` — Terminal basma: uç kapanır
- `test_b2_open()` — Seal: uç açık kalır
- `test_b2_pending()` — Makaron: uç açık, bileşen "Beklemede"
- `test_b2_closed_node_add()` — Zaten "Dolu" düğüme Terminal Kapağı takma: düğüm statüsü değişmez, kapak eklenir
- `test_b3_doppel_terminal()` — 5 kablo terminal ile birleşir, hepsi Tüketildi
- `test_b3_doppel_lehim()` — 2 kablo Lehim düğümüyle birleşir, kalay hammaddesi tüketilir
- `test_b3_doppel_percin()` — 2 kablo Perçin düğümüyle birleşir, perçin hammaddesi tüketilir
- `test_b4_socket_pins()` — 3 kablo, 3 farklı pin, pin numaraları korunur
- `test_b5_injection()` — Düğüm "Kalıplanmış" olur, ikinci işlem reddedilir
- `test_b6_shaping()` — Gruplama damgası, WIP aktif kalır
- `test_b6_finishing()` — Malzeme tüketilir, WIP "Tamamlandı" olur
- `test_b7_test_result()` — OK/NOK kaydedilir
- `test_b8_activate_ok()` — Test OK (test_zorunlu=E) sonrası Makaron aktifleşir
- `test_b8_activate_blocked()` — Test NOK veya yokken (test_zorunlu=E) Isıtma reddedilir
- `test_b8_activate_no_test_needed()` — test_zorunlu=H iken test olmadan ısıtma başarılı olur
- `test_b9_split_endpoint()` — T1 ucu 5 damara bölünür, orijinal T1 container olur
- `test_b9_split_then_crimp()` — Bölünmüş damarlara ayrı ayrı terminal basılır
- `test_b9_direct_crimp_on_container_blocked()` — Container düğüme doğrudan terminal basma girişimi reddedilir
- `test_b10_sub_assembly_new_wip()` — Alt montaj bileşenleri yeni bağımsız WIP olarak havuza düşer
- `test_b10_sub_assembly_attach_to_wip()` — Alt montaj mevcut WIP'e bağlanır
- `test_work_order_isolation()` — Farklı WO havuzları birbirine karışmaz
- `test_old_work_order_unaffected()` — `is_graph_based=0` iş emirleri bozulmaz
- `test_wip_capacity_validation()` — WIP tüketim miktarı, WIP üretim miktarını aşamaz

### Manuel Doğrulama
Uçtan uca iki ayrı sahada senaryo:

**Senaryo A — Tek Damarlı Kablo (OP11 Makaron + Test Sonrası Isıtma):**
`OP10 (Kesme)` → `OP11 (Seal + Doppel)` → `OP11 (Makaron Geçir, Beklemede)` → `OP30 (Soketleme)` → `OP40 (Enjeksiyon)` → `OP50 (Pushback → OK → Makaron Isıtma [test_zorunlu=E] → Shaping)` → `OP60 (Paketleme)`

**Senaryo B — Çok Damarlı Kablo:**
`OP10 (Kesme)` → `OP20 (Manto Sıyırma → 5 Damara Böl)` → `OP11 (Her Damara Ayrı Terminal)` → `OP30 (Soketleme, Pin Bazlı)` → `OP50 (Test)` → `OP60 (Paketleme)`

**Senaryo C — OP11'de Makaron Geçir + Hemen Isıt (Test Zorunsuz):**
`OP10 (Kesme)` → `OP11 (Makaron Geçir [Beklemede] → Makaron Isıt [test_zorunlu=H])` → `OP11 (Terminal Basma)` → `OP30 (Soketleme)` → `OP50 (Test)` → `OP60 (Paketleme)`

### UI/UX: AltOperasyonView ve Grafik Önizleme (WIP Filtreleme)
Alt işlemlerdeki "Büyüteç" (Grafiği Görüntüle) butonunun çalışmasında önemli bir UX iyileştirmesi yapılmıştır:
1. **İşlem Öncesi (Havuzdan Seçilenler):** Sol taraftaki "HAVUZDAN SEÇİLDİ" altındaki büyütece tıklanırsa, işlemden önceki (girgilerin) ham hali gösterilir. 
2. **İşlem Sonrası (Terminal vs. Eklenenler):** Sağ taraftaki bileşen seviyesindeki büyütece tıklanırsa, eğer işlem kaydedilmiş ve `wip_snapshots` içindeki `created_wips` dolmuşsa sistem direkt olarak Ana Çıktı WIP'i (`operation_ref` kontrolü ile kalıntıları dışlayarak) çizer. Bu, Doppel gibi işlemlerde kalıntı kabloların `Birleşim` terminali ortaklaştırmasını bozmasını engeller ve kullanıcının sadece Ana WIP'in sonucunu (Doppel yapısını kusursuz olarak) görmesini sağlar.
