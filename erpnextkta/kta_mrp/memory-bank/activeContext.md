# Aktif Bağlam: KTA MRP Optimizasyonu

## Mevcut Odak Noktası
Kapasite planlamadan malzeme ihtiyaçlarına kadar uçtan uca planlama zincirinin mükemmelleştirilmesi ve "Üretim Komuta Merkezi" üzerinden stratejik takibin sağlanması.

## Son Değişiklikler
- **Üretim Boru Hattı Analizi (Komuta Merkezi)**: Excel modelleriyle tam uyumlu, haftalık stok ilerleyişini (Stock Evolution) takip eden stratejik rapor geliştirildi.
- **Dinamik Kapasite Hiyerarşisi**: Kapasite tespiti için "Manuel Tanım > Geçmiş Performans (3 Aylık Ort.) > Sınırsız" hiyerarşisi kuruldu.
- **Açık İş Emri (WIP) Entegrasyonu**: Devam eden üretimi stok girişlerine dahil eden ve yeni planı buna göre daraltan akıllı mekanizma eklendi.
- **Sert Kapasite Dengeleme**: Backlog (birikmiş borç) olduğu sürece fabrikayı tam kapasite (7.000 veya tanımlı limit) çalışmaya zorlayan algoritma uygulandı.
- **Koli Bazlı Yuvarlama**: Tüm talep ve üretim rakamları, müşteriye özel paketleme miktarlarına (MPQ) göre otomatik yukarı yuvarlanıyor.

## Gelecek Adımlar
- **Doğrulama**: MOQ yuvarlamasından kaynaklanan "Stok Fazlası" durumunun uzun vadeli etkilerinin izlenmesi.
- **Arayüz Geliştirme**: Çok fazla ürün geçişi yapıldığında "Hazırlık Süresi" (Setup Time) maliyetinin kapasiteye yansıtılması.
- **Verimlilik**: Çok geniş ürün setleri için Malzeme İhtiyaç raporunun hızlandırılması.

## Aktif Kararlar
- **Backlog Önceliği**: Tüm gecikmiş siparişler "1. Hafta" (Bugün) kolonunda toplanarak planın gerçek borçla başlaması kararlaştırıldı.
- **Kanıtlanmış Kapasite**: Eğer ürün kartında kapasite tanımlı değilse, son 3 aylık İş Emri verilerinden hesaplanan ortalama haftalık hızın baz alınması standart hale getirildi.
