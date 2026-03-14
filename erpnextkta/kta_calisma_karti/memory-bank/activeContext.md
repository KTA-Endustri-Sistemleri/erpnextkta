# Active Context — kta_calisma_karti

> Son güncelleme: 2026-03-14

Branş birleştirmesi (**Combined Enhancements Merge**) başarıyla tamamlandı. `calisma-karti-op-enhancements` ve `operation-jc-mapping` özellikleri tek bir stabil branşta toplandı. Bugün yapılan geliştirmeyle alt operasyonların ID yerine başlık (Title) üzerinden seçilmesi sağlandı.

## Mevcut Odak
*   **Hata Giderme (Tamamlandı)**: 
    *   QI onaylama yetki hatası (`frappe.set_user` swap ile) çözüldü.
    *   Operasyon bazlı miktar girişi mantığı (`miktar_zorunlu_mu`) eklendi.
*   **Geliştirme Kuralları**: Frontend build kuralı ve bütünleşik modül dökümantasyonu eklendi (Tamamlandı).
*   **Arayüz İyileştirmeleri**: Alt operasyon seçiminin iyileştirilmesi (Tamamlandı).
*   **Test Masası Entegrasyonu**: Arayüz tarafındaki eksiklerin giderilmesi (Planlanıyor).
*   **Statü Senkronizasyonu**: CK → Job Card statü akışının tasarımı (Beklemede).

## Son Değişiklikler (2026-03-14) — Alt Operasyon Başlık Seçimi
*   **Backend API**: `get_alt_operasyon_options` fonksiyonu ile sub-op'ların Title ve ID'leri çekiliyor.
*   **Prompt Güncellemesi**: `prompts.ts` içindeki alt operasyon alanı `Select` tipine çevrildi, başlık gösterimi sağlandı.
*   **Vue Entegrasyonu**: `AltOperasyonView.vue` bileşeni API ile beslenerek kullanıcı deneyimi iyileştirildi.

## Son Değişiklikler (2026-03-13) — Akıllı Vardiya Sonu Kapatma & Scheduler Düzeltmesi

Otomatik kart kapatma mantığı kullanıcı geri bildirimleri doğrultusunda revize edildi ve scheduler yapılandırması düzeltildi:

*   **Scheduler Cron Birleştirmesi**: `hooks.py` içinde ayrı satırlarda olan `16:15` ve `00:15` cron tanımları, Frappe'nin çakışma nedeniyle sadece birini çalıştırmasından dolayı `15 0,16 * * *` şeklinde tek satırda birleştirildi.
*   **Akıllı Bitiş Mantığı (Smart Shift-End)**: 
    *   **Duruşta Olan Kartlar**: Bitiş saati, kartın duruşa alındığı gerçek zaman (`durus_baslangic`) olarak set edilir.
    *   **Çalışıyor Olan Kartlar**: Bitiş saati, vardiyanın resmi bitiş saati (`16:00` veya `00:00`) olarak set edilir.
*   **Kümülatif Süre Sınırı**: 430 dakikalık net çalışma süresi sınırı, kart kapatıldıktan sonra `doc.update_durum()` üzerinden operatörün o vardiyadaki tüm işleri baz alınarak otomatik hesaplanmaya devam eder.
*   **Hata Giderme**: `TEST-KULLANICISI` üzerinden yapılan simülasyonlarla yeni mantık doğrulandı ve manuel tetikleme ile ucu açık kalan kayıtlar temizlendi.

## Son Değişiklikler (2026-03-11) — Kalite Kontrol (QI) Geliştirmeleri & Draft Akışı

Kalite kontrol süreci daha esnek ve güvenli bir yapıya kavuşturuldu:

