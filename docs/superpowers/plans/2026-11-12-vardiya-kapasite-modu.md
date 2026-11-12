# Vardiya Kapasite Modu — Uygulama Planı (Faz 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 430 dk vardiya kapasite sınırını `KTA Calisma Karti Settings` içindeki tek bir check ile kapatılabilir yapmak.

**Architecture:** `CalismaKarti.hesapla_toplam_sure` içindeki kesme adımı `_apply_shift_cap` adlı ayrı bir metoda taşınır. Check işaretliyse bu metot kota sorgusunu hiç çalıştırmadan ham net süreyi döndürür. Kartlara yeni alan eklenmez. Kesilmeden önceki süre gerektiğinde `toplam_sure − toplam_durus` ile türetilir (spec §5.2).

**Tech Stack:** Frappe v15 / ERPNext v15, Python 3.10, `FrappeTestCase` (`KTATestCase`), `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-11-12-shopfloor-oee-yetkinlik-design.md` — Bölüm 5 (Faz 1)

## Global Constraints

- Ayar alanı: `vardiya_kapasite_sinirini_devre_disi_birak`, Check, `default "0"`. Etiket: "Vardiya Kapasite Sınırını Devre Dışı Bırak". Yeri: `kart_uyari_suresi_dk` alanının hemen altı.
- Ayar 0 iken veya hiç kaydedilmemişken mevcut davranış **birebir** korunmalı.
- `Calisma Karti` doctype'ına, `tasks.py`'ye ve `api_impl/cards.py`'ye dokunulmaz. Patch gerekmez.
- Süre metinleri `format_sure()` ile üretilir, `_parse_minsec()` ile okunur.
- Proje kuralları:
  - Kullanıcıya görünen metinler `frappe._()` içine alınır ve `translations/en.csv` ile `de.csv` dosyalarına eklenir (`kaynak,çeviri`; virgül içeren metin tırnak içinde).
  - Etiketlerde Title Case kullanılır.
  - Fonksiyon çekirdeği ~10 satırı geçmez.
- Doctype JSON'unun `"modified"` değeri güncel zamana çekilir. Aksi halde `bench migrate` alanı senkronize etmez.
- Commit formatı: `feat(calisma-karti): ...`. Her commit'ten önce `pre-commit run --all-files` çalıştırılır.
- Testler bench konteynerinde çalışır. Alan eklendikten sonra `bench --site test_site migrate` gerekir.
- **Çalışma dalı:** PR #177 merge edildikten sonra güncel `main`'den açılan `feat/vardiya-kapasite-modu`.

## Review Focus

1. **Deploy sonrası ayar hiç kaydedilmemiş:** Sınır aktif kalmalı → `test_unsaved_setting_keeps_cap`.
2. **Serbest modda kilitli sorgu:** `_other_cards_net_seconds_in_shift` çağrılmamalı → `test_cap_disabled_skips_cap`.
3. **Serbest modda açık duruştaki kart:** Açık duruşun o ana kadarki süresi net süreden düşülmeli → `test_cap_disabled_excludes_active_downtime`.
4. **Açık kartta mod değişimi:** Kesilmiş kart, ayar açıldıktan sonra yeniden hesaplanınca kesilmemiş değere dönmeli → `test_mode_switch_recomputes_open_card`.
5. **Mevcut davranışın korunması:** `test_shift_capacity_cap` ve `test_total_duration_multiple_downtimes` değişmeden geçmeli.

---

### Task 1: Vardiya kapasite sınırı ayarı

