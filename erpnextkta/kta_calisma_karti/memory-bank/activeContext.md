# Active Context — kta_calisma_karti

> Son güncelleme: 2026-03-11

## Mevcut Odak

ERPNext standart Kalite Muayene (MAT-QA) entegrasyonu tamamlandı. Operatörler artık ürün bazlı kalite şablonlarını seçerek ölçüm girebiliyor ve bu kayıtlar doğrudan Çalışma Kartı ile ilişkilendiriliyor.

## Son Değişiklikler (2026-03-11) — Kalite Kontrol (QI) Geliştirmeleri & Draft Akışı

Kalite kontrol süreci daha esnek ve güvenli bir yapıya kavuşturuldu:

*   **Numune Sayısı (sample_size)**: Kullanıcı artık şablondaki numune sayısını modal üzerinden belirleyebiliyor.
*   **Reddedildi QI Kaydı**: "Reddedildi" (Reject) işlemi yapıldığında da arka planda bir QI belgesi oluşturulması sağlandı. Bu sayede ret kararları da dökümante ediliyor.
*   **Draft & Auto-Submit**: QI belgeleri artık ilk aşamada **Draft** (docstatus=0) olarak kaydediliyor. Çalışma Kartı "Bitir" (Bitis) işlemine alındığında bağlı olan draft QI belgesi otomatik olarak **Submit** ediliyor (`cards.py:_handle_bitis` üzerinden).
*   **Manual Inspection Flag**: ERPNext'in otomatik durum hesaplamasının kullanıcı girdisini (Accepted/Rejected) ezmesini önlemek için `manual_inspection: 1` flag'i her reading satırı için zorunlu kılındı.
*   **Reading Alanları**: Numerik veriler için `reading_1`, metin veriler için `reading_value` ayrımı kesinleştirildi.
*   **QI Link Görünümü**: Kalite sekmesinde `quality_inspection` alanı doluysa doğrudan link ve "Görüntüle" butonu eklendi.

**Commitler**: 
- `405746f` — `feat(kalite): sample_size, rejected QI destegi ve modal iyilestirmeleri`
- `388719e` — `feat(kalite): QI belgesi kart bitirilince submit edilsin`
- `3ffdc3c` — `feat(kalite): quality_inspection alani API yanitina eklendi`
- `cb904d7` — `fix(kalite): QI link QcToggle altina tasindi ve route duzeltildi`

---

## Son Değişiklikler (2026-03-11) — QC Entegrasyonu & Hata Giderimi

*   **QC Şablon Getirme Hatası Giderildi**: `get_qc_templates_for_ck` ve `get_template_details` metodlarındaki kritik hatalar (`OperationalError` ve `AttributeError`) düzeltildi.
*   **Çoklu Şablon Desteği (Robust Discovery)**: Şablon toplama mantığı Item Master + Job Card + Wildcard araması olarak genişletildi.
*   **Arayüz Entegrasyonu**: `QualityInspectionModal.vue` üzerinden veri girişi ve `App.vue` tetikleyicileri hazırlandı.
*   **🚧 Bekleyen İşler**: Backend fonksiyonları tekil olarak denendi, ancak **uçtan uca (end-to-end) testler evde devam edecek**. Özellikle MAT-QA kaydı sonrası CK statü geçişlerinin tam doğrulanması gerekiyor.

## Recent Changes
*   **Seed Scripti Geliştirildi**: 14 iş günü geçmişe yönelik, sadece operasyonda tanımlı (veya `DEPT_ANAHTAR_KELIMELERI` ile seçilmiş) departman çalışanlarına yönelik 5 farklı statüdeki Çalışma Kartlarını simüle eden test verisi seed yazılımı oluşturuldu.
*   **Grafik Kaynakları (Backend & Frontend) Oluşturuldu**:
    *   `Operasyon Başına Tamamlanan Miktar` (Bar): Her operasyonda kaç parça çıktığını gösterir.
    *   `Duruş Nedeni Dağılımı` (Donut): Sisteme girilen duruş kodlarının toplam dakika dağılımını gösterir.
    *   `Kalite Kontrol Dağılımı` (Donut): Onay durumu ve ret oranlarını dağılım olarak gösterir.
    *   `Departman Bazlı Net Çalışma Süresi` (Bar): Operatör performansını departman kırılımında toplam net süre olarak gösterir.
