# Vardiya Kapasite Modu ve Operatör Kontrolü — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 430 dk vardiya kapasite sınırını ve vardiya sonu otomatik kapatmayı `KTA Calisma Karti Settings` içindeki bağımsız iki check ile devre dışı bırakılabilir yapmak; kapasite sınırı kapatıldığında dakika alanını (`max_kart_suresi_dk`) gizlemek ve test loglarını `[TEST] [modül] [metot]: açıklama` formatına yükseltmek.

**Architecture:** `test_utils.py` içinde test loglaması `[TEST] [modül] [metot]: açıklama` formatına dönüştürülür ve altyapı sıfırlamasına yeni ayarlar eklenir. `CalismaKarti.hesapla_toplam_sure` içindeki kesme adımı `_apply_shift_cap` metoduna taşınır. Check işaretliyse kota sorgusu ve `FOR UPDATE` kilitleri çalıştırılmadan ham net süre (`toplam_sure - toplam_durus`) döner. `max_kart_suresi_dk` alanına `depends_on: "eval:!doc.vardiya_kapasite_sinirini_devre_disi_birak"` eklenir. `tasks.auto_close_timed_out_cards` fonksiyonuna kapatma ayarı kontrolü eklenir. Job Card senkronizasyonu ve `distribute_completed_qty` adet paylaştırma algoritmasına dokunulmaz.

**Tech Stack:** Frappe v15 / ERPNext v15, Python 3.10, `FrappeTestCase` (`KTATestCase`), `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-11-15-vardiya-kapasite-ve-kapanis-modu-design.md`

## Global Constraints

- Ayar alanları:
  - `vardiya_kapasite_sinirini_devre_disi_birak`, Check, `default "0"`. Etiket: "Vardiya Kapasite Sınırını Devre Dışı Bırak". Yeri: `kart_uyari_suresi_dk` alanının hemen altı.
  - `max_kart_suresi_dk`: `depends_on: "eval:!doc.vardiya_kapasite_sinirini_devre_disi_birak"` eklenir.
  - `vardiya_sonu_otomatik_kapatmayi_devre_disi_birak`, Check, `default "0"`. Etiket: "Vardiya Sonu Otomatik Kapatmayı Devre Dışı Bırak". Yeri: `timeout_durus_nedeni` alanının hemen altı.
- Ayarlar 0 iken veya hiç kaydedilmemişken mevcut davranış **birebir** korunmalıdır (sıfır regresyon).
- `Calisma Karti` tablosuna yeni süre alanı eklenmez. Ham süre gerektiğinde `toplam_sure - toplam_durus` formülünden türetilir.
- Job Card adet paylaştırma algoritmasına (`job_card_sync.distribute_completed_qty`) dokunulmaz; süre Job Card'a `to_time = baslangic + net_calisma_suresi` olarak gitmeye devam eder.
- Kullanıcıya görünen metinler `frappe._()` içine alınır ve `translations/en.csv` ile `de.csv` dosyalarına eklenir (`kaynak,çeviri`; virgül içeren metin tırnak içinde).
- Etiketlerde Title Case kullanılır.
- Fonksiyon çekirdeği ~10 satırı geçmez.
- Doctype JSON'unun `"modified"` değeri güncel zamana çekilir (`bench migrate` için).
- Commit formatı: `feat(calisma-karti): ...` veya `test(core): ...`. Her commit'ten önce `pre-commit run --all-files` çalıştırılır.

## Review Focus

1. **Test Log Formatı:** Her test başlangıcında `🔍 [TEST] [<modül_adı>] [<metot_adı>]: <açıklama>` konsola yazılmalı.
2. **Deploy sonrası ayar hiç kaydedilmemiş:** Sınır aktif kalmalı → `test_unsaved_setting_keeps_cap`.
3. **Serbest modda kilitli sorgu:** `_other_cards_net_seconds_in_shift` çağrılmamalı → `test_cap_disabled_skips_cap`.
4. **Serbest modda açık duruştaki kart:** Açık duruşun o ana kadarki süresi net süreden düşülmeli → `test_cap_disabled_excludes_active_downtime`.
5. **Açık kartta mod değişimi:** Kesilmiş kart, ayar açıldıktan sonra yeniden hesaplanınca kesilmemiş değere dönmeli → `test_mode_switch_recomputes_open_card`.
6. **Otomatik kapatma devre dışı:** `auto_close_timed_out_cards` ayar aktifken kartları kapatmadan çıkmalı → `test_auto_close_disabled_skips_processing`.
7. **Mevcut davranışın korunması:** `test_shift_capacity_cap`, `test_total_duration_multiple_downtimes` ve `distribute_completed_qty` testleri değişmeden geçmeli.

