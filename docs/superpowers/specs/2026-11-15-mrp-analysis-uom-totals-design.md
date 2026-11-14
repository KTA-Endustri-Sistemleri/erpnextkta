# Design Document: MRP Analysis Raporunda Ölçü Birimi (UOM) Bazlı Alt Toplam Ayrımı

**Tarih:** 2026-11-15  
**Durum:** Taslak / Kullanıcı Onayına Sunuldu  
**Kapsam:**
- `erpnextkta/kta_mrp/report/mrp_analysis/mrp_analysis.py`
- `erpnextkta/kta_mrp/report/mrp_analysis/mrp_analysis.js`
- `erpnextkta/tests/test_mrp_analysis.py`

---

## 1. Intent and The Why (Gerekçe ve Amaç)
MRP Analiz raporunda kablo/makaron gibi metrajlı malzemeler (`Metre`), terminal/soket gibi sayımlı malzemeler (`Adet`) ve kimyasal/reçine gibi tartımlı malzemeler (`kg`, `Litre`) bir arada listelenmektedir.

Mevcut alt toplam satırında:
$$\sum (\text{Metre}) + \sum (\text{Adet}) + \sum (\text{kg}) \longrightarrow \text{Tek Bir Toplam}$$
şeklinde fiziksel olarak anlamsız (elma ile armut toplanarak elde edilen) bir havuz toplamı oluşmaktadır. 

Bu tasarımın amacı:
1. Her satıra kalemin ölçü birimini gösteren **Birim (`stock_uom`)** sütununu eklemek.
2. Alt toplamı, rapordaki aktif birimlere göre (`TOPLAM (Metre)`, `TOPLAM (Adet)`, `TOPLAM (kg)` vb.) ayrı satırlar halinde sunarak planlamacının fiziksel miktarları doğru okumasını sağlamak.
3. Finansal bakiye değerini genel toplam olarak korumak.

---

## 2. Goals & Non-Goals

### Goals (Hedefler)
1. **Birim Kolonu:** `Hammadde Adı` ile `Varsayılan Tedarikçi` kolonları arasına `Birim` (`stock_uom`) kolonu eklenmesi.
2. **Birim Bazlı Alt Toplam Satırları:**
   - Raporda yer alan satırların ölçü birimleri (örneğin `Metre`, `Adet`, `kg`) tespit edilir.
   - Her birim için ayrı bir toplam satırı (`TOPLAM (Metre)`, `TOPLAM (Adet)` vb.) oluşturulur.
   - Bu satırlarda `depo_stok`, `rezerve_stok`, `serbest_stok`, müşteri grupları (`ARC`, `BTT-SA` vb.) ve `genel_toplam` yalnızca o birime ait kalemlerin toplamını içerir.
3. **Genel Bakiye Değeri Satırı:**
   - Bütün kalemlerin para biriminden bağımsız ortak parasal büyüklüğü olan `Bakiye Değeri (TL)`, en altta yer alan `GENEL BAKİYE DEĞERİ (TL)` satırında konsolide olarak gösterilir.
4. **JS Biçimlendirme Uyumu:**
   - `mrp_analysis.js` içindeki satır formatlayıcı, `is_total_row == 1` olan tüm birim toplamı satırlarını ve genel değer satırını kalın (`font-weight: bold; background-color: #f8f9fa;`) olarak render eder.
5. **Otomatik Birim Testleri:**
   - `test_mrp_analysis.py` içine farklı birimlerdeki (Metre ve Adet) kalemlerin alt toplamlarda doğru satırlara ayrıldığını doğrulayan birim test eklenmesi.

