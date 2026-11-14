# Design Document: MRP Analysis Raporu Rezervasyon, Fiyat ve Tüketim İyileştirmeleri

**Tarih:** 2026-11-15  
**Durum:** Onaylandı / Uygulamaya Hazır  
**Kapsam:** 
- `erpnextkta/kta_mrp/report/mrp_analysis/mrp_analysis.py`
- `erpnextkta/kta_mrp/report/mrp_analysis/mrp_analysis.js`
- `erpnextkta/tests/test_mrp_analysis.py`

---

## 1. Intent and The Why (Gerekçe ve Amaç)
Üst yönetim, "MRP Analysis" raporunu incelerken raftaki brüt "Depo Stok" miktarının yanı sıra, bu stoğun ne kadarının açık iş emirlerine veya siparişlere rezerve edildiğini ve gerçekten ne kadar serbest hammadde kaldığını tek bakışta görmek istemektedir. 

Ayrıca mevcut raporda tespit edilen ve çözüme kavuşturulacak konular:
1. **Fiyat Standardizasyonu:** Varsayılan tedarikçi fiyatı yerine rastgele son fiyatın gelmesini önlemek için kullanıcıyı her seferinde filtre işaretleme zahmetinden kurtarmak ve sözleşmeli varsayılan tedarikçi fiyatını kalıcı standart yapmak.
2. **Sıfır Tüketim Sızıntısının Kapatılması:** "Sıfır Tüketimi Göster" seçildiğinde depodaki montajı bitmiş ürünlerin (`ÜRÜN`), makinelerin bakım parçalarının (`BAKIM`) veya ambalajların (`AMBALAJ`) hammadde raporuna sızmasını engellemek; sadece gerçek `HAMMADDE` ve faz-out olmuş ölü stok (`OBS*`) kalemlerini dahil etmek.
3. **Alt Toplam Tamamlama:** Alt `TOPLAM` satırında eksik olan depo stoğu, rezervasyon miktarı, serbest stok ve bakiye değerlerini tamamlamak.
4. **Başlık Netliği:** Para birimi karışıklığını gidermek için `Bakiye Değeri` kolonunu `Bakiye Değeri (TL)` olarak netleştirmek.

---

## 2. Goals & Non-Goals

### Goals (Hedefler)
1. **Rezerve & Serbest Stok Kolonları:** `Depo Stok` kolonunun hemen sağına:
   * **Rezerve Miktar (`rezerve_stok`):** Float, genişlik 110 px.
   * **Serbest Stok (`serbest_stok`):** Float, genişlik 110 px.
   Hesaplama: `warehouse_type = 'Kullanılabilir Stok'` olan depolarda:
   $$\text{rezerve\_stok} = \sum (\text{reserved\_qty\_for\_production} + \text{reserved\_qty} + \text{reserved\_qty\_for\_sub\_contract})$$
   $$\text{serbest\_stok} = \text{depo\_stok} - \text{rezerve\_stok}$$
2. **Varsayılan Tedarikçi Fiyat Standardizasyonu:**
   * `mrp_analysis.js` üzerindeki `fiyat_varsayilan_tedarikci` checkbox filtresi kaldırılacak.
   * `mrp_analysis.py` içinde fiyat sorgusu daima `Item Default` tablosundaki `default_supplier`'ın en güncel satın alma fiyatını getirecek.
3. **Sıfır Tüketim Filtresi İyileştirmesi (`get_zero_consumption_items`):**
   * `sifir_tuketimi_goster` seçildiğinde `custom_ara_malzeme_grubu = 'HAMMADDE' OR custom_ara_malzeme_grubu LIKE 'OBS%%'` filtresi uygulanacak (`item.disabled = 0` korumasıyla).
   * Böylece `BAKIM`, `AMBALAJ`, `ÜRÜN` ve `YARIMAMUL` elenecek; `feat/mrp-modular-refactor` ile tam kod uyumu sağlanacak.
