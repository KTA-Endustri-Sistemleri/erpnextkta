# Hat İkmal Toplama (PDA) UX Yenileme, Katı FIFO Sapma Onayı ve Eksik Ürün RBAC Tasarımı

**Tarih:** 2026-11-26
**Durum:** Implemented — Kalite Kapısı Doğrulandı
**Boyut:** Orta / Kapsamlı Özellik & UX İyileştirmesi
**Kapsam:** `KTA Line Replenishment Item`, `line_replenishment_picking.py`, `line_replenishment_service.py`, `erpnextkta/public/line-replenishment-pda/**`, `erpnextkta/public/pda-hub/views/PickingModuleView.vue`, Clean-CI Testleri, `/docs/` & `translations/`

---

## 1. Amaç ve Problem Tanımı

Mevcut `/pda` Hat İkmal Toplama ekranı (`PickingModuleView.vue`, `PickingItemCard.vue`) ve legacy Desk sayfası (`PdaApp.vue`), partili (`1 Kutu = 1 Parti`) malzeme toplamada hem operatör ergonomisi hem de stok bütünlüğü açısından 4 kritik probleme sahiptir:

1. **Partili Kolilerde Manuel Miktar ve Checkbox Riski:**
   - Mevcut `PickingItemCard.vue` her kartta manuel `Toplandı` onay kutusu, `- / +` miktar artır-azalt düğmeleri, elle sayı girişi, `⚡ Tümünü Al` butonu, 4 hücreli tekrarlı özet tablosu ve satır içi ilerleme çubuğu göstermektedir.
   - Bu kontroller operatörün fiziksel koli barkodunu okutmadan satırı tamamlanmış işaretlemesine veya `1 Kutu = 1 Parti` bütünlüğünü bozacak şekilde kısmi/hatalı miktar girmesine açık kapı bırakmaktadır.
   - Ayrıca yüksek kart gövdesi yüzünden PDA ekranına aynı anda yalnızca 1–2 kart sığmakta, depo yürüyüşü yavaşlamaktadır.
2. **Kısmi Seçimde Sessiz Tam Transfer Hatası:**
   - `PickingModuleView.vue` içinde `canCompleteTransfer` yalnızca `pickedItemsCount > 0` kontrolü yapmaktadır. Operatör tek bir kalem okutup `Transferi Tamamla`ya bastığında backend `complete_line_replenishment_picking()` `order.items` döngüsünde gönderilmeyen diğer tüm satırları da `picked_qty = deficit_qty` varsayarak `Stock Entry`'ye eklemektedir.
3. **Çift Okutmada Miktar İkiye Katlama Hatası:**
   - `PickingModuleView.vue` aynı koli barkodu ikinci kez okutulduğunda `picked_qty = row.picked_qty + scanQty` hesabı yapmakta, aynı kapalı koliyi çift saymaktadır.
4. **Salt Ürün Barkodu İle Parti Atlatma & Canlı Bakiye Eksikliği:**
   - `PdaApp.vue` parti takipli ürünlerde salt `item_code` okutulmasına izin vermektedir.
   - `resolve_scanned_barcode()` ise okutulan partinin canlı raf bilgisini (`warehouse`) ve güncel tam koli bakiyesini döndürmediği için farklı raftan alternatif bir parti okutulduğunda gerçek kaynak raf (`s_warehouse`) ve tam koli miktarı güvenli biçimde işlenememektedir.

---

## 2. Hedefler, Kapsam Dışı ve Anti-Hedefler

### Hedefler
- **Yaklaşım A — Akıllı Yürüyüş Listesi + Katlanan Kartlar:** Bekleyen kalemleri raf yürüyüş sırasına (doğal alfanümerik sıralama: `W1A-01-01 → W1A-02-01 → W1A-10-01`) göre dizmek; okutulan ve atlanan satırları tek satırlık kompakt yeşil/soluk satırlara katlamak.
- **Partili Kalemde Sıfır Manuel Giriş:** `has_batch_no == 1` (veya `suggested_batch_no` atanmış) satırlarda manuel `Toplandı` checkbox, `- / +` stepper, miktar inputu, `Tümünü Al`, 4 hücreli grid ve satır içi progress bar kaldırılır; toplama yalnızca fiziksel koli/SUT/parti barkodu okutularak yapılır. Partisiz (`has_batch_no == 0`) ürün istisnası için hafif miktar/onay kontrolü korunur.
- **Katı FIFO + Tek Tıkla Onaylı FIFO Sapma Modalı:**
  - Atanan `suggested_batch_no` okutulursa satır anında sessizce onaylanır.
  - Aynı ürünün farklı partisi okutulursa (`Stock User`, `KTA PDA Stock User`, `Stock Manager`, `System Manager`) otomatik açılan **FIFO Sapma Uyarı Modalı** ile operatöre önerilen vs. okutulan (parti, gerçek raf, gerçek tam koli bakiyesi) gösterilir ve tek tıkla onaylanır.
  - Onaylanan FIFO sapmaları otomatik olarak **`Stock Entry.remarks`** ve **`KTA Line Replenishment Order.remarks`** alanlarına yapısal denetim kaydı olarak işlenir.
- **Eksik Ürün Atlama (RBAC) + Otomatik Yeniden Açığa Düşme:**
  - Fiziksel olarak rafta ve diğer raflarda hiç bulunmayan bir kalemi yalnızca **`Stock Manager` veya `System Manager`** yetkisine sahip kullanıcı **`Atla`** aksiyonu ile atlayabilir (sunucu tarafı `PermissionError` korumalı).
  - Atlanan satır `Stock Entry`'ye eklenmez ve notlara yazılır; emir `Completed` (en az 1 koli toplandıysa) veya `Cancelled` (tüm satırlar atlandıysa — boş `Stock Entry` oluşturulmaz) durumuna geçtiğinde `_get_drafts_by_item()` yalnızca `docstatus = 0 AND status = 'Draft'` emirleri açık hesabından düştüğü için atlanan kalemler bir sonraki hat ikmal listesinde otomatik olarak yeniden açığa (`deficit`) düşer.
