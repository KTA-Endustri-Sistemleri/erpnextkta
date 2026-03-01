# Active Context — kta_calisma_karti

> Son güncelleme: 2026-03-02

## Mevcut Odak

Alt operasyon modülü geliştirildi. Aktif geliştirme yok; bir sonraki odak bekleniyor.

## Son Değişiklikler (2026-03-02)

### Alt Operasyon Geliştirmesi
- **`api_impl/alt_operasyon.py`** yeniden yazıldı:
  - `_assert_can_write()` ortak helper çıkarıldı
  - `hammadde`, `uom`, `note` opsiyonel parametreye alındı (lint temiz)
  - Her write sonrası `frappe.db.commit()` + `publish_calisma_karti_changed()` eklendi
- **`api_impl/cards.py`**'e `_attach_alt_operasyon_titles()` helper eklendi:
  - `get_calisma_karti_detail` artık her alt_operasyon satırına `alt_operasyon_title` ve `alt_operasyon_sequence` döndürüyor
- **`views/AltOperasyonView.vue`** güncellendi:
  - `sortedRows` computed (sequence → idx sırası)
  - Başlık olarak `alt_operasyon_title` gösterimi (fallback: raw name)

### Keşfedilen Gerçekler (calisma_karti.py okundu)
- `callIslem` → `erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.islem_yap`
- `STATU_HARITASI`: `hazir | calisiyor | durusta | bitmis | reddedildi`
- `tamamlanan_miktar`: `doc.tamamlanan_miktar` alanı (Custom Field) — Duruş ve Bitiş'te artırılıyor
- QC gate: `Bitis` işlemi `kalite_kontrol == "Onaylandı"` olmadan bloklanıyor
- `autoname` formatı: `{operator}-{wo_tail}-{op_clean}-.##`

## Sonraki Adımlar

Kullanıcı tarafından henüz belirtilmedi. Muhtemel odak noktaları:

1. **`callIslem` endpoint'i** — `view-calisma-karti/composables/useCalismaKarti.ts` içinde ne yapıldığının incelenmesi (Başlat/Durdur/Bitir backend metodu)
2. **`calisma_karti.py` DocType controller'ı** — `STATU_HARITASI`, `get_durum()`, `qc_on_submit` hook'u
3. **`tamamlanan_miktar` alanı** — DocType JSON'da görünmüyor; Custom Field veya migration ile eklenmiş olabilir
4. **QC → Job Card senkronizasyonu** — CK tamamlandığında ERPNext Job Card'ı etkiliyor mu?

## Aktif Kararlar ve Tercihler

- **API stable facade**: `api.py` asla doğrudan implementasyon barındırmaz; frontend method path'leri değişmez
- **Yorum dili**: Kaynak kodda "English comments as requested" notu var → commit'lerde İngilizce yorum
- **Güvenlik prensibi**: `ignore_permissions` SADECE sıkı rol kapısı geçildikten sonra kullanılabilir
- **Realtime fail-safe**: `publish_calisma_karti_changed()` çağrıları try/except içinde; başarısızlık ana işlemi bloklamaz

## Önemli Örüntüler

### Hurda Akışı (v2 — BOM operasyon kısıtlı)
```
add_hurda(name, parca_no, ...)
  → _assert_can_write_on_doc()           # operator kontrolü
  → _assert_cost_center_allowed()        # Malzeme Sarfları - KTA altında mı?
  → _assert_hurda_item_allowed_for_operation()  # BOM + JC.operation kısıtı
  → doc.append() → doc.save()
```

### QC Akışı
```
update_kalite_kontrol(name, val)
  → _require_qc_role()                   # KTA Kalite / QM / SM
  → val ∈ {"Onay Bekliyor", "Onaylandı", "Reddedildi"}
  → ignore_permissions → db_set()
  → "Reddedildi" ise durum da "Reddedildi"
  → publish_realtime
```

## Proje İçgörüleri

- `customer_group` alanı doktipte yok; `Item Customer Detail` join'i ile runtime'da hesaplanıyor → performans dikkat
- List SPA'da `sortKey` değişimi API'yı tetikliyor; diğer filtreler client-side → büyük veri setinde dikkat
- `view-calisma-karti` tek başına TypeScript + composable mimarisiyle yazılmış; diğerleri düz JS