4. **Alt `TOPLAM` Satırı Tamamlama:**
   * En alttaki `TOPLAM` satırında eksik olan `depo_stok`, `rezerve_stok`, `serbest_stok` ve `bakiye_degeri` alanları hesaplanıp yazılacak.
5. **Kolon Başlığı Netliği:**
   * `Bakiye Değeri` kolon başlığı `Bakiye Değeri (TL)` olarak güncellenecek.

### Non-Goals (Kapsam Dışı)
* Raporun altındaki özet kartlarının (`report_summary`) yapısını değiştirmek (aynen korunacaktır).
* Renkli biçimlendirme yapmak (standart float formatında tutulacaktır).

---

## 3. Detailed Changes (Detaylı Tasarım)

### 3.1. `mrp_analysis.py`

#### A. Sıfır Tüketim Fonksiyonu (`get_zero_consumption_items`)
```python
def get_zero_consumption_items():
	"""Kullanılabilir stokta olan ve ara malzeme grubu HAMMADDE ya da OBS ile başlayan kalemler."""
	return frappe.db.sql_list(
		"""
		SELECT DISTINCT bin.item_code
		FROM `tabBin` bin
		INNER JOIN `tabWarehouse` wh ON bin.warehouse = wh.name
		INNER JOIN `tabItem` item ON item.name = bin.item_code
		WHERE wh.warehouse_type = 'Kullanılabilir Stok'
		  AND bin.actual_qty > 0
		  AND item.disabled = 0
		  AND (item.custom_ara_malzeme_grubu = 'HAMMADDE' OR item.custom_ara_malzeme_grubu LIKE 'OBS%%')
		"""
	)
```

`execute` içinde çağrılışı:
```python
if filter_sifir_tuketimi_goster:
    for item_code in get_zero_consumption_items():
        if item_code not in material_cg_totals:
            raw_materials.append(item_code)
            material_all_totals[item_code] = 0
```

#### B. Standart Fiyat Çekimi (Daima Varsayılan Tedarikçi)
```python
price_data = frappe.db.sql(
    """
    SELECT ip.item_code, ip.price_list_rate, ip.currency, ip.supplier
    FROM `tabItem Price` ip
    INNER JOIN (
        SELECT item_code, supplier, MAX(creation) as max_creation
        FROM `tabItem Price`
        WHERE item_code IN %s AND buying = 1 AND supplier IS NOT NULL AND supplier != ''
        GROUP BY item_code, supplier
    ) latest ON ip.item_code = latest.item_code AND ip.supplier = latest.supplier AND ip.creation = latest.max_creation
    WHERE ip.buying = 1
""",
    [tuple(raw_materials)],
    as_dict=True,
)
for p in price_data:
    def_sup = default_supplier_map.get(p.item_code)
    if def_sup and def_sup == p.supplier:
        price_map[p.item_code] = p.price_list_rate
        currency_map[p.item_code] = p.currency
```

#### C. Stok ve Rezervasyon Sorgusu
```python
stock_data = frappe.db.sql(
    """
    SELECT 
        bin.item_code, 
        SUM(bin.actual_qty) as total_qty, 
        SUM(bin.stock_value) as total_value,
        SUM(
            COALESCE(bin.reserved_qty_for_production, 0) + 
            COALESCE(bin.reserved_qty, 0) + 
            COALESCE(bin.reserved_qty_for_sub_contract, 0)
        ) as total_reserved
    FROM `tabBin` bin
    INNER JOIN `tabWarehouse` wh ON bin.warehouse = wh.name
    WHERE bin.item_code IN %s
      AND wh.warehouse_type = 'Kullanılabilir Stok'
    GROUP BY bin.item_code
""",
    [tuple(raw_materials)],
    as_dict=True,
)
for d in stock_data:
    stock_map[d.item_code] = d.total_qty or 0
    stock_value_map[d.item_code] = d.total_value or 0
    reserved_map[d.item_code] = d.total_reserved or 0
```

