# Shopfloor Hatlar Arası Transfer (`Line Transfers`) ve Saf Ana Ambar Hat İkmali Tasarım Dokümanı

**Tarih:** 2026-11-21  
**Durum:** Onaylandı — Uygulama Tasarımı  
**Kapsam:** `kta_stock`, `kta_shopfloor`, `public/shopfloor-hub`, `public/line-replenishment-*`, `docs`, `translations`

---

## 1. Mimari Ayrım ve Problem Çözümü

Önceki tasarımda kardeş üretim hatları arası stok aktarımı (`150x ↔ 150x`) ile ana ambardan hatlara çekme (`110 HAMMADDE → 150x`) aynı `Line Replenishment Hub` içinde `Smart Sourcing (WIP First)` altında birleştirilmişti. Bu durum sahada iki açıdan kafa karışıklığı ve operasyonel uyumsuzluk yaratıyordu:
1. **Rol ve Süreç Farkı:** Ana ambardan gelen ikmal kapalı koli/makara bölmeden FIFO ile raf gezen depo ekibi (LRO + PDA toplama) tarafından yürütülür; oysa üretim hatları arası aktarım vardiya amiri/hat lideri tarafından saha içinde anlık yapılır.
2. **Parti Tüketim Mantığı (FIFO vs LIFO):** Ana ambardan FIFO (en eski parti) ve tam ambalaj çekilirken, üretim hattındaki aktif açık/rezerve partiyi bozmamak için kardeş hattan başka bir hatta malzeme verirken **en yeni partiden geriye doğru (LIFO)** ve tam ihtiyaç miktarı kadar çekilmesi gerekir.

### Netleşen İki Ayrı Alan

1. **`Line Replenishment Hub & PDA` (%100 Saf Ana Ambar İkmali):**
   - Yalnızca `110 HAMMADDE` yaprak raflarından (`W1A-01-01` vb.) hedef `150x` üretim hattına **FIFO tam koli/makara** çekme emri (`KTA Line Replenishment Order`) ve mobil PDA toplama sürecini yürütür.
   - `Tedarik Stratejisi` (`sourcing_strategy`), `Kaynak Tipi` (`sourcing_type`), `free_stock_qty` ve kardeş hat tarama mantığı tamamen temizlenmiştir.

2. **`Shopfloor Hub → Hatlar Arası Transfer` (`Line Transfers` — 4. Sekme):**
   - Üretim sahasındaki `150 ÜRETİM` hat depoları (`1501`–`1509` ve diğer aktif üretim yaprak depoları) arasında çalışır; `110 HAMMADDE` / ana ambar depoları her iki yönde de kesinlikle engellenir.
   - Araya sipariş veya PDA adımı girmeden tek adımda resmi `Stock Entry (Material Transfer)` fişi keser ve onaylar (`docstatus=1`).

---

## 2. `Hatlar Arası Transfer` Sekmesi Özellikleri ve İş Kuralları

### 2.1 Üç Çalışma Modu / Aksiyonu
1. **Açık Karşılama (`deficit_pull` — Hedef Hat Bazlı):**
   - Seçilen hedef `150x` hattın aktif iş emri rezervasyon açıklarını (`reserved_qty_for_production - actual_qty > 0`) tarar.
   - Yalnızca kardeş `150x` üretim hatlarında fiili stoğu (`actual_qty > 0`) bulunan kalemleri listeler (kardeş hatlarda hiç stoğu olmayanlar `Line Replenishment Hub` konusudur, burada gösterilmez).
   - Kaynak hatları `free_qty` (serbest stok) yüksekliğine göre sıralar ve serbest stoğu olanı varsayılan seçili (`default_selected = True`) getirir.
2. **Atıl Hat Stoğu (`idle_push` — Kaynak Hat Bazlı):**
   - Seçilen kaynak `150x` hattında `actual_qty - reserved_qty_for_production > 0` (boşta bekleyen) tüm malzemeleri listeler.
   - Aynı malzeme için rezervasyon açığı olan kardeş bir `150x` hat varsa `suggested_target_warehouse` ve `target_deficit_qty` otomatik önerilir.
3. **`+ Manuel Transfer` Modalı:**
   - Kullanıcı kaynak `150x` hattı, hedef `150x` hattı ve kaynakta stoğu olan kalemleri arayarak seçer; ihtiyaç miktarı girip tek adımda aktarır.

### 2.2 Arka Plan Otomatik LIFO Parti Tahsisi
- Arayüzde kullanıcıya parti seçtirilmez; sade tutulur.
- `has_batch_no = 1` kalemlerde `resolve_lifo_batches()` servisi kaynak hattaki pozitif bakiyeli, aktif (`disabled = 0`) ve süresi geçmemiş (`expiry_date >= today()` veya boş) partileri **son giriş tarihine göre tersten (LIFO: en yeni parti önce)** sıralar.
- Amaç: Kaynak hattın kendi üretim teyitlerinde (backflush) FIFO ile tüketeceği ve tezgahta açılmış olan ilk partiyi korumaktır.
- Tam makara zorunluluğu yoktur; ihtiyaç miktarı kadar (`min(avail_qty, remaining)`) bölünerek tahsis edilir.

### 2.3 Rezerve Stok Koruması ve Onaylı Öncelik Kaydırma
- Her kaynak hat için `serbest_stok = max(0, actual_qty - reserved_qty_for_production)` hesaplanır.
- Normal akışta transfer miktarı serbest stokla sınırlanır.
- Acil üretim önceliği değiştiğinde kullanıcı miktarı `serbest_stok < qty <= actual_qty` aralığına çıkarırsa sistem bunu engeller; ancak kullanıcı arayüzdeki **Öncelik Kaydırma Onay Modalı** ile açık onay verdiğinde (`allow_reserved_override = 1`) fiziksel stoğa (`actual_qty`) kadar transfer onaylanır.
- `qty > actual_qty` kesinlikle yasaktır.

### 2.4 Mevcut Shopfloor Hub Sekmeleriyle Entegrasyon
- **`Operasyonlar` Sekmesi (`MaterialStagingModal.vue`):** Başlık **"Hatlar Arası Hızlı Transfer"** olarak güncellenir; arka planda aynı LIFO parti tahsisli ve rezerve uyarılı ortak `execute_line_transfer(..., work_order=wo.name)` servisini kullanır (`allow_reserved_override` checkbox onayı ile).
- **`İş Emirleri` Sekmesi (`WorkOrderReleasePanel.vue`):** Eksik bileşenlerde kardeş üretim hatlarında stok bulunduğunda (`has_sibling_line_stock = True`), uygunluk tablosunda tek tıkla hedef hattı seçili halde **`Hatlar Arası Transfer`** sekmesine geçiş kısayolu sunulur.
