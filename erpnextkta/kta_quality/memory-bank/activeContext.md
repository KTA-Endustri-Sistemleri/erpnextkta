# Aktif Bağlam: kta_quality

## Mevcut Odak (2026-06-25)
Şu anki odak noktamız, `kta_quality` modülündeki teknik kütüphane verilerinin (`KTA Krimp Book`) ve test masası kontrollerinin, `kta_calisma_karti` modülüyle olan entegrasyonunu kusursuzlaştırmaktır. Son dönemde tamamlanan Krimp ölçüm cascade seçim yapısı ve tolerans kontrolleri ile test masası doğrulama kayıtlarının ilişkileri stabilize edilmiştir.

## Son Değişiklikler
- `TestMasasiDogrulamaKaydi` DocType'ı ve `Calisma Karti` entegrasyonunun kararlı hale getirilmesi.
- `KTA Krimp Book` üzerindeki 1540+ teknik referans verisine dayalı krimp yükseklik tolerans doğrulamalarının `kta_calisma_karti` üzerinden çağrılması.
- KTA Ayarlarından (`KTA Quality Settings`) `Item Group` bazlı terminal kısıtlama mantığının devreye alınması.
- `Administrator` kullanıcısı üzerinden koşan test suite kararlılık güncellemeleri.

## Aktif Kararlar
- **Krimp Mimarisi:** `KTA Krimp Book`'un bir "Referans Ansiklopedisi" olarak kalmasına, `KTA Krimp Yukseklik Parametreleri`'nin ise bu kitaptan beslenen birer "Onaylı Uygulama" katmanı olmasına karar verildi.
- **Dinamik Kısıt:** `Kontak No` seçimlerinin `KTA Quality Settings` üzerinden yönetilebilir `Item Group` filtreleri ile yapılması sağlandı.
- **Fiziksel Bağlantı:** Gelecek fazda `Amboss Takımları` (Kalıp) ile kitap verisi arasındaki Link bağlantılarının kurulması planlanmaktadır.
- **Dil Seçimi:** Tüm sistem dökümantasyonu Türkçe olarak sürdürülüyor.

## Sonraki Adımlar
- [/] **Krimp Protokolü Baskı Şablonu:** Krimp doğrulama protokolü için gerekli print template şablonunun tasarlanması (Tasarım/Bekleme aşamasında).
- [ ] **Dijital Test Masası Entegrasyonu:** Test masasından gelen dijital test verilerinin `Calisma Karti` ile otomatik eşleştirilmesi.
- [ ] **Krimp Otomasyonu:** Parametreler sayfasında terminal seçildiğinde Book'tan otomatik veri çekme mantığının kurulması.
- [ ] Sabit kriterlerin veritabanından dinamik yönetilmesine yönelik mimari refaktör çalışması.

