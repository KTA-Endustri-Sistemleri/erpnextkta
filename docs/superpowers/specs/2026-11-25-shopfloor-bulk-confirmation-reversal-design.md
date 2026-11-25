# Shopfloor Hub — Çoklu İş Emri Teyit Yönetimi ve Toplu İptal (SAP CORS) Tasarım Belgesi

**Tarih:** 2026-11-25  
**Durum:** Onaylandı  
**Kapsam:** `kta_shopfloor` backend, `shopfloor-hub` Vue 3 SPA, rol yetki temizliği ve dokümantasyon/çeviri senkronizasyonu

---

## 1. Amaç ve Problem Tanımı

Mevcut Shopfloor Hub ekranında üretim teyitlerinin (`KTA Production Confirmation`) ters kayıt (*storno* / SAP CORS) ile iptali yalnızca `Operations` sekmesinde seçili tek bir İş Emri bağlamında (`ConfirmationHistory.vue`) ve satır bazında tek tek yapılabilmektedir.

Birden fazla İş Emrine yayılmış ve çok sayıda operasyona/teyide ait kayıtların tek merkezden filtrelenip seçilerek topluca geri alınabilmesi için merkezi bir yönetim ve toplu iptal ekranına ihtiyaç vardır.

Ek olarak, `kta_shopfloor` modülündeki yetkilendirme gözden geçirildiğinde `KTA Çalışma Kartı Yöneticisi` rolünün yanlışlıkla `shopfloor_hub` sayfası ve `ReversalService` iptal listesine eklendiği görülmüştür. Bu rol Çalışma Kartı modülüne aittir ve Shopfloor kapsamından tamamen çıkarılacaktır.

---

## 2. Değerlendirilen Yaklaşımlar ve Seçilen Yol

| Yaklaşım | Artıları | Eksileri | Karar |
|---|---|---|---|
| **1. Üst menüde bağımsız `Teyitler` sekmesi** (`Work Orders \| Operations \| Teyitler \| Work Cards \| Reports`) | Tek İş Emri seçimi gerektirmez; tam genişlikte çoklu İş Emri filtreleme ve seçim sunar; yıkıcı toplu iptal aksiyonunu salt-okunur raporlardan ayırır. | Navbar 4 sekmeden 5 sekmeye çıkar. | **Seçildi** |
| **2. `Reports` sekmesi altında yeni rapor görünümü** | Navbar değişmez. | `Reports` alanı salt-okunur analiz için tasarlanmıştır; mutasyon yapan toplu iptal orada kavramsal olarak uyumsuzdur. | Reddedildi |
| **3. Sadece `ConfirmationHistory.vue` içine çoklu seçim ekleme** | Küçük UI değişikliği. | Tek İş Emri sınırını aşamaz; birden fazla İş Emrine yayılmış teyitleri çözemez. | Reddedildi |

---

## 3. Yetki Modeli ve Rol Temizliği

1. **`KTA Çalışma Kartı Yöneticisi` rolünün tamamen çıkarılması:**
   - `shopfloor_hub.json` sayfa erişim rollerinden çıkarılır.
   - `ReversalService.ALLOWED_REVERSAL_ROLES` içinden çıkarılır.
   - Portal ve geliştirici dokümantasyonundan çıkarılır.
2. **Shopfloor Hub ve Teyit İptal Yetkileri:**
   - **Sayfa Erişimi & Teyit Oluşturma:** `System Manager`, `Manufacturing Manager`, `Manufacturing User`
   - **Teyit İptali (Tekli ve Toplu):** Yalnızca `System Manager` ve `Manufacturing Manager` (ek olarak `Administrator`)
   - **`Manufacturing User` Davranışı:** Operasyon teyidi verebilir ve `Teyitler` sekmesini **salt-okunur** görüntüleyebilir; ancak ne tekli ne de toplu iptal gerçekleştirebilir. Frontend `can_cancel` bayrağına göre seçim kutularını ve iptal düğmelerini gizler; backend her çağrıda yetkiyi zorunlu doğrular.

---

## 4. Backend Mimarisi (`erpnextkta/kta_shopfloor/`)

