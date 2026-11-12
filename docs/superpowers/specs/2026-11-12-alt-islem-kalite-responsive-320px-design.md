# Responsive Design Spec: Alt İşlem ve Kalite Bileşenleri (<= 320px)

## 1. Intent & Why
320px ve altındaki ultra dar ekranlarda (özellikle depo/üretim sahasındaki el terminalleri, eski barkod okuyucu Android cihazlar ve küçük mobil ekranlar) Çalışma Kartı'nın **Alt İşlem** ve **Kalite** sekmelerinde bileşenlerin yatay taşma yapması (horizontal overflow / scroll) operatör ergonomisini bozmakta ve onay/düzenleme butonlarının ekrandan taşmasına neden olmaktadır. Bu tasarım, 320px ve altı çözünürlüklerde arayüzün %100 taşmasız, dikey yığınlanan (stacked), net ve okunabilir olmasını hedefler.

---

## 2. Goals, Non-Goals & Anti-Goals

### Goals
- **Sıfır Yatay Taşma:** 320px genişlikte `AltOperasyonView.vue`, `AltOperasyonKaliteSection.vue`, `EnjeksiyonSection.vue` ve `KrimpSection.vue` bileşenlerinde hiçbir öğenin ekran dışına taşmaması (`overflow-x: hidden / clip` zorlamadan doğal esneklikle sığması).
- **Kalıp Numarası Rozeti Optimizasyonu:** 10 haneli kalıp numarasının (`8718645633`) 22px dev kutu yerine başlığın altında/yanında kompakt bir çip (`🏷️ Kalıp: 8718645633`) olarak gösterilmesi. Kısa sıra no (`satir_no`: `1`, `2`) varsa sol kutuda gösterilmeye devam etmesi.
- **Dikey Yığınlama (`@media (max-width: 420px)`):**
  - Akordiyon başlıklarında ve mini item'larda aksiyon butonları (`Kalite Onayı Ver`, `Reddet`, `Düzenle`, `Sil`) alt satıra geçerek tam genişlikte (`width: 100%`) esnek yerleşmesi.
  - Açılır akordiyon butonunun (Chevron) başlık hizasında sağ üstte sabit kalması.
- **Ölçüm Izgarası (`.ck-enjeksiyon-grid`):** `<= 340px` ekranlarda kutu içi padding ve yazı tipi boyutlarının optimize edilmesi; metinlerin kutudan taşmasını önleyen `min-width: 0; word-break: break-word;` kurallarının uygulanması.

### Non-Goals
- Masaüstü veya tablet görünümünü değiştirmek (mevcut geniş ekran grid ve hiyerarşisi aynen korunur).
- Yeni backend API endpoint'i veya veritabanı şeması eklemek (bu tamamen bir frontend/CSS/Vue UI uyumluluk çalışmasıdır).

### Anti-Goals
- `overflow-x: scroll` veya yatay kaydırma çubukları eklemek (operatörün butonu görmek için sağa kaydırmak zorunda kalması kabul edilemez).
- Okunaksız derecede küçük fontlar (< 9px) kullanmak.

---

## 3. Constraints
- Framework: Vue 3 `<script setup lang="ts">`, Vanilla CSS (scoped).
- Build Rule: `bench build --app erpnextkta --production` komutuyla hatasız derlenmeli.
- Target Devices: 320px - 360px genişliğe sahip el terminalleri (Zebra, Honeywell, Chainway) ve mobil tarayıcılar.

---

## 4. Approaches Considered

### Yaklaşım 1 (Seçilen): Akıllı Kırılım, Dikey Yığınlama & Rozet İyileştirmesi
- **Detay:** 
  - `h.satir_no` varsa sol büyük rozette kalır; yoksa kalıp no başlığın altına çip olarak taşınır.
  - `@media (max-width: 420px)` ve `@media (max-width: 340px)` sorgularıyla flex satırları dikey sütuna (`column`) geçer.
  - Aksiyon butonları alt satırda tam genişlikte 2 sütunlu butonlara dönüşür.
- **Neden Seçildi:** Operatör kaydırma yapmadan tüm verilere ulaşır, butonlar büyük dokunmatik hedefler sunar, taşma tamamen sıfırlanır.

### Yaklaşım 2: Yatay Kaydırma (Horizontal Scroll)
- **Detay:** Kartları `overflow-x: auto` ile sarmalamak.
- **Neden Reddedildi:** Operatör "Kalite Onayı Ver" butonunu görebilmek için sağa kaydırmak zorunda kalır, ergonomi ve hız kaybına yol açar.

### Yaklaşım 3: İki Ayrı Template (Mobile vs Desktop)
- **Detay:** `v-if="isMobile320"` ile farklı DOM ağaçları render etmek.
- **Neden Reddedildi:** Kod tekrarı ve yüksek bakım maliyeti.

---

## 5. Implementation Details

### A. `AltOperasyonView.vue`
- Sol büyük kutu kontrolü: Sadece `h.satir_no` varsa 22px sol kutu render edilir. `h.kalip_no` başlığın altında `ck-mini-sub` veya kompakt bir rozet olarak kalır.
- `.ck-mini-item`: `@media (max-width: 420px)` için `padding: 10px 12px; flex-direction: column; align-items: stretch; gap: 8px;`.
- `.ck-mini-actions`: Mobilde `width: 100%; display: flex; gap: 6px;` ile butonlar `flex: 1` genişlik alır.

### B. `AltOperasyonKaliteSection.vue`
- Sol kutu: Sadece `h.satir_no` varsa render edilir; kalıp no içerik alanında gösterilir.
- `.ck-mini-item`: `@media (max-width: 480px)` için `flex-direction: column; align-items: stretch; gap: 10px;`.
- `.ck-mini-actions`: `@media (max-width: 480px)` için `width: 100%; flex-wrap: wrap; justify-content: flex-start; gap: 6px;`.
- Kalite butonları (`Kalite Onayı Ver`, `Reddet`): Mobilde `flex: 1; text-align: center;` genişlik alır.

### C. `EnjeksiyonSection.vue`
- Akordiyon başlığı:
  - Sadece `ao.satir_no` varsa sol 22px kutusu gösterilir; `ao.kalip_no` ise başlığın altında `Kalıp No: {kalip_no}` olarak sunulur.
  - `.ck-accordion-header`: `@media (max-width: 420px)` için `flex-direction: column; align-items: stretch; gap: 10px; position: relative;`.
  - Chevron butonu (`.ck-accordion-toggle-btn`): Mobilde `position: absolute; right: 0; top: 0; padding: 6px;` olarak konumlandırılır.
  - `.ck-accordion-right`: Mobilde `width: 100%; display: flex; flex-wrap: wrap; justify-content: flex-start; align-items: center; gap: 6px;`.
- `.ck-enjeksiyon-grid`:
  - `@media (max-width: 340px)` için kutu paddingleri `4px 6px`, yazı tipi `10px`, değerler `12px` ve `min-width: 0; word-break: break-word;` ile optimize edilir.

### D. `KrimpSection.vue`
- Benzer akordiyon başlığı ve sağ buton bloğu `@media (max-width: 420px)` responsive düzenine kavuşturulur.