*   **Numune Sayısı (sample_size)**: Kullanıcı artık şablondaki numune sayısını modal üzerinden belirleyebiliyor.
*   **Reddedildi QI Kaydı**: "Reddedildi" (Reject) işlemi yapıldığında da arka planda bir QI belgesi oluşturulması sağlandı. Bu sayede ret kararları da dökümante ediliyor.
*   **Draft & Auto-Submit**: QI belgeleri artık ilk aşamada **Draft** (docstatus=0) olarak kaydediliyor. Çalışma Kartı "Bitir" (Bitis) işlemine alındığında bağlı olan draft QI belgesi otomatik olarak **Submit** ediliyor (`cards.py:_handle_bitis` üzerinden).
*   **Manual Inspection Flag**: ERPNext'in otomatik durum hesaplamasının kullanıcı girdisini (Accepted/Rejected) ezmesini önlemek için `manual_inspection: 1` flag'i her reading satırı için zorunlu kılındı.
*   **Reading Alanları**: Numerik veriler için `reading_1`, metin veriler için `reading_value` ayrımı kesinleştirildi.
*   **QI Link Görünümü**: Kalite sekmesinde `quality_inspection` alanı doluysa doğrudan link ve "Görüntüle" butonu eklendi.

## Son Değişiklikler (2026-03-05) — Operasyon → Job Card Eşleştirme Sistemi

#### Yeni Child DocType: `KTA Operation ERPNext Mappings`
- `erpnext_operation` (Link → ERPNext Operation, zorunlu)
- `production_item` (Link → Item, isteğe bağlı) — dolu ise yalnızca o ürünün BOM'unda geçerlidir
- `KTA Calisma Karti Operasyonlari`'na parent olarak bağlı

#### KTA Calisma Karti Operasyonlari — Yeni Alan ve Autoname
- **`erpnext_operations` Table alanı** eklendi (`KTA Operation ERPNext Mappings` child tablosunu bağlar)
- **Koşullu `autoname()`:** `customer_group` doluysa `"Kablo Kesme-BOSCH"`, boşsa yalnızca `"Kablo Kesme"` ID’si üretir
- `autoname: "Prompt"`, `naming_rule: "Set by user"` Şklinde güncellendi

## Önemli Teknik Gelişmeler

### Vardiya Penceresi + Operatör Net Süre Limiti
- Aynı vardiyada birden fazla kart açan operatörlerin toplam süresini kontrol eden `hesapla_toplam_sure()` güncellemesi.
- `auto_close_timed_out_cards` ve `delete_old_unstarted_cards` cron job iyileştirmeleri.

### Hammadde Filtreleme — item-group Tabanlı Mimari
- BOM/Job Card bağımsızlığı: WO `required_items` ∩ operasyon `allowed_material_groups`.
- Alt operasyon bazlı hammadde kısıtları.

### Hurda Filtreleme Kapsamı Genişletildi
- Operatörün o anki operasyon sırasına (sequence) göre önceki tüm operasyonların malzemelerini görebilmesi.

### Makine Günlük Bakım Sistemi
- **Bakım Talimatı**: `Bakim Talimati` DocType'ı ile tanımlanan (örn: `PTR.BT.049`) standart talimatların operatöre gösterilmesi.
- **Bakım Onayı**: Operatörün kart üzerinde çalışırken ilgili makineyi (Asset) seçip talimata göre onay vermesi.
- **Bakım Formu**: `Makine Gunluk Bakim Formu` ile back-end tarafında submit edilen resmi kayıtlar oluşturulması.
- **UI Entegrasyonu**: `BakimView.vue` bileşeni ile kart detaylarında "Bakım" sekmesi.

### Test Masası Doğrulama Sistemi (Altyapı)
- **DocType**: `Test Masasi Dogrulama Kaydi` (PTR 07/005).
- **Mantık**: KTA Operasyonu üzerinde `board_dogrulamasi_gerektirir` işaretli ise, karta bir doğrulama kaydı (Bağlantı noktaları, kriterler vb.) bağlanması gerekir.
- **Durum**: Şu an için back-end tarafında referans bağı (`on_submit` / `after_insert`) aktiftir, ancak Vue SPA arayüzüne entegrasyonu (buton/sekme) henüz yapılmamıştır.

## Proje İçgörüleri
- `api.py` stable facade mantığı korunuyor.
- Realtime events (Socket.io) tüm CRUD işlemlerini kapsıyor.
- `view-calisma-karti` TypeScript + Composable mimarisiyle en modern bileşen.
