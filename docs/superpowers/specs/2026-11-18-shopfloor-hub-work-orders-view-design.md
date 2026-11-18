# Tasarım Dokümanı: Shopfloor Hub Çoklu Görünüm (Views) & Work Orders Yönetimi

**Tarih:** 2026-11-18  
**Durum:** Nihai Tasarım (Tüm Kararlar Çözüldü & Onaylandı)  
**Yazar:** Tech Lead / Coordinator  
**Hedef Kapsam:** `erpnextkta/kta_shopfloor/**`, `erpnextkta/public/shopfloor-hub/**`, `erpnextkta/erpnextkta/custom/**`, `docs/**`

---

## 1. Amaç ve Arka Plan (Intent & Why)

Shopfloor Hub, operatör ve hat liderlerine atölye zemininde hızlı, hatasız ve tek ekrandan operasyon teyidi (ve SAP CO11N/CORS benzeri backflush/storno) sunmak üzere tasarlandı. Ancak sahadaki üretim akışı yalnızca operasyon teyitleriyle sınırlı değildir:
- Yeni üretim ihtiyaçları, acil partiler veya planlanan işler için atölye terminalinden doğrudan yeni İş Emri (Work Order) oluşturulabilmeli (SAP CO01 benzeri),
- Oluşturulan taslak iş emirleri üretime serbest bırakılmadan (Release / Submit edilmeden) önce **hammadde ve bileşen stok uygunluğu** kontrol edilebilmeli,
- Eksik hammadde durumunda kesin bloklama yapılmaksızın hat liderine şeffaf bir uyarı ve eksik listesi sunulmalı; onay verilirse iş emri eksiklik kaydıyla serbest bırakılabilmelidir.

Bu tasarım, Shopfloor Hub'ı en üstte hiyerarşik bir sekme çubuğu ile çoklu görünümlere (`[ ⚡ Work Orders ]` ve `[ 📋 Operations ]`) böler.

---

## 2. Hedefler, Kapsam Dışı ve Anti-Hedefler

### 2.1 Hedefler (Goals)
1. **Sabit Üst Menü (Header Tab Bar):**
   - Sayfanın en üstünde dikkat dağıtmayan, sade ve hiyerarşik sıralı navigasyon: `[ ⚡ Work Orders ]` (kapsayıcı/başlangıç) ve `[ 📋 Operations ]` (detay teyit).
   - Sağ üstte gereksiz dil veya profil butonları bulunmayacak; ekran tamamen atölye işlevine odaklanacak.
2. **Work Orders Görünümü:**
   - **İş Emri Açma (Create):** Minimalist + Gelişmiş Seçenekler akordeon yapısıyla; yalnızca Mamul Kodu (`production_item`) ve Üretim Miktarı (`qty`) zorunlu tutulacak. Reçete (`default_bom`), depolar ve tarihler sistem varsayılanlarından otomatik yüklenecektir.
     - **Planlanan Bitiş Tarihi Hesabı:** `planned_end_date = planned_start_date + T_prod`. Dahili imalat süresi ($T_{\text{prod}}$), `feat/mrp-modular-v2` lead time hiyerarşisine uyumlu olarak çözümlenir (`Item Customer Detail.custom_production_time_days` -> `Item.custom_manufacturing_lead_days` -> fallback 14 gün).
   - **Hammadde Stok Kontrolü (Material Availability):** Seçilen taslak iş emrinin reçetesindeki tüm alt bileşenler için kaynak depodaki anlık stok (`actual_qty`) ile gereken miktarı (`required_qty`) kıyaslayan, parça bazında karşılama oranını (% ve miktar) gösteren net bir matris.
   - **Rezervasyon & Tüketim Mekaniği:** İş emri serbest bırakıldığında (Release / `docstatus=1`), ERPNext standart motoru ilgili depodaki `Bin.reserved_qty_for_production` miktarını artırarak hammaddeyi rezerve eder. `Operations` sekmesinden operasyon teyidi verilip backflush malzeme tüketimi (`Material Consumption for Manufacture`) yapıldığında, `wo_item.consumed_qty` artar ve rezervasyon miktarı otomatik olarak düşer (`Bin.reserved_qty_for_production = required_qty - consumed_qty`). Ters kayıt (storno) yapıldığında ise rezervasyon otomatik olarak eski haline döner.
   - **Serbest Bırakma (Release):** İş emrini onaylayarak (`Submit`) üretim iş kartlarını (Job Card) üretime hazır hale getirme.
     - Stok tam ise: Doğrudan onay ve serbest bırakma.
     - Stok eksik ise: "Uyarı ile İzin" (Allow with Warning). Eksik parçalar uyarı penceresinde gösterilir; yetkili onaylarsa iş emrindeki `custom_released_with_shortage` alanı `1` yapılır ve eksik parça detayları Frappe aktivite geçmişine (Comment) yazılır.
   - **İşlem Sonrası Akış:** Release işleminden sonra ekran mevcut `Work Orders` sekmesinde kalır ve kullanıcıya başarı bildirimi verilir.