---

### Task 1: Test Altyapısı: Zengin Log Formatı ve Otomatik DB İzolasyonu

**Files:**
- Modify: `erpnextkta/tests/test_utils.py` (`KTATestCase.setUp`, `setup_kta_infrastructure`)
- Modify: `erpnextkta/kta_calisma_karti/doctype/calisma_karti/test_calisma_karti_unit.py` (loglayıcıyı miras alma)

- [x] **Step 1: `test_utils.py` içinde log formatını ve sıfırlamayı güncelle**

`erpnextkta/tests/test_utils.py`:
1. `setUp` içinde modül adını ayıkla ve `🔍 [TEST] [{module_tag}] [{self._testMethodName}]: {desc}` formatında yazdır:
```python
parts = self.__class__.__module__.split(".")
module_tag = parts[1] if len(parts) > 1 and parts[1] != "tests" else (parts[-1].replace("test_", "") if len(parts) > 1 else "kta")
tag_str = f"[{module_tag}]"
method_str = f"[{self._testMethodName}]"
desc = self.shortDescription()
if desc:
    print(f"\n🔍 [TEST] {tag_str} {method_str}: {desc}")
else:
    print(f"\n🔍 [TEST] {tag_str} {method_str}")
```
2. `setup_kta_infrastructure()` içine ayarları sıfırlama komutlarını ekle:
```python
frappe.db.set_single_value("KTA Calisma Karti Settings", "vardiya_kapasite_sinirini_devre_disi_birak", 0)
frappe.db.set_single_value("KTA Calisma Karti Settings", "vardiya_sonu_otomatik_kapatmayi_devre_disi_birak", 0)
```

- [x] **Step 2: `test_calisma_karti_unit.py` sınıflarını loglayıcı ile zenginleştir**

`test_calisma_karti_unit.py` test sınıflarının `setUp` metodlarında loglama fonksiyonunu çağırarak unit testlerin de konsola `🔍 [TEST] [kta_calisma_karti] [...]` şeklinde çıkmasını sağla.

- [x] **Step 3: Testi çalıştırıp çıktı formatını doğrula**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_calisma_karti.doctype.calisma_karti.test_calisma_karti`
Expected: Testler geçer ve loglarda `🔍 [TEST] [kta_calisma_karti] [test_shift_capacity_cap]: ...` formatı görünür.

- [x] **Step 4: Commit**

```bash
pre-commit run --all-files
git add erpnextkta/tests/test_utils.py erpnextkta/kta_calisma_karti/doctype/calisma_karti/test_calisma_karti_unit.py
git commit -m "test(core): enhance test logging format with module and method tags"
```

---

### Task 2: Vardiya kapasite sınırı ayarı ve dakika alanı dinamik gizleme

**Files:**
- Modify: `erpnextkta/kta_calisma_karti/doctype/kta_calisma_karti_settings/kta_calisma_karti_settings.json` (`field_order` ve `fields` içine `vardiya_kapasite_sinirini_devre_disi_birak`; `max_kart_suresi_dk` içine `depends_on`; `"modified"` güncellemesi)
- Modify: `erpnextkta/kta_calisma_karti/doctype/calisma_karti/calisma_karti.py` (`hesapla_toplam_sure`, `_apply_shift_cap`, `_kapasite_siniri_devre_disi_mi`)
- Test: `erpnextkta/kta_calisma_karti/doctype/calisma_karti/test_calisma_karti.py` (`TestCalismaKartiIntegration`)

**Interfaces:**
- Produces:
  - `_kapasite_siniri_devre_disi_mi() -> bool` (modül fonksiyonu, `calisma_karti.py`)
  - `CalismaKarti._apply_shift_cap(self, start_dt: datetime, raw_net_saniye: float) -> float`

- [x] **Step 1: Failing testleri yaz**

`erpnextkta/kta_calisma_karti/doctype/calisma_karti/test_calisma_karti.py` içine şu testleri ekle:
```python
def test_cap_disabled_skips_cap(self):
    """Kapasite sınırı devre dışıyken kotanın uygulanmadığını ve kilitli sorgunun çağrılmadığını doğrular."""
    doc = make_mock_calisma_karti(baslangic_saati="2024-01-15 15:00:00", bitis_saati="2024-01-15 16:00:00")
    MOD = "erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti"
    with patch(f"{MOD}._other_cards_net_seconds_in_shift", return_value=24000) as other, \
         patch(f"{MOD}.get_kta_settings", return_value=(430, 400)), \
         patch(f"{MOD}._kapasite_siniri_devre_disi_mi", return_value=True):
        doc.hesapla_toplam_sure()
    self.assertEqual(doc.net_calisma_suresi, format_sure(3600))
    other.assert_not_called()

