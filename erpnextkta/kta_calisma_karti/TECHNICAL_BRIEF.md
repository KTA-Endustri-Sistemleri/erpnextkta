# kta_calisma_karti — Teknik Brief

> Son güncelleme: 2026-03-02
>
> Bu belge, `kta_calisma_karti` modülünün backend ve frontend mimarisini, veri modelini, API katmanını ve mevcut durumu özetler.

---

## 1. Genel Amaç

`kta_calisma_karti`, ERPNext'in standart Job Card / Work Order akışını genişleten, fabrika operatörlerine yönelik bir **üretim takip ve kalite kontrol** modülüdür.

Temel kullanım akışı:
1. Operatör/YÖNETİCİ bir **Çalışma Kartı** (CK) oluşturur (Job Card + Work Order + Operasyon + İstasyon + Operatör seçilerek).
2. Operatör kartı açıp **Başlat → Duraklat → Bitir** döngüsünü yönetir.
3. Kalite kullanıcısı **IDC ölçümleri**, **barkod kayıtları** ve **QC onayı** girer.
4. Hurda varsa operatör kayıt oluşturur; BOM/operasyon bazlı kısıtlama uygulanır.

---

## 2. Dizin Yapısı

```
erpnextkta/kta_calisma_karti/
├── api.py                     ← Stable facade (frontend buraya çağrı yapar)
├── realtime.py                ← Socket.IO event publisher
├── api_impl/
│   ├── _helpers.py            ← Rol, employee, child-table yardımcıları
│   ├── cards.py               ← Liste ve detay query'leri
│   ├── create.py              ← CK oluşturma (create_calisma_karti)
│   ├── hurda.py               ← Hurda CRUD + BOM operasyon filtresi
│   ├── qc.py                  ← QC güncelleme + IDC/Barkod CRUD
│   ├── alt_operasyon.py       ← Alt operasyon kayıtları CRUD
│   └── barcode.py             ← Barkod ile JC/WO arama
├── doctype/
│   ├── calisma_karti/         ← Ana doctype
│   ├── calisma_karti_alt_operasyon_kayitlari/
│   ├── calisma_karti_barkod_kayitlari/
│   ├── calisma_karti_hurda/
│   ├── calisma_karti_idc_olcumleri/
│   ├── kta_calisma_karti_alt_operasyonlari/
│   ├── kta_calisma_karti_operasyonlari/
│   ├── kta_operasyon_grubu/
│   └── operasyon_duruslari/
├── page/
│   ├── create_calisma_karti/
│   ├── list_calisma_cards/
│   └── view_calisma_karti/
└── workspace/

erpnextkta/public/
├── create-calisma-karti/      ← Wizard SPA (Vue 3)
├── list-calisma-cards/        ← Liste SPA (Vue 3)
└── view-calisma-karti/        ← Detay SPA (Vue 3 + TypeScript)
```

---

## 3. Veri Modeli

### 3.1 Ana Doctype: `Calisma Karti`

| Alan | Tip | Açıklama |
|------|-----|----------|
| `name` | Data | Otomatik isimlendirme |
| `is_istasyonu` | Link → Workstation | Zorunlu |
| `operator` | Link → Employee | Atanmış operatör |
| `operasyon` | Link → KTA Calisma Karti Operasyonlari | Zorunlu |
| `is_karti` | Link → Job Card | Zorunlu |
| `custom_work_order` | Link → Work Order | Bağlı iş emri |
| `urun_kodu` | (ayrı alan) | İş kartından türetilir |
| `durum` | Select | Hazır / Çalışıyor / Duruşta / Bitmiş / Reddedildi |
| `kalite_kontrol` | Select (permlevel=1) | Onay Bekliyor / Onaylandı / Reddedildi |
| `baslangic_saati` | Datetime | read_only |
| `bitis_saati` | Datetime | read_only |
| `toplam_sure` | Data | dk:sn formatı, read_only |
| `toplam_durus` | Data | read_only |
| `net_calisma_suresi` | Data | read_only |
| `hurdalar` | Table → Calisma Karti Hurda | — |
| `duruslar` | Table → Operasyon Duruslari | — |
| `idc_olcumleri` | Table → Calisma Karti IDC Olcumleri | — |
| `barkod_kayitlari` | Table → Calisma Karti Barkod Kayitlari | — |
| `alt_operasyon_kayitlari` | Table → Calisma Karti Alt Operasyon Kayitlari | — |

