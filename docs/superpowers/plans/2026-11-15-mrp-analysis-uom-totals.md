# MRP Analysis Ölçü Birimi (UOM) Bazlı Alt Toplam Ayrımı Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MRP Analiz raporuna `Birim` (`stock_uom`) kolonu eklemek ve alt toplam satırını ölçü birimlerine göre (`TOPLAM (Metre)`, `TOPLAM (Adet)` vb.) gruplayarak farklı birimlerin birbirine toplanmasını engellemek; parasal bakiye değerini genel toplam olarak sunmak.

**Architecture:** 
1. `mrp_analysis.py` içinde `tabItem` sorgusundan `stock_uom` çekilerek kolonlara ve her veri satırına `birim` alanı olarak eklenir.
2. Sütun toplamları tek bir havuz yerine ölçü birimi bazında `uom_totals = defaultdict(lambda: defaultdict(float))` sözlüğünde toplanır.
3. Raporun altındaki tek satırlık `TOPLAM` yerine veride bulunan her birim için ayrı bir alt toplam satırı (`TOPLAM (Metre)`, `TOPLAM (Adet)` vb.) oluşturulur; tüm kalemlerin toplam parasal büyüklüğü ise en altta tek bir `GENEL BAKİYE DEĞERİ` satırı olarak eklenir.
4. `mrp_analysis.js` içindeki formatter katmanı, `is_total_row: 1` olan tüm satırları kalınlaştırarak görsel vurguyu sağlar.

**Tech Stack:** Python, Frappe Framework v15, ERPNext, JavaScript, esbuild

**Spec:** [docs/superpowers/specs/2026-11-15-mrp-analysis-uom-totals-design.md](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/docs/superpowers/specs/2026-11-15-mrp-analysis-uom-totals-design.md)

## Global Constraints
- Target branch is `main`. PR target is PR #178.
- Never use `yarn build` directly; always run `bench build --app erpnextkta --production`.
- PR descriptions and commit messages must strictly follow Conventional Commits ($\le 72$ chars) and NEVER include commercial vendor names (e.g. Türk Prysmian) or confidential prices.
- Mandatory PR template from `.github/PULL_REQUEST_TEMPLATE.md` must be used.

## Review Focus
1. **Birim Eksikliği:** Eğer bir `Item` kartında `stock_uom` boş veya tanımsızsa, çökme olmadan `_("Adet")` varsayılanına düşmelidir.
2. **Yatay ve Dikey Toplam Tutarlılığı:** `TOPLAM (Metre)` satırında müşteri gruplarının yatay toplamı `Genel Toplam` sütununa tam eşit olmalıdır.
3. **Depo/Rezerve/Serbest Denge:** Her birim toplam satırında `serbest_stok == depo_stok - rezerve_stok` eşitliği kuruşu kuruşuna korunmalıdır.
4. **Tek Birim Durumu:** Filtreler sonucu yalnızca tek bir birim (örn. sadece Metre) kaldığında yalnızca o birimin toplam satırı ve genel değer satırı üretilmelidir; boş birim satırları oluşmamalıdır.
5. **Görsel Temizlik:** `is_total_row` satırlarında hücre içinde ham HTML etiketleri (`<b>`, `<span>`) kullanılmamalı, kalınlaştırma JS formatter katmanında yapılmalıdır.

---

### Task 1: Birim (`stock_uom`) Kolonu ve Veri Eşlemesi

**Files:**
- Modify: `erpnextkta/kta_mrp/report/mrp_analysis/mrp_analysis.py:90-160`
- Test: `erpnextkta/tests/test_mrp_analysis.py`

- [x] **Step 1.1: Birim kolonu ve satır eşleme testini yaz**
  `erpnextkta/tests/test_mrp_analysis.py` içine `test_birim_column_and_item_uom_mapping` testini ekle:
  - Kolon listesinde `fieldname == "birim"` olan bir kolonun var olduğunu ve `label == "Birim"` olduğunu doğrula.
  - Veri satırlarında `row.get("birim")` alanının boş olmadığını doğrula.

- [x] **Step 1.2: Testi çalıştır ve başarısız olduğunu gör**
  `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.tests.test_mrp_analysis`
  *Beklenen sonuç:* `AssertionError: 'birim' kolonu bulunamadı`.

- [x] **Step 1.3: `mrp_analysis.py` içinde `stock_uom` alanını çek ve kolona ekle**
  - `Item` alan listesine `"stock_uom"` ekle.
  - `columns` listesinde `hammadde_adi` hemen sağına:
    `{"label": _("Birim"), "fieldname": "birim", "fieldtype": "Data", "width": 80}` ekle.
  - Veri satırı oluşturulurken `row["birim"] = item_info.stock_uom if item_info and item_info.stock_uom else _("Adet")` ata.