def test_unsaved_setting_keeps_cap(self):
    """Ayar DB'de hiç yokken veya kaydedilmemişken varsayılanın kapalı (sınırın aktif) olduğunu doğrular."""
    from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import _kapasite_siniri_devre_disi_mi
    frappe.db.delete("Singles", {"doctype": "KTA Calisma Karti Settings", "field": "vardiya_kapasite_sinirini_devre_disi_birak"})
    frappe.clear_cache(doctype="KTA Calisma Karti Settings")
    self.assertFalse(_kapasite_siniri_devre_disi_mi())

def test_setting_saved_true_disables_cap(self):
    """Ayar kaydedildiğinde fonksiyonun True döndüğünü doğrular."""
    from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import _kapasite_siniri_devre_disi_mi
    frappe.db.set_single_value("KTA Calisma Karti Settings", "vardiya_kapasite_sinirini_devre_disi_birak", 1)
    try:
        self.assertTrue(_kapasite_siniri_devre_disi_mi())
    finally:
        frappe.db.set_single_value("KTA Calisma Karti Settings", "vardiya_kapasite_sinirini_devre_disi_birak", 0)

def test_cap_disabled_excludes_active_downtime(self):
    """Kapasite sınırı kapalıyken de devam eden aktif duruş süresinin net süreden düşüldüğünü doğrular."""
    from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import _parse_minsec
    doc = make_mock_calisma_karti(baslangic_saati=frappe.utils.add_to_date(None, minutes=-60), bitis_saati=None)
    doc.append("duruslar", {"durus_baslangic": frappe.utils.add_to_date(None, minutes=-10), "durus_nedeni": "Diğer"})
    MOD = "erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti"
    with patch(f"{MOD}._kapasite_siniri_devre_disi_mi", return_value=True):
        doc.hesapla_toplam_sure()
    self.assertAlmostEqual(_parse_minsec(doc.net_calisma_suresi), 3000, delta=20)

def test_mode_switch_recomputes_open_card(self):
    """Açık kartın mod değişimi sonrasında doğru şekilde yeniden hesaplandığını doğrular."""
    doc = make_mock_calisma_karti(baslangic_saati="2024-01-15 15:00:00", bitis_saati="2024-01-15 16:00:00")
    MOD = "erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti"
    with patch(f"{MOD}._other_cards_net_seconds_in_shift", return_value=24000), \
         patch(f"{MOD}.get_kta_settings", return_value=(430, 400)), \
         patch(f"{MOD}._kapasite_siniri_devre_disi_mi", return_value=False):
        doc.hesapla_toplam_sure()
    net_ilk = doc.net_calisma_suresi
    self.assertEqual(net_ilk, format_sure(1800))
    with patch(f"{MOD}._kapasite_siniri_devre_disi_mi", return_value=True):
        doc.hesapla_toplam_sure()
    self.assertEqual(doc.net_calisma_suresi, format_sure(3600))
```

- [x] **Step 2: Testleri çalıştır, fail ettiklerini doğrula**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_calisma_karti.doctype.calisma_karti.test_calisma_karti`
Expected: FAIL, `ImportError: cannot import name '_kapasite_siniri_devre_disi_mi'`

- [x] **Step 3: Ayar alanını ve `depends_on` kuralını Settings JSON'una ekle**

`erpnextkta/kta_calisma_karti/doctype/kta_calisma_karti_settings/kta_calisma_karti_settings.json`:
1. `max_kart_suresi_dk` nesnesine `"depends_on": "eval:!doc.vardiya_kapasite_sinirini_devre_disi_birak"` ekle.
2. `field_order` içinde `kart_uyari_suresi_dk` sonrasına `"vardiya_kapasite_sinirini_devre_disi_birak"` ekle.
3. `fields` listesine ekle:
```json
{
    "default": "0",
    "fieldname": "vardiya_kapasite_sinirini_devre_disi_birak",
    "fieldtype": "Check",
    "label": "Vardiya Kapasite Sınırını Devre Dışı Bırak",
    "description": "İşaretlenirse operatörün vardiya içindeki toplam net süresi Maksimum Çalışma Kartı Süresi ile sınırlandırılmaz; kartlara fiili net süre yazılır."
}
```
4. `"modified"` alanını güncel ISO zaman damgasına çek.
5. Çalıştır: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost migrate`

- [x] **Step 4: `calisma_karti.py` içinde mantığı uygula**

1. `_kapasite_siniri_devre_disi_mi() -> bool`:
```python
def _kapasite_siniri_devre_disi_mi() -> bool:
    from frappe.utils import cint
    return bool(cint(frappe.db.get_single_value("KTA Calisma Karti Settings", "vardiya_kapasite_sinirini_devre_disi_birak")))