*   **Yetkilendirme Geliştirmesi**: Tüm ana grafiklerde ve Kalite Kontrol Dağılımı Dashboard konfigürasyonlarında (Dashboard Manager, System Manager vb.) roller eklendi.
*   **Özel Renklendirme (Custom Colors)**: "Kalite Kontrol Dagilimi" grafiği için Mavi ve Yeşil gibi custom hex kodları (JSON seviyesinde) atandı.

### Hurda Filtreleme Kapsamı Genişletildi
*   Hurda (Scrap) Item bazlı `_helpers.py` doğrulama mantığı (ve arayüzdeki büyüteç listesi) değiştirildi.
*   Artık operatör hurda parçası eklerken sadece o andaki operasyonun grubunu değil; o anki `KTA Calisma Karti Operasyonlari` dokümanının `sequence`'ine bakarak **kendinden önceki veya eşit sıradaki tüm Ana ve Alt operasyonların** gruplarından gelen 30+ onaylı materyali topluca görüntüleyebiliyor.

### Commit
`81c9452` — `style(dashboard): set custom colors for kalite_kontrol_dagilimi chart`
`b6493d3` — `feat(kta-calisma-karti): extend scrap filtering to include all prior KTA operations and sub-operations`
`e6b53a0` — `feat(dashboard): add active and paused number cards`

### Dashboard Fixture — `kta_calisma_karti_dashboard`
- `calisma_karti.json` güncellendi: İki chart da Full genişlikte eklendi
- `calisma_karti.json` güncellendi: "Calisan Kart Sayisi" ve "Durusta Kart Sayisi" adında iki yeni Number Card Dashboard ana görünümüne entegre edildi.

### Workspace Fixture — `çalışma_kartı`
- Çalışma Kartı workspace ana ekranına (JSON) "Calisan Kart Sayisi" ve "Durusta Kart Sayisi" Number Card'ları eklendi.

### Number Cards
- Eski "Toplam Açık Kart Sayısı" mantığı "Çalışan" ve "Duruşta" kart sayıları veren iki ayrı karta bölündü.
- `calisan_kart_sayisi` ve `durusta_kart_sayisi` (JSON ve Custom Python Backend) klasörlerine kendi isimleriyle yerleştirildi.

### Teknik Notlar
- Frappe Dashboard Chart Source `filters` parametresi her zaman JSON string olarak gelir → backend'de `json.loads` ile parse edilmeli
- `from frappe import _` çeviri fonksiyonu, döngü değişkeni olarak `_` kullanılırsa ezilir → her zaman `i` vb. kullan
- `currency: TRY` alanı chart JSON'unda olursa Frappe değerleri para birimi formatında gösterir → custom source'larda bu alanı koyma

### Commit
`f33ad1b` — `feat(dashboard): add Calisma Karti and Operator Net Sure chart sources`

## Son Değişiklikler (2026-03-05) — Önceki

### UI ve Validasyon İyileştirmeleri
- **Alt İşlem ve Hurda Buton Gizlenmesi:** Kartın durumu `"Hazır"` veya `"Bitmiş"` iken `AltOperasyonView.vue` ve `HurdaView.vue` içindeki "Ekle" butonları (`v-if` şartıyla) gizlendi.
- **QC IDC Ölçümleri Genişletilmesi:** `qc.py` içindeki IDC validasyonu `120-IDC Connector`'a ek olarak `110-Connector` item grubunu da kapsayacak şekilde güncellendi. Artık iki gruptaki hammaddeler de eklenebiliyor.


### Vardiya Net Süre Simülasyonu ve Düzeltmeler

#### `docstatus` Filtre Düzeltmesi
Canlı sistemde henüz Submit edilmemiş (Draft - `docstatus=0`) kartların vardiya net süre kapasitesini (430 dk) tüketmediği tespit edildi. 
- **`calisma_karti.py`** → `_other_cards_net_seconds_in_shift`: `"docstatus": 1` filtresi `"docstatus": ["!=", 2]` (iptal hariç hepsi) olarak değiştirildi. Artık taslak kartlar da limiti tüketiyor.
- **`tasks.py`** → `auto_close_timed_out_cards` ve `delete_old_unstarted_cards` işlevlerindeki filtreler de aynı şekilde güncellenerek Draft kartları tarayacak hale getirildi. Submit olmuş kartlar için `ignore_validate_update_after_submit` kondisyonel yapıldı.

