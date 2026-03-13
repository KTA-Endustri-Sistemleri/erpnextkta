# Project Brief — kta_calisma_karti

## Ne?
`kta_calisma_karti`, `erpnextkta` Frappe uygulaması içindeki bir modüldür.  
ERPNext'in standart **Job Card / Work Order** akışını genişleterek fabrika zeminine yönelik bir **üretim takip ve kalite kontrol** sistemi sunar.

## Neden?
KTA Endüstri Sistemleri operatörlerinin ERPNext'in karmaşık formlarına girmeden, mobil-dostu ve barkod destekli arayüzlerle çalışabilmesi gerekiyor.

## Kapsam

### Backend
- `Calisma Karti` DocType ve 5 child table + `quality_inspection` Link alanı
- `api.py` stable facade → `api_impl/` (qc, cards, hurda, idc, etc.)
- Rol bazlı güvenlik (System Manager / KTA Kalite Kullanıcısı / Manufacturing User)
- ERPNext Quality Inspection (MAT-QA) entegrasyon API'ları
- Socket.IO realtime events

### Frontend (Vue 3 SPA)
- **create-calisma-karti**: Barkod ile WO veya JC'den CK oluşturma wizard'ı
- **list-calisma-cards**: Realtime güncellemeli, çok filtreli kart listesi
- **view-calisma-karti**: Başlat/Durdur/Bitir + Standart QC Modal + Hurda + IDC + Barkod tab arayüzü

## Başarı Kriterleri
- Operatör, barkod okutarak 3–5 adımda CK oluşturabilmeli
- QC süreçlerinde ERPNext standart MAT-QA belgeleri otomatik oluşturulup bağlanmalı
- QC kullanıcısı IDC ölçümü ve barkod kaydı yapabilmeli
- Hurda kaydı BOM/operasyon kısıtı ile sınırlanmalı
- Liste ekranı anlık güncellenmeli (Socket.IO)

## Sınırlar (Scope Out)
- Muhasebe / faturalama entegrasyonu bu modülde yok
- Batch splitting bu modülün sorumluluğunda değil (bkz. `api.py`)