```
2. `CalismaKarti._apply_shift_cap(self, start_dt, raw_net_saniye) -> float`:
```python
def _apply_shift_cap(self, start_dt, raw_net_saniye):
    if _kapasite_siniri_devre_disi_mi():
        return raw_net_saniye
    max_limit, _ = get_kta_settings()
    remaining = self._calculate_remaining_shift_capacity(start_dt, max_limit * 60)
    return min(raw_net_saniye, remaining)
```
3. `hesapla_toplam_sure`:
```python
raw_net_saniye = max(0, toplam_saniye - toplam_durus_saniye)
net_saniye = self._apply_shift_cap(start_dt, raw_net_saniye)
```

- [x] **Step 5: Testleri çalıştır, geçtiklerini doğrula**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_calisma_karti.doctype.calisma_karti.test_calisma_karti`
Expected: Yeni 5 test ile `test_shift_capacity_cap` ve `test_total_duration_multiple_downtimes` PASS.

- [x] **Step 6: Commit**

```bash
pre-commit run --all-files
git add erpnextkta/kta_calisma_karti/doctype/kta_calisma_karti_settings/kta_calisma_karti_settings.json \
        erpnextkta/kta_calisma_karti/doctype/calisma_karti/calisma_karti.py \
        erpnextkta/kta_calisma_karti/doctype/calisma_karti/test_calisma_karti.py
git commit -m "feat(calisma-karti): add toggle to disable shift capacity limit and hide duration field"
```

---

### Task 3: Vardiya sonu otomatik kapatmayı devre dışı bırakma ayarı

**Files:**
- Modify: `erpnextkta/kta_calisma_karti/doctype/kta_calisma_karti_settings/kta_calisma_karti_settings.json` (`field_order` ve `fields` içine `vardiya_sonu_otomatik_kapatmayi_devre_disi_birak`)
- Modify: `erpnextkta/tasks.py` (`auto_close_timed_out_cards`)
- Test: `erpnextkta/kta_calisma_karti/doctype/calisma_karti/test_calisma_karti_unit.py`

**Interfaces:**
- Consumes: `frappe.db.get_single_value("KTA Calisma Karti Settings", "vardiya_sonu_otomatik_kapatmayi_devre_disi_birak")`

- [x] **Step 1: Failing test yaz**

`erpnextkta/kta_calisma_karti/doctype/calisma_karti/test_calisma_karti_unit.py` içine şu testi ekle:
```python
def test_auto_close_disabled_skips_processing(self):
    """Vardiya sonu otomatik kapatma devre dışıyken auto_close_timed_out_cards'ın işlem yapmadığını test eder."""
    from erpnextkta.tasks import auto_close_timed_out_cards
    with patch("frappe.db.get_single_value", return_value=1) as mock_setting, \
          patch("frappe.get_all") as mock_get_all:
        auto_close_timed_out_cards()
        mock_get_all.assert_not_called()
```

- [x] **Step 2: Testi çalıştır, fail ettiğini doğrula**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_calisma_karti.doctype.calisma_karti.test_calisma_karti_unit`
Expected: FAIL (`AssertionError: Expected 'mock_get_all' not to have been called. Called 1 times.`)

- [x] **Step 3: Ayar alanını Settings JSON'una ekle**

`erpnextkta/kta_calisma_karti/doctype/kta_calisma_karti_settings/kta_calisma_karti_settings.json`:
1. `field_order` içinde `timeout_durus_nedeni` sonrasına `"vardiya_sonu_otomatik_kapatmayi_devre_disi_birak"` ekle.
2. `fields` listesine ekle:
```json
{
    "default": "0",
    "fieldname": "vardiya_sonu_otomatik_kapatmayi_devre_disi_birak",
    "fieldtype": "Check",
    "label": "Vardiya Sonu Otomatik Kapatmayı Devre Dışı Bırak",
    "description": "İşaretlenirse vardiya bitimlerinde (16:15 ve 00:15) açık kalan kartlar sistem tarafından otomatik kapatılmaz; kart kapatma kontrolü tamamen operatörde kalır."
}
```
3. `"modified"` alanını güncelle.
4. Çalıştır: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost migrate`

- [x] **Step 4: `tasks.py` içinde kontrolü ekle**