> `kalite_kontrol` alanı `permlevel=1`'dir; doğrudan form üzerinden sadece yetkili roller güncelleyebilir. API tarafında `ignore_permissions` + sıkı rol kapısı kullanılır.

### 3.2 Child Doctypes

| Doctype | Alanlar |
|---------|---------|
| `Calisma Karti Hurda` | parca_no, hurda_nedeni (Cost Center), miktar, birim, depo |
| `Calisma Karti IDC Olcumleri` | item_code, yukseklik_mm, cekme_n, olcum_tarihi, olcumu_giren |
| `Calisma Karti Barkod Kayitlari` | barcode, olcum_tarihi, olcumu_giren |
| `Calisma Karti Alt Operasyon Kayitlari` | alt_operasyon, hammadde, adet, uom, note |
| `Operasyon Duruslari` | durus_nedeni, aciklama, başlangıç/bitiş saati |

### 3.3 Master Doctypes

| Doctype | Amaç |
|---------|------|
| `KTA Calisma Karti Operasyonlari` | Operasyon master listesi (customer_group bağlantısı var) |
| `KTA Calisma Karti Alt Operasyonlari` | Alt operasyon tanımları |
| `KTA Operasyon Grubu` | Operasyon gruplama |

---

## 4. Backend API Katmanı

### 4.1 Facade: `api.py`

`erpnextkta.kta_calisma_karti.api` pathi frontend tarafından kullanılan **tek stabil giriş noktası**. Tüm implementasyonlar `api_impl/` altındadır; `api.py` sadece re-export yapar.

### 4.2 Whitelist Fonksiyonları

| Fonksiyon | Kaynak | Yetki Kuralı |
|-----------|--------|--------------|
| `get_my_calisma_kartlari` | `cards.py` | System Manager / KTA Kalite Kullanıcısı → tümü; diğerleri → kendi `operator` kaydı |
| `get_calisma_karti_detail` | `cards.py` | System Manager / Kalite → serbest; diğerleri → sadece kendi CK'sı |
| `create_calisma_karti` | `create.py` | Manufacturing User; WO docstatus=1 ve status=["Not Started","In Process"] zorunlu |
| `get_hurda_nedeni_options` | `hurda.py` | Herkese açık |
| `search_allowed_hurda_items` | `hurda.py` | Operatör + BOM/operasyon filtresi (Job Card.operation == BOM Item.operation) |
| `add_hurda / update_hurda / delete_hurda` | `hurda.py` | Operator kimlik doğrulama + Cost Center whitelist + BOM item whitelist |
| `update_kalite_kontrol` | `qc.py` | KTA Kalite Kullanıcısı / Quality Manager / System Manager |
| `search_allowed_idc_items` | `qc.py` | QC rol kapısı + item_group="120-IDC Connector" + BOM filtresi |
| `add/update/delete_idc_olcumu` | `qc.py` | QC rol kapısı; `ignore_permissions` ile parent'a yazma |
| `add/update/delete_barkod_kaydi` | `qc.py` | QC rol kapısı |
| `add/update/delete_alt_operasyon_kaydi` | `alt_operasyon.py` | Operator veya System Manager/Kalite |
| `get_job_card_by_barcode` | `barcode.py` | JC read yetkisi + WO status kontrolü |
| `get_work_order_by_barcode` | `barcode.py` | WO read yetkisi + status kontrolü |

### 4.3 Yardımcı Modüller

**`_helpers.py`**
- `is_system_manager()`, `is_quality_user()` → Rol kontrolleri
- `require_my_employee()` → user_id / company_email / personal_email ile Employee çözümleme
- `first_child_table(doc, candidates)` → Field adı fallback ile child table okuma
- `get_child_table_fieldname(parent_doc, child_doctype)` → Meta üzerinden fieldname bulma
- `HURDA_PARENT_COST_CENTER = "Malzeme Sarfları - KTA"` → Sabit

**`realtime.py`**
```python
publish_calisma_karti_changed(docname, reason)

# Yayımlanan event'ler:
"kta_calisma_karti:list_changed"               # liste ekranları için (broadcast)
f"kta_calisma_karti:doc_changed:{docname}"     # tek kart detayı için
```

### 4.4 Güvenlik Mimarisi

```
Genel kural:
  1. Frappe.whitelist() → HTTP erişimi aç
  2. Rol kontrolü → is_system_manager() / is_quality_user() / require_my_employee()
  3. doc.check_permission("read"/"write") → Frappe permission layer
  4. Domain validation → BOM whitelist, Cost Center whitelist, item_group kontrol
  5. Azami ayrıcalık → QC işlemlerinde ignore_permissions + strict rol kapısı
```