#### Simülasyon ve Temizlik Scriptleri (repo: `scripts/`)
- `vardiya_sim.py`: DB'ye dokunmadan o anki vardiyadaki (veya önceki vardiyadaki) `docstatus!=2` kartların net süre hesabını simüle eden ve limit aşımı/kalan kapasiteleri konsola basan analiz scripti.
- `cleanup_timed_out.py`: `tasks.py` içindeki zaman aşımı rutini (`auto_close_timed_out_cards`) manuel tetikleyen bench scripti.
- `fix_closed_cards_net_time.py`: Önceden kapanmış ama limiti (örn: 430 dk) çok aşmış (3700+ dk) eski kart turlarını tespit edip net çalışma süresini gerçek sınıra kırpan DB-fix scripti.

## Son Değişiklikler (2026-03-04 → 2026-03-05)

### Operasyon → Job Card Eşleştirme Sistemi

#### Yeni Child DocType: `KTA Operation ERPNext Mappings`
- `erpnext_operation` (Link → ERPNext Operation, zorunlu)
- `production_item` (Link → Item, isteğe bağlı) — dolu ise yalnızca o ürünün BOM'unda geçerlidir
- `KTA Calisma Karti Operasyonlari`'na parent olarak bağlı

#### KTA Calisma Karti Operasyonlari — Yeni Alan ve Autoname
- **`erpnext_operations` Table alanı** eklendi (`KTA Operation ERPNext Mappings` child tablosunu bağlar)
- **Koşullu `autoname()`:** `customer_group` doluysa `"Kablo Kesme-BOSCH"`, boşsa yalnızca `"Kablo Kesme"` ID’si üretir
- `autoname: "Prompt"`, `naming_rule: "Set by user"` Şklinde güncellendi

#### Backend: `get_operations_for_job_card(job_card)` (`create.py`)
JC'nin `operation` ve `production_item` alanlarına göre **üçlü öncelik** mantığı:
1. **En spesifik:** `erpnext_operation == jc.operation` VE `production_item == jc.production_item` → o ürüne özel KTA operasyonları
2. **Operasyon-generic:** `erpnext_operation == jc.operation` VE `production_item` boş → aynı operasyon koduna sahip tüm ürünler için
3. **Tam generic:** Hiç mapping satırı olmayan KTA operasyonları → tüm JC'lere açık fallback

**Pratikte:** Az sayıda 4-adımlı BOM için product-specific mapping yapılır; çoğunluğu oluşturan 2-adımlı BOM'lar mapping-boş bırakılır → Priority 3 tüm KTA operasyonlarını gösterir.

#### Frontend: `create-calisma-karti/App.vue`
- `fetchOperations()` kaldırıldı; `fetchOperationsForJobCard(jcName)` yeni backend API'sini çağırıyor
- JC Mode: JC belirlendikten hemen sonra operasyon listesi çekiliyor
- WO Mode: `selectedJobCardName` watcher'a JC başarılınca operasyon listesi çekiliyor
- `onMounted`'tan `fetchOperations()` kaldırıldı

#### `api.py` Facade
- `get_operations_for_job_card` re-export olarak eklendi



### Vardiya Penceresi + Operatör Net Süre Limiti (Commit: `35bd322`)
- **`_shift_name_by_now(now_dt)`:** Saat dilimine göre aktif vardiyayı döndürür (1./2./3. Vardiya).
- **`_shift_window(now_dt)`:** HRMS `Shift Type` dokümanından başlangıç/bitiş saatlerini çekip `(window_start, window_end)` döndürür. Gece geçen vardiyaları (`we <= ws`) bir gün ileri alır.
- **`_parse_minsec(value)`:** `'M:SS'` formatını toplam saniyeye çevirir.
- **`_other_cards_net_seconds_in_shift(operator, shift_start, shift_end, exclude_name)`:** Aynı vardiya penceresindeki diğer onaylı (`docstatus=1`) ve reddedilmemiş kartların `net_calisma_suresi` toplamını döndürür.
- **`hesapla_toplam_sure()` güncellemesi:** Sabit `max_limit` uygulamasına ek olarak artık vardiya penceresindeki **diğer kartların süresi de hesaba katılıyor**. Kalan kapasite = `(max_limit * 60) - other_net` formülüyle belirleniyor; kart bu kapasiteyi aşamaz.
- **`tasks.py` iyileştirmesi:** `auto_close_timed_out_cards` fonksiyonuna kayıt başlangıcı log eklendi (`frappe.logger().info`). Timeout duruşu artık *sıfır süreli bilgi kaydı* (`durus_suresi=0`, `durus_nedeni="Zaman Aşımı"`) olarak ekleniyor. Kart kapatma akışı sadeleştirildi (erken `continue` mantığına geçildi). `realtime.publish_calisma_karti_changed` zamanlayıcı kapatmalarında da çağrılıyor.
- **`delete_old_unstarted_cards`:** Silmeden önce `docstatus=1` ise otomatik `cancel()` yapılıyor.

