# 🧪 KTA Çalışma Kartı - Test Planı (Gece Vardiyası Geliştirmeleri)

Bu doküman, geliştirilen özelliklerin doğrulanması için kullanılan checklist'leri ve **Otomatik Entegrasyon Testlerini** barındırır.

---

## 🤖 0. Otomatik API Entegrasyon Testleri (`test_api.py`)
Aşağıdaki kritik uç noktalar artık `bench run-tests` ile otomatik olarak doğrulanmaktadır:
- [x] `test_islem_yap_workflow`: Kart durum geçişleri (Başlat/Duruş/Bitiş).
- [x] `test_qc_submission_via_api`: Kalite Muayene Belgesi entegrasyonu.
- [x] `test_scrap_synchronization_via_api`: Hurda ve Stok Girişi senkronizasyonu.
- [x] `test_alt_operasyon_crud_via_api`: Alt operasyon yönetimi.
- [x] `test_create_calisma_karti_double_click_protection`: Mükerrer kayıt koruması.
- [x] `test_manual_submission_without_bitis_fails`: Bitmemiş kart submission engeli.
- [x] `test_amend_flow`: İptal edilen kartı düzeltme (amend) akışı.
- [x] `test_user_dashboard_override`: Kullanıcı profili panelinde (User Dashboard) open count ve internal link listesi verilerinin doğrulanması.

---

## 🛡️ 10. Frontend Unit & Race Condition Testleri (Vitest)
Aşağıdaki senaryolar `npm run test` (Vitest) ile otomatik olarak doğrulanmaktadır:
- [x] **Race Condition (Enter Spam):** Barkod okutulurken Enter tuşuna basılı tutulduğunda (veya çok hızlı basıldığında) sadece ilk isteğin işlendiği, diğerlerinin `loading` guard tarafından reddedildiği.
- [x] **Race Condition (Click Spam):** "Oluştur" veya "Bitir" butonlarına API yanıtı gelmeden art arda basıldığında mükerrer API çağrısı yapılmadığı.
- [x] **Network Latency Simulation:** Ağ gecikmesi (örn: 2 saniye) simüle edildiğinde, bu süre zarfında gelen tüm kullanıcı girişlerinin dondurulduğu.
- [x] **Loading State Consistency:** Her başarılı veya hatalı işlem sonrası `loading` durumunun mutlaka `false`'a çekildiği (`finally` bloğu kontrolü).
- [x] **Wizard Step Consistency:** Adımlar arası geçişte `loading` aktifken barkod inputunun kilitlendiği.

---

## 🏗️ 1. Alt Operasyon ve Hammadde (Material Group) Kısıtları
- [ ] **Kısıtlı Seçim Testi:** Ana Operasyon / Alt Operasyon kayıtlarına malzeme grubu kısıtı (`100-Raw Material` vb.) tanımlanmış bir iş seçildiğinde, Arayüzde (Hammadde alanı) sadece o gruba ait malzemeler mi listeleniyor?
- [ ] **Kısıt Yokken (Fallback) Testi:** Alt operasyonda hiçbir malzeme grubu tanımlı değilken, Ana Operasyondaki gruplar geçerli oluyor mu? Her ikisi de boşsa tüm hammaddeler seçilebiliyor mu?

## 📏 2. IDC Ölçümleri (Yetki Esnetmesi ve Opsiyonel Alanlar)
- [ ] **Yetki (Role) Testi:** Sadece Operatör yetkisi olan (QC yetkisi olmayan) bir kullanıcı "Yeni IDC Ölçümü" girebiliyor mu?
- [ ] **Opsiyonel Alan Testi:** Yükseklik (mm) ve Çekme Kuvveti (N) alanları boş bırakıldığında sistem varsayılan olarak `0` atayıp ölçümü başarıyla kaydediyor mu?

## ♻️ 3. Hurda Kapsamının Genişletilmesi (Geçmiş Operasyonlar)
- [ ] **Geçmiş BOM Kapsamı Testi:** "3. Sıradaki" bir operasyonda hurda eklemek istendiğinde; sistem sadece 3. değil, geçmişteki 1. ve 2. operasyonların reçete kalemlerine de erişim (seçim) izni veriyor mu?

## ⚠️ 4. Concurrency (Anti-Double-Click / 30 Sn. Koruması)
- [ ] **Spam/Çift Tıklama Testi:** Yeni Çalışma Kartı (Create Calisma Karti) arayüzüne barkod okutulduğunda ve "Oluştur" butonuna seri halde 3-4 defa "Spam" yapıldığında, sistem mükerrer kayıt yaratmayıp tek bir kart içerisine mi yönlendiriyor?

## ⏸️ 5. Tekil Çalışma Kartı (Otomatik Duruş / Auto-Pause)
- [ ] **Auto-Pause (Duruş) Testi:** Operatör, açık unuttuğu ve çalışmaya devam eden bir kartı (OP-A) varken, yepyeni bir kart (OP-B) yaratıp Başlatırsa; "OP-A" kartı otomatik olarak *"Diger"* sebebiyle statüsünü "Duruşta" olarak güncelleyip kendi süresini donduruyor mu?

