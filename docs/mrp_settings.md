# KTA MRP Ayarları (KTA MRP Settings)

Tüm KTA MRP motorunun, kapasite dengeleme matematiğinin, planlama ufkunun ve stok kurallarının tek bir merkezden yönetildiği sistem kontrol paneli.

---

## 1. Neden Merkezi Ayarlar?

Eski sistemde kapasite dengeleme ve ramp-up gibi ayarlar her kullanıcının rapor ekranındaki filtre çubuğunda ayrı ayrı yer almaktaydı. Bu durum şu kritik sorunlara yol açıyordu:
* Kullanıcılar farklı filtre kombinasyonları seçtiğinde raporlar arasında tutarsız sonuçlar oluşabiliyordu.
* Arka planda çalışan veya otomatik tetiklenen motor servisleri hangi parametreyi baz alacağını bilemiyordu.
* Kapasite kuralı gibi fabrika geneli stratejik bir karar son kullanıcının anlık inisiyatifine bırakılmıştı.

`KTA MRP Settings` (Single DocType) oluşturularak tüm matematiksel parametreler merkezi bir yönetim odasına taşınmıştır. Rapor filtrelerinden gereksiz teknik kutular temizlenmiş ve tüm MRP ekosisteminin aynı kurallarla tek bir gerçeklik (Single Source of Truth) üzerinden çalışması sağlanmıştır.

---

## 2. Ayar Parametreleri Sözlüğü

### 2.1 Kapasite & Dengeleme Parametreleri

| Parametre | Tip / Varsayılan | Açıklama ve Üretim Üzerindeki Etkisi |
| :--- | :--- | :--- |
| **enable_capacity_leveling** | Check / **1 (Açık)** | Kapasite aşımı olan haftalardaki fazla üretim yükünün sonraki haftalara ileriye doğru (Forward Scheduling) aktarılmasını sağlar. |
| **enable_ramp_up** | Check / **0 (Kapalı)** | Geriye Doldurma (Backward Fill) ve Ramp-up (Akıllı Yumuşatma) aşamalarını devreye alır. |
| **default_rampup_weeks** | Int / **3 Hafta** | Ramp-up algoritmasının yoğun bir haftanın yükünü en fazla kaç hafta öncesine kadar yayabileceğini belirler. |
| **rampup_trigger_utilization** | Percent / **%85** | Bir haftanın kapasite doluluğu bu oranın üzerine çıktığında ramp-up yumuşatma mekanizması devreye girer. |
| **rampup_max_capacity_limit** | Percent / **%95** | Geriye çekilen yükün, hedef önceki haftayı en fazla ne kadar doldurabileceğini belirler. |
| **min_smoothing_qty** | Int / **10 Adet** | Geriye yayma yapılırken taşınacak miktarın alt sınırıdır. Çok küçük adetlerin parçalanmasını önler. |

### 2.2 Planlama Ufku & Zaman Parametreleri

| Parametre | Tip / Varsayılan | Açıklama ve Üretim Üzerindeki Etkisi |
| :--- | :--- | :--- |
| **planning_horizon_days** | Int / **90 Gün** | Raporlar açıldığında Bitiş Tarihi (to_date) bu gün sayısı eklenerek otomatik getirilir (Örn: 180 gün seçildiğinde 6 aylık ufukla açılır). |
| **backlog_lookback_days** | Int / **270 Gün** | Geçmişten sarkan, teslimatı gecikmiş açık satış siparişlerinin geriye doğru taranma günü. |
| **default_production_time_days** | Int / **14 Gün** | Tanımlı özel bir üretim süresi bulunamadığında geriye düşülecek standart üretim süresidir. |
| **default_delivery_time_days** | Int / **2 Gün** | Adres, Müşteri veya Müşteri Grubu kartında süre eşleşmezse kullanılan varsayılan lojistik nakliye/sevk süresidir. |
| **urgent_shortage_weeks** | Int / **4 Hafta** | Malzeme İhtiyaç Raporunda "İlk Eksik Hafta" için kırmızı alarm rozetinin verileceği hafta sınırıdır. |

### 2.3 Depo & Satınalma Parametreleri

| Parametre | Tip / Varsayılan | Açıklama ve Üretim Üzerindeki Etkisi |
| :--- | :--- | :--- |
| **available_warehouse_type** | Link / **Kullanılabilir Stok** | MRP motorunun fiziksel ve rezerve stok hesaplarken dikkate alacağı depoların tipidir. Hurda, karantina veya transit depoları hesaba katılmaz. |
| **default_include_po** | Check / **1 (Açık)** | Malzeme İhtiyaç netleştirmesinde açık PO'ların varsayılan olarak dahil edilip edilmeyeceğini belirler. |
| **wo_consumption_strategy** | Select / **Anlık Stok Rezervasyonu (Klasik)** | İş emirlerinin hammadde ihtiyacının ve ambar stok rezervasyonlarının nasıl yönetileceğini belirleyen tek ve merkezi parametredir (Klasik peşin rezervasyon veya haftalık kapasite planına göre zaman fazlı tüketim). |
| **antrepo_clearance_days** | Int / **4 Gün** | Antrepodaki mallar gümrüklemeye alındığında millileşme için gereken operasyonel tampon süredir. MRP motoru bu süreyi ekleyerek serbest stoka katılım haftasını belirler. |

#### ⚡ `wo_consumption_strategy` (İş Emri Malzeme Tüketim Stratejisi) Modları:
Fabrikanın iş emri hammadde tüketimini, stok rezervasyonlarını ve satınalma tetikleme dinamiğini tek bir merkezden yöneten temel parametredir:
- **Anlık Stok Rezervasyonu (Klasik):** Açık iş emirlerinin tüm reçetesi oluşturulduğu gün (W0) serbest stoktan peşin düşülür (`Bin.reserved_qty_for_production`). İmalat süresi haftalara yayılsa dahi hammadde W0'da bloke edilir ($\text{Net Serbest Stok} = \text{Mevcut Stok} - \text{İş Emri Rezervasyonu}$) ve açık iş emirlerinin malzemeleri güvenceye alınır.
- **Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı):** Açık iş emirleri ambar stokunu peşin kilitlemez. Rezervasyonlar ambar stokundan peşin düşülmek yerine, fabrikanın haftalık kapasite planındaki üretim hızına (ör. haftalık 7.000 adet tavanı) ve imalat sürelerine (Lead Time) göre zaman fazlı tüketilir. Bu sayede 2 haftalık erken satın alma baskısı ve ortak hammaddeli kardeş ürünlerin malzeme kilitlenmeleri önlenir.

---

## 3. Yetkiler ve Erişim

* ERPNext arama çubuğuna **KTA MRP Settings** yazılarak ayarlara ulaşılabilir.
* Bu sayfadaki parametreler sadece **Manufacturing Manager** ve **System Manager** rolleri tarafından düzenlenebilir.
