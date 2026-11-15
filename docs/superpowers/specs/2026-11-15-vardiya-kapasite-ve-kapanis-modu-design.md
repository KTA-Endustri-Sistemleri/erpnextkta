# Tasarım Dokümanı: Vardiya Kapasite Modu ve Operatör Kontrolü (Faz 1 Genişletilmiş)

- **Tarih:** 2026-11-15
- **Durum:** Onay Bekliyor
- **Kapsam:** `erpnextkta/kta_calisma_karti` (Settings, Calisma Karti, Tasks, Translations, Tests)

---

## 1. Amaç ve Neden

Mevcut sistemde operatörlerin net çalışma süresi 430 dakikalık vardiya kapasite kotasıyla (`hesapla_toplam_sure` ve `_calculate_remaining_shift_capacity`) sınırlandırılmakta, süreler tırpanlanmakta ve arka planda `FOR UPDATE` ile kart kilitleri alınmaktadır. Ayrıca vardiya bitimlerinde (16:15 ve 00:15) açık kalan kartlar `auto_close_timed_out_cards` ile zorla kapatılmaktadır.

Bu durum hem raporlarda operatörlerin gerçek eforunun görünmesini engellemekte hem de gereksiz veritabanı kilitlerine yol açmaktadır. Kullanıcı, mevcut düzeni hiç bozmadan tek tıkla süreyi ve kart yönetimini tamamen operatörün fiili hareketlerine bırakmak istemektedir.

---

## 2. Hedefler, Kapsam Dışı ve Anti-Hedefler

### Hedefler
- **H1:** `KTA Calisma Karti Settings` içindeki tek bir check (`vardiya_kapasite_sinirini_devre_disi_birak`) ile 430 dk kota kesintisini ve kilitli sorguları tamamen devre dışı bırakmak; karta fiili net süreyi (`toplam - durus`) yazmak.
- **H2:** Bu check işaretlendiğinde arayüzde `max_kart_suresi_dk` (dakika girilen alan) `depends_on` ile gizlenmek.
- **H3:** İkinci bir check (`vardiya_sonu_otomatik_kapatmayi_devre_disi_birak`) ile 16:15 ve 00:15 cron otomatik kapatmasını devre dışı bırakabilmek; kart kapatma inisiyatifini tamamen operatöre vermek.
- **H4:** Ayarlar kapalıyken (`0` veya henüz kaydedilmemiş) mevcut çalışan tüm süre, vardiya ve otomatik kapanış davranışlarını %100 korumak (sıfır regresyon).

### Kapsam Dışı ve Korunan Yapılar
- OEE hesaplamaları ve yetkinlik kontrolleri (Faz 2 ve Faz 3).
- `_auto_pause_other_active_cards` mantığını kaldırmak (operatörün aynı anda iki kartta aktif çalışmaması kuralı korunur).
- **Job Card Adet Paylaştırma Algoritması (`distribute_completed_qty`):** Kodda hiçbir değişiklik yapılmaz. Job Card `time_logs` tablosuna Çalışma Kartı'nın fiili net süresi (`to_time = baslangic + net`) gitmeye devam eder; Job Card miktarı (`for_quantity`) satırların net süreleri oranında (`row_weight = time_in_mins / total_time_in_mins`) zamana orantılı paylaştırılmayı birebir sürdürür. Hatta suni 430 dk kesintisi kalktığı için adet dağılımı operatörün gerçek eforuyla tam örtüşür.

### Anti-Hedefler
- Deploy sonrası ayar hiç kaydedilmemişken varsayılan davranışın sessizce değişmesi.
- Kart tablosuna gereksiz yeni süre alanları eklemek (ham süre `toplam - durus` formülünden türetilir).

---

## 3. Değerlendirilen Yaklaşımlar ve Seçim

| Yaklaşım | Açıklama | Avantaj / Dezavantaj | Durum |
|---|---|---|---|
| **Yaklaşım 1 (Seçilen)** | Bağımsız iki ayar (`vardiya_kapasite_sinirini_devre_disi_birak` + `vardiya_sonu_otomatik_kapatmayi_devre_disi_birak`) ve `depends_on` dinamik gizleme. | Tam operasyonel esneklik sağlar; kota kesilmezken otomatik kapanış açık tutulabilir veya her ikisi birden kapatılabilir. | **Kullanıcı tarafından seçildi** |
| **Yaklaşım 2** | Tek şemsiye check ("Operatör Serbest Modu"). | Tek tık avantajı vardır ancak süre kotası ile cron kapanışını birbirinden ayırma esnekliğini yok eder. | Elendi |

---

## 4. Detaylı Teknik Şartname