- **Paylaşımlı Frontend Mimarisi:** Hem `/pda` (`PickingModuleView.vue`) hem legacy Desk sayfası `/app/line-replenishment-picking` (`PdaApp.vue`) ortak composable (`useLineReplenishmentPicking.ts`) ve ortak alt bileşenleri kullanır; her `.vue` dosyası `<= 500` satır kuralına uyar.
- **Clean-CI Uyumu:** Tüm backend testleri boş `test_site` üzerinde sıfır hardcoded şirket/depo varsayımıyla çalışır; frontend Vitest + build + Ruff + docs/i18n senkronizasyonu tam yapılır.

### Kapsam Dışı ve Anti-Hedefler (Kritik Görsel ve Mimari Kilit)
- **Mevcut `/pda` Kabuğu ve Renk Paleti Kesinlikle Değiştirilmeyecektir:**
  - `PdaHubApp.vue`, `.pda-topbar` (`☰ Menü`, `📱 KTA PDA`, operatör rozeti, hareketsizlik sayacı, kırmızı `Devret ↩` butonu), `.pda-subbar` (`← Geri | Stock › Hat İkmal Toplama`) ve `erpnextkta/public/pda-hub/pda-hub.bundle.css` içindeki light/dark CSS değişkenleri (`--bg-color`, `--card-bg`, `--control-bg`, `--text-color`, `--text-muted`, `--border-color`, `--pda-primary`, `--pda-success`, `--pda-danger`, `--pda-surface-alt`) **aynen korunur**.
  - Stitch konseptinde üretilen koyu lacivert üst bar ve alt kısımdaki ikinci `ONAYLA [ENT]` çubuğu **uygulanmaz**. Altta yalnızca tek bir yapışkan `TransferFooter.vue` aksiyon butonu yer alır.
- **Sunucu Tarafı Ara-Taslak (Mid-Pick Autosave) Kapsam Dışıdır:** Operatörün emir içindeki anlık okutmaları istemci state'inde tutulur; tamamlama/iptal aksiyonu ile tek atomik sunucu isteğinde işlenir (sayfa yenilenirse mevcut Draft emri baştan okutulur).
- **Yeni DocType Oluşturulmaz:** Yalnızca mevcut `KTA Line Replenishment Item` alt tablosuna 3 İngilizce alan eklenir.
- **Ticari/Gizli Bilgi Kısıtı:** Denetim notlarında (`remarks`), testlerde ve dokümantasyonda asla gerçek birim fiyat, maliyet veya tedarikçi/müşteri firma unvanı bulunmaz.

---

## 3. Değerlendirilen Tasarım Yaklaşımları

| Yaklaşım | Özet | Avantajlar | Dezavantajlar | Karar |
|---|---|---|---|---|
| **Yaklaşım A (Seçildi)** | **Akıllı Yürüyüş Listesi + Katlanan Kartlar** (Bekleyen / Toplanan / Atlanan sekmeleri, raf yürüyüş sırası) | Operatör aynı koridordaki sonraki 3–5 rafı tek bakışta görür; okutulan kartlar tek satıra katlandığı için ekran şişmez; hem PDA hem tabletlerde hızlı | Ek sekme şeridi eklenir (~36px yükseklik) | **Seçildi** |
| **Yaklaşım B** | **Tek Kart Odaklı Adım Adım Görünüm** | Tek satırda maksimum odak | Koridorda peş peşe duran kolileri önceden görmeyi engeller; rastgele sırada okutulan kolide kart zıplaması yaratır | Elendi |

---

## 4. Veri Modeli ve Backend Tasarımı

### 4.1 `KTA Line Replenishment Item` Şema Değişikliği
Dosya: `erpnextkta/kta_stock/doctype/kta_line_replenishment_item/kta_line_replenishment_item.json`

Mevcut alanların sonuna AGENTS.md Section 5 (strictly English, lowercase underscore) kuralına uygun 3 yeni alan eklenir:

| Fieldname | Label | Fieldtype | Options / Default | Read Only |
|---|---|---|---|---|
| `is_skipped` | `Is Skipped` | `Check` | Default `"0"`, `in_list_view: 1` | `0` |
| `skipped_by` | `Skipped By` | `Link` | Options `"User"`, `in_list_view: 0` | `1` |
| `is_fifo_override` | `FIFO Override` | `Check` | Default `"0"`, `in_list_view: 0` | `1` |

**`KTALineReplenishmentOrder` Uyumluluğu (`kta_line_replenishment_order.py`):**
- `_calculate_totals()` tüm satırların `flt(item.picked_qty)` değerini toplar. Backend atlanan satırlara her zaman `is_picked = 0` ve `picked_qty = 0.0` atayacağı için `total_picked_qty` yalnızca gerçekten transfer edilen miktarı yansıtır.
- `_handle_status_cancellation()` ve `on_cancel()` zaten `if self.stock_entry:` korumasındadır. Tüm satırlar atlandığında `order.stock_entry = None` bırakılıp `order.status = "Cancelled"` ile kaydedilmesi mevcut kontrolcüde güvenli şekilde desteklenir.

### 4.2 Doğal Raf Sıralaması ve Emir Detayları (`get_replenishment_order_details`)
Dosya: `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py`

1. **Üst Seviye Yetki Bayrağı:**
   - `_SKIP_ALLOWED_ROLES = frozenset({"Stock Manager", "System Manager"})`
   - Dönen payload içine `can_skip_items: bool(user_roles.intersection(_SKIP_ALLOWED_ROLES))` eklenir.
