# Sistem Kalıpları: kta_quality

## Mimarisi
`kta_quality` modülü, Frappe Framework üzerine inşa edilmiş olup, standart ERPNext iş akışlarını KTA'ya özel kontrol listeleriyle genişletir.

## Ana Teknik Desenler

### 1. Otomatik Veri Doldurma (Seed Matching)
`TestMasasiDogrulamaKaydi` dokümanı oluşturulurken, operatörün hatalı veya eksik madde girmesini önlemek için sabit kriterler otomatik olarak eklenir.

- **Hook:** `before_insert`
- **Metot:** `_doldur_sabit_satirlar`
- **Sabitler:**
    - `SABIT_KRITERLER`: Test masası güvenliği vePoke-Yoke ile ilgili 17 madde.
    - `BAGLANTI_NOKTASI_SATIRLAR`: Kilit sistemi, Poke-Yoke, Board görselleri gibi teknik kontrol alanları.

### 2. Form Doğrulaması ve Metin Yönetimi
`validate` metodu kullanılarak, dokümana otomatik olarak uzun bir "Uygulama Metni" (PTR form referansları içeren bilgilendirme) atanır. Bu, dokümanın her zaman yasal ve prosedürel gerekliliklere uygun basılmasını sağlar.

### 3. Çapraz Modül Veri Senkronizasyonu (Sync Logic)
Test masası doğrulaması yapıldığında, bu sonucun ilgili üretim kartına (`Calisma Karti`) anlık olarak yansıtılması gerekir.

- **Desen:** Event Hooks (`after_insert`, `on_update`, `on_submit`)
- **İşleyiş:** `calisma_karti_ref` alanı doluysa, `Calisma Karti` üzerindeki `test_masasi_dogrulama_kaydi` alanı bu dokümanın ID'si ile güncellenir.
- **Kod Örneği:**
  ```python
  def on_update(self):
      if self.calisma_karti_ref:
          frappe.db.set_value("Calisma Karti", self.calisma_karti_ref, "test_masasi_dogrulama_kaydi", self.name)
          frappe.db.commit()
  ```

### 4. Krimp Teknik Veri Hiyerarşisi (Gelecek Vizyonu)
Krimp operasyonlarında veri doğruluğunu sağlamak için "Ansiklopedi vs. Uygulama" katmanlı yapısı benimsenmiştir:

- **Katman 1: KTA Krimp Book (Referans/Ansiklopedi):** Üretici kataloglarından gelen 1548+ kayıtlık devasa veri kümesi. Statiktir ve genel standartları tutar.
- **Katman 2: KTA Krimp Yukseklik Parametreleri (Onaylı Uygulama):** Belirli bir kablo grubu ve fiziksel kalıp (`Amboss Takımı`) seti için onaylanmış süreç standardı. `Krimp Book`'tan veri koparılıp burada "Submit" edilerek dondurulur.
- **İlişki Mantığı:** Gelecekte `Krimp Book`'taki metin (Data) bazlı kalıp isimleri, `KTA Amboss Takimlari` asset kayıtlarına `Link` ile bağlanarak tam bir izlenebilirlik sağlanacaktır.

### 5. Çapraz Modül Tolerans Doğrulama Deseni (Cross-Module Tolerance Validation)
`kta_calisma_karti` üzerinde krimp ölçüm değerleri girildiğinde, doğru limitleri doğrulamak için `kta_quality` altındaki kütüphane verileri kullanılır:
- **Tetikleyici**: `Calisma Karti` krimp ölçümleri kaydedilirken veya validate edilirken.
- **Akış**: `Calisma Karti` bileşeni, `kta_quality` modülünün `KTA Krimp Book` veritabanı tablosuna (kesit, kablo tipi, kontak no baz alınarak) sorgu atar. Bulunan min/maks limit değerlerini kendi UI segment göstergesinde ve backend validation adımında kullanarak ölçülen değerin standartlara uygunluğunu denetler.

## Veri İlişkileri
- **Ebeveyn:** `TestMasasiDogrulamaKaydi`
- **Çocuk Tablolar:**
    - `degerlendirme_kriterleri` (DocType: `Degerlendirme Kriteri`)
    - `baglanti_noktasi_tablosu` (DocType: `Baglanti Noktasi Satiri`)
- **Referans:** `Calisma Karti` (Linked via `calisma_karti_ref`)
- **Teknik Kitaplık:** `KTA Krimp Book` (Referans veri kaynağı)