### 4.1. KTA Calisma Karti Settings
- **`vardiya_kapasite_sinirini_devre_disi_birak`**:
  - `fieldtype`: `Check`
  - `default`: `"0"`
  - `label`: `"Vardiya Kapasite Sınırını Devre Dışı Bırak"`
  - `description`: `"İşaretlenirse operatörün vardiya içindeki toplam net süresi Maksimum Çalışma Kartı Süresi ile sınırlandırılmaz; kartlara fiili net süre yazılır."`
  - Konum: `kart_uyari_suresi_dk` alanının hemen altı.
- **`max_kart_suresi_dk` Güncellemesi**:
  - `depends_on`: `"eval:!doc.vardiya_kapasite_sinirini_devre_disi_birak"`
  - Check 1 olduğunda Desk arayüzünde dakika girilen bu alan dinamik olarak gizlenir.
- **`vardiya_sonu_otomatik_kapatmayi_devre_disi_birak`**:
  - `fieldtype`: `Check`
  - `default`: `"0"`
  - `label`: `"Vardiya Sonu Otomatik Kapatmayı Devre Dışı Bırak"`
  - `description`: `"İşaretlenirse vardiya bitimlerinde (16:15 ve 00:15) açık kalan kartlar sistem tarafından otomatik kapatılmaz; kart kapatma kontrolü tamamen operatörde kalır."`
  - Konum: `timeout_durus_nedeni` alanının hemen altı.

### 4.2. `calisma_karti.py` Süre Algoritması
- `_kapasite_siniri_devre_disi_mi() -> bool`:
  `bool(cint(frappe.db.get_single_value("KTA Calisma Karti Settings", "vardiya_kapasite_sinirini_devre_disi_birak")))`
- `_apply_shift_cap(self, start_dt, raw_net_saniye) -> float`:
  - Ayar aktifse: doğrudan `raw_net_saniye` döner. `get_kta_settings` ve `_calculate_remaining_shift_capacity` çağrılmaz (DB kilitleri ve vardiya sorguları atlanır).
  - Ayar pasifse: `min(raw_net_saniye, self._calculate_remaining_shift_capacity(start_dt, max_saniye))` döner (mevcut davranış).
- `hesapla_toplam_sure()`:
  - `raw_net_saniye = max(0, toplam_saniye - toplam_durus_saniye)`
  - `net_saniye = self._apply_shift_cap(start_dt, raw_net_saniye)`

### 4.3. `tasks.py` Otomatik Kapatma Görevi
- `auto_close_timed_out_cards()` fonksiyonu başlangıcında:
  ```python
  if cint(frappe.db.get_single_value("KTA Calisma Karti Settings", "vardiya_sonu_otomatik_kapatmayi_devre_disi_birak")):
      frappe.logger().info("auto_close_timed_out_cards: disabled in settings, skipping.")
      return
  ```

### 4.4. Çeviriler (`en.csv`, `de.csv`)
Tüm yeni etiket ve açıklamalar Title Case kuralına uygun olarak eklenir.

### 4.5. Test Altyapısı ve Zengin Log Formatı (`test_utils.py`)
- `KTATestCase.setUp()` metodunda log formatı hiyerarşik hale getirilir:
  `🔍 [TEST] [<modül_adı>] [<metot_adı>]: <açıklama>`
  (Örn: `🔍 [TEST] [kta_calisma_karti] [test_setting_saved_true_disables_cap]: ...`)
- `setup_kta_infrastructure()` içine yeni ayarların sıfırlanması eklenir:
  - `vardiya_kapasite_sinirini_devre_disi_birak = 0`
  - `vardiya_sonu_otomatik_kapatmayi_devre_disi_birak = 0`
  Böylece her entegrasyon testi temiz bir varsayılan ortamda başlar.
- `test_calisma_karti_unit.py` sınıfları da bu loglama standardına bağlanarak tüm unit test çıktılarının kapsamlı görünmesi sağlanır.

---

## 5. Doğrulama ve Test Planı
1. **`test_unsaved_setting_keeps_cap`**: Ayar hiç kaydedilmemişken 430 dk sınırı ve kilitli hesaplama aktif kalır.
2. **`test_cap_disabled_skips_cap`**: Ayar 1 iken `_other_cards_net_seconds_in_shift` çağrılmaz, net süre ham süredir.
3. **`test_cap_disabled_excludes_active_downtime`**: Sınır kapalıyken de açık duruş süresi net süreden düşülür.
4. **`test_mode_switch_recomputes_open_card`**: Açık kart mod değiştiğinde doğru net süreye güncellenir.
5. **`test_auto_close_disabled_skips_processing`**: Otomatik kapatma ayarı aktifken cron kartlara dokunmaz.
6. **Mevcut regresyon testleri**: `test_shift_capacity_cap`, `test_total_duration_multiple_downtimes` değişmeden geçmelidir.

---

## 6. Sıradaki Adım
Bu tasarım onaylandıktan sonra `superpowers:writing-plans` becerisi çağrılarak adım adım uygulama planı (`docs/superpowers/plans/...`) güncellenecektir.