2. **Toplu `Item.has_batch_no` Çözümleme:**
   - Emirdeki tüm `item_code` değerleri için tek sorgu (`frappe.get_all("Item", filters={"name": ["in", item_codes]}, fields=["name", "has_batch_no"])`) ile N+1 sorgudan kaçınılır.
   - Her satıra eklenen alanlar: `has_batch_no` (`0` veya `1`), `is_skipped` (`cint(row.is_skipped)`), `skipped_by` (`row.skipped_by`), `is_fifo_override` (`cint(row.is_fifo_override)`).
   - **Geriye Dönük `picked_qty` Davranışı:** Mevcut `test_get_replenishment_order_details_with_shelf_and_batch` testinin beklentisini korumak için atlanmamış satırlarda `picked_qty = flt(row.picked_qty) or flt(row.deficit_qty)` davranışı aynen korunur; `is_skipped == 1` olan satırlarda `0.0` döner. (Frontend başlangıçta okutulmamış partili satırlara "Toplanmadı" muamelesi yapar, miktarını yalnızca okutma sonrası sabit koli miktarı olarak gösterir.)
3. **Doğal Alfanümerik Raf Sıralaması (`_natural_shelf_sort_key`):**
   - `suggested_source_warehouse` alanını `re.split(r"(\d+)", wh.strip())` ile parçalayarak sayısal blokları `(0, int(part))`, metin bloklarını `(1, part.lower())` tuple'larına dönüştürür; böylece `W1A-02-01` < `W1A-10-01` < `W1B-01-01` < `W1F-01-01` sırası garanti edilir.
   - Boş raf değerleri `(1, ...)` anahtarı ile listenin sonuna itilir; aynı raftaki kalemlerde bağ kırıcı olarak `(row.item_code or "", row.suggested_batch_no or "", row.idx or 0)` kullanılır.

### 4.3 Canlı Stok & Raf Çözümleme (`resolve_scanned_barcode`)
Dosya: `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py`

İmza (geriye dönük uyumlu):
```python
@frappe.whitelist()
def resolve_scanned_barcode(barcode: str | None = None, order_name: str | None = None) -> dict:
```

- Mevcut 4 aşamalı arama sırası korunur: (1) Direct `Item`, (2) `KTA Stock Label` (`sut_barcode` / `name`), (3) `Batch` (`name` / `batch_id`), (4) `Item Barcode`.
- `Item` tablosundan `has_batch_no` (`0`/`1`) çekilir ve dönüş sözlüğüne eklenir.
- Eğer çözümlenen kayıt bir `batch_no` içeriyorsa (`KTA Stock Label` veya `Batch` eşleşmesi):
  1. `Batch` metadata'sından `disabled` okunur. `cint(batch_meta.disabled) == 1` ise `batch_disabled: True`, `warehouse: None`, `qty: 0.0`, `available_balances: []` döndürülür.
  2. `erpnextkta.kta_stock.services.relabeling_service.get_batch_ledger_balances(item_code, batch_no)` çağrılır.
  3. Eğer `order_name` verildiyse emrin `target_warehouse`, `company` ve `items` satırları okunur.
  4. Pozitif (`qty > 1e-6`) bakiye satırları için tek toplu `Warehouse` meta sorgusu çekilir (`name`, `is_group`, `disabled`, `is_rejected_warehouse`, `company`):
     - `is_group == 0`, `disabled == 0`, `is_rejected_warehouse == 0` olan (ve emir şirketine uyan) raflar uygun kaynak adaylarıdır.
     - Eğer `order.target_warehouse` bu listede varsa ayrı tutulur; başka hiçbir uygun rafta bakiye yoksa `already_in_target: True` döndürülür.
     - Kalan uygun kaynak raflar `available_balances` (`[{"warehouse": wh, "qty": flt(qty)}]`) listesine yazılır.
  5. **Birincil Raf ve Tam Koli Miktarı Seçimi:**
     - Eğer `available_balances` boş değilse: öncelikle emirde bu `(item_code, batch_no)` için önerilmiş raf varsa o seçilir; yoksa en yüksek bakiyeli / doğal raf sıralı ilk raf seçilir ve `warehouse = selected["warehouse"]`, `qty = flt(selected["qty"])` set edilir.
     - Eğer `available_balances` boşsa (`0` bakiye veya sadece hedef/pasif/red deposunda): `warehouse = None`, `qty = 0.0` döndürülür (eski `KTA Stock Label.qty` değeri sahte stok gibi kullanılmaz; yalnızca sıfır bakiye uyarısı verilir).
- Parti içermeyen (`Item` / `Item Barcode`) eşleşmelerde mevcut dönüş sözlüğü (`item_code`, `batch_no: None`, `qty: 0.0`, `source`, `has_batch_no`) korunur.

### 4.4 Tamamlama, Kısmi/Tam Atlama ve Denetim Kaydı (`complete_line_replenishment_picking`)
Dosya: `erpnextkta/kta_stock/line_replenishment_service.py`

1. **Sabitler ve Dönüş Tipi:**
   - `_SKIP_ALLOWED_ROLES = frozenset({"Stock Manager", "System Manager"})`
   - Dönüş tipi her zaman `str` kalır (mevcut tüm çağıranlarla %100 uyum):
     - En az 1 toplanan satır varsa -> oluşturulan `Stock Entry` belgesinin adı (`se.name`).
     - Tüm satırlar `Stock Manager` tarafından atlandıysa (`0` toplanan satır) -> boş `Stock Entry` oluşturulmaz, emir `status = "Cancelled"` olarak kaydedilir ve `""` (boş string) döndürülür.