- [x] **Step 1.4: Testi çalıştır ve geçtiğini doğrula**
  Testlerin başarıyla geçtiğini (`OK`) doğrula.

---

### Task 2: Birim Bazlı Alt Toplam Satırları ve Genel Bakiye Değeri

**Files:**
- Modify: `erpnextkta/kta_mrp/report/mrp_analysis/mrp_analysis.py:200-285`
- Test: `erpnextkta/tests/test_mrp_analysis.py`

- [x] **Step 2.1: Birim bazlı alt toplam testini yaz**
  `erpnextkta/tests/test_mrp_analysis.py` içine `test_uom_grouped_subtotals_and_grand_value` testini ekle:
  - Raporda tek bir `TOPLAM` satırı yerine `TOPLAM (<Birim>)` formatında satırlar olduğunu doğrula.
  - En altta `GENEL BAKİYE DEĞERİ` satırının varlığını ve `bakiye_degeri` alanının pozitif bir float olduğunu doğrula.
  - Her birim alt toplam satırında `serbest_stok == round(depo_stok - rezerve_stok, 2)` olduğunu doğrula.

- [x] **Step 2.2: Testi çalıştır ve başarısız olduğunu gör**
  *Beklenen sonuç:* Mevcut kod tek bir `TOPLAM` satırı döndüğü için test patlar.

- [x] **Step 2.3: `mrp_analysis.py` içinde birim gruplu alt toplamları oluştur**
  - `uom_totals = defaultdict(lambda: defaultdict(float))` tanımla.
  - `total_bakiye_degeri = 0.0` tanımla.
  - Satır döngüsü içinde ilgili `uom` için `depo_stok`, `rezerve_stok`, `serbest_stok`, müşteri grubu değerleri, `genel_toplam` ve `toplam_tuketim` topla.
  - `total_bakiye_degeri += bakiye_degeri` olarak kümülatif topla.
  - Birimleri sırala (`Metre` ve `Adet` öncelikli):
    `sorted_uoms = sorted(uom_totals.keys(), key=lambda u: (0 if u == "Metre" else 1 if u == "Adet" else 2, u))`
  - Her birim için:
    ```python
    uom_row = {
        "hammadde_kodu": f"{_('TOPLAM')} ({u})",
        "birim": u,
        "is_total_row": 1,
        "depo_stok": t_depo,
        "rezerve_stok": t_rezerve,
        "serbest_stok": round(t_depo - t_rezerve, 2),
        "genel_toplam": t_genel,
        "toplam_tuketim": t_tuketim,
        "fark_oran": round(((t_tuketim - t_genel) / t_genel * 100), 6) if t_genel > 0 else 0,
    }
    for cg in cg_names:
        uom_row[cg_fieldnames[cg]] = round(uom_totals[u][cg_fieldnames[cg]], 2)
    data.append(uom_row)
    ```
  - En alta genel değer satırını ekle:
    ```python
    data.append({
        "hammadde_kodu": _("GENEL BAKİYE DEĞERİ"),
        "is_total_row": 1,
        "bakiye_degeri": round(total_bakiye_degeri, 2),
    })
    ```

- [x] **Step 2.4: Testi çalıştır ve geçtiğini doğrula**
  Testlerin başarıyla geçtiğini (`OK`) doğrula.

---

### Task 3: JS Formatter Uyumu ve Frontend Derleme

**Files:**
- Modify: `erpnextkta/kta_mrp/report/mrp_analysis/mrp_analysis.js`

- [x] **Step 3.1: `mrp_analysis.js` içindeki formatter kontrolünü doğrula**
  `data.is_total_row` olduğunda satırın kalın font ve uygun arka plan rengiyle render edildiğini teyit et.

- [x] **Step 3.2: Production frontend build çalıştır**
  `docker exec -u frappe erpnext-dev-frappe-1 bench build --app erpnextkta --production`
  Hatasız derlendiğini doğrula.

---

### Task 4: Doğrulama, Git Commit ve PR Güncellemesi

**Files:**
- Modify: `erpnextkta/tests/test_mrp_analysis.py` (varsa kalan assert'ler)
- PR: `#178`

- [x] **Step 4.1: Tüm `test_mrp_analysis` test süitini çalıştır**
  `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.tests.test_mrp_analysis`
  Tüm testlerin geçtiğinden emin ol.

- [x] **Step 4.2: Conventional Commits kuralına uygun commit oluştur**
  Commit mesajı: `feat(mrp): add uom column and group subtotal rows by uom`
  `origin/feat/mrp-analysis-factory-reservations` dalına pushla.

- [x] **Step 4.3: PR #178 açıklamasını güncelle ve kullanıcıya sun**
  `.github/PULL_REQUEST_TEMPLATE.md` şablonuna uygun kopya-yapıştır yapılabilir Markdown bloğu üret.
