# Active Context — kta_calisma_karti

> Son güncelleme: 2026-03-02

## Mevcut Odak

Alt operasyon geliştirmesi tamamlandı, IDC yetki + zorunluluk düzeltmesi yapıldı. Alt operasyon modülünde devam edilecek.

## Son Değişiklikler (2026-03-02)

### IDC Ölçüm Düzeltmesi (commit: `d041bcb`)
- `qc.py`'e `_get_doc_for_idc_write()` helper eklendi: operatör kendi kartına IDC girebilir
- `search_allowed_idc_items` — `_require_qc_role()` kaldırıldı; erişim olan herkes arayabilir
- `add/update_idc_olcumu` — `yukseklik_mm=0`, `cekme_n=0` default parametreler
- `calisma_karti_idc_olcumleri.json` — `yukseklik_mm` ve `cekme_n` `reqd: 1` kaldırıldı
- `prompts.ts` — `idcOlcumFields` içinde `reqd: 0` yapıldı

### Alt Operasyon Geliştirmesi (commit: `151baf7`)
- `alt_operasyon.py` yeniden yazıldı: `_assert_can_write()`, hammadde opsiyonel, realtime events
- `cards.py`: `_attach_alt_operasyon_titles()` helper; detail API'sine `alt_operasyon_title` ve `alt_operasyon_sequence` eklendi
- `AltOperasyonView.vue`: `sortedRows` computed, `alt_operasyon_title` gösterimi

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