2. **`picked_items` Eşleme ve Eksiksizlik Kuralı:**
   - **`picked_items is None` (Headless/Legacy Test Modu):** Mevcut testlerin bozulmaması için tüm `order.items` satırları önerilen raf/parti ve `deficit_qty` ile `is_picked = 1` kabul edilerek tam transfer edilir.
   - **`picked_items` Liste/JSON Verildiyse:**
     - Eşleme sırası (çift eşleşme engelleyici `matched_row_names: set[str]` ile):
       1. `row.name == p_item.get("name")`
       2. `name` yoksa `item_code` + (verildiyse) `picked_batch_no` / `suggested_batch_no` eşleşmesi
       3. Hala eşlenmemiş aynı `item_code` satırı
     - **Eksiksiz Çözümleme Şartı:** `picked_items` gönderildiğinde `order.items` içindeki **her satır** kesin olarak ya `is_picked = 1` ya da `is_skipped = 1` olarak çözümlenmiş olmalıdır. Eşlenmemiş veya ne toplanmış ne atlanmış satır kalırsa `frappe.ValidationError` fırlatılır (sessizce tüm listeyi transfer etme bug'ı kapatılır).
     - `is_skipped` flag'i falsy olan eski test payload'ları (ör. `{"item_code": "...", "picked_qty": 110.0}`) varsayılan olarak `is_picked = 1` kabul edilir.
3. **Sunucu Tarafı Skip RBAC:**
   - Herhangi bir satırda `cint(row.is_skipped) == 1` ise kullanıcının rolleri `frappe.get_roles(frappe.session.user)` kontrol edilir.
   - `_SKIP_ALLOWED_ROLES` kesişimi yoksa `frappe.throw(_("Kalem atlama işlemi için Stok Yöneticisi (Stock Manager) yetkisi gereklidir."), frappe.PermissionError)` fırlatılır.
   - Yetki onaylanırsa atlanan satırlara sunucuda zorla `row.is_skipped = 1`, `row.skipped_by = frappe.session.user`, `row.is_picked = 0`, `row.picked_qty = 0.0` yazılır.
4. **Partili Kalem Doğrulamaları & `1 Kutu = 1 Parti` Politikası:**
   - **Grup Ambarı Çözümleme:** `s_warehouse` bir grup ambarı ise mevcut `get_leaf_warehouses()` mantığı ile yaprak ambara çözülür (önce `picked_items is None` legacy testleriyle tam uyum korunur).
   - **Kaynak Ambar Kontrolü:** `s_warehouse` boş olamaz; `s_warehouse == order.target_warehouse`, `disabled == 1` veya `is_rejected_warehouse == 1` ise `frappe.ValidationError` fırlatılır.
   - **Partili Kalemler (`has_batch_no == 1` veya `batch_no` dolu):**
     - `Batch.item == row.item_code` ve `Batch.disabled == 0` kontrolü yapılır.
     - Aynı emir içinde iki toplanmış satır aynı `(item_code, batch_no, s_warehouse)` kolisini tüketemez -> `frappe.ValidationError` ("Aynı koli/parti birden fazla satırda kullanılamaz").
     - Eğer çağrı PDA'dan `picked_items` ile geldiyse canlı `get_batch_ledger_balances(row.item_code, batch_no)` üzerinden `s_warehouse` bakiyesi (`live_qty > 1e-6`) kontrol edilir; `picked_qty` değerinin tam koli bakiyesine eşit olması (`abs(picked_qty - live_qty) <= 1e-6`) şarttır (`1 Kutu = 1 Parti`, partili kolide kısmi bölme olmadan tam koli transferi). Bu doğrulama sağlandığında alternatif FIFO partisinin koli miktarı başlangıç ihtiyacının `%15` üstünde olsa bile reddedilmez.
   - **Partisiz Kalemler (`has_batch_no == 0` ve `batch_no` boş):** Mevcut `max(deficit_qty * 1.15, deficit_qty + 1.0)` üst tolerans sınırı aynen korunur.
5. **Yapısal Denetim Notları (`Stock Entry.remarks` & `KTA Line Replenishment Order.remarks`):**
   - Her FIFO sapması (`batch_no` ve `(batch_no != row.suggested_batch_no or s_warehouse != row.suggested_source_warehouse)`) için `row.is_fifo_override = 1` kaydedilir ve satır özetine eklenir:
     - `"- {item_code}: Önerilen {suggested_batch} ({suggested_wh}) -> Okutulan {picked_batch} ({picked_wh}, {qty} {uom}) [Onay: {user}]"`
   - Her atlanan satır için özet satırı eklenir:
     - `"- {item_code}: {deficit_qty} {uom} (Önerilen: {suggested_batch or '-'} @ {suggested_wh or '-'}) [Atlayan: {user}]"`
   - Oluşturulan standart metin bloğu (`"[HAT İKMAL: {order.name}]"` başlığı altında `"[FIFO SAPMASI]"` ve/veya `"[ATLANAN KALEMLER]"` bölümleri):
     - En az 1 koli toplandıysa: `Stock Entry.remarks` ve `order.remarks` alanlarına yazılır, `order.status = "Completed"`, `order.stock_entry = se.name`, `order.total_picked_qty = total_picked` kaydedilir.
     - Tüm satırlar atlandıysa (`0` koli toplandıysa): `Stock Entry` oluşturulmaz, `order.stock_entry = None`, `order.total_picked_qty = 0.0`, `order.status = "Cancelled"` ve `order.remarks` güncellenip kaydedilir.
   - Notlara asla birim fiyat, maliyet veya tedarikçi/müşteri adı eklenmez.

### 4.5 Atlanan Kalemlerin Otomatik Yeniden Açığa Düşmesi
`erpnextkta/kta_shopfloor/services/reservation_deficit_service.py` içinde `_get_drafts_by_item()` (satır 178–198) açık miktarı yalnızca `docstatus = 0 AND status = 'Draft'` durumundaki ikmal emirlerinden düşmektedir:
- Emrin kalan kolileri transfer edilip emir **`Completed`** olduğunda,
- Ya da tüm kalemler atlanıp emir **`Cancelled`** olduğunda,
atlanan kalemler `target_warehouse` (`150x`) stoğuna hiç girmediği ve emir artık `'Draft'` olmadığı için bir sonraki ikmal taramasında ek bir cron veya müdahale gerekmeden **otomatik olarak yeniden açık (deficit)** listesine düşer.

### 4.6 FIFO Sıralama İyileştirmesi (`expiry_date → manufacturing_date → creation`)
Dosya: `erpnextkta/kta_stock/line_replenishment_service.py`

Raf-içi veya raflar arası `Material Transfer` yapıldığında `Batch.creation` değişmediği için FIFO sırası zaten bozulmaz. Ancak (a) koli bölme / birleştirme / yeniden etiketleme (`Package Split / Merge`) işlemlerinde yeni oluşan alt parti `manufacturing_date` ve `expiry_date` değerlerini miras almasına rağmen veritabanında yeni `Batch.creation` damgası aldığından ve (b) geçmiş tarihli irsaliyelerde (`Backdated Purchase Receipt`) gerçek giriş tarihi `Batch.manufacturing_date` alanına yazıldığından, `expiry_date` alanı boş olan malzemelerde saf `creation` sıralaması yeni irsaliyenin (`IRS02`) eski irsaliyenin (`IRS01` veya bölünmüş kolisi) önüne geçmesine yol açabilmektedir.

Bunu önlemek için `allocate_fifo_batches()` ve `bulk_allocate_fifo_batches()` içindeki ortak sıralama anahtarı `_fifo_candidate_sort_key(c: dict) -> tuple` yardımcı fonksiyonunda birleştirilir:
- Her iki fonksiyonda `Batch` sorgusuna `"manufacturing_date"` alanı eklenir (`["name", "expiry_date", "manufacturing_date", "creation"]`).
- Ortak sıralama sırası:
  ```python
  (
      exp is None,
      exp_str,
      mfg is None,
      mfg_str,
      created_str,
      c.get("batch_no") or "",
      c.get("warehouse") or "",
  )
  ```
- Böylece hem raf transferi sonrası, hem koli bölme/birleştirme sonrası, hem de geçmiş tarihli irsaliye girişlerinde en eski üretim/irsaliye tarihli (`IRS01`) koli daima ilk sırada kalır.

---

## 5. Frontend UI / UX ve Bileşen Mimarisi

### 5.1 Dosya Yapısı ve 500-Satır Kuralı
- **Ortak Türler:** `erpnextkta/public/line-replenishment-pda/types.ts`
  - `PickingItem` genişletmesi: `has_batch_no?: number | boolean`, `is_skipped?: number | boolean`, `skipped_by?: string | null`, `is_fifo_override?: number | boolean`.
  - `ReplenishmentOrder` genişletmesi: `can_skip_items?: boolean`, `skipped_count?: number`.
  - `ScanResult` genişletmesi: `warehouse?: string | null`, `available_balances?: Array<{ warehouse: string; qty: number }>`, `already_in_target?: boolean`, `batch_disabled?: boolean`, `has_batch_no?: number | boolean`.
  - Doğal raf sıralama yardımcısı: `compareShelfNames(a?: string, b?: string): number` (backend ile birebir aynı alfanümerik kural).
- **Ortak Composable:** `erpnextkta/public/line-replenishment-pda/composables/useLineReplenishmentPicking.ts`
  - Hem `PickingModuleView.vue` (`/pda`) hem `PdaApp.vue` (`/app/line-replenishment-picking`) tüm iş mantığını buradan tüketir. Böylece iki ekran davranışsal olarak %100 eşitlenir ve `PdaApp.vue` (~620 -> ~200 satır) ile `PickingModuleView.vue` (~220 satır) kolayca `<= 500` satır kuralı altında kalır.
- **Bileşenler (`erpnextkta/public/line-replenishment-pda/components/`):**
  - `OrderSelector.vue`: Mevcut seçici + tek satırda ilerleme göstergesi (`X / Y Koli`).
  - `BarcodeScannerBar.vue`: Yapışkan barkod girişi; bilgi (`info`), başarı (`success`) ve hata (`error`) toast desteği (koyu tema uyumlu renklerle); modal açıkken `disabled` / focus koruması.
  - `PickingItemCard.vue` (`<= 300` satır): Yaklaşım A kompakt yürüyüş kartı & katlanan tek satır görünümü.
  - `FifoOverrideModal.vue` (`<= 220` satır, yeni, `<Teleport to="body">`): FIFO sapma uyarı ve tek tık onay modalı.
  - `SkipItemModal.vue` (`<= 180` satır, yeni, `<Teleport to="body">`): `Stock Manager` eksik ürün atlama onay modalı.
  - `TransferFooter.vue`: Tek yapışkan alt buton (`Transferi Tamamla` veya tümü atlandığında `Emri İptal Et`).

### 5.2 Görsel Yerleşim ve Kart Tasarımı (Yaklaşım A + Mevcut `/pda` Paleti)

1. **Üst Kabuk (Dokunulmaz):** Mevcut `.pda-topbar` ve `.pda-subbar` olduğu gibi kalır (`--card-bg`, `--pda-surface-alt`, `--border-color`).
2. **Sipariş & İlerleme Şeridi + Yapışkan Barkod Çubuğu:**
   - Mevcut `OrderSelector` ve `BarcodeScannerBar` kartları `--card-bg` + `--border-color` ile korunur; `OrderSelector` altına ince tek satırlık ilerleme barı (`Toplanan: X / Y`) eklenir.
3. **Segmented Filtre Sekmeleri:**
   - Barkod barının hemen altında 2 (atlanan varsa 3) dokunmatik sekme:
     - `Bekleyen (N)` (varsayılan aktif)
     - `Toplanan (M)`
     - `Atlanan (K)` (yalnızca `K > 0` iken görünür)
   - Tüm bekleyenler (`N === 0`) bittiğinde sekme listesinin üstünde kısa bir yeşil/amber başarı özet şeridi ("Tüm kalemler işlendi — Transferi tamamlamaya hazır" veya "Tüm kalemler atlandı — Emri iptal edebilirsiniz") gösterilir.
4. **Kart Durumları (`PickingItemCard.vue`):**
   - **Durum A — Bekleyen Partili Kart (`has_batch_no !== 0` ve `!is_picked && !is_skipped`):**
     - **Üst Satır:** Sol tarafta yüksek kontrastlı raf rozeti (`📍 W1A-01-01` — `--text-color` / `#0f172a` arka plan + `#fef08a` vurgu), sağ tarafta sabit tam koli miktar rozeti (`500 Adet`).
     - **Orta Satır:** Kalın monospace `item_code`, altında en fazla 2 satıra kırpılmış `item_name`.
     - **Alt Satır:** Sol tarafta `🏷️ {suggested_batch_no}` FIFO parti etiketi; sağ tarafta yalnızca `canSkip === true` ise düşük profilli ikincil `Atla` butonu (`--border-color`, `min-height: 36px`).
     - **Kaldırılan Öğeler:** `Toplandı` checkbox, `- / +` stepper, miktar `<input>`, `⚡ Tümünü Al`, 4 hücreli grid ve kart içi progress bar partili satırlarda **asla render edilmez**.
   - **Durum B — Bekleyen Partisiz İstisna Kartı (`has_batch_no === 0`):**
     - Aynı kompakt üst/orta gövde + altta küçük miktar inputu (varsayılan `deficit_qty`, `+%15` tolerans uyarılı) ve `✓ Onayla` butonu. (Çift barkod okutulursa yine artmaz; yalnızca manuel/ilk tarama onayı içindir.)
   - **Durum C — Toplanan Kart (Katlanmış 1 Satır Yeşil Kart):**
     - Tek yatay satır (`border-left: 4px solid var(--pda-success)`): `✓` ikonu · `Raf` · `item_code` · `{picked_qty} {uom}` · `{picked_batch_no}` · (eğer `is_fifo_override` ise amber `⚠️ FIFO Sapması` rozeti) · sağda küçük `↩` (Geri Al / Sıfırla) ikonu.
   - **Durum D — Atlanan Kart (Katlanmış 1 Satır Soluk/Amber Kart):**
     - Tek yatay satır (`opacity: 0.85`): `⊘` ikonu · `Raf` · `item_code` · `Atlandı` rozeti · sağda (`canSkip` ise) `↩` (Geri Al) ikonu.

### 5.3 Barkod Okutma Karar Ağacı (8 Senaryo)

Operatör barkod okuttuğunda `useLineReplenishmentPicking.onBarcodeScan(code)` sırayla şu kontrolleri yapar:

1. **Modal Kilidi:** Açık bir `FifoOverrideModal` veya `SkipItemModal` varken arka plan taramaları yok sayılır.
2. **Backend Çözümleme:** `resolve_scanned_barcode({ barcode: cleanCode, order_name: activeOrder.name })` çağrılır.
3. **Senaryo 1 — Bilinmeyen Barkod:** `!resolved.item_code` → Hata sesi + `"Barkod tanınamadı veya sistemde bulunamadı."`
4. **Senaryo 2 — Emir Dışı Ürün:** Emirde `item_code` eşleşen hiç satır yoksa → Hata sesi + `"Okutulan malzeme bu ikmal emrinde yer almıyor."`
5. **Senaryo 3 — Çift Okutma Koruması:** Eğer eşleşen tüm ilgili satırlar zaten `is_picked` veya `resolved.batch_no` bu emirdeki `picked_batch_no` alanlarından biriyle birebir eşleşiyorsa → Miktarı **kesinlikle artırma**, kısa uyarı/bilgi sesi + `"Bu koli ({0}) zaten okutuldu."` (`info` geri bildirim).
6. **Senaryo 4 — Zaten Hedef Hatta / Sıfır Bakiye / Pasif Parti:**
   - `resolved.batch_disabled` → Hata sesi + `"Okutulan parti pasif durumdadır."`
   - `resolved.already_in_target` → Hata sesi + `"Bu koli zaten hedef üretim hattında ({0}) bulunuyor."`
   - Partili üründe (`resolved.batch_no` dolu) `!resolved.warehouse || Number(resolved.qty || 0) <= 0` → Hata sesi + `"Bu partinin uygun kaynak raflarda kullanılabilir bakiyesi yok."`
7. **Senaryo 5 — Partili Üründe Salt Ürün Kodu / Item Barkodu Okutulması:**
   - Emirde bu ürünün bekleyen satırı `has_batch_no !== 0` (veya `suggested_batch_no` dolu) iken `!resolved.batch_no` dönmüşse → Hata sesi + `"Bu malzeme parti takiplidir. Lütfen koli/SUT parti barkodunu okutun."`
8. **Senaryo 6 — Birebir FIFO Parti Eşleşmesi:**
   - Bekleyen (`!is_picked && !is_skipped`) satırlarda `row.item_code === resolved.item_code` ve `row.suggested_batch_no === resolved.batch_no` bulunursa → Sessiz başarı:
     - `row.is_picked = 1`, `row.is_fifo_override = 0`
     - `row.picked_batch_no = resolved.batch_no`
     - `row.picked_source_warehouse = resolved.warehouse || row.suggested_source_warehouse`
     - `row.picked_qty = Number(resolved.qty || 0) > 0 ? Number(resolved.qty) : row.deficit_qty`
     - Başarı bip + kart vurgulama + `"Okutuldu: {0} [{1}]"`
9. **Senaryo 7 — FIFO Sapması (Farklı Koli / Parti):**
   - Bekleyen satırlarda `row.item_code === resolved.item_code` mevcut fakat `suggested_batch_no !== resolved.batch_no` ise (ilk bekleyen satır aday alınır; bekleyen satır hiç kalmamışsa *"Bu malzemenin bekleyen kolisi kalmadı."* hatası verilir):
     - Uyarı bip çalınır ve **`FifoOverrideModal.vue`** açılır:
       - Önerilen: `suggested_batch_no` · `suggested_source_warehouse` · `deficit_qty uom`
       - Okutulan: `resolved.batch_no` · `resolved.warehouse` · `resolved.qty uom`
       - Bilgi notu: `"Bu değişim Stock Entry notlarına otomatik kaydedilecektir."`
     - Operatör **`Yine de Kullan (FIFO Sapması)`** düğmesine bastığında (tek tık):
       - `row.is_picked = 1`, `row.is_fifo_override = 1`
       - `row.picked_batch_no = resolved.batch_no`
       - `row.picked_source_warehouse = resolved.warehouse`
       - `row.picked_qty = Number(resolved.qty)`
       - Kısa başarı bip + focus tekrar `BarcodeScannerBar`a döner.
     - Operatör **`İptal`** düğmesine basarsa satır bekleyen olarak kalır ve focus tarayıcıya döner.
10. **Senaryo 8 — Partisiz Ürün (`has_batch_no === 0` ve `!resolved.batch_no`):** İlk bekleyen partisiz satır `picked_qty = row.picked_qty || row.deficit_qty` ile `is_picked = 1` yapılır (veya operatör karttaki miktar + `Onayla`yı kullanır).

### 5.4 Tek Sabit `TransferFooter.vue` Kuralları ve Sayfa Sonu Sabitleme Düzeltmesi
- **Kök Neden ve Düzeltme (`position: fixed` Sabitleme):** Mevcut `TransferFooter.vue` `position: sticky; bottom: 0;` kullandığı ve ebeveyn `.pda-picking-view` kabında `padding-bottom: 92px;` bulunduğu için, kullanıcı sayfanın en altına kaydırdığında footer içeriğin sonunda `92px` yukarı kaymakta ve kısa listelerde ekran ortasında asılı kalmaktadır.
- **Viewport Alt Sabitleme:** `TransferFooter.vue` dış kabuğu **`position: fixed; bottom: 0; left: 0; right: 0; z-index: 38;`** olarak sabitlenir (`padding-bottom: calc(10px + env(safe-area-inset-bottom, 0px))` ile mobil safe-area uyumlu; iç `.pda-footer-inner` kapsayıcısı tablette `max-width: 960px; margin: 0 auto;` ile hizalanır). Bu sayede `PdaMenuDrawer` (`z-index: 1200`) ve `<Teleport to="body">` modallarının (`z-index: 1070`) altında kalır, sayfa sonuna inildiğinde asla yukarı kaymaz.
- **Liste Alt Boşluğu:** `.pda-picking-view` / `.pda-main` kabına mobilde `padding-bottom: 112px`, tablette `padding-bottom: 84px` verilerek en alt kartın sabit footer altında gizlenmesi önlenir.
- Alt alanda yalnızca **tek** bir sabit çubuk ve **tek** bir ana buton bulunur:
  - Özet satırı: `"{0} / {1} Tamamlandı"` + atlanan varsa `"({0} Atlandı)"` + eksik varsa `"{0} koli bekliyor"`.
  - **Bekleyen satır > 0:** Buton `disabled`, etiket `"Transferi Tamamla"`.
  - **Bekleyen == 0 ve Toplanan > 0:** Yeşil aktif buton `"Transferi Tamamla"`.
  - **Bekleyen == 0, Toplanan == 0 ve Atlanan == Toplam (`canSkip` olan Stock Manager):** Amber/uyarı aktif buton `"Emri İptal Et (Tümü Atlandı)"` (tıklandığında `complete_line_replenishment_picking` aynı payload ile çağrılır, boş `Stock Entry` olmadan emir `Cancelled` yapılır ve kullanıcıya bilgi toast'ı gösterilir).

### 5.5 Tablet Responsive Düzeni (`min-width: 768px`)
- **Mobil (`< 768px`):** Mevcut tam genişlik tek kolon düzen ve parmak dostu `44–52px` dokunma hedefleri aynen korunur.
- **Tablet (`>= 768px`) Ölçek & Yerleşim:**
  - `PickingModuleView.vue` ve `PdaApp.vue` ana içeriği `max-width: 960px; margin: 0 auto; width: 100%;` kapsayıcı ile ortalanır (devasa tam ekran esneme engellenir).
  - Üst kontrol şeridinde `OrderSelector.vue` ve `BarcodeScannerBar.vue` yan yana 2 kolonlu (`grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr); gap: 10px`) yerleşir; tablette üst alan yüksekliği yarıya iner ve daha fazla kart ilk ekranda görünür.
  - Bekleyen kartlar (`PickingItemCard.vue`) `>= 768px` ekranlarda **2 kolonlu CSS Grid** (`grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px`) olarak dizilir; kart padding/tipografi/kontrolleri tablete uygun kompakt ölçeğe (`padding: 10px`, `min-height: 40px`, dengeli font boyutları) çekilir. Katlanmış 1 satırlık `Toplanan` / `Atlanan` özetleri `max-width: 960px` içinde düzenli tek liste halinde hizalanır.
  - Yapışkan `TransferFooter.vue` tablette tek satırlık yatay çubuğa (`flex-direction: row; justify-content: space-between; align-items: center; max-width: 960px; margin: 0 auto;`) geçer; buton tam ekran genişlemek yerine sağda orantılı boyutta (`width: auto; min-width: 240px; min-height: 44px; padding: 8px 22px`) durur.
  - `FifoOverrideModal.vue` ve `SkipItemModal.vue` `max-width: 460px; width: calc(100% - 24px);` sınırıyla ortalanır.
- Mevcut `/pda` üst kabuğu (`PdaHubApp.vue`, `.pda-topbar`, `.pda-subbar`, `pda-hub.bundle.css` paleti) yine dokunulmadan korunur.

---

## 6. Doğrulama ve Test Matrisi (Clean-CI + Vitest + Kalite Kapısı)

### 6.1 Backend Clean-CI Testleri
Tüm yeni testler `frappe.tests.utils.FrappeTestCase` tabanlı, tamamen dinamik şirket/depo/ürün/kullanıcı kurgusuyla yazılır (boş `test_site` uyumlu):

1. **`test_line_replenishment_picking_page.py`:**
   - `get_replenishment_order_details` doğal raf sıralaması testi (`W1A-10-01`, `W1A-02-01`, `W1B-01-01` → çıktı sırası `W1A-02-01`, `W1A-10-01`, `W1B-01-01`).
   - `can_skip_items` rol bazlı doğruluk (`KTA PDA Stock User` / `Stock User` -> `False`; `Stock Manager` -> `True`) ve satır seviyesinde `has_batch_no` doğruluğu.
   - `resolve_scanned_barcode(barcode, order_name)` canlı bakiye testleri:
     - Aktif kaynak raftaki tam koli miktarı ve raf dönüşü.
     - Koli hedef hatta (`target_warehouse`) ise `already_in_target=True` ve kaynak rafın `None` dönmesi.
     - Sıfır bakiyeli/pasif partide uygun uyarı bayrakları.
     - `order_name=None` çağrısıyla tam geriye dönük uyumluluk.
2. **`test_line_replenishment_transfer.py`:**
   - FIFO sapmalı transfer (`suggested_batch != picked_batch`, farklı tam koli miktarı ör. `deficit=100` iken okutulan kapalı koli `140` — `>+15%` kapalı koli kabulü): `Stock Entry` doğru `s_warehouse`/`batch_no`/`140` ile oluşur, `row.is_fifo_override == 1` ve hem `Stock Entry.remarks` hem `order.remarks` içinde `[FIFO SAPMASI]` kaydı bulunur.
   - Partili kalemde kısmi koli miktarı veya aynı partinin iki satırda çift tüketimi ile `picked_items` gönderildiğinde `ValidationError`.
   - Eksik/çözülmemiş satır bırakılarak (ne `is_picked` ne `is_skipped`) `picked_items` gönderildiğinde `ValidationError`.
   - `KTA PDA Stock User` / `Stock User` kullanıcısının `is_skipped=1` içeren payload göndermesinin `frappe.PermissionError` ile reddedilmesi.
   - **`Stock Manager` kısmi atlama + yeniden açığa düşme:** 2 kalemli emirde 1 kalem toplanıp 1 kalem atlandığında; yalnız toplanan kalem için `Stock Entry` oluşturulur, `order.status == "Completed"`, `[ATLANAN KALEMLER]` notu kaydedilir ve `_get_drafts_by_item()` (veya `calculate_line_material_deficits`) atlanan kalemi tekrar açık (deficit) olarak raporlar.
   - **`Stock Manager` tüm satırları atlama (boş Stock Entry önleme):** Tüm satırlar `is_skipped=1` gönderildiğinde; `complete_line_replenishment_picking` `""` döner, hiçbir `Stock Entry` oluşturulmaz (`order.stock_entry` boş), `order.status == "Cancelled"`, `order.remarks` atlama notunu içerir ve tüm atlanan kalemler yeniden açığa düşer.
3. **`test_line_replenishment_service.py`:**
   - Hem `allocate_fifo_batches` hem `bulk_allocate_fifo_batches` için `manufacturing_date` FIFO öncelik testi (`expiry_date` boş iken daha eski `manufacturing_date` ve daha yeni `creation` değerine sahip bölünmüş/geçmiş-tarihli partinin yeni `manufacturing_date`'li partiden önce gelmesi).
   - Raf-içi/raflar arası `Material Transfer` sonrası taşınan eski partinin yeni rafıyla birlikte yine 1. sırada önerilmesi.

### 6.2 Frontend Vitest Testleri
Dosya: `erpnextkta/public/pda-hub/__tests__/PickingModuleView.spec.ts` (yeni)
- Raf yürüyüş sıralaması doğrulaması (`W1A-10-01` vs `W1A-02-01`).
- Partili kartta checkbox / `-` / `+` / `Tümünü Al` düğmelerinin render edilmemesi; partisiz kartta istisna kontrollerinin görünmesi.
- Aynı barkodu 2. kez okutmada miktarın artmaması ve `"zaten okutuldu"` bilgi mesajı.
- Partili kalemde salt `item_code` okutulmasının reddi.
- Alternatif parti okutulduğunda `FifoOverrideModal` açılışı, iptal ve tek tıkla onay (`⚠️ FIFO Sapması` rozeti + gerçek miktar/raf güncellemesi).
- `can_skip_items: false` vs `can_skip_items: true` durumlarında `Atla` butonu görünürlüğü.
- Kısmi toplamada `Transferi Tamamla` butonunun tüm bekleyenler bitmeden devre dışı kalması; tüm satırlar atlandığında `"Emri İptal Et"` durumuna geçmesi.

### 6.3 Dokümantasyon ve Çok Dilli Çeviriler (`docs-i18n`)
- `erpnextkta/www/docs/stok-lojistik.html`
- `erpnextkta/www/docs/line_replenishment.html`
- `docs/kta_stok_lojistik_kilavuzu.md`
- `erpnextkta/translations/tr.csv`, `en.csv`, `de.csv` (yalnızca sona ekleme / append-only, Title Case, 0 silme, 0 duplicate)

### 6.4 Final Kalite Kapısı Komutları
1. `bench --site development.localhost migrate` (yeni JSON alanları DB'ye uygulamak için)
2. `bench build --app erpnextkta --production`
3. Frontend Vitest suite (`PickingModuleView.spec.ts` dahil tüm `pda-hub` testleri)
4. Backend testler (`test_line_replenishment_picking_page`, `test_line_replenishment_transfer`, `test_line_replenishment_service`, `test_line_replenishment_doctypes`)
5. `/home/frappe/frappe-bench/env/bin/ruff check` ve `ruff format --check`
