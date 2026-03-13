# Active Context — kta_calisma_karti

> Son güncelleme: 2026-03-04

## Mevcut Odak

Vardiya bazlı net süre kontrolü ve dinamik uyarı süresi eklendi. Hammadde filtreleme item-group tabanlı yeni mimariye geçirildi. Bir sonraki geliştirme bekleniyor.

## Son Değişiklikler (2026-03-02 → 2026-03-04)

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
