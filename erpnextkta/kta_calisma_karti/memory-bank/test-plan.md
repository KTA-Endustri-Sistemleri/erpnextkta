# 🧪 KTA Çalışma Kartı - Test Planı (Gece Vardiyası Geliştirmeleri)

Bu doküman, gece boyunca geliştirilen özelliklerin doğrulanması için kullanılacak bir checklist (kontrol listesi) barındırır. Herhangi bir maddeyi test ettiğinizde bildirebilir, `[x]` olarak işaretleyebilirsiniz.

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
