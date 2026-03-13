# Active Context — kta_calisma_karti

> Son güncelleme: 2026-03-12

## Mevcut Odak

Branş birleştirmesi (**Combined Enhancements Merge**) başarıyla tamamlandı. `calisma-karti-op-enhancements` (Premium Wizard, Smart Tolerance, QI Draft Flow) ve `operation-jc-mapping` (Job Card Mapping, Alt Operasyon Geliştirmeleri) özellikleri tek bir stabil branşta (`combined-op-jc-enhancements`) toplandı. Sistem şu an hem İş Emri (WO) hem de İş Kartı (JC) akışlarında tam kapasiteyle çalışmaktadır.

## Son Değişiklikler (2026-03-13) — Combined Enhancements Merge & Stabilizasyon

İki ana özellik seti birleştirildi ve build/migrate hataları giderildi:

*   **Integrated Wizard (Birleşik Sihirbaz)**: Hem WO hem de JC barkodlarıyla uyumlu, akıllı önek algılamalı (MFG-WO-, PO-) ve "Smart Tolerance" destekli yeni sihirbaz devreye alındı.
*   **Job Card Mapping & Sequence Filtering**: KTA operasyonlarının ERPNext operasyonlarıyla eşleştirilmesi (mapping) ve hammadde/hurda listelerinin operasyon sırasına (`sequence`) göre kümülatif olarak filtrelenmesi sağlandı.
*   **Smart Tolerance (Akıllı Tolerans)**: İş emri kapalı olsa bile son üretim amaçlı stok girişinden sonraki N saat (ayarlanabilir) boyunca kart açılabilmesi sağlandı.
*   **QI Draft Flow**: Kalite Kontrol belgelerinin taslak olarak oluşturulup kart bitişinde otomatik onaylanması (`cards.py`) mimarisi stabil hale getirildi.
*   **Hata Yönetimi**: Agresif modal susturma ve premium alert kutuları ile pürüzsüz bir operatör deneyimi sağlandı.

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
