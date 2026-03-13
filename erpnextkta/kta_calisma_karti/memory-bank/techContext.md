# Tech Context — kta_calisma_karti

## Teknoloji Yığını

### Backend
| Katman | Teknoloji |
|--------|-----------|
| Framework | Frappe (Python) |
| ORM | Frappe ORM → MariaDB |
| Realtime | Socket.IO (`frappe.publish_realtime`) |
| Versiyonlama | Frappe DocType JSON + Python controller |
| Test | — (henüz test yapısı yok) |

### Frontend
| Katman | Teknoloji |
|--------|-----------|
| Framework | Vue 3 (Composition API) |
| Tip sistemi | TypeScript (sadece `view-calisma-karti`) |
| API köprüsü | `frappe.call()` (global Frappe JS) |
| Realtime | `frappe.realtime.on/off` (Socket.IO) |
| Routing | `frappe.set_route()` / `frappe.get_route()` |
| CSS | Scoped CSS + Frappe CSS değişkenleri |
| Build | Frappe asset build (`*.bundle.js` entry point) |

## Geliştirme Ortamı

```
Root: c:\Users\ufukk\GitHub\frappe_docker\development\frappe-bench\apps\erpnextkta
Module: erpnextkta/kta_calisma_karti/
Public: erpnextkta/public/
  ├── create-calisma-karti/  ← create-calisma-karti.bundle.js
  ├── list-calisma-cards/    ← list-calisma-cards.bundle.js
  └── view-calisma-karti/    ← view-calisma-karti.bundle.js
```

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

## Kritik Bağımlılıklar

```python
# ERPNext doktipleri (dış bağımlılık)
"Job Card"              # is_karti → operasyon, workstation, bom_no, production_item
"Work Order"            # custom_work_order → bom_no, status, docstatus, required_items
"Stock Entry"           # Smart Tolerance kontrolü için (Manufacture/Repack)
"KTA Operation ERPNext Mappings" # Operasyon bazlı Job Card eşleştirmesi
"KTA Operation Allowed Material Groups" # Ana operasyon kısıtları
"KTA Sub Operation Allowed Material Groups" # Alt operasyon kısıtları
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

## Tool & Patterns

- `frappe.confirm()` — Aksiyonlar (Başlat/Bitir) öncesi onay diyaloğu
- `frappe.prompt()` — Duruş nedeni ve tamamlanan miktar girişi
- `frappe.msgprint()` — Başarı bildirimleri
- `frappe.show_alert()` — Non-blocking QC güncellemesi bildirimi