`erpnextkta/tasks.py` `auto_close_timed_out_cards` başlangıcına:
```python
from frappe.utils import cint
if cint(frappe.db.get_single_value("KTA Calisma Karti Settings", "vardiya_sonu_otomatik_kapatmayi_devre_disi_birak")) == 1:
    frappe.logger().info("auto_close_timed_out_cards: disabled in settings, skipping.")
    return
```

- [x] **Step 5: Testi çalıştır, geçtiğini doğrula**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_calisma_karti.doctype.calisma_karti.test_calisma_karti_unit`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
pre-commit run --all-files
git add erpnextkta/kta_calisma_karti/doctype/kta_calisma_karti_settings/kta_calisma_karti_settings.json \
        erpnextkta/tasks.py \
        erpnextkta/kta_calisma_karti/doctype/calisma_karti/test_calisma_karti_unit.py
git commit -m "feat(calisma-karti): add toggle to disable auto close timed out cards"
```

---

### Task 4: Job Card senkronizasyon doğrulaması, çeviriler ve dokümantasyon

**Files:**
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`
- Modify: `docs/kta_calisma_karti_ayarlar_rehberi.md`
- Modify: `erpnextkta/www/docs/calisma-karti-ayarlar.html`
- Test: `erpnextkta/tests/test_job_card_sync.py`

- [x] **Step 1: Job Card paylaştırma regresyon testini çalıştır**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.tests.test_job_card_sync`
Expected: PASS (Tüm `distribute_completed_qty` testleri yeşil).

- [x] **Step 2: Çevirileri `en.csv` ve `de.csv` dosyalarına ekle**

`erpnextkta/translations/en.csv`:
```csv
Vardiya Kapasite Sınırını Devre Dışı Bırak,Disable Shift Capacity Limit
"İşaretlenirse operatörün vardiya içindeki toplam net süresi Maksimum Çalışma Kartı Süresi ile sınırlandırılmaz; kartlara fiili net süre yazılır.","If checked, the operator's total net time within a shift is not limited by the Maximum Work Card Duration; the actual net time is written to the cards."
Vardiya Sonu Otomatik Kapatmayı Devre Dışı Bırak,Disable Shift End Auto-Close
"İşaretlenirse vardiya bitimlerinde (16:15 ve 00:15) açık kalan kartlar sistem tarafından otomatik kapatılmaz; kart kapatma kontrolü tamamen operatörde kalır.","If checked, open cards are not automatically closed by the system at shift ends (16:15 and 00:15); closing cards remains completely with the operator."
```

`erpnextkta/translations/de.csv`:
```csv
Vardiya Kapasite Sınırını Devre Dışı Bırak,Schichtkapazitätsgrenze Deaktivieren
"İşaretlenirse operatörün vardiya içindeki toplam net süresi Maksimum Çalışma Kartı Süresi ile sınırlandırılmaz; kartlara fiili net süre yazılır.","Wenn aktiviert, wird die gesamte Nettozeit des Bedieners innerhalb einer Schicht nicht durch die maximale Arbeitskartendauer begrenzt; die tatsächliche Nettozeit wird auf die Karten geschrieben."
Vardiya Sonu Otomatik Kapatmayı Devre Dışı Bırak,Automatische Schichtende-Schließung Deaktivieren
"İşaretlenirse vardiya bitimlerinde (16:15 ve 00:15) açık kalan kartlar sistem tarafından otomatik kapatılmaz; kart kapatma kontrolü tamamen operatörde kalır.","Wenn aktiviert, werden offene Karten zum Schichtende (16:15 und 00:15) nicht automatisch vom System geschlossen; die Schließung bleibt vollständig beim Bediener."
```

- [x] **Step 3: Dokümantasyon rehberlerini güncelle**

`docs/kta_calisma_karti_ayarlar_rehberi.md` ve `erpnextkta/www/docs/calisma-karti-ayarlar.html` dosyalarında "Vardiya ve Süre Limitleri" bölümüne yeni iki ayar maddesini ve `max_kart_suresi_dk`'nın dinamik gizlenme davranışını ekle.

- [x] **Step 4: Tüm test süitini çalıştır**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_calisma_karti.doctype.calisma_karti.test_calisma_karti`
Expected: `OK` (Tüm KTA testleri yeşil, 0 hata, zengin log çıktılı).

- [x] **Step 5: Pre-commit ve nihai commit**

```bash
pre-commit run --all-files
git add erpnextkta/translations/en.csv erpnextkta/translations/de.csv \
        docs/kta_calisma_karti_ayarlar_rehberi.md erpnextkta/www/docs/calisma-karti-ayarlar.html
git commit -m "docs(calisma-karti): update translations and settings guide for shift capacity and auto close toggles"
```
