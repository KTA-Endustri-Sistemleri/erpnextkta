# Malzeme İhtiyacı (MRP) Matrisi: Side Drawer ve %100 Light/Dark Tema Uyumu — Tasarım

- **Durum:** Onaya Hazır
- **Tarih:** 2026-11-16
- **Dal:** `feat/mrp-modular-refactor`
- **Kapsam:** `erpnextkta/public/material-requirement/**`

---

## 1. Amaç ve Neden

Malzeme İhtiyacı Planlama arayüzünde (`material-requirement` Vue 3 SPA), plancıların haftalık üretim ve tedarik projeksiyonlarını izlerken yaşadığı iki temel kullanıcı deneyimi ve okunabilirlik problemi çözülmektedir:

1. **Akordiyonun Tablo Geometrisini Bozması:** Mevcut yapıda bir haftalık hücreye (`MrpWeekCell`) veya malzeme kimliğine (`MrpItemIdentity`) tıklandığında, tablonun tam ortasında tüm sütunları kapsayan devasa bir akordiyon satırı (`<tr>`) açılmaktadır. Bu durum tablonun dikey akışını aşağı doğru kaydırmakta, dondurulmuş sol sütun hizasını zorlamakta ve kullanıcının seçili haftanın dikey sütunuyla göz temasını koparmaktadır.
2. **Karanlık Mod (Dark Mode) Kontrast ve Okunabilirlik Kaybı:** Arayüz bileşenlerinde (`MrpFilterBar`, `MrpToolbar`, `MrpMatrixTable`, `MrpItemIdentity`, `MrpWeekCell`, `MrpPeggingList`, `MrpPoReceiptList`, `MrpSupplierPlannedOrders`) ve `App.vue` üzerinde hardcoded `#fff`, `#f8fafc`, `#e2e8f0`, `#1e293b` gibi açık tema renkleri kullanılmıştır. Frappe Desk karanlık moda (`[data-theme="dark"]`) geçtiğinde matris parlak beyaz kalmakta veya gri metinler okunamaz hale gelmektedir.

Bu tasarım ile:
- Tablo içi akordiyon geçici olarak **deaktif edilir (kod silinmez, yoruma alınır)**; seçili malzemenin haftalık hesaplama özeti, açık teslimatları ve mamul kırılımları sağdan kayan modern bir **Side Drawer (Overlay Yan Panel)** içine taşınır.
- `material-requirement` altındaki tüm bileşenler **%100 Light & Dark Theme** uyumlu hale getirilir.

---

## 2. Hedefler, Kapsam Dışı ve Anti-Hedefler

### Hedefler
- `components/drawer/MrpDetailDrawer.vue` adında `<Teleport to="body">` ile çalışan, z-index çakışması yapmayan (`z-[1050]`), ESC tuşu ve dışarı tıklama ile kapanan pürüzsüz sağ panel oluşturmak.
- Bir hücreye veya malzemeye tıklandığında matris tablosunun yatay ve dikey pozisyonunu bozmadan çekmecede seçili haftanın verilerini açmak.
- `useMrpState.ts` composable'ına çekmece durumunu (`isDrawerOpen`, `drawerItemCode`, `drawerWeekKey`, `openDrawer`, `closeDrawer`) bağlamak.
- `App.vue` ve bileşenler seviyesinde Frappe CSS değişkenleriyle tam entegre semantik tema paleti kurmak (`--mrp-bg`, `--mrp-card-bg`, `--mrp-text`, `--mrp-text-muted`, `--mrp-border`, `--mrp-cell-hover`, `--mrp-header-bg` vb.).
- Hem `[data-theme="dark"]` hem de `@media (prefers-color-scheme: dark)` modlarında tüm 8 bileşenin kontrastını ve okunabilirliğini garanti altına almak.

### Kapsam Dışı (Non-Goals)
- Backend MRP motoru hesaplamalarını (`mrp_engine/**`) veya API yanıt şemasını değiştirmek.
- Akordiyon bileşenlerini (`MrpPeggingList.vue`, `MrpPoReceiptList.vue`, `MrpSupplierPlannedOrders.vue`) silmek (bunlar çekmece içinde yeniden kullanılacaktır).
- Matris tablosundaki 5 lojistik rozetinin renk tonlarını değiştirmek (bunlar KTA standart durum renkleridir; ancak zeminleri karanlık modda okunabilir kılınacaktır).

### Anti-Hedefler (Başarısızlık Kriterleri)
- Yan panel açıldığında matris tablosunun dikey veya yatay olarak sıçraması / kayması.
- Akordiyon kodlarının repodan tamamen silinmesi (ileride geri dönülebilirlik için sadece deaktif edilmelidir).
- Karanlık modda arka planın beyaz kalması veya metinlerin arka planla aynı renge düşüp görünmez olması.
- Tek bir `.vue` dosyasının 500 satır kuralını aşması.

