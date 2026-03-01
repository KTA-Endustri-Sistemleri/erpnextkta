# API Reference — kta_calisma_karti

Frontend method path prefix: `erpnextkta.kta_calisma_karti.api.`

## Liste & Detay

| Fonksiyon | Parametreler | Döner | Yetki |
|-----------|-------------|-------|-------|
| `get_my_calisma_kartlari` | `order_by`, `start`, `page_length`, `customer_group` | `[{name, operator, durum, ...}]` | Herkese açık (filtreli) |
| `get_calisma_karti_detail` | `name` | `{name, hurdalar, duruslar, ...}` | Operator veya SM/QC |

## Oluşturma

| Fonksiyon | Parametreler | Döner | Yetki |
|-----------|-------------|-------|-------|
| `create_calisma_karti` | `is_karti`, `operasyon`, `is_istasyonu`, `custom_work_order?`, `operator?` | CK dict | Manufacturing User |

## Barkod

| Fonksiyon | Parametreler | Döner | Yetki |
|-----------|-------------|-------|-------|
| `get_job_card_by_barcode` | `barcode` | JC + WO payload | JC read |
| `get_work_order_by_barcode` | `barcode` | WO payload | WO read |

## Hurda

| Fonksiyon | Parametreler | Yetki |
|-----------|-------------|-------|
| `get_hurda_nedeni_options` | `parent_cost_center?` | Herkese açık |
| `search_allowed_hurda_items` | `doctype, txt, searchfield, start, page_len, filters{calisma_karti}` | Operator |
| `add_hurda` | `name, parca_no, hurda_nedeni, miktar, birim, depo?` | Operator |
| `update_hurda` | `name, rowname, parca_no, hurda_nedeni, miktar, birim, depo?` | Operator |
| `delete_hurda` | `name, rowname` | Operator |

## Kalite Kontrol

| Fonksiyon | Parametreler | Yetki |
|-----------|-------------|-------|
| `update_kalite_kontrol` | `name, kalite_kontrol` | KTA Kalite / QM / SM |
| `search_allowed_idc_items` | `doctype, txt, searchfield, start, page_len, filters{calisma_karti}` | KTA Kalite / QM / SM |
| `add_idc_olcumu` | `name, item_code, yukseklik_mm, cekme_n` | KTA Kalite / QM / SM |
| `update_idc_olcumu` | `name, rowname, item_code, yukseklik_mm, cekme_n` | KTA Kalite / QM / SM |
| `delete_idc_olcumu` | `name, rowname` | KTA Kalite / QM / SM |
| `add_barkod_kaydi` | `name, barcode` | KTA Kalite / QM / SM |
| `update_barkod_kaydi` | `name, rowname, barcode` | KTA Kalite / QM / SM |
| `delete_barkod_kaydi` | `name, rowname` | KTA Kalite / QM / SM |

## Alt Operasyon

| Fonksiyon | Parametreler | Yetki |
|-----------|-------------|-------|
| `add_alt_operasyon_kaydi` | `calisma_karti, alt_operasyon, hammadde, adet, uom?, note?` | Operator / SM / QC |
| `update_alt_operasyon_kaydi` | `calisma_karti, row_id, alt_operasyon, hammadde, adet, uom?, note?` | Operator / SM / QC |
| `delete_alt_operasyon_kaydi` | `calisma_karti, row_id` | Operator / SM / QC |

## Realtime Events

| Event | Tetikleyici | Dinleyen |
|-------|------------|---------|
| `kta_calisma_karti:list_changed` | her create/update/qc sonrası | list SPA |
| `kta_calisma_karti:doc_changed:{name}` | aynı, docname ile | view SPA |

## Sabitler (_helpers.py)

```python
HURDA_PARENT_COST_CENTER = "Malzeme Sarfları - KTA"

QC_ALLOWED_ROLES = {"KTA Kalite Kullanıcısı", "Quality Manager", "System Manager"}
QC_ALLOWED_VALUES = {"Onay Bekliyor", "Onaylandı", "Reddedildi"}
```