#### D. Kolon Tanımları ve Satır Hesapları
```python
columns = [
    {"label": "Hammadde Kodu", "fieldname": "hammadde_kodu", "fieldtype": "Link", "options": "Item", "width": 130},
    {"label": "Grup", "fieldname": "grup", "fieldtype": "Data", "width": 140},
    {"label": "Hammadde Adı", "fieldname": "hammadde_adi", "fieldtype": "Data", "width": 200},
    {"label": "Varsayılan Tedarikçi", "fieldname": "varsayilan_tedarikci", "fieldtype": "Link", "options": "Supplier", "width": 180},
    {"label": "Fiyat", "fieldname": "fiyat", "fieldtype": "Float", "width": 100},
    {"label": "Para Birimi", "fieldname": "para_birimi", "fieldtype": "Data", "width": 80},
    {"label": "Depo Stok", "fieldname": "depo_stok", "fieldtype": "Float", "width": 100},
    {"label": "Rezerve Miktar", "fieldname": "rezerve_stok", "fieldtype": "Float", "width": 110},
    {"label": "Serbest Stok", "fieldname": "serbest_stok", "fieldtype": "Float", "width": 110},
    {"label": "Bakiye Değeri (TL)", "fieldname": "bakiye_degeri", "fieldtype": "Float", "width": 130},
    {"label": "Müşteri Grubu Dağılımı", "fieldname": "musteri_grubu_dagilimi", "fieldtype": "Data", "width": 220},
    {"label": "Ara Malzeme Grubu", "fieldname": "ara_malzeme_grubu", "fieldtype": "Data", "width": 140},
]
```

Her satır için:
```python
depo_stok = stock_map.get(hammadde, 0)
rezerve_stok = reserved_map.get(hammadde, 0)
serbest_stok = round(depo_stok - rezerve_stok, 2)
bakiye_degeri = stock_value_map.get(hammadde, 0)

row = {
    ...
    "depo_stok": depo_stok,
    "rezerve_stok": rezerve_stok,
    "serbest_stok": serbest_stok,
    "bakiye_degeri": bakiye_degeri,
    ...
}
column_totals["depo_stok"] += depo_stok
column_totals["rezerve_stok"] += rezerve_stok
column_totals["serbest_stok"] += serbest_stok
column_totals["bakiye_degeri"] += bakiye_degeri
```

Toplam satırı için:
```python
total_row["depo_stok"] = round(column_totals["depo_stok"], 2)
total_row["rezerve_stok"] = round(column_totals["rezerve_stok"], 2)
total_row["serbest_stok"] = round(column_totals["serbest_stok"], 2)
total_row["bakiye_degeri"] = round(column_totals["bakiye_degeri"], 2)
```

### 3.2. `mrp_analysis.js`
`fiyat_varsayilan_tedarikci` filtre tanımı kaldırılacak.

---

## 4. Test Stratejisi
* Testler `erpnextkta/tests/test_mrp_analysis.py` altında konumlandırılacak. Böylece `feat/mrp-modular-refactor` branch'inin `erpnextkta/kta_mrp/report/mrp_analysis/test_mrp_analysis.py` dosyasıyla rebase çakışması engellenecek.
* Testler:
  1. `rezerve_stok`, `serbest_stok` kolonları ve `Bakiye Değeri (TL)` başlığının varlığı,
  2. Her satırda `serbest_stok == round(depo_stok - rezerve_stok, 2)` eşitliği,
  3. `TOPLAM` satırındaki toplamların doğrulanması,
  4. `get_zero_consumption_items` fonksiyonunun sadece `HAMMADDE` ve `OBS*` gruplarını getirmesi, bakım veya bitmiş ürün getirmemesi,
  5. `10023999` için varsayılan tedarikçi (`default_supplier`) fiyat ve para biriminin gelmesi.
