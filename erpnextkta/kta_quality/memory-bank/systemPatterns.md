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

## Veri İlişkileri
- **Ebeveyn:** `TestMasasiDogrulamaKaydi`
- **Çocuk Tablolar:**
    - `degerlendirme_kriterleri` (DocType: `Degerlendirme Kriteri`)
    - `baglanti_noktasi_tablosu` (DocType: `Baglanti Noktasi Satiri`)
- **Referans:** `Calisma Karti` (Linked via `calisma_karti_ref`)