### Zaman Aşımı Duruş Nedeni (Commit: `37848be`)
- **`operasyon_duruslari.json`:** `"Zaman Aşımı"` seçeneği `durus_nedeni` select listesine eklendi.
- Artık otomatik kapama sırasında bu standart duruş nedeni kullanılıyor (önceki commit ile entegre).

### Hammadde Filtreleme — item-group Tabanlı Mimari (Commit: `dcd1b05`)
- **`_helpers.py` → `get_allowed_items_with_groups(calisma_karti_name, alt_operasyon=None)`:** BOM/Job Card bağlantısından bağımsız yeni merkezi yardımcı fonksiyon eklendi. Mantık:
  - `alt_operasyon` verilmişse: Alt-op'un `allowed_material_groups` listesine bakılır. Doluysa yalnızca o gruplar; boşsa sıradaki alt op'lar + parent op'un grupları kullanılır.
  - `alt_operasyon` yoksa (hurda vb.): `Calisma Karti.operasyon`'a bağlı ana operasyon grupları kullanılır.
  - Grup tanımlıysa Work Order `required_items` içinden filtrelenir; grup tanımlı değilse tüm WO kalemleri döner.
- **`hurda.py`:** Eski `_get_job_card_name_from_calisma_karti`, `_get_allowed_hurda_item_codes_for_doc`, `_assert_hurda_item_allowed_for_operation`'daki BOM sorgu bloğu kaldırıldı. `_assert_hurda_item_allowed_for_operation` artık yalnızca `get_allowed_items_with_groups(doc.name)` çağırıyor. `search_allowed_hurda_items` endpoint'i tüm BOM SQL sorgusunu bırakıp `get_allowed_items_with_groups` döndürdüğü listeyi kullanıyor.
- **`alt_operasyon.py`:** `_assert_hammadde_allowed(alt_operasyon, hammadde)` → `_assert_hammadde_allowed(calisma_karti, hammadde, alt_operasyon)` imzasına güncellendi. `search_allowed_hammadde_items` artık hem `calisma_karti` hem `alt_operasyon` parametresi alıyor.
- **Frontend `prompts.ts`:** `altOperasyonFields` imzası `(parentOperationLabel, calismaKartiName, defaults, getAltOpValue?)` olarak genişletildi. Hammadde `get_query` closure'ı artık `calisma_karti` filtresi de gönderiyor; `getAltOpValue` callback'i sayesinde dialog açıkken seçilen `alt_operasyon` değeri canlı olarak okunuyor.
- **Frontend `AltOperasyonView.vue`:** `frappe.prompt` çağrıları `let d; d = frappe.prompt(...)` formunda yeniden yazıldı; böylece dialog referansı (`d`) `getAltOpValue` callback'ine geçilebiliyor.

### Dinamik Kart Uyarı Süresi (Commit: `d01098b`)
- **`cards.py`:** `get_calisma_karti_detail()` artık `max_kart_suresi_dk` ve `kart_uyari_suresi_dk` değerlerini `KTA Calisma Karti Settings`'ten okuyup yanıta ekliyor.
- **`App.vue`:** `showTimeoutWarning` computed property'si sabit `400`'ü `doc.kart_uyari_suresi_dk || 400` ile değiştirdi. Banner metni de bu dinamik değeri kullanıyor.

### item-group Seçim Mantığı İyileştirmesi (Commit: `b769ea3`)
- `get_allowed_items_with_groups`'taki sub-op grup önceliği netleştirildi: alt-op kendi `allowed_material_groups`'ına sahipse YALNIZCA bunlar kullanılır; boşsa sequence'a göre önceki alt-op'lar + parent op birleştirilir.