### 4.1 `ReversalService` (`services/reversal_service.py`)
- `ALLOWED_REVERSAL_ROLES = {"System Manager", "Manufacturing Manager"}`
- `can_cancel_confirmations(user: str | None = None) -> bool`: Tekil yetki doğrulama kaynağı (`_check_permission` da bunu kullanır).
- `bulk_cancel_confirmations(confirmation_names: list[str] | str, user: str | None = None) -> dict`:
  1. Başlangıçta `_check_permission(user)` uygular, boş/geçersiz liste için `frappe.ValidationError` fırlatır, tekrarlı ID’leri sırayı bozmadan temizler.
  2. Mevcut teyitleri `(creation, name) DESC` (en yeniden eskiye) sırasıyla işler — stok defteri ve *catchup* bağımlılıkları için güvenli sıra.
  3. **Zincirleme (*catchup*) koruması:** Önceki bir teyidin iptali sırasında zaten zincirleme iptal edilmiş (`cancelled_catchup_confirmations`) bir kayıt listede tekrar karşısına çıkarsa hata vermez; `cascade_cancelled` listesine (`cancelled_by` referansıyla) eklenir.
  4. **Bağımsız savepoint izolasyonu (kısmi devam):** Her teyit `ReversalService.cancel_confirmation()` içindeki kendi savepoint’inde yürütülür. Bir kayıt stok/validasyon nedeniyle iptal edilemezse yalnızca o kaydın işlemi geri alınır, `frappe.clear_messages()` ile hata kuyruğu temizlenir, kayıt `failed` listesine nedeni ile eklenir ve kalan teyitler işlenmeye devam eder.
  5. Yapılandırılmış özet döner: `success`, `partial`, `total_requested`, `cancelled_count`, `cascade_cancelled_count`, `failed_count`, `cancelled`, `cascade_cancelled`, `failed`, `affected_work_orders`.

### 4.2 Whitelisted API (`api.py`)
- `get_shopfloor_hub_context`: Yanıta `can_cancel_confirmations` eklenir.
- `_attach_stock_entries_to_confirmations`: `get_production_confirmations` ve `get_confirmations_for_management` tarafından ortak kullanılır (N+1 sorgu ve kod tekrarı önlenir).
- `get_confirmations_for_management(...)`:
  - `KTA Production Confirmation` ve `Work Order` okuma iznini doğrular.
  - Filtreler: `status_filter` (`active` | `cancelled` | `all`), `search` (İş Emri / Ürün Kodu / Ürün Adı / Teyit No), `operation`, `confirmed_by`, `work_order`, `from_date`, `to_date`, `company`, `limit` (`1..500`, varsayılan `200`).
  - Yanıt: `rows`, `total_count`, `counts`, `summary`, `filter_options` (`operations`, `users`), `can_cancel`.
- `bulk_cancel_production_confirmations(confirmation_names)` (`POST`): `ReversalService.bulk_cancel_confirmations` çağırır.

---

## 5. Frontend Mimarisi (`erpnextkta/public/shopfloor-hub/`)

- **`ShopfloorNavbar.vue` & `types.ts` & `App.vue`:**
  - Sekme sırası: `Work Orders | Operations | Teyitler | Work Cards | Reports` (`WorkOrderViewMode` içine `'confirmations'` eklenir).
  - `confirmations` sekmesinde sol sidebar gizlenir, tam genişlik workspace açılır.
- **`ConfirmationsFilters.vue`:**
  - Durum sekmeleri (`Aktif`, `İptal Edildi`, `Tümü`) + sayaçlar + Yenile.
  - Arama, Operasyon, Teyit Eden Kullanıcı, Başlangıç/Bitiş Tarihi ve Filtreleri Temizle aksiyonu.
- **`ConfirmationsManagementPanel.vue`:**
  - Özet kart şeridi (`Aktif Teyit`, `İş Emri`, `Toplam Miktar`).
  - `!canCancel` durumunda salt-okunur bilgilendirme bandı.
  - Sticky toplu aksiyon çubuğu (`Seçilen X Teyit (Y İş Emri)`, `Seçimi Temizle`, `Seçilenleri İptal Et`).
  - Satır checkbox’ları, görünen aktiflerin tümünü seçme ve İş Emri bazlı `"Tümünü Seç"` kısayolu; satırdan İş Emri linki ile `Operations` sekmesine geçiş; tekli `↩ İptal` aksiyonu; limit aşımında `"Daha Fazla Göster"`.
- **`BulkCancelResultModal.vue` (`<Teleport to="body">`):**
  - `confirm` modu: Seçilen teyit sayısı, benzersiz İş Emri sayısı, toplam miktar, ters kayıt uyarısı ve ilk 10 kayıt önizlemesi.
  - `result` modu: `İptal Edildi`, `Zincirleme İptal`, `Hatalı` KPI özeti ve satır bazlı sonuç tablosu.
- **`ConfirmationHistory.vue`:**
  - `canCancel?: boolean` prop’u ile yetkisiz rolde iptal sütununu gizler.
- Tüm `.vue` dosyaları 500 satır sınırının altında kalır, Light/Dark tema CSS değişkenleriyle uyumludur ve cümle bütünlüğü olan `__()` çağrıları kullanır.

---

## 6. Doğrulama ve Dokümantasyon

- Backend testleri: `test_reversal_service.py` ve `test_api.py` (rol reddi/onayı, çoklu İş Emri toplu iptal, catchup deduplication, kısmi hata savepoint izolasyonu, yönetim listesi filtreleri).
- Üretim derlemesi: `bench build --app erpnextkta --production`.
- Kod kalitesi: `ruff check` ve `ruff format --check`.
- Dokümantasyon ve çeviri: `erpnextkta/www/docs/shopfloor-hub.html`, `docs/kta_shopfloor_hub_kilavuzu.md`, `erpnextkta/translations/{tr,en,de}.csv`.