---

## 3. Kullanıcı Deneyimi ve Arayüz Akışı (Wireframe)

```
┌──────────────────────────────────────────────────────────────────┬────────────────────────────┐
│ MRP Malzeme İhtiyacı Matrisi                                     │ 📑 Malzeme Detayı      [X] │
├──────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ [Filtreler & Arama Barı]                                         │ KBL-001 - 2.5 NYA Kablo    │
├──────────────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬────┤ UOM: Metre | Stok: 1.250   │
│ Malzeme      │ W46  │ W47  │ W48  │ W49  │ W50  │ W51  │ W52  │ ...│ Hafta: 2026-W48 (Seçili)   │
├──────────────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼────┼────────────────────────────┤
│ KBL-001 (NYA)│  120 │  450 │ [890]│  -   │  200 │  150 │  ... │    │ 📊 Hafta Hesaplama Özeti   │
│ KBL-002 (TTR)│  500 │  300 │  200 │  100 │  -   │  400 │  ... │    │ • Brüt İhtiyaç: 1.500 m    │
│ TRM-010 (Krm)│  -   │ 1.200│  400 │  -   │  800 │  -   │  ... │    │ • Planlanan Giriş: 500 m   │
│ ...          │  ... │  ... │  ... │  ... │  ... │  ... │  ... │    │ • Net İhtiyaç: 890 m       │
│              │      │      │      │      │      │      │      │    │ • Önerilen Sipariş: 1.000 m│
│              │      │      │      │      │      │      │      │    ├────────────────────────────┤
│              │      │      │      │      │      │      │      │    │ 🚢 Açık PO & Sevkiyatlar   │
│              │      │      │      │      │      │      │      │    │ [Yolda] PO-091: 500 m (ETA)│
│              │      │      │      │      │      │      │      │    ├────────────────────────────┤
│              │      │      │      │      │      │      │      │    │ 🔗 Mamul Kırılımı (Pegging)│
│              │      │      │      │      │      │      │      │    │ WO-2026-102: 800 m         │
└──────────────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴────┴────────────────────────────┘
```

---

## 4. Teknik Mimari ve Değişiklikler

### 4.1 State Yönetimi (`useMrpState.ts`)
- Eklenen durumlar:
  ```typescript
  const isDrawerOpen = ref(false);
  const drawerItemCode = ref<string | null>(null);
  const drawerWeekKey = ref<string | null>(null);
  ```
- Eklenen/Güncellenen fonksiyonlar:
  - `openDrawer(itemCode: string, weekKey?: string)`: Çekmeceyi açar. Eğer `weekKey` verilmemişse malzemenin `first_shortage_week` (ilk eksik haftası) veya aktif haftası (`is_current`) otomatik seçilir.
  - `closeDrawer()`: Çekmeceyi kapatır.
  - `setDrawerWeek(weekKey: string)`: Çekmece açıkken kullanıcının çekmece başlığından veya matristen başka bir haftaya geçmesini sağlar.
- `focusWeekForMaterial(itemCode, weekKey)` metodu hem hücre seçimini günceller hem de `openDrawer(itemCode, weekKey)` fonksiyonunu tetikler.

### 4.2 Yeni Bileşen: `MrpDetailDrawer.vue` (Non-Modal / Kesintisiz Gezinme)
- Yol: `erpnextkta/public/material-requirement/components/drawer/MrpDetailDrawer.vue`
- Yapı ve Etkileşim Modeli:
  - `<Teleport to="body">`
  - **Non-Modal / Backdropsuz Mimari:** Arka plan karartılmaz (`backdrop` yoktur). Çekmece sağda açıkken kullanıcı matristeki farklı haftalara veya farklı malzemelere doğrudan tıklayabilir; çekmece anında o hücreye güncellenir.
  - Kapatma: Başlıktaki 'X' butonu veya `ESC` tuşu ile kapanır.
  - Sağdan kayan çekmece paneli: `w-[460px] max-w-[95vw] h-full shadow-2xl z-[1050] fixed top-0 right-0 border-l`.
  - Başlık: Malzeme adı, kodu, UOM, mevcut stok, **Hafta Seçici (yatay kaydırılabilir hafta butonları/pills)** ve kapatma butonu.
  - Gövde (Scrollable):
    1. Seçili hafta metrikleri (Brüt, Girişler, Stok Projeksiyonu, Net Eksik, Önerilen Sipariş).
    2. Açık Teslimatlar (`MrpPoReceiptList.vue`).
    3. Mamul İhtiyaç Kırılımı (`MrpPeggingList.vue`).
    4. Tedarikçi Dağılımı (`MrpSupplierPlannedOrders.vue`).