### Non-Goals (Kapsam Dışı)
- Müşteri grubu sütunlarına para birimi cinsinden değerler eklemek (fiziksel miktar planlaması önceliklidir).
- Üst filtre paneline Birim filtresi eklemek (kullanıcı Yaklaşım 1'i seçmiştir; filtreleme olmadan tüm birimlerin tek ekranda ayrılması esastır).

---

## 3. Approaches (Değerlendirilen Yaklaşımlar)

1. **Yaklaşım 1 (Seçilen): Birim Kolonu + Alt Toplamda Birim Bazlı Çoklu Satırlar:**
   - *Tanım:* Her satıra `Birim` kolonu eklenir; alt toplam bloğu her ölçü birimi için ayrı satır (`TOPLAM (Metre)`, `TOPLAM (Adet)`...) ve en altta genel bakiye değeri satırı üretir.
   - *Seçilme Nedeni:* Filtre değiştirmeden tek bakışta tüm fabrikanın kablo metrajı, terminal adedi ve toplam bütçesi net olarak ayrıştırılır. Kullanıcı tarafından onaylandı.
2. **Yaklaşım 2: Filtrelere "Birim (UOM)" Eklemek:**
   - *Tanım:* Kullanıcı üstten birim filtreler, alt toplam sadece filtrelenen birimi verir.
   - *Neden Seçilmedi:* Bütünleşik fabrika analizinde genel bakışta birim ayrımı yapılamaz; her birim için filtre değiştirip raporu yeniden çalıştırmak gerekir.
3. **Yaklaşım 3: Hibrit Model:**
   - *Tanım:* Hem filtre hem çoklu toplam satırları.
   - *Neden Seçilmedi:* Mevcut ihtiyaç için gereksiz filtre karmaşıklığı yaratır.

---

## 4. Detailed Specification (Teknik Tasarım)

### 4.1. `mrp_analysis.py` Değişiklikleri

1. **`Item` Sorgusu:**
   `fields` listesine `stock_uom` eklenir:
   ```python
   items = frappe.db.get_all(
       "Item",
       filters={"name": ["in", raw_materials]},
       fields=[
           "name",
           "item_name",
           "item_group",
           "stock_uom",
           "custom_ara_malzeme_grubu",
           "custom_musteri_grubu",
       ],
   )
   ```

2. **Kolon Tanımı:**
   ```python
   # "Hammadde Adı" hemen sağına:
   {"label": _("Birim"), "fieldname": "birim", "fieldtype": "Data", "width": 80},
   ```

3. **Veri Satırları (`row`):**
   ```python
   uom = item_info.stock_uom if item_info and item_info.stock_uom else _("Adet")
   row["birim"] = uom
   ```

4. **Birim Bazlı Toplam Toplayıcıları:**
   ```python
   uom_totals = defaultdict(lambda: defaultdict(float))
   total_bakiye_degeri = 0.0

   # Satır döngüsü içinde:
   uom_totals[uom]["depo_stok"] += depo_stok
   uom_totals[uom]["rezerve_stok"] += rezerve_stok
   uom_totals[uom]["serbest_stok"] += serbest_stok
   total_bakiye_degeri += bakiye_degeri

   for cg in cg_names:
       fn = cg_fieldnames[cg]
       uom_totals[uom][fn] += cg_values[fn]

   uom_totals[uom]["genel_toplam"] += genel_toplam
   uom_totals[uom]["toplam_tuketim"] += toplam_tuketim
   ```

5. **Alt Toplam Satırlarının Üretilmesi:**
   ```python
   # Öncelikli sıralama: Metre ve Adet en başta, ardından alfabetik diğer birimler
   sorted_uoms = sorted(uom_totals.keys(), key=lambda u: (0 if u == "Metre" else 1 if u == "Adet" else 2, u))

   for u in sorted_uoms:
       t_depo = round(uom_totals[u]["depo_stok"], 2)
       t_rezerve = round(uom_totals[u]["rezerve_stok"], 2)
       t_serbest = round(t_depo - t_rezerve, 2)
       t_genel = round(uom_totals[u]["genel_toplam"], 2)
       t_tuketim = round(uom_totals[u]["toplam_tuketim"], 2)

       uom_row = {
           "hammadde_kodu": f"{_('TOPLAM')} ({u})",
           "birim": u,
           "is_total_row": 1,
           "depo_stok": t_depo,
           "rezerve_stok": t_rezerve,
           "serbest_stok": t_serbest,
           "bakiye_degeri": None,
           "genel_toplam": t_genel,
           "toplam_tuketim": t_tuketim,
           "fark_oran": round(((t_tuketim - t_genel) / t_genel * 100), 6) if t_genel > 0 else 0,
       }
       for cg in cg_names:
           fn = cg_fieldnames[cg]
           uom_row[fn] = round(uom_totals[u][fn], 2)
       data.append(uom_row)

   # En alt genel bakiye değeri satırı:
   data.append({
       "hammadde_kodu": _("GENEL BAKİYE DEĞERİ"),
       "is_total_row": 1,
       "bakiye_degeri": round(total_bakiye_degeri, 2),
   })
   ```

### 4.2. `mrp_analysis.js` Değişiklikleri
- `formatter(value, row, column, data, default_formatter)` içinde `data.is_total_row` kontrolü halihazırda bulunmaktadır. Tüm `is_total_row` satırları kalın ve vurgulu stil ile render edilecektir.

### 4.3. `test_mrp_analysis.py` Test Kapsamı
- `TestMrpAnalysisReservationsAndFilters` sınıfına:
  - `test_uom_column_exists_and_populated`: Kolon yapısında `birim` alanının varlığı ve satırlarda `Nos`/`Metre`/`Adet` doluluğu.
  - `test_uom_grouped_total_rows`: Alt toplamda birim bazlı satırların (`TOPLAM (Nos)` / `TOPLAM (Metre)` vb.) üretildiği, miktarların birim bazında ayrıştığı ve `GENEL BAKİYE DEĞERİ` satırının doğruluğu.

---

## 5. Doğrulama ve Kabul Kriterleri
1. `bench run-tests --app erpnextkta --module erpnextkta.tests.test_mrp_analysis` tüm testlerden geçmelidir.
2. `bench build --app erpnextkta --production` hatasız derlenmelidir.
3. Rapor arayüzünde kablo satırları (`Metre`) ile terminal satırları (`Adet`) alt toplamda birbirine karışmamalıdır.