3. **Operations Görünümü:**
   - Mevcut hazırlanan tek ekranlı operasyon teyidi, hurda, çoklu stok fişi ve ters kayıt (storno) kokpiti bu sekme altında yer alır.
   - Sol çekmecede sekmeye özel filtreleme uygulanır: `Operations` sekmesinde **yalnızca serbest bırakılmış** (Not Started / In Process) iş emirleri listelenir; Taslaklar yer almaz.
4. **Çekmece ve Sekme Davranışı:**
   - `Work Orders` sekmesinde sol çekmece: Tümü, Taslak ve Serbest Bırakılan filtrelerini barındırır.
   - `Operations` sekmesinde sol çekmece: Yalnızca Tümü (aktif olanlar), Devam Eden ve Tamamlananları listeler.

### 2.2 Kapsam Dışı (Non-Goals)
- Standart ERPNext Reçete (BOM) oluşturma veya düzenleme ekranını Shopfloor Hub'a taşımak.
- Kapasite planlama (CRP) veya çizelgeleme (Gantt) algoritmalarını bu aşamada buraya dahil etmek.

### 2.3 Anti-Hedefler (Anti-Goals)
- **Aşırı Karmaşıklaştırılmış Form:** Standart Frappe Work Order formundaki onlarca alanı operatörün önüne yığmak.
- **Katı / Engelleyici Blokaj:** Hammadde depoda eksik olsa bile hattı kilitlemek yerine hat liderine inisiyatif verip eksik ile serbest bırakmaya izin vermek.

---

## 3. Kısıtlamalar (Constraints)

1. **Geriye Dönük Uyumluluk:** Standart ERPNext Work Order veya Stock Entry iş akışları etkilenmemeli; standart yoldan açılan iş emirleri de Shopfloor Hub'da sorunsuz listelenebilmeli ve teyit edilebilmelidir.
2. **Mimari & Kurallar:**
   - `.agents/AGENTS.md` gereği hiçbir DocType Türkçe adla oluşturulamaz.
   - Arayüz metinleri TR, EN ve DE dillerine uygun translation wrapper'ları (`__('Text')`) ile sarılmalıdır.
   - Frontend derlemesi `bench build --app erpnextkta --production` kuralına tam uymalıdır.
   - Frontend TypeScript (`<script setup lang="ts">`) standardında kalmalıdır.

---

## 4. Değerlendirilen Yaklaşımlar (Approaches)

### Yaklaşım 1: Sol Çekmeceyi Koruyan Entegre Çift Mod (SEÇİLEN)
- **Açıklama:** Sol taraftaki `WorkOrderSidebar` bileşeni her iki görünümde de ortak omurga olarak kalır. Sekmeye göre filtre içeriği dinamik uyarlanır.
- **Çalışma Şekli:**
  - `Work Orders` sekmesinde sol çekmecenin üstünde `[ + Yeni İş Emri Aç ]` butonu ve `Taslak` sekmesi yer alır. Seçilen taslak için sağ alanda "Hammadde Stok Uygunluk Matrisi" ve `[ 🚀 Release ]` aksiyonu gösterilir.
  - `Operations` sekmesinde sol çekmeceden taslaklar filtrelenir; yalnızca üretime hazır emirler listelenerek teyit akışı sunulur.
- **Tercih Sebebi:** Ekranın mevcut ergonomik dengesini korur, gereksiz sayfa sıçramalarını önler ve atölye zeminine en uygun akışı sağlar.

### Yaklaşım 2: Bağımsız Tam Ekran Liste & Wizard Masası (ELENDİ)
- **Açıklama:** `Work Orders` sekmesine geçildiğinde sol çekmece gizlenir, ekran büyük bir tabloya dönüşür.
- **Elenme Sebebi:** İki sekme arasında sayfa düzeninin radikal biçimde değişmesi kullanıcı deneyimini bozar.

---

## 5. Detaylı Tasarım ve Bileşen Mimarisi

### 5.1 Navigasyon Çubuğu (`ShopfloorNavbar.vue`)
- `[ ⚡ Work Orders ]` (Aktif / Pasif durum)
- `[ 📋 Operations ]` (Aktif / Pasif durum)
- Sağ üstte profil/dil bilgisi bulunmaz; temiz ve minimalist tasarım.

### 5.2 Work Orders Görünümü Bileşenleri

#### A. Hızlı İş Emri Açma Modali (`CreateWorkOrderModal.vue`)
- **Temel Alanlar:**
  - Mamul Kodu (`production_item`): Arama ve otomatik tamamlama.
  - Miktar (`qty`): Sayısal alan.
- **Gelişmiş Seçenekler Akordeonu (Varsayılan kapalı):**
  - Reçete (`bom_no`): Mamul seçilince otomatik varsayılan BOM yüklenir; gerekirse değiştirilebilir.
  - Depolar (`source_warehouse`, `wip_warehouse`, `fg_warehouse`).
  - Planlanan Başlangıç / Bitiş Tarihleri.