---

## 5. Frontend Sayfaları

### 5.1 `create-calisma-karti` — Wizard SPA

**Dosyalar:**
- `App.vue` (1112 satır) → Wizard orchestrator
- `components/StepWorkOrder.vue` → WO barkod girişi
- `components/StepJobCard.vue` → JC listesi/seçimi
- `components/StepWorkstation.vue` → İstasyon seçimi
- `components/StepOperation.vue` → Operasyon seçimi
- `components/StepUser.vue` → Operatör seçimi
- `components/StepJobCardSearch.vue` → JC barkod modu
- `components/StepIndicator.vue` → İlerleme göstergesi

**Çalışma Modları:**
- **WO Modu** (5 adım): Work Order → Job Card → Workstation → Operasyon → Operatör
- **JC Modu** (3 adım): Job Card → Operasyon → Operatör

**Öne çıkan özellikler:**
- Enter tuşu ile barkod okuyucu desteği (global keydown listener)
- `customer_group` bazlı operasyon filtreleme (WO veya JC'den türetilen grup)
- Workstation auto-fill (Job Card'dan)
- Min 700ms loading göstergesi (UX için)
- Başarılı oluşturmada `frappe.msgprint` + yeni kart oluşturma seçeneği

**API çağrıları:**
```
get_work_order_by_barcode    → WO barkod arama
get_job_card_by_barcode      → JC barkod arama
frappe.client.get_list (Job Card)
frappe.client.get_list (KTA Calisma Karti Operasyonlari, fields: name, calisma_karti_op, customer_group)
frappe.client.get_list (Employee, filters: {status: Active, user_id: set})
create_calisma_karti         → Oluşturma
```

---

### 5.2 `list-calisma-cards` — Liste SPA

**Dosyalar:** `App.vue` (928 satır) — tek dosya, component yok

**Özellikler:**
- Realtime Socket.IO: `kta_calisma_karti:list_changed` event'i dinler; 250ms debounce ile yeniler
- **Durum filtresi:** Hazır / Çalışıyor / Duruşta / Bitmiş / Reddedildi (badge sayaçlı)
- **QC filtresi:** Onay Bekliyor / Onaylandı / Reddedildi
- **Customer Group filtresi:** Listedeki kartlara göre dinamik (rows'dan türetilir)
- Metin arama: ad, operatör, iş emri, iş kartı, operasyon, ürün kodu, customer group
- Sıralama: modified/creation/name asc/desc
- Sayfalama: `start` + `page_length=200`, "Daha fazla yükle" butonu
- Client-side filtre: `sortKey` değişince API yeniden çağrılır; diğer filtreler client-side

**Kart görünümü:**
- Sol: Dikey `durum` pill'i (dalgalı CSS clip-path, renk tonuna göre)
- Orta: Operatör adı, Ürün Kodu, İş Emri, İş Kartı, Operasyon
- Sağ: Chevron

**API çağrıları:**
```
get_my_calisma_kartlari(order_by, start, page_length) → Liste
```

---

### 5.3 `view-calisma-karti` — Detay SPA

**Dosya yapısı (TypeScript):**
```
App.vue                        ← Root orchestrator
composables/
  useCalismaKarti.ts           ← Tüm API çağrıları ve state
  useCalismaKartiUi.ts         ← UI computed values (durumLabel, statusClass vs.)
  prompts.ts                   ← frappe.prompt field tanımları (durus, bitir)
components/
  CkTopbar.vue                 ← Geri butonu + Form aç
  CkChips.vue                  ← Durum + QC chip'leri
  CkActionbar.vue              ← Başlat/Durdur/Bitir butonları
  CkTabs.vue                   ← Tab navigation
types/                         ← TypeScript tip tanımları
utils/                         ← Yardımcı fonksiyonlar
views/
  InfoView.vue                 ← Temel bilgiler
  AltOperasyonView.vue         ← Alt operasyon CRUD
  HurdaView.vue                ← Hurda CRUD
  DurusView.vue                ← Duruş listesi (read-only)
  KaliteView.vue               ← QC toggle + IDC + Barkod CRUD
```

**Tab Yapısı:**

| Tab | İçerik |
|-----|--------|
| `info` | CK genel bilgiler (iş emri, kart, operasyon, süre) |
| `alt_operasyon` | Alt operasyon kayıtları CRUD |
| `hurda` | Hurda kayıtları CRUD |
| `durus` | Duruş listesi (salt okunur) |
| `kalite` | QC toggle + IDC ölçümleri + Barkod kayıtları |

**Aksiyon butonu mantığı:**
- `showStart` → durum = "Hazır" ve QC reddedilmemiş
- `showResume` → durum = "Duruşta"
- `showStop` → durum = "Çalışıyor"
- `showFinish` → durum = "Çalışıyor"
- Bitir: `frappe.prompt` ile tamamlanan miktar istenir
- Durdur: `frappe.prompt` ile durus_nedeni + aciklama + tamamlanan_miktar istenir

**Realtime:**
```js
frappe.realtime.on(`kta_calisma_karti:doc_changed:${docname}`, handler)
```
→ Belge güncellendiğinde otomatik yenileme.

**Route pattern:** `view-calisma-karti/<docname>` — Frappe page router kullanılır.

**API çağrıları:**
```
get_calisma_karti_detail(name)
callIslem("Baslat" | "Durus" | "Bitis", ...)   → (Frappe doctype methoduna mı yoksa custom endpoint'e mi bağlı incelenecek)
update_kalite_kontrol(name, kalite_kontrol)
add/update/delete_hurda
add/update/delete_idc_olcumu
add/update/delete_barkod_kaydi
add/update/delete_alt_operasyon_kaydi
```

---

## 6. Rollar ve Yetki Matrisi

| Rol | Liste | Detay Okuma | Durum Değiştirme | Hurda | QC / IDC / Barkod |
|-----|-------|------------|-----------------|-------|-------------------|
| System Manager | Tümü | Tümü | ✅ | ✅ | ✅ |
| KTA Kalite Kullanıcısı | Tümü | Tümü | — | — | ✅ |
| Manufacturing User | Kendi | Kendi | ✅ (kendi kartı) | ✅ (kendi kartı) | — |

> `kalite_kontrol` alanı permlevel=1; sadece `update_kalite_kontrol` API fonksiyonu üzerinden değiştirilebilir.

---

## 7. Bilinen Kısıtlamalar / Dikkat Edilmesi Gerekenler

1. **`callIslem` endpoint'i** (`view-calisma-karti` → Başlat/Durus/Bitir aksiyon butonları) `useCalismaKarti.ts` içinde. Hangi backend methoduna bağlandığı (CK DocType method'u mu, ayrı API mi) `composables/useCalismaKarti.ts` okunmadan kesin söylenemez.

2. **Child table fieldname fallback** `first_child_table(doc, candidates)` kullanımı: `doctype/calisma_karti.json`'daki `alt_operasyon_kayitlari` field adı şemasıyla uyumluluk kontrol edilmeli (JSON'da bu alan gözükmüyor — migrations veya hooks ile eklenmiş olabilir).

3. **`tamamlanan_miktar` alanı** doctype JSON'ında görünmüyor. Büyük ihtimalle `custom_fields` ya da başka bir migration ile eklenmiş.

4. **Durum geçişleri** (Hazır→Çalışıyor→Duruşta→Bitmiş) `STATU_HARITASI` + `get_durum()` metodu ile yönetiliyor. Bu mantık `doctype/calisma_karti/calisma_karti.py`'de. Brief kapsamında okunmadı.

5. **Worker/Job Card durumu senkronizasyonu:** CK tamamlandığında ERPNext tarafındaki Job Card üzerinde bir güncelleme yapılıp yapılmadığı (`on_submit`, `on_update` hooks) `calisma_karti.py`'de araştırılmalı.

6. **list-calisma-cards sortkey değişince** `load()` tetikleniyor (API çağrısı), ancak status/qc/customerGroup filtreleri sadece client-side çalışıyor — büyük veri setinde performans sorunu olabilir.

---

## 8. Bağımlı Frappe/ERPNext Doktipleri

| Doctype | Kullanım Noktası |
|---------|-----------------|
| `Job Card` | CK oluşturma, hurda filtresi, barkod arama |
| `Work Order` | CK oluşturma, IDC filtresi, durum validasyonu |
| `BOM` / `BOM Item` | Hurda item filtresi (operasyon bazlı), IDC filtresi |
| `Workstation` | is_istasyonu alanı |
| `Employee` | operator alanı, kullanıcı → employee eşleme |
| `Cost Center` | Hurda nedeni whitelist (`HURDA_PARENT_COST_CENTER`) |
| `Item Customer Detail` | customer_group türetme (liste ve wizard) |
| `Item` | IDC item grubu kontrolü (`item_group = "120-IDC Connector"`) |
