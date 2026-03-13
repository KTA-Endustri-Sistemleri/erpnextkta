# Product Context — kta_calisma_karti

## Neden Var?

ERPNext'in standart Job Card formu üretim zemini için fazla karmaşık.  
KTA operatörleri:
- Barkod okuyucu ile hızlı kart oluşturmak istiyor
- Duruş / başlat / bitir işlemlerini sade bir arayüzden yapmak istiyor
- Kalite ekibi IDC ölçümü ve barkod kayıtlarını mobil uyumlu ekranda girmek istiyor
- Yöneticiler tüm kartların anlık durumunu görmek istiyor

## Çözdüğü Problemler

| Problem | Çözüm |
|---------|-------|
| ERPNext form karmaşıklığı | Adım adım wizard + tek sayfa detay görünümü |
| Barkod okuyucu entegrasyonu | Global Enter listener + barcode API endpoint |
| Yetki karmaşası (QC vs. operatör) | Rol bazlı API kapıları + permlevel=1 |
| Anlık liste güncellemesi | Socket.IO realtime: `kta_calisma_karti:list_changed` |
| Hurda kaydında yanlış parça | BOM + operasyon bazlı item whitelist |
| IDC ölçümünde yanlış malzeme | `item_group = "120-IDC Connector"` + BOM scope filtresi |
| Kalite belgerinin izlenebilirliği | ERPNext standart MAT-QA entegrasyonu ve otomatik linkleme |
| Tamamlanmış iş emirlerinde tıkanma | **Smart Tolerance**: Son stok girişinden sonraki N saat (varsayılan 8) boyunca işlem izni |

## Kullanıcı Grupları

### Operatör (Manufacturing User)
- Kendi kartlarını oluşturur, görür ve yönetir
- Başlat / Duraklat / Bitir aksiyonları
- Hurda kaydı (BOM'daki operasyon malzemeleriyle sınırlı)
- Alt operasyon kayıtları

### Kalite Kullanıcısı (KTA Kalite Kullanıcısı)
- Tüm kartları görebilir (sorgulamak için)
- IDC ölçümü ve barkod kaydı ekleyebilir/düzenleyebilir/silebilir
- ERPNext standart Kalite Muayene (MAT-QA) şablonlarını kullanarak ölçüm girişi yapabilir
- Kalite durumunu güncelleyebilir ve MAT-QA belgesi oluşturabilir

### Yönetici (System Manager)
- Tüm operasyonlara tam erişim
- Herhangi bir kartı görebilir ve düzenleyebilir

## Kullanıcı Deneyimi Hedefleri

- **Hız:** Barkod okutulduğunda mümkün olan maksimum şey otomatik doldurulsun (Smart Prefix: 2026-0 -> MFG-WO-2026-0)
- **Netlik:** Kart durumu (Hazır/Çalışıyor/Duruşta/Bitmiş/Reddedildi) tek bakışta anlaşılsın
- **Güvenlik:** Yanlış veri girilmesini önleyen sunucu tarafı doğrulama
- **Canlılık:** Liste ekranı yeni kart oluşturulduğunda ya da durum değiştiğinde anlık güncellensin
- **Premium UX:** Hata modalları yerine modern Alert kutuları, akıcı animasyonlar (shake) ve tam karanlık mod uyumu
