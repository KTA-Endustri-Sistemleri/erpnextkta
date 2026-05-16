# Sistem Yapıları: KTA MRP

## Mimari
ERPNext içindeki `kta_mrp` uygulaması altında modüler bir eklenti olarak tasarlanmıştır. Hesaplama motoru için Python, kullanıcı arayüzü için Frappe'nin "Script Report" altyapısı kullanılır.

## Temel Teknik Kararlar
- **Ortak Filtre Kaydı**: Tüm MRP raporları filtrelerini `report_utils.py::get_report_filters()` üzerinden alır; tekrar eden JS/Python filter bloğu ortadan kalkar.
- **Ortak JS Formatter**: `kta_report_utils.js::kta.report_utils.std_formatter` tüm raporların `formatter` callback'ine bağlanır.
- **Geriye Dönük Geçiş (Smoothing)**: Gelecekteki yük patlamalarını boş haftalara çekmek için sondan başa doğru çalışan bir döngü uygulanmıştır (Ramp-up).
- **İleriye Dönük Tahsis (Allocation)**: Kalan kapasite için FIFO (ilk giren ilk çıkar) öncelikli ve oransal dağılım mantığı kurulmuştur.
- **Durumsal Devir (Carry-over)**: Karşılanamayan talepleri haftalar boyunca hassas bir şekilde izlemek için `item_carry_over` sözlüğü kullanılır.
- **Stok Evrimi Formülü**: `Önceki Stok + (WIP + Yeni Plan) - Sevkiyat = Mevcut Stok` döngüsü her hafta için kümülatif hesaplanır.

## Tasarım Kalıpları
- **Delegasyon (Yetkilendirme)**: `İş Emri Planlama` ve `Malzeme İhtiyacı` raporları, temel talep hesaplamasını `Kapasite Planlama` motoruna delege eder.
- **Kısıt Bazlı Planlama**: Her tahsis işlemi, Ürün Grubu'nun tanımlı veya kanıtlanmış haftalık kapasitesine karşı kontrol edilir.
- **MOQ ve Paketleme Sarmalayıcı**: Net malzeme ihtiyaçları, `max(moq, ceil(eksik / paket) * paket)` fonksiyonu ile hem minimum sipariş hem de paketleme standartlarına göre sarmalanır. Değerler `Item Price` (Buying=1) tablosundan çekilir.
- **Non-Invasive Report Override**: `kta_report_overrides.js` ile `frappe.provide("kta.report_overrides")` namespace'i altında `page-change` event'ine bağlı dinamik injection yapılır. Core ERPNext dosyaları değiştirilmez; yeni raporlar için namespace'e yeni key eklenmesi yeterlidir.

## Bileşen İlişkileri
```mermaid
graph TD
    CP[Kapasite Planlama Raporu] --> |Dengelenmiş Plan Sağlar| WO[İş Emri Planlama]
    CP --> |Dengelenmiş Plan Sağlar| MR[Malzeme İhtiyacı]
    CP --> |Stok Evrimi Sağlar| PCC[Üretim Komuta Merkezi]
    WO --> |Kontrol Eder| WOD[İş Emri Belgesi]
    MR --> |Patlatır| BOM[BOM Belgesi]
    MR --> |Düşer| Bin[Stok Durumu]
    MR --> |Düşer| PO[Satınalma Siparişi]
    RU[report_utils.py] --> |Filtre Sağlar| CP
    RU --> |Filtre Sağlar| MR
    RU --> |Filtre Sağlar| PCC
    JS[kta_report_utils.js] --> |Formatter Sağlar| CP
    JS --> |Formatter Sağlar| MR
    OV[kta_report_overrides.js] --> |Override Enjekte Eder| BOM_SR[BOM Stock Report]
```
