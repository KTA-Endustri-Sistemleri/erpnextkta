# Active Context — kta_calisma_karti

> Son güncelleme: 2026-03-02

## Mevcut Odak

Alt operasyon geliştirmesi ve IDC yetki düzeltmesi tamamlandı. Material group kısıtı uygulandı. Bir sonraki geliştirme bekleniyor.

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

### Hurda Akışı (v2 — BOM operasyon kısıtlı)
```
add_hurda(name, parca_no, ...)
  → _assert_can_write_on_doc()           # operator kontrolü
  → _assert_cost_center_allowed()        # Malzeme Sarfları - KTA altında mı?
  → _assert_hurda_item_allowed_for_operation()  # BOM + JC.operation kısıtı
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