- **Aksiyon:** `[ Taslak Olarak Kaydet ]` -> Backend API `create_work_order` çağrılır, yeni iş emri Draft statüsünde listeye eklenir.

#### B. Hammadde Uygunluk Matrisi & Release Paneli (`WorkOrderReleasePanel.vue`)
- Seçili iş emri için `check_material_availability(work_order)` çağrılır.
- **3 Kademeli Stok ve Hat Besleme Modeli (Ek Özellik):**
  - **Hattaki Net Kullanılabilir Stok:** $\text{line\_available\_qty} = \max(0, \text{Bin.actual\_qty} - \text{Bin.reserved\_qty\_for\_production})$ (açık üretim rezervasyonları düşülür, arayüzde rezerve miktar `(Rezerve: {0})` olarak sunulur).
  - **Diğer Fabrika Depoları Görünürlüğü (Plant-Wide Visibility):** Şirketin diğer tüm aktif, grup-olmayan depolarındaki kullanılabilir serbest stoklar sorgulanır ve `other_warehouses_qty` sütununda depo bazlı döküm tooltip'i ile gösterilir.
  - **3 Kademeli Durum Sınıflandırması:**
    1. `available` (✅ Hatta Mevcut): `line_available_qty >= required_qty`.
    2. `transfer_required` (⚠️ Transfer Edilebilir): `line_available_qty + other_warehouses_qty >= required_qty`. Malzemeler Merkez/Diğer depolardan hat transferiyle temin edilebilir.
    3. `critical_shortage` (🚫 Fabrikada Yok): `line_available_qty + other_warehouses_qty < required_qty`. Fabrika genelinde temin edilemeyen kritik hammadde eksikliği.
- **Dinamik Durum Banner'ı:** Kritik eksiklik, transfer edilebilir veya tam hazır olma durumuna göre renkli rehber banner'lar görüntülenir.
- **Kart Başlığı:** İş Emri No, Mamul, Miktar, Durum, Genel Hazır Olma Yüzdesi (Örn: `%100 Hazır` veya `⚠️ %65 Hazır - 2 Kalem Eksik`).
- **Malzeme Tablosu:**
  - Sütunlar: Hammadde (Bileşen Kodu ve Açıklama), İhtiyaç Miktarı, Hatta (Tüketim Deposu), Diğer Depolarda, Karşılama Oranı %, Durum Rozeti (✅ Hatta Mevcut / ⚠️ Transfer Edilebilir / 🚫 Fabrikada Yok).
- **Release Butonu:** `[ 🚀 İş Emrini Serbest Bırak (Release) ]`
  - Stok tam ise: Onay diyaloğu -> `release_work_order(work_order)` -> İş Emri submit edilir.
  - Stok eksik ise: Eksik Parça Uyarısı Modali (transfer edilebilirlik notuyla) -> "Yine de Serbest Bırak" onayı -> `release_work_order(work_order, allow_shortage=1)`:
    - Work Order üzerinde `custom_released_with_shortage = 1` yapılır.
    - Frappe aktivite geçmişine detaylı eksik malzeme tablosu yorum olarak eklenir.
  - Sonuç: Başarı bildirimi görüntülenir, ekran `Work Orders` görünümünde kalır.

### 5.3 Backend API Kontratı (`erpnextkta/kta_shopfloor/api.py`)

1. `get_item_default_bom(item_code: str) -> dict`:
   - Mamulün varsayılan BOM'unu, UOM'unu, temel verilerini ve çözümlenen imalat süresini (`manufacturing_lead_days`) döner.
2. `create_work_order(item_code: str, qty: float, bom_no: str = None, source_warehouse: str = None, fg_warehouse: str = None, planned_start_date: str = None, planned_end_date: str = None) -> dict`:
   - Standard ERPNext Work Order dokümanını `Draft` statüsünde oluşturur. `planned_end_date` girilmemişse `planned_start_date + manufacturing_lead_days` otomatik atanır.
3. `check_material_availability(work_order: str) -> dict`:
   - `required_items` üzerinden kaynak depodaki `Bin.actual_qty` verilerini tarar, genel yüzdeyi ve kalem bazlı eksiklikleri hesaplar.
4. `release_work_order(work_order: str, allow_shortage: int = 0) -> dict`:
   - İş emrini kontrol eder, eksiklik varsa ve `allow_shortage=1` ise `custom_released_with_shortage` alanını ve aktivite yorumunu işler; ardından `wo.submit()` ile onaylar.

### 5.4 Şema Değişiklikleri
- `Work Order` DocType'ına (`erpnextkta/erpnextkta/custom/work_order.json`):
  - `custom_released_with_shortage` (Check, label: "Eksik Parça ile Serbest Bırakıldı", read_only: 1).
- `Item` DocType'ına (`erpnextkta/kta_mrp/custom/item.json`):
  - `custom_manufacturing_lead_days` (Int, label: "Üretim Süresi (Gün)", default: 14).

---

## 6. Geliştiriciye Bırakılan Detaylar
- Sekme geçiş animasyonları ve CSS detayları.
- Malzeme matrisinde tablo responsive kaydırma tasarımı.
