---
trigger: always_on
---

# Module Memory Bank Management

Bu kural, modül bazlı dokümantasyonun (memory-bank) güncel tutulması ve okunması süreçlerini tanımlar.

## 1. Değişikliklerin Dokümante Edilmesi
Bir modül içindeki dosyalarda (kod, konfigürasyon, UI vb.) herhangi bir önemli değişiklik, mimari güncelleme veya hata düzeltmesi yaptığınızda, bu değişiklikleri mutlaka dokümante etmelisiniz.

## 2. Memory Bank Güncellemesi
Her modülün altında bir `memory-bank` dizini bulunabilir (örn. `erpnextkta/[modul_adi]/memory-bank/`).
- Yaptığınız değişikliklerle ilgili olarak, ilgili modülün `memory-bank` dizinindeki dokümanları güncelleyin.
- Eğer ilgili modül altında henüz bir `memory-bank` klasörü veya bağlama uygun bir doküman yoksa, bilgi kaybını önlemek adına bunu oluşturmalısınız.

## 3. Memory Bank'ten Okuma Yapılması
Herhangi bir modül üzerinde çalışmaya, değişiklik yapmaya veya yeni bir görev planlamaya başlamadan önce:
- O modülün altında bir `memory-bank` dizini olup olmadığını kontrol edin.
- Varsa, ilgili modülün mimarisini, davranış tiplerini ve iş kurallarını anlamak için görevle ilgili dokümanları **mutlaka** okuyun. 
- Ajanlar, her işlemde bu kuralları otomatik bir iş akışı olarak takip etmelidir.