# Product Context — kta_calisma_karti

## Neden Var?

ERPNext'in standart Job Card formu üretim zemini için fazla karmaşık.  
KTA operatörleri:
- Barkod okuyucu ile hızlı kart oluşturmak istiyor
- Duruş / başlat / bitir işlemlerini sade bir arayüzden yapmak istiyor
- Kalite ekibi IDC ölçümü ve barkod kayıtlarını mobil uyumlu ekranda girmek istiyor
- Yöneticiler tüm kartların anlık durumunu görmek istiyor

| Problem | Çözüm |
|---------|-------|
| ERPNext form karmaşıklığı | Adım adım wizard + tek sayfa detay görünümü |
| Barkod okuyucu entegrasyonu | Global Enter listener + barcode API endpoint (Smart Prefix desteğiyle) |
| Yetki karmaşası (QC vs. operatör) | Rol bazlı API kapıları + permlevel=1 |
| Anlık liste güncellemesi | Socket.IO realtime: `kta_calisma_karti:list_changed` |
| İş Emri - KTA Operasyon uyumsuzluğu | **Job Card Mapping**: ERPNext operasyonlarını esnek şekilde KTA operasyonlarına bağlayan eşleştirme tablosu |
| Tamamlanmış iş emirlerinde tıkanma | **Smart Tolerance**: Son stok girişinden sonraki N saat (varsayılan 8) boyunca işlem izni |
| Makine arızaları / Denetim eksikliği | **Makine Günlük Bakım**: Operatörün işe başlamadan önce makine kontrolü yapmasını sağlayan talimat ve form sistemi |

## Duruş ve Verimlilik Yönetimi
- **Dinamik Duruş Nedenleri**: Tüm duruş nedenleri `KTA Durus Sebebi` tablosundan yönetilir.
- **Duruş Tipleri**: 
    - **Plansız**: Üretim sırasındaki beklenmedik duruşlar (Arıza, Malzeme Bekleme vb.).
    - **Planlı**: Mola, Eğitim veya Planlı Bakım süreçleri.
    - **Sistem**: API veya arka plan görevleri tarafından üretilen duruşlar (Otomatik Duraklatma, Zaman Aşımı).
- **Standart Manuel Nedenler**: Arıza, Bakım, Mola, Kalite Kontrol, Malzeme Bekleme, Diğer (Diger), Kalıp Bağlama / Makine Ayarı, Board Kurma Hazırlık, Malzeme Taşıma, Depo / Hammadde Yerleştirme.
    - *Diğer Validasyonu*: Kullanıcı duruş sebebi olarak "Diger" seçtiğinde, duruşun nedenini açıklayan bir metin girmek frontend (dialog) ve backend (validate hook) düzeyinde **zorunludur**.
- **Otomatik Duruşlar**: Başka kart başlatıldığında veya vardiya sonu zaman aşımında sistem tarafından otomatik olarak eklenir.

## Operasyonel Raporlama ve Dashboard Takibi
- **Operatör Hata / Düşük Süre Raporu**: Günlük net çalışma hedefi (7 saat 10 dakika) altında çalışan ve özellikle 5 saatin altında kalan operatörlerin listesi, amirlerine her sabah otomatik olarak detaylı bir HTML e-posta raporu şeklinde iletilir.
- **Kullanıcı Paneli (User Dashboard) Takibi**: Her sistem kullanıcısının kendi profil panelinde (User Dashboard), kendisiyle ilişkili Employee üzerinden atanmış olan açık ve tamamlanmış Çalışma Kartı listesi ve sayısı dinamik olarak gösterilir.
- **Düşük Net Süre Grafiği (Operator Performance)**: Yönetici panellerinde, son günlerde en düşük performans gösteren (hedef net sürenin gerisinde kalan) operatörleri ve net sürelerini dakika bazında karşılaştıran custom bar chart'lar kullanılır.

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
