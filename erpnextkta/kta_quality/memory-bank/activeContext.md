# Aktif Bağlam: kta_quality

## Mevcut Odak (2026-04-19)
Şu anki odak noktamız, `kta_quality` modülünün `kta_calisma_karti` ile olan entegrasyonunu güçlendirmek ve bugün tamamlanan **"Duruş Standardizasyonu"** projesinin (Arıza, Board Kurma, Kalite Kontrol vb.) kalite darboğaz analizleri üzerindeki etkisini izlemek ve raporlamaktır.

## Son Değişiklikler
- `TestMasasiDogrulamaKaydi` DocType'ının işlevsel hale getirilmesi.
- `SABIT_KRITERLER` (17 maddelik liste) ve `BAGLANTI_NOKTASI_SATIRLAR` listelerinin Python kontrolcü seviyesinde otomatik doldurulmasının sağlanması.
- `before_insert`, `validate`, `on_update` ve `after_insert` hook'larının `Calisma Karti` ile veri senkronizasyonu için yapılandırılması.

## Aktif Kararlar
- **Krimp Mimarisi:** `KTA Krimp Book`'un bir "Referans Ansiklopedisi" olarak kalmasına, `KTA Krimp Yukseklik Parametreleri`'nin ise bu kitaptan beslenen birer "Onaylı Uygulama" katmanı olmasına karar verildi.
- **Dinamik Kısıt:** `Kontak No` seçimlerinin `KTA Quality Settings` üzerinden yönetilebilir `Item Group` filtreleri ile yapılması sağlandı.
- **Fiziksel Bağlantı:** Gelecek fazda `Amboss Takımları` (Kalıp) ile kitap verisi arasındaki Link bağlantılarının kurulması planlanmaktadır.
- **Dil Seçimi:** Tüm sistem dökümantasyonu Türkçe olarak sürdürülüyor.

## Sonraki Adımlar
- [ ] `systemPatterns.md` dosyasının teknik detaylarla (hook'lar ve veri akışı) doldurulması.
- [ ] `techContext.md` dosyasının DocType ilişkileri ile oluşturulması.
- [ ] `progress.md` dosyasının mevcut durum özetiyle hazırlanması.
- [ ] Tüm dokümanların genel bir tur rehberi (Walkthrough) ile sunulması.
