# Proje Özeti: kta_quality

KTA Endüstri Sistemleri için özel olarak geliştirilen `kta_quality` modülü, üretim hattındaki test süreçlerinin güvenilirliğini ve doğruluğunu sağlamak amacıyla tasarlanmıştır.

## Temel Amaç
Bu modülün ana hedefi, **Test Masası Doğrulama (Test Bench Verification)** süreçlerini dijitalleştirmektir. Üretim operasyonları başlamadan önce, test masasının fiziksel, elektriksel ve güvenlik açısından uygun olduğunu garanti altına alır.

## Kapsam
- **Test Masası Doğrulama Kaydı:** Test masasının her devreye alınışında veya periyodik kontrollerinde doldurulan ana form.
- **Sabit Kontrol Kriterleri:** Elektriksel bağlantılar, Poke-Yoke mekanizmaları, etiket doğruluğu ve switch kontrolleri gibi standartlaştırılmış maddeler.
- **Entegrasyon:** `Calisma Karti` (İş Kartı) ile olan referans bağlantıları sayesinde, kalite kontrol sonuçlarının üretim akışına dahil edilmesi.

## Başarı Kriterleri
- Test masası hazırlık hatalarının minimuma indirilmesi.
- Tüm doğrulama adımlarının tarihsel olarak izlenebilir olması.
- Operatörlerin standartlaştırılmış bir kontrol listesi üzerinden çalışmasının sağlanması.
