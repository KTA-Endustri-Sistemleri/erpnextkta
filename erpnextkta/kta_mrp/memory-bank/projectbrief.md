# Proje Özeti: KTA MRP ve Kapasite Planlama Optimizasyonu

## Temel Gereksinimler
ERPNext KTA kapasite planlama iş akışını modernize ederek, bağımsız ürün kapasite hesaplamalarından, akıllı yük dengelemeli, ortak ve grup tabanlı bir modele geçiş yapmak.

## Hedefler
1.  **Ortak Kapasite**: Aynı gruptaki kalemlerin ortak bir haftalık üretim limitini paylaştığı bir model uygulamak.
2.  **Akıllı Dengeleme**: Hibrit bir FIFO (Önce Birikmiş İşler) ve Kritiklik tabanlı (Oransal) dağıtım stratejisi kullanmak.
3.  **Üretim Yumuşatma (Heijunka)**: Doğrusal bir ramp-up (hazırlık) algoritması aracılığıyla üretimdeki ani patlamaları ortadan kaldırmak.
4.  **Operasyonel Doğruluk**: İş emri önerilerinin ve malzeme ihtiyaçlarının dengelenmiş üretim planıyla senkronize edilmesini sağlamak.
5.  **Lojistik Optimizasyonu**: Hammaddeler için MOQ (Minimum Sipariş Miktarı) ve paketleme boyutu yuvarlamasını uygulamak.
6.  **Stratejik İzleme**: Üretim Komuta Merkezi aracılığıyla stok ilerleyişini, gecikmiş siparişleri (backlog) ve gerçek depo durumunu Excel hassasiyetinde takip etmek.
