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

| Parametre | Tip / Varsayılan | Açıklama ve Üretim Üzerindeki Etkisi |
| :--- | :--- | :--- |
| **enable_capacity_leveling** | Check / **1 (Açık)** | Kapasite aşımı olan haftalardaki fazla üretim yükünün sonraki haftalara ileriye doğru (Forward Scheduling) aktarılmasını sağlar. |
| **enable_ramp_up** | Check / **0 (Kapalı)** | Geriye Doldurma (Backward Fill) ve Ramp-up (Akıllı Yumuşatma) aşamalarını devreye alır. |
| **default_rampup_weeks** | Int / **3 Hafta** | Ramp-up algoritmasının yoğun bir haftanın yükünü en fazla kaç hafta öncesine kadar yayabileceğini belirler. |
| **rampup_trigger_utilization** | Percent / **%85** | Bir haftanın kapasite doluluğu bu oranın üzerine çıktığında ramp-up yumuşatma mekanizması devreye girer. |
| **rampup_max_capacity_limit** | Percent / **%95** | Geriye çekilen yükün, hedef önceki haftayı en fazla ne kadar doldurabileceğini belirler. |
| **min_smoothing_qty** | Int / **10 Adet** | Geriye yayma yapılırken taşınacak miktarın alt sınırıdır. Çok küçük adetlerin parçalanmasını önler. |
| **planning_horizon_days** | Int / **90 Gün** | Raporlar açıldığında Bitiş Tarihi (to_date) bu gün sayısı eklenerek otomatik getirilir (Örn: 180 gün seçildiğinde 6 aylık ufukla açılır). |
| **backlog_lookback_days** | Int / **270 Gün** | Geçmişten sarkan, teslimatı gecikmiş açık satış siparişlerinin geriye doğru taranma günü. |
| **default_production_time_days** | Int / **14 Gün** | Tanımlı özel bir üretim süresi bulunamadığında geriye düşülecek standart üretim süresidir. |
| **urgent_shortage_weeks** | Int / **4 Hafta** | Malzeme İhtiyaç Raporunda "İlk Eksik Hafta" için kırmızı alarm rozetinin verileceği hafta sınırıdır. |
| **available_warehouse_type** | Link / **Kullanılabilir Stok** | MRP motorunun stok ve rezerve hesaplarken dikkate alacağı depoların tipidir. |
| **default_include_po** | Check / **1 (Açık)** | Malzeme İhtiyaç netleştirmesinde açık PO'ların varsayılan olarak dahil edilip edilmeyeceğini belirler. |
| **antrepo_clearance_days** | Int / **2 Gün** | Antrepodaki mallar gümrüklemeye alındığında millileşme için gereken operasyonel tampon süredir. MRP motoru bu süreyi ekleyerek serbest stoka katılım haftasını belirler. |

---

## 3. Yetkiler ve Erişim

* ERPNext arama çubuğuna **KTA MRP Settings** yazılarak ayarlara ulaşılabilir.
* Bu sayfadaki parametreler sadece **Manufacturing Manager** ve **System Manager** rolleri tarafından düzenlenebilir.
