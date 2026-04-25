# Tech Context — kta_calisma_karti

## Teknoloji Yığını

### Backend
| Katman | Teknoloji |
|--------|-----------|
| Framework | Frappe (Python) |
| ORM | Frappe ORM → MariaDB |
| Realtime | Socket.IO (`frappe.publish_realtime`) |
| Versiyonlama | Frappe DocType JSON + Python controller |
| Test | Pytest (Integration) |

### Frontend
| Katman | Teknoloji |
|--------|-----------|
| Framework | Vue 3 (Composition API) |
| Test | Vitest (Unit/Integration/Race) |
| Tip sistemi | TypeScript (sadece `view-calisma-karti`) |
| API köprüsü | `frappe.call()` (global Frappe JS) |
| Realtime | `frappe.realtime.on/off` (Socket.IO) |
| Routing | `frappe.set_route()` / `frappe.get_route()` |
| CSS | Scoped CSS + Frappe CSS değişkenleri |
| Build | Frappe asset build (`bench build --app erpnextkta --production`) |

> [!CAUTION]
> **Build Zorunluluğu**: Frontend dosyalarında (`public/` altı) yapılan her değişiklikten sonra derleme (build) komutu çalıştırılmalıdır. Aksi takdirde değişiklikler arayüze yansımaz.

## Geliştirme Ortamı

```
Root: c:\Users\ufukk\GitHub\frappe_docker\development\frappe-bench\apps\erpnextkta
Module (Backend): erpnextkta/kta_calisma_karti/
Public (Frontend): erpnextkta/public/
  ├── create-calisma-karti/  ← create-calisma-karti.bundle.js
  ├── list-calisma-cards/    ← list-calisma-cards.bundle.js
/srv/workspaces/apps/erpnextkta/erpnextkta/public/view-calisma-karti/
  ├── components/
  ├── composables/
  ├── utils/
  │   └── format.ts    ← Yeni formatDuration yardımcı aracı
  ├── views/
  └── App.vue
```

> [!NOTE]
> Geliştirme sürecinde backend (`kta_calisma_karti`) ve frontend (`public/*`) klasörleri tek bir "Çalışma Kartı Paketi" olarak düşünülmelidir.

#### Liste Görünümü (`list-calisma-cards`)
- **Modüler Yapı**: Büyük bir monolith (`App.vue`) yerine, her bir parçanın kendi bileşeninde (`CkCard`, `CkFilters`, `CkSkeleton`) yaşadığı modüler bir yapı kullanılır.
- **Server-Side Filtering**: Arama, sıralama ve kategorik filtreler (Durum, QC, Müşteri Grubu) doğrudan SQL API'ye (`get_my_calisma_kartlari`) parametre olarak gönderilir.
- **Realtime Sync**: Socket.io üzerinden `list_changed` event'i dinlenerek liste anlık güncellenir.
- **Modern UI**: Shimmer efektli skeleton loading ve gölge/ovallik bazlı premium kart tasarımı.

## Frappe Entegrasyon Noktaları

| Frappe API | Kullanım Yeri |
|------------|--------------|
| `@frappe.whitelist()` | Tüm public API fonksiyonları |
| `frappe.get_doc()` | CK + child table okuma |
| `frappe.db.get_value/get_all` | Performans kritik sorgular |
| `frappe.get_all()` | Liste sorguları |
| `frappe.get_meta()` | Child table fieldname discovery |
| `frappe.get_roles()` | Rol kontrolü |
| `frappe.publish_realtime()` | after_commit=True ile olay yayını |
| `frappe.validate_and_sanitize_search_inputs` | Link field search decorator |
| `frappe.db.sql()` | BOM item whitelist sorguları (JOIN gerekli) |
| `doc.docstatus` | API yanıtlarına mutlaka dahil edilmelidir (UI statü önceliği için) |

- **`hurda_gider_hesabi`** (Link → Account): Hurda Stok Belgelerinde (`Stock Entry Item`) kullanılacak olan varsayılan gider hesabı.
- **`kart_gecis_modu`** (Select): Sıkı / Esnek.

## Yeni ERPNext Doküman Özellikleri

### Stock Entry Type: `Scrap for Manufacturing`
- **Purpose**: `Material Issue`
- **Custom Logic**: Bu tipteki belgeler için `on_update` ve `on_trash` hook'ları üzerinden `Calisma Karti` senkronizasyonu tetiklenir.
- **Field Enrichment**: `is_scrap_item: 1` bayrağı ile hurda satırları normal sarfiyat satırlarından ayırt edilir.

## Kritik Bağımlılıklar

```python
# ERPNext doktipleri (dış bağımlılık)
"Job Card"              # is_karti → operasyon, workstation, bom_no, production_item
"Work Order"            # custom_work_order → bom_no, status, docstatus, required_items
"Stock Entry"           # Smart Tolerance kontrolü için (Manufacture/Repack)
"KTA Operation ERPNext Mappings" # Operasyon bazlı Job Card eşleştirmesi
"KTA Operation Allowed Material Groups" # Ana operasyon kısıtları
"KTA Sub Operation Allowed Material Groups" # Alt operasyon kısıtları
"KTA Durus Sebebi"      # Dinamik duruş nedenleri (Planlı/Plansız)
"Makine Gunluk Bakim Formu" # Günlük bakım kayıtları
"Bakim Talimati"        # Standart bakım talimatları (Örn: PTR.BT.049)
"Test Masasi Dogrulama Kaydi" # Test masası doğrulama kayıtları (PTR 07/005)
"Employee"              # operator eşleştirme
"Workstation"           # is_istasyonu
"Item"                  # item_group ve customer_group kontrolleri
```

## Teknik Kısıtlar

1. **`kalite_kontrol` permlevel=1** — Normal form üzerinden güncellenemez; `db_set + ignore_permissions` zorunlu
2. **Child table fieldname belirsizliği** — `first_child_table()` ile candidate listesi denenebilir
3. **Employee eşleştirme fallback** — `user_id → company_email → personal_email` sırası
4. **`after_commit=True` realtime** — Event DB commit sonrası tetiklenir; başarısızlık CK işlemini bloklamaz
5. **Vue bundle'lar** — Her SPA bağımsız import zinciri; Frappe'nin hot-reload'u kısıtlıdır (dev'de `bench build` gerekebilir)
6. **Agresif Modal Susturma** — `App.vue` açıkken `frappe.msgprint` override edilir ve 250ms'de bir mesaj kuyruğu (`frappe.messages`) temizlenir (Sıkıyönetim Modu).
7. **Frontend Race Condition (loading)** — `withLoading` ve `loading.value` kontrolleri atomiklik sağlamak için senkron olarak API çağrısı öncesi kontrol edilir.
8. **Double Validation** — Hem frontend (loading guard) hem backend (before_submit) katmanlarında veri bütünlüğü kontrol edilir.

## Tool & Patterns

- `frappe.confirm()` — Aksiyonlar (Başlat/Bitir) öncesi onay diyaloğu
- `frappe.prompt()` — Duruş nedeni ve tamamlanan miktar girişi
- `frappe.msgprint()` — Başarı bildirimleri
- `frappe.show_alert()` — Non-blocking QC güncellemesi bildirimi
