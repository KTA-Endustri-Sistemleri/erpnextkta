# İlerleme: kta_quality

## Tamamlanan Özellikler
- [x] **TestMasasiDogrulamaKaydi DocType:** Temel veri yapısı ve çocuk tablolar (kriterler, bağlantı noktaları) oluşturuldu.
- [x] **Otomatik Kriter Doldurma:** `before_insert` sırasında 17 maddelik standart listenin otomatik yüklenmesi.
- [x] **Calisma Karti Entegrasyonu:** Doğrulama sonuçlarının anlık olarak `Calisma Karti` üzerinde güncellenmesi.
- [x] **Uygulama Metni Yönetimi:** PTR form referanslarını içeren standart metnin formlara eklenmesi.
- [x] **KTA Krimp Book DocType:** 1548 adet teknik referans verisinin aktarımı ve kütüphane yapısı.
- [x] **Dinamik Kontak Kısıtı:** `KTA Quality Settings` üzerinden Item Group bazlı terminal filtreleme altyapısı.
- [x] **Hafıza Bankası (Memory Bank):** Modül dokümantasyonunun ve Krimp mimari vizyonunun Türkçe olarak tamamlanması.

## Üzerinde Çalışılanlar (In-Progress)
- [/] **Gelecek Mimari Planlama:** Krimp Book ve Amboss Takımları arasındaki Link ilişkisinin detaylandırılması.

## Gelecek Planları / Yapılacaklar
- [ ] **Krimp Otomasyonu:** Parametreler sayfasında terminal seçildiğinde Book'tan otomatik veri çekme mantığının kurulması.
- [ ] **Raporlama:** Test masası doğrulama başarı oranlarını ve uygunsuzluk (DÇF) istatistiklerini gösteren özel raporların eklenmesi.

## Bilinen Sorunlar
- Sabit kriterlerin kodda tanımlı olması sebebiyle, yeni bir kriter eklenmesi geliştirici müdahalesi (`.py` değişikliği) gerektiriyor. (Gelecek planlarıyla çözülecek).
- `kta_calisma_karti` modülü yüklü değilse, cross-module senkronizasyonda hata alınabilir.