## ⏱️ 6. Sistem Limitleri (430 Dk. Tolerans ve Proaktif 400 Dk. Uyarısı)
- [ ] **Single Doctype Testi:** Frappe desk'te aratıldığında `KTA Calisma Karti Settings` tablosu ulaşılabiliyor ve içindeki değerler (430 / 400) değiştirilebiliyor mu?
- [ ] **400 Dakika Uyarısı Testi:** Kartın net çalışma süresi eşiği (İsterseniz ayarlardan 1 dk'ya düşürün) aştığında ve kaydedilmek istendiğinde tepeden kırmızı uyarı butonu fırlıyor mu?
- [ ] **Max Limit Testi:** Süre ne kadar uzun olursa olsun "Net Süre" hesaplamasının (ve raporlara yansımasının) Ayarlardaki Maksimum değeri (430) aşmadığı doğrulandı mı?

## 🧹 7. Vardiya Sonu Cron Job'lar (Arka Plan Silici ve Kapatıcı)
- [ ] **Zaman Aşımında Kapatma (16:15 / 00:15):** Süre sınırını fersah fersah aşmış kartlarda `bench execute erpnextkta.tasks.auto_close_timed_out_cards` komutu çalıştırıldığında kart otomatik olarak (sistem notu ile birlikte) limit süresinde kapatılıyor mu?
- [ ] **Geçersizleri Çöpe Atma (04:00):** +24 saattir `Hazır` statüsünde kalmış ve hiç başlatılmamış bir karta `bench execute erpnextkta.tasks.delete_old_unstarted_cards` komutu uygulandığında kart veritabanından tamamen (`frappe.delete_doc` ile) eziliyor mu?

## ⚡ 8. Frontend SQL Filtreleme (Client-Side'dan Server-Side'a Geçiş)
- [ ] **Arayüz (Load / Paginasyon) Testi:** Vue arayüzünde filtreler sekmesine, Arama (`q`) sekmesine VEYA sayfayı aşağı kaydırma (Load More) işlemine basıldığında sayfa asla takılmıyor, kilitlenmiyor ve hedef doğru veriyi (`network` üzerinden SQL aracılığıyla milisaniyelerde) ekrana yansıtıyor mu?
## 🛡️ 9. Standart Kalite Muayene (QC) Entegrasyonu
- [ ] **Şablon Algılama Testi:** Şablonu olan bir ürünün Çalışma Kartında "Onaylandı" butonuna basıldığında Kalite Muayene modalı otomatik olarak açılıyor mu?
- [ ] **Çoklu Şablon Testi:** Üçün birden fazla kalite şablonu (Quality Inspection Template) varsa, kullanıcıya modal başında seçim yaptırıyor mu?
- [ ] **Ölçüm Giriş ve Limit Testi:** Sayısal parametrelerde girilen değerler Low/High limit dışındaysa durum otomatik "Rejected" (Reddedildi) olarak değişiyor mu?
- [ ] **Belge Linkleme Testi:** Kayıt sonrası Çalışma Kartı üzerinde "Bağlı Kalite Belgesi" linki beliriyor mu ve tıklandığında doğru MAT-QA formuna yönlendiriyor mu?
- [ ] **Durum Senkronizasyon Testi:** Kalite muayenesi "Accepted" (Kabul) ise Çalışma Kartı Quality Control durumu "Onaylandı", "Rejected" ise "Reddedildi" olarak güncelleniyor mu?

## ⏸️ 11. Duruş "Diğer" Nedeni Açıklama Validasyonu
- [ ] **Frontend Prompt Testi**: Kart detay ekranında duruş başlat butonuna basılıp duruş sebebi olarak "Diger" seçildiğinde açıklama alanının kırmızı asteriks işaretiyle (`*`) zorunlu hale geldiği ve boş geçilmek istendiğinde hata mesajı vererek kaydı durdurduğu.
- [ ] **Backend Controller Testi**: API üzerinden duruş nedeni "Diger" olup açıklaması (`aciklama`) boş olan bir duruş satırı gönderildiğinde, backend `validate` hook'unun hata fırlatarak (frappe.throw) kaydı veritabanına işlemediği.

## 👤 12. User Dashboard Entegrasyonu
- [ ] **Kullanıcı Paneli Sayımı Testi**: Herhangi bir kullanıcı ile giriş yapılıp kendi User profili açıldığında, dashboard alanında "Aktivite" kartı altında "Çalışma Kartı" seçeneğinin belirdiği ve kullanıcının bağlı olduğu Employee kartı üzerinden open count sayısının (Açık ve biten toplam kart adedi) doğru yansıdığı.

## 📊 13. Günlük Performans/Hata Raporu ve Grafikler
- [ ] **Cron Job Gönderim Testi**: `bench execute erpnextkta.tasks.send_daily_calisma_karti_error_report` komutu çalıştırıldığında dünkü net çalışma süresi 5 saatin altında kalan operatörlerin listesini içeren HTML e-postasının başarıyla oluşturulup KTA Settings'te tanımlı alıcılara gönderildiği.
- [ ] **Dashboard Chart Hesaplama Testi**: "Operator Düşük Net Süre" grafiğinde, belirtilen gün filtresine göre operatörlerin çalışma dakikalarının doğru hesaplanıp en az çalışanların en üstte/grafikte listelendiği.

