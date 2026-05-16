# Ürün Bağlamı: KTA MRP Sistemi

## Bu Proje Neden Var?
Standart ERPNext planlama araçları genellikle kalemleri birbirinden bağımsız ele alır, bu da "yapay kapasite çoğalmasına" neden olur (aynı hattaki iki ürünün de tüm kapasiteye sahip olduğunu sanması gibi). Ayrıca, talep patlamaları genellikle ulaşılamaz üretim planlarına (1. Haftada 10.000 adet, 2. Haftada 0) yol açar.

## Çözülen Sorunlar
- **Gerçekçi Olmayan Planlar**: Yükü geriye (Ramp-up) ve ileriye (Carry-over) yayarak "patlama" haftalarını engeller.
- **Grup Darboğazları**: Aynı makineyi/hattı paylaşan ürünler artık ortak bir grup kapasitesiyle sınırlandırılır.
- **Backlog (Birikmiş İş) Yönetimi**: En eski siparişlerin, yenileri gömmeden önce üretilmesini sağlar.
- **Satınalma Baskısı**: Malzeme ihtiyaçları artık "yumuşatılmış" bir şekilde sunulur, böylece "her şeyi yarın getirin" krizlerini önler.
- **Stok Evrimi**: Fiziksel stok, yoldaki üretim (WIP) ve sevkiyatları birleştirerek gelecekteki stok durumunu Excel hassasiyetinde gösterir.

## Nasıl Çalışır?
Sistem 3+1 katmanlı bir zinciri takip eder:
1.  **Kapasite Planlama**: "Beyin". Her bir kalem için haftalık en uygun üretim miktarını hesaplar.
2.  **Üretim Komuta Merkezi**: "Strateji". Stok ilerleyişini ve backlog eritme sürecini izler.
3.  **İş Emri Planlama**: "Aksiyon". Planı mevcut İş Emirleriyle karşılaştırır ve yenilerini önerir.
4.  **Malzeme İhtiyacı**: "Tedarik". Planı BOM üzerinden patlatır ve Stok, PO ve MOQ'u dikkate alarak net ihtiyacı hesaplar.

## Kullanıcı Deneyimi Hedefleri
- **Berraklık**: Kapasite kullanımı için görsel ipuçları (hücre renkleri).
*   **Stratejik Bakış**: Backlog ve stok ilerleyişinin net takibi.
- **Kontrol**: Dengeleme (Balancing) ve Ramp-up için modüler açma/kapama düğmeleri.
- **Güvenilirlik**: Bir üretim müdürünün gerçekten imzalayabileceği ve bir satınalma sorumlusunun uygulayabileceği bir plan.