### 4.3 `MrpMatrixTable.vue` Deaktif Edilme & 500 Satır Kuralı
- Mevcut `tr.mrp-row-accordion` bloğu silinmez; `<!-- Akordiyon Deaktif: Yerine Side Drawer kullanılmaktadır -->` notu ve `v-if="false && isRowExpanded(m.item_code)"` ile pasife alınır.
- Satır genişleme tıklamaları (`toggleAccordion`) doğrudan `openDrawer(m.item_code)` eylemine bağlanır.
- `MrpMatrixTable.vue` (şu an 511 satır) ve yeni `MrpDetailDrawer.vue` kesinlikle 500 satır altında kalacaktır. Mevcut çalışan 751 satırlık `MrpPoReceiptList.vue` bileşeni ise regresyon riskini önlemek için bu aşamada gereksiz yere parçalanmayacak; yalnızca tema CSS değişkenlerine bağlanacaktır.

### 4.4 %100 Light & Dark Tema Mimarisi (`App.vue` & Bileşenler)
- `App.vue` kök CSS tanımları:
  ```css
  :root, [data-theme="light"] {
    --mrp-bg: #f8fafc;
    --mrp-card-bg: #ffffff;
    --mrp-text: #0f172a;
    --mrp-text-muted: #64748b;
    --mrp-border: #e2e8f0;
    --mrp-header-bg: #f1f5f9;
    --mrp-cell-hover: rgba(37, 99, 235, 0.08);
    --mrp-cell-selected: rgba(37, 99, 235, 0.16);
    --mrp-table-zebra: #fcfdfe;
  }

  [data-theme="dark"], body.dark, html.dark {
    --mrp-bg: #0f172a;
    --mrp-card-bg: #1e293b;
    --mrp-text: #f1f5f9;
    --mrp-text-muted: #94a3b8;
    --mrp-border: #334155;
    --mrp-header-bg: #1e293b;
    --mrp-cell-hover: rgba(59, 130, 246, 0.15);
    --mrp-cell-selected: rgba(59, 130, 246, 0.25);
    --mrp-table-zebra: #141f32;
  }
  ```
- Bileşen bazlı renk dönüştürme:
  - `MrpFilterBar.vue`: Giriş alanları ve butonlar `--mrp-card-bg` ve `--mrp-border`.
  - `MrpToolbar.vue`: İstatistik kartları ve arama kutusu `--mrp-card-bg`, metinler `--mrp-text`.
  - `MrpMatrixTable.vue`: Sabit dondurulmuş sütunlar `--mrp-card-bg`, kenarlıklar `--mrp-border`.
  - `MrpItemIdentity.vue`: Malzeme kartı arka planı ve etiket renkleri dark uyumlu.
  - `MrpWeekCell.vue`: Durum arkaplanları karanlık temada gözü yormayan doygunlukta (`rgba(...)`).
  - `MrpDetailDrawer.vue`, `MrpPeggingList.vue`, `MrpPoReceiptList.vue`, `MrpSupplierPlannedOrders.vue`: Panel, tablolar ve liste satırları `--mrp-card-bg` ve `--mrp-text` ile senkron.

---

## 5. Doğrulama ve Kabul Kriterleri

1. **Side Drawer Fonksiyonelliği:**
   - Herhangi bir haftalık hücreye veya malzeme kimliğine tıklandığında sağdan çekmece açılmalı; matris tablosu yatay/dikey olarak zıplamamalıdır.
   - ESC tuşuna basıldığında veya 'X' butonuna tıklandığında çekmece pürüzsüzce kapanmalıdır.
   - Çekmecede seçili haftanın hesaplama özeti, açık PO/sevkiyatları ve mamul kırılımı eksiksiz listelenmelidir.
2. **Akordiyonun Korunması:**
   - Eski akordiyon kodu silinmemiş, kontrollü şekilde deaktif edilmiş olmalıdır.
3. **%100 Light & Dark Tema Uyumu:**
   - Frappe Desk üzerinden açık temadan koyu temaya geçildiğinde arayüzde hiçbir parlak beyaz zemin, görünmez koyu metin veya kontrast kaybı yaşanmamalıdır.
   - Tüm arka planlar, kenarlıklar, metinler ve kartlar tanımlı CSS değişkenleriyle dinamik renk değiştirmelidir.
4. **Kod Kalitesi ve Derleme:**
   - Yeni bileşen (`MrpDetailDrawer.vue`) ve güncellenen `MrpMatrixTable.vue` kesinlikle 500 satır sınırının altında kalmalıdır.
   - Frontend derlemesi istisnasız `bench build --app erpnextkta --production` komutu ile sıfır hata ile tamamlanmalıdır.