## Son Değişiklikler (2026-03-02)

### Kapsamlı Mimari İyileştirme (Refactoring)
- **Concurrency (Veri Yarışı) Kontrolü:** `create_calisma_karti` metoduna "Son 30 saniyede aynı özelliklerde açılmış kart var mı?" (Anti-Double-Click) kontrolü eklendi.
- **Monolith Parçalaması:** `calisma_karti.py` içindeki tek parça ve +100 satırlık `islem_yap` metodu küçük, yönetilebilir fonksiyonlara (`_handle_baslat`, vb.) bölünüp `api_impl/cards.py` altına taşındı.
- **KTA Calisma Karti Settings:** Hardcoded olarak yazılan (400, 430 dk) bitiş ve ikaz süreleri yeni oluşturulan Single Doctype ayar tablosundan (`get_single_value`) çekilecek şekilde tasarlandı.
- **Frontend Server-Side Filtering & Fixes:** `App.vue` üzerindeki tüm filtreler (`q`, `status`, `customerGroup`, `qcFilter`) JS dizilerinden koparılıp `get_my_calisma_kartlari` backend SQL API'sine bağlandı. Ayrıca reaktif değişkenlerin başlatılma sırasından (TDZ) ve şablondaki eski referanslardan kaynaklanan kritik hatalar giderildi.
- **Submittable Card Fix:** Çalışma Kartı "Onaylı" (Submitted) durumuna zorunlu kılındı ve oluşturma anında otomatik onaylanması sağlandı.
- **Permission Fix:** Kartlar onaylı durumdayken aktivite yapılabilmesi için durum ve kayıt tabloları "Allow on Submit" olarak işaretlendi. Ayrıca `api_impl` modüllerinde (qc, hurda, alt_operasyon) Frappe validation bypass bayrağı (`ignore_validate_update_after_submit`) eklendi.
- **Calculation Fix:** Aktif duruş sırasında `net_calisma_suresi`'nin artmaya devam etmesi hatası giderildi.

### Tekil Çalışma Kartı (Otomatik Duruş) (Commit: `b68a63e`)
- **Backend (Otomatik Duraklatma):** Kullanıcı yeni bir kartı başlattığında (`islem_yap` - Baslat), kendisine ait daha önceden başlattığı diğer tüm açık kartları bularak bunlara bir Duruş Nedeni ("Diger") ekleyip durumu zorla otomatipe çeken `_auto_pause_other_active_cards` fonksiyonu yazıldı.

### Çalışma Kartı Zaman Aşımı ve Otomatik Temizlik (Commit: `2d849cd`)
- **Backend (Hesaplama Sınırı):** `calisma_karti.py` içindeki süre hesaplamalarına `MAX_NET_CALISMA_DK = 430` sabiti eklendi. Açık kalan kartlar maksimum bu değere ulaşır.
- **Backend (Otomatik Kapatma):** `tasks.py` içerisine `auto_close_timed_out_cards` fonksiyonu eklendi. Vardiya sonlarından 15 dk sonra (`16:15` ve `00:15` cron) açık kartları bitirir.
- **Backend (Başlatılmamış Kartların Silinmesi):** `tasks.py` içerisine `delete_old_unstarted_cards` eklendi. `docstatus=1` olan ve üzerinden 1 gün geçip başlatılmayan kartları her gece `04:00` cron tablosuyla veritabanından tamamen siler (`frappe.delete_doc`).
- **Backend (Kullanıcı Uyarısı):** `validate()` hook'unda kart > 400 dk aktif ise `frappe.msgprint` eklendi.
- **Frontend (Kullanıcı Uyarısı):** `App.vue` içinde (real-time timer yardımıyla) işlem 400 dakikayı geçtiğinde kırmızı bir banner (🚨) gösteriliyor.

