# Teknik Bağlam: kta_quality

## Teknolojiler
- **Frappe Framework:** Modülün Python backend ve JS frontend kısmını yönetmek için kullanılır.
- **MariaDB:** `kta_quality` altındaki DocType verilerinin saklandığı veritabanı.
- **Python / Javascript:** Sunucu tarafı ve istemci tarafı mantıkları (validation, UI güncellemeleri) için kullanılır.

## Geliştirme Ortamı Kurulumu
Bu modül `erpnextkta` uygulamasının bir parçasıdır. Geliştirme yapmak için:
1. Frappe-bench ortamının kurulu olduğundan emin olun.
2. `erpnextkta` uygulamasının yüklü olduğunu kontrol edin.
3. DocType değişikliklerinden sonra `bench migrate` komutunu çalıştırın.

## Teknik Kısıtlamalar ve Bağımlılıklar
- **Bağımlılık:** `TestMasasiDogrulamaKaydi`, `Calisma Karti` DocType'ına referans verir. Bu nedenle `kta_calisma_karti` modülü kurulu olmadan tam fonksiyonel çalışmaz.
- **Kısıtlama:** Test masası kriterleri (SABIT_KRITERLER) şu an için kod seviyesinde (`.py` dosyası içinde) tanımlıdır; veritabanı üzerinden dinamik olarak yönetilemez. Bu maddeler değişecekse Python kontrolcüsünde (`test_masasi_dogrulama_kaydi.py`) güncelleme yapılması gerekir.

## Veri Yapısı (Schema) Summary
- **TestMasasiDogrulamaKaydi (Ana)**: `calisma_karti_ref`, `tarih`, `kontrol_eden`, `uygulama_metni` gibi alanları barındırır.
- **degerlendirme_kriterleri (Child Table)**: `sira_no`, `kriter_metni`, `cevap` (Evet/Hayır/NA) alanlarını barındırır.
- **baglanti_noktasi_tablosu (Child Table)**: `sira_no`, `tanim`, `durum` alanlarını barındırır.
