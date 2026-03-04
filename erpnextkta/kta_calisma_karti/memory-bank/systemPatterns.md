# System Patterns — kta_calisma_karti

## Mimari Genel Bakış

```
Frontend (Vue 3 SPA)
    ↕  frappe.call() / frappe.realtime
Backend Facade: api.py          ← Tek stabil giriş noktası
    ↕ import
api_impl/ (implementasyon katmanı)
    ↕ frappe.get_doc / frappe.db
Frappe ORM → MariaDB
```

## Tasarım Desenleri

### 1. Facade Pattern — `api.py`
```python
# api.py sadece re-export yapar
from .api_impl.cards import get_my_calisma_kartlari, get_calisma_karti_detail
from .api_impl.hurda import add_hurda, ...
```
- Frontend method string'leri `erpnextkta.kta_calisma_karti.api.*` şeklinde sabit kalır
- İmplementasyon yerine `api_impl/` içinde değiştirilebilir

### 2. Role-Gate Pattern
```python
# Tüm write endpoint'lerinde:
if is_system_manager(): return  # tam yetki
if is_quality_user(): return    # QC yetki
emp = require_my_employee()
if doc.operator != emp: frappe.throw(...PermissionError)
```

### 3. Permlevel Bypass Pattern (QC)
```python
# kalite_kontrol alanı permlevel=1 → normal write izni işe yaramaz
_require_qc_role()          # ← sıkı kapı
doc.flags.ignore_permissions = True
doc.db_set("kalite_kontrol", val)  # güvenli bypass
```

### 4. Child Table Fieldname Discovery
```python
# first_child_table() — alan adı bilinmiyorsa deneme sırası
first_child_table(doc, ["hurdalar", "hurda", "calisma_karti_hurda"])

# get_child_table_fieldname() — meta üzerinden kesin bulma
meta = frappe.get_meta(parent_doc.doctype)
for df in meta.fields:
    if df.fieldtype == "Table" and df.options == child_doctype:
        return df.fieldname
```

### 5. item-group Tabanlı Whitelist Pattern (v3)
```python
# Hurda: WO required_items ∩ operasyon allowed_material_groups filtresi
# (BOM/JC bağlantısından bağımsız)
get_allowed_items_with_groups(calisma_karti_name, alt_operasyon=None)

# Alt-op: alt-op grubu tanımlıysa YALNIZCA o grup
#         boşsa: sequence ≤ current alt-op + parent op grupları
# Hurda (alt_operasyon=None): parent operasyon grupları

# IDC: sadece Work Order BOM'undaki item_group="120-IDC Connector" kalemler
BOM Item JOIN Item WHERE item_group="120-IDC Connector"
```

### 6. Realtime Event Pattern
```python
# Her yazma işlemi sonrası (create.py, qc.py, ...):
publish_calisma_karti_changed(docname, reason="create:calisma_karti")
# →
frappe.publish_realtime("kta_calisma_karti:list_changed", ...)
frappe.publish_realtime(f"kta_calisma_karti:doc_changed:{docname}", ...)
```

Frontend'de:
```js
frappe.realtime.on("kta_calisma_karti:list_changed", handler)
```

### 7. Settings / Configuration Pattern
```python
# Sistem genelinde geçerli olan hard limitler (Örn: 430 dk bitiş) "KTA Calisma Karti Settings" tekil tablosu (Single Doctype) qua get_single_value() metodu ile kontrol edilir.
max_limit = frappe.db.get_single_value("KTA Calisma Karti Settings", "max_kart_suresi_dk") or 430
```

### 8. Server-Side Filtering Pattern
Büyük liste verileri içeren (Çalışma Kartları) Vue frontend ekranlarında, `computed` tabanlı tarayıcı düzeyinde döngülerden (client-side data arrays filtering) kaçınılır. Ara yüz sadece arama(`search_term`), durum(`durum`, `qc_filter`) parametrelerini backend'e gönderir. Süzme ve paginasyon işlemleri (SQL `WHERE` ve `LIMIT/OFFSET`) arka tarafta (`frappe.get_all` parametreleri ve `or_filters`) yapılır.

## Bileşen İlişkileri

```
Calisma Karti (Ana DocType)
  ├── hurdalar              → Calisma Karti Hurda
  ├── duruslar              → Operasyon Duruslari
  ├── idc_olcumleri         → Calisma Karti IDC Olcumleri
  ├── barkod_kayitlari      → Calisma Karti Barkod Kayitlari
  └── alt_operasyon_kayitlari → Calisma Karti Alt Operasyon Kayitlari

Bağlı ERPNext Doktipleri:
  is_karti   → Job Card → BOM (hurda ve IDC filtresi için)
  custom_work_order → Work Order → BOM
  is_istasyonu → Workstation
  operator   → Employee
  operasyon  → KTA Calisma Karti Operasyonlari (customer_group ile)
```

## Kritik Implementasyon Yolları

### CK Oluşturma:
`create_calisma_karti() → JC yükle → WO çöz → Status kontrol (docstatus=1, Not Started/In Process) → doc.insert() → publish_realtime → Departman tag ekle`

### 9. Operasyon → JC Eşleştirme Pattern
```
get_operations_for_job_card(job_card)
  → jc.operation + jc.production_item okunur
  → Tüm KTA Operasyonları + mapping satırları tek sorguda çekilir
  → Prio-1: erpnext_operation == jc.operation AND production_item == jc.production_item → döndür
  → Prio-2: erpnext_operation == jc.operation AND production_item boş → döndür
  → Prio-3: Hiç mapping satırı olmayan KTA operasyonları → döndür
```

### 10. Koşullu Autoname Pattern (KTA Operasyonlari)
```python
def autoname(self):
    op = self.calisma_karti_op.strip()
    cg = (self.customer_group or "").strip()
    self.name = f"{op}-{cg}" if cg else op
    # Generic: "Kablo Kesme" | Spec: "Kablo Kesme-BOSCH"
```

### Kalite Kontrol Güncelleme:
`update_kalite_kontrol() → _require_qc_role() → değer whitelist kontrolü → ignore_permissions → db_set() → publish_realtime`

### Hurda Ekleme (v3 — item-group tabanlı):
`add_hurda() → _assert_can_write_on_doc() → _assert_cost_center_allowed() → _assert_hurda_item_allowed_for_operation() [get_allowed_items_with_groups()] → doc.append() → doc.save()`

### Vardiya Penceresi Net Süre Hesabı:
`hesapla_toplam_sure() → _shift_window(end_dt) [HRMS Shift Type] → _other_cards_net_seconds_in_shift() → remaining=max_limit-other_net → net_saniye=min(net_saniye, remaining)`

### Create Wizard Operasyon Adımı:
`JC seç/belirle → fetchOperationsForJobCard(jcName) → get_operations_for_job_card() [Prio-1 → Prio-2 → Prio-3] → filteredOperations computed (customer_group) → StepOperation gösterim`