**Files:**
- Modify: `erpnextkta/kta_calisma_karti/doctype/kta_calisma_karti_settings/kta_calisma_karti_settings.json` (`field_order`'da `kart_uyari_suresi_dk`'dan sonra; `fields` içinde aynı konum; `modified`)
- Modify: `erpnextkta/kta_calisma_karti/doctype/calisma_karti/calisma_karti.py` (`hesapla_toplam_sure`; yeni modül fonksiyonu ve metot)
- Modify: `erpnextkta/translations/en.csv`, `erpnextkta/translations/de.csv`
- Modify: `docs/kta_calisma_karti_ayarlar_rehberi.md` (§1 "Vardiya ve Süre Limitleri"), `erpnextkta/www/docs/calisma-karti-ayarlar.html` (aynı liste)
- Test: `erpnextkta/kta_calisma_karti/doctype/calisma_karti/test_calisma_karti.py` (`TestCalismaKartiIntegration`, `test_shift_capacity_cap`'in yanına)

**Interfaces:**
- Produces:
  - `_kapasite_siniri_devre_disi_mi() -> bool` (modül fonksiyonu, `calisma_karti.py`)
  - `CalismaKarti._apply_shift_cap(self, start_dt: datetime, raw_net_saniye: float) -> float`

- [ ] **Step 1: Failing testleri yaz**

Testler `test_shift_capacity_cap` ile aynı kart kurulumunu (15:00–16:00, 3600 sn) ve aynı `get_kta_settings` patch'ini kullanır. `MOD = "erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti"`. `_kapasite_siniri_devre_disi_mi` dosya başındaki import listesine eklenir.

```python
def test_cap_disabled_skips_cap(self):
    # _other_cards → 24000 (kalan 1800) olsa bile kesilmez
    with patch(f"{MOD}._other_cards_net_seconds_in_shift", return_value=24000) as other, \
         patch(f"{MOD}.get_kta_settings", return_value=(430, 400)), \
         patch(f"{MOD}._kapasite_siniri_devre_disi_mi", return_value=True):
        doc.hesapla_toplam_sure()
    self.assertEqual(doc.net_calisma_suresi, format_sure(3600))
    other.assert_not_called()

def test_unsaved_setting_keeps_cap(self):
    frappe.db.delete("Singles", {"doctype": "KTA Calisma Karti Settings",
                                 "field": "vardiya_kapasite_sinirini_devre_disi_birak"})
    frappe.clear_cache(doctype="KTA Calisma Karti Settings")
    self.assertFalse(_kapasite_siniri_devre_disi_mi())

def test_setting_saved_true_disables_cap(self):
    frappe.db.set_single_value("KTA Calisma Karti Settings",
                               "vardiya_kapasite_sinirini_devre_disi_birak", 1)
    try:
        self.assertTrue(_kapasite_siniri_devre_disi_mi())
    finally:
        frappe.db.set_single_value("KTA Calisma Karti Settings",
                                   "vardiya_kapasite_sinirini_devre_disi_birak", 0)

def test_cap_disabled_excludes_active_downtime(self):
    # bitis_saati yok; baslangic = now-60dk; tek açık duruş now-10dk'da başlamış
    # _kapasite_siniri_devre_disi_mi → True
    self.assertAlmostEqual(_parse_minsec(doc.net_calisma_suresi), 3000, delta=20)

def test_mode_switch_recomputes_open_card(self):
    # önce devre_disi=False ile hesapla → net 1800; sonra devre_disi=True ile tekrar → 3600
    self.assertEqual(net_ilk, format_sure(1800))
    self.assertEqual(doc.net_calisma_suresi, format_sure(3600))
```

- [ ] **Step 2: Testleri çalıştır, fail ettiklerini doğrula**

Run: `bench --site test_site run-tests --app erpnextkta --module erpnextkta.kta_calisma_karti.doctype.calisma_karti.test_calisma_karti`
Expected: FAIL, `ImportError: cannot import name '_kapasite_siniri_devre_disi_mi'`

- [ ] **Step 3: Ayar alanını Settings JSON'una ekle**

```json
{
    "default": "0",
    "fieldname": "vardiya_kapasite_sinirini_devre_disi_birak",
    "fieldtype": "Check",
    "label": "Vardiya Kapasite Sınırını Devre Dışı Bırak",
    "description": "İşaretlenirse operatörün vardiya içindeki toplam net süresi Maksimum Çalışma Kartı Süresi ile sınırlandırılmaz; kartlara fiili net süre yazılır."
}
```
Ardından: `bench --site test_site migrate`

- [ ] **Step 4: `calisma_karti.py` içinde mantığı uygula**

- `_kapasite_siniri_devre_disi_mi() -> bool`: `bool(cint(frappe.db.get_single_value("KTA Calisma Karti Settings", "vardiya_kapasite_sinirini_devre_disi_birak")))`. `cint`, `frappe.utils` importuna eklenir.
- `_apply_shift_cap(self, start_dt, raw_net_saniye) -> float`:
  - Ayar devre dışıysa `raw_net_saniye` döner. Bu durumda `get_kta_settings` ve `_calculate_remaining_shift_capacity` **çağrılmaz**.
  - Değilse `min(raw_net_saniye, self._calculate_remaining_shift_capacity(start_dt, max_limit * 60))` döner.
- `hesapla_toplam_sure`: `raw_net_saniye`'yi bugünkü gibi hesaplar ve `net_saniye = self._apply_shift_cap(start_dt, raw_net_saniye)` kullanır. Diğer satırlar değişmez.

- [ ] **Step 5: Testleri çalıştır, geçtiklerini doğrula**

Run: Step 2'deki komut.
Expected: Yeni 5 test ile `test_shift_capacity_cap` ve `test_total_duration_multiple_downtimes` PASS.

- [ ] **Step 6: Çeviri ve dokümantasyon**

`en.csv` / `de.csv` dosyalarına iki satır eklenir:
- `Vardiya Kapasite Sınırını Devre Dışı Bırak` → `Disable Shift Capacity Limit` / `Schichtkapazitätsgrenze Deaktivieren`
- Ayar açıklaması → `"If checked, the operator's total net time within a shift is not limited by the Maximum Work Card Duration; the actual net time is written to the cards."` / `"Wenn aktiviert, wird die gesamte Nettozeit des Bedieners innerhalb einer Schicht nicht durch die maximale Arbeitskartendauer begrenzt; die tatsächliche Nettozeit wird auf die Karten geschrieben."`

Rehberde (md ve html), "Vardiya ve Süre Limitleri" bölümünde:
- `max_kart_suresi_dk` maddesi şu metinle değiştirilir: "Operatörün bir vardiya içinde tüm kartlarına yazılabilecek toplam net süre kotasıdır (Standart: 430). Kotayı aşan süre son karttan kesilir. Kapasite sınırı devre dışıyken bu değer yalnızca hedef olarak kullanılır."
- Altına yeni madde eklenir: "**Vardiya Kapasite Sınırını Devre Dışı Bırak (`vardiya_kapasite_sinirini_devre_disi_birak`):** İşaretlenirse süre kesilmez; kartlara fiili net süre yazılır. Sınır açıkken kesilen süre, kartın *Toplam Süre − Toplam Duruş − Net Çalışma Süresi* farkıdır. Vardiya sonu otomatik kapatma bu ayardan etkilenmez."

- [ ] **Step 7: Tüm uygulama testleri**

Run: `bench --site test_site run-tests --app erpnextkta`
Expected: `OK`. Mevcut 146+ test yeşil.

- [ ] **Step 8: Commit**

```bash
pre-commit run --all-files
git add erpnextkta/kta_calisma_karti/doctype/kta_calisma_karti_settings/kta_calisma_karti_settings.json \
        erpnextkta/kta_calisma_karti/doctype/calisma_karti/calisma_karti.py \
        erpnextkta/kta_calisma_karti/doctype/calisma_karti/test_calisma_karti.py \
        erpnextkta/translations/en.csv erpnextkta/translations/de.csv \
        docs/kta_calisma_karti_ayarlar_rehberi.md erpnextkta/www/docs/calisma-karti-ayarlar.html
git commit -m "feat(calisma-karti): add toggle to disable shift capacity limit"
```

---

## PR Notları

- Arayüz değişikliği: Settings formunda yeni bir check var. Proje kuralı gereği PR'a ekran görüntüsü eklenmeli.
- Frontend (`public/`) dosyalarına dokunulmuyor, `bench build` gerekmiyor.