### Alt Operasyon — Material Group Kısıtı
- **Yeni:** `KTA Operation Allowed Material Groups` child doctype (parent: Ana Op)
- **Yeni:** `KTA Sub Operation Allowed Material Groups` child doctype (parent: Alt Op)
- **Güncelleme:** `kta_calisma_karti_operasyonlari.json` → `allowed_material_groups` Table alanı
- **Güncelleme:** `kta_calisma_karti_alt_operasyonlari.json` → `allowed_material_groups` Table alanı
- **Backend:** `_get_allowed_groups_for_alt_op()` — Sub-op listesi dolu → sub-op; boş → parent op; her ikisi boş → kısıtsız
- **Backend:** `_assert_hammadde_allowed()` + `search_allowed_hammadde_items` whitelist endpoint
- **Backend:** `add/update_alt_operasyon_kaydi`'ya hammadde validasyonu eklendi
- **Frontend:** `prompts.ts` hammadde field'ına `get_query` eklendi

### Not: `bench migrate` gerekiyor
Yeni child doctypeler için bir kez `bench migrate` çalıştırılmalı.

### IDC Ölçüm Düzeltmesi (commit: `d041bcb`)
- `qc.py`'e `_get_doc_for_idc_write()` helper eklendi: operatör kendi kartına IDC girebilir
- `search_allowed_idc_items` — `_require_qc_role()` kaldırıldı; erişim olan herkes arayabilir
- `add/update_idc_olcumu` — `yukseklik_mm=0`, `cekme_n=0` default parametreler
- `calisma_karti_idc_olcumleri.json` — `yukseklik_mm` ve `cekme_n` `reqd: 1` kaldırıldı
- `prompts.ts` — `idcOlcumFields` içinde `reqd: 0` yapıldı

### Alt Operasyon Geliştirmesi (commit: `151baf7`)
- `alt_operasyon.py` yeniden yazıldı: `_assert_can_write()`, hammadde opsiyonel, realtime events
- `cards.py`: `_attach_alt_operasyon_titles()` helper; detail API'sine `alt_operasyon_title` ve `alt_operasyon_sequence` eklendi
- `AltOperasyonView.vue`: `sortedRows` computed, `alt_operasyon_title` gösterimi

## Sonraki Adımlar

Kullanıcı tarafından henüz belirtilmedi. Muhtemel odak noktaları:

1. **`callIslem` endpoint'i** — `view-calisma-karti/composables/useCalismaKarti.ts` içinde ne yapıldığının incelenmesi (Başlat/Durdur/Bitir backend metodu)
2. **`calisma_karti.py` DocType controller'ı** — `STATU_HARITASI`, `get_durum()`, `qc_on_submit` hook'u
3. **`tamamlanan_miktar` alanı** — DocType JSON'da görünmüyor; Custom Field veya migration ile eklenmiş olabilir
4. **QC → Job Card senkronizasyonu** — CK tamamlandığında ERPNext Job Card'ı etkiliyor mu?

## Aktif Kararlar ve Tercihler

- **API stable facade**: `api.py` asla doğrudan implementasyon barındırmaz; frontend method path'leri değişmez
- **Yorum dili**: Kaynak kodda "English comments as requested" notu var → commit'lerde İngilizce yorum
- **Güvenlik prensibi**: `ignore_permissions` SADECE sıkı rol kapısı geçildikten sonra kullanılabilir
- **Realtime fail-safe**: `publish_calisma_karti_changed()` çağrıları try/except içinde; başarısızlık ana işlemi bloklamaz

## Önemli Örüntüler

### Hurda Akışı (v3 — item-group tabanlı kısıt)
```
add_hurda(name, parca_no, ...)
  → _assert_can_write_on_doc()           # operator kontrolü
  → _assert_cost_center_allowed()        # Malzeme Sarfları - KTA altında mı?
  → _assert_hurda_item_allowed_for_operation()
      → get_allowed_items_with_groups(doc.name)  # WO items ∩ operasyon item-group filtresi
  → doc.append() → doc.save()
```

### QC Akışı
```
update_kalite_kontrol(name, val)
  → _require_qc_role()                   # KTA Kalite / QM / SM
  → val ∈ {"Onay Bekliyor", "Onaylandı", "Reddedildi"}
  → ignore_permissions → db_set()
  → "Reddedildi" ise durum da "Reddedildi"
  → publish_realtime
```

## Proje İçgörüleri

- `customer_group` alanı doktipte yok; `Item Customer Detail` join'i ile runtime'da hesaplanıyor → performans dikkat
- List SPA'da `sortKey` değişimi API'yı tetikliyor; diğer filtreler client-side → büyük veri setinde dikkat
- `view-calisma-karti` tek başına TypeScript + composable mimarisiyle yazılmış; diğerleri düz JS
