# MRP Malzeme İhtiyacı Matrisi: Frappe Desk Orijinal Tema Harmonizasyonu ve Ayrışık Durum Renkleri — Tasarım

- **Durum:** Onaya Hazır
- **Tarih:** 2026-11-16
- **Kapsam:** `erpnextkta/public/material-requirement/**`
- **Yürütücü Subagent:** `frontend-public`

---

## 1. Amaç ve Neden
Malzeme İhtiyacı Planlama arayüzünde (`material-requirement` Vue 3 SPA), harici Tailwind Slate tonları ve sabit hex renkler kullanıldığı için sayfa Frappe Desk'in orijinal tasarım sisteminden (`desk.bundle.css`) ve KTA özel cam stilinden (`erpnextkta.bundle.css`) görsel olarak ayrışmaktadır.

Bu tasarım ile:
1. `App.vue` içindeki semantik tema token'ları Frappe Desk'in native CSS değişkenlerine (`--bg-color`, `--card-bg`, `--control-bg`, `--border-color`, `--text-color`, `--text-muted`, vb.) bağlanacaktır.
2. Toolbar, filtre popover'ı ve yan detay çekmecesine sırıtmayan, dengeli KTA cam efekti (`backdrop-filter: blur(8px)`, yarı saydam arka plan) uygulanacaktır.
3. Yoğun veri tablosunun dondurulmuş sol sütunu (`.mrp-th-fixed`, `.mrp-td-fixed`) ve yapışkan başlıkları (`.mrp-th-sticky-top`), kaydırma sırasında metinlerin birbirine geçmesini önlemek için **tam opak** Frappe yüzey renklerini koruyacaktır.
4. Lojistik ve tedarik boru hattı rozetleri (PO, In-Transit/Yolda, Antrepo, Gümrük, Uyuşmazlık, Serbest Stok, Eksik, Kota) birbirine asla benzemeyecek, renk tekerleğinde tamamen farklı spektrumlarda ve hem Light hem Dark modda yüksek kontrastlı olacak şekilde ayrıştırılacaktır.
5. **320px Responsive Desteği:** Araç çubuğu (`MrpToolbar`), popover filtreler ve detay çekmecesi (`MrpDetailDrawer`) en dar mobil ekran olan **320px** genişlikte dahi yatay taşma (overflow) yapmayacak, kontroller dikey/akıcı olarak sarmalanacak (`flex-wrap: wrap`) ve okunabilir kalacaktır. Matrix tablosu ise yatay kaydırma çubuğu (`overflow-x: auto`) ile 320px'de dondurulmuş sütun hizasını koruyacaktır.

---

## 2. Değerlendirilen Yaklaşımlar

- **Yaklaşım 1 (Seçilen - Hibrit Frappe Desk & Dengeli Cam & Ayrışık Rozetler):**
  - `--mrp-*` değişkenleri Frappe Desk native CSS değişkenlerine bağlanır.
  - Toolbar, Popover ve Drawer hafif cam efektine kavuşur.
  - Matrix tablosu opak kalarak %100 veri okunabilirliği garanti edilir.
  - Lojistik rozetler net renk kodlarıyla birbirine karışmayacak şekilde ayrıştırılır.
- **Yaklaşım 2 (Saf Flat Desk - Elendi):**
  - Sıfır cam efekti, tamamen düz beyaz/gri kartlar. KTA'nın modern arayüz kimliğinden geride kaldığı için tercih edilmedi.
- **Yaklaşım 3 (İzole Özel Hex Paleti - Elendi):**
  - Frappe Desk değişkenlerine bağlanmadan yeni sabit hex'ler tanımlamak. Tema değişikliklerinde kırılacağı ve bakımı zor olduğu için elendi.

---

## 3. Ayrışık Rozet ve Gösterge Renk Paleti (Kesin Kural)

Plancıların tek bakışta tedarik aşamalarını ayırt edebilmesi için hiçbir aşama birbirine benzer ton almayacaktır:

| Kategori | Anlamı | Light Mod (Zemin / Yazı / Kenarlık) | Dark Mod (Zemin / Yazı / Kenarlık) | İkon |
|---|---|---|---|---|
| **PO (Sipariş)** | Açık satınalma siparişi | `#eef2ff` / `#4338ca` (İndigo) | `rgba(99, 102, 241, 0.2)` / `#a5b4fc` | `fa-file-text-o` |
| **Yolda (In-Transit)** | Gemide / tırda sevkiyat | `#fef3c7` / `#b45309` (Amber / Canlı Sarı) | `rgba(245, 158, 11, 0.2)` / `#fcd34d` | `fa-truck` |
| **Antrepoda** | Liman / antrepo beklemede | `#e0f2fe` / `#0369a1` (Sky Blue / Camgöbeği) | `rgba(14, 165, 233, 0.2)` / `#7dd3fc` | `fa-cubes` |
| **Gümrüklemede** | Millileştirme / beyanname süreci | `#ffedd5` / `#c2410c` (Canlı Turuncu) | `rgba(249, 115, 22, 0.2)` / `#fdba74` | `fa-building-o` |
| **Uyuşmazlık** | Kapıda bloke / red / karantina | `#fee2e2` / `#b91c1c` (Koyu Kırmızı) | `rgba(239, 68, 68, 0.25)` / `#fca5a5` | `fa-exclamation-triangle` |
| **Serbest Stok** | Depoda kullanılabilir stok | `#dcfce7` / `#15803d` (Zümrüt Yeşili) | `rgba(34, 197, 94, 0.2)` / `#86efac` | `fa-check-circle` |
| **Acil Eksik** | 1-2 hafta içinde tükenme | `#ffe4e6` / `#be123c` (Kızıl Gül / Coral) | `rgba(244, 63, 94, 0.25)` / `#fda4af` | `fa-bolt` |
| **Kotalı Alım** | Çoklu tedarikçi bölüşümü | `#f3e8ff` / `#7e22ce` (Koyu Menekşe / Mor) | `rgba(168, 85, 247, 0.2)` / `#d8b4fe` | `fa-pie-chart` |

---

## 4. Değişken Eşleme Tablosu (`App.vue`)

```css
:root,
[data-theme="light"] {
  --mrp-bg: var(--bg-color, #f0f2f5);
  --mrp-card-bg: var(--card-bg, #ffffff);
  --mrp-card-subtle: var(--control-bg, #f3f3f3);
  --mrp-text: var(--text-color, #171717);
  --mrp-text-muted: var(--text-muted, #7c7c7c);
  --mrp-border: var(--border-color, #ededed);
  --mrp-border-subtle: var(--border-color, #f3f3f3);
  --mrp-header-bg: var(--subtle-accent, #f8f8f8);
  --mrp-current-week-header-bg: rgba(99, 102, 241, 0.08);
  --mrp-cell-hover: rgba(99, 102, 241, 0.06);
  --mrp-cell-selected: rgba(99, 102, 241, 0.15);
  --mrp-table-zebra: rgba(255, 255, 255, 0.6);
  --mrp-glass-bg: rgba(255, 255, 255, 0.82);
  --mrp-glass-blur: blur(8px);
}

[data-theme="dark"] {
  --mrp-bg: var(--bg-color, #0c111b);
  --mrp-card-bg: var(--card-bg, #171717);
  --mrp-card-subtle: var(--control-bg, #232323);
  --mrp-text: var(--text-color, #f8f8f8);
  --mrp-text-muted: var(--text-muted, #c7c7c7);
  --mrp-border: var(--border-color, #282828);
  --mrp-border-subtle: var(--border-color, #1f1f1f);
  --mrp-header-bg: var(--control-bg, #1c1c1c);
  --mrp-current-week-header-bg: rgba(129, 140, 248, 0.15);
  --mrp-cell-hover: rgba(129, 140, 248, 0.1);
  --mrp-cell-selected: rgba(129, 140, 248, 0.25);
  --mrp-table-zebra: rgba(25, 25, 25, 0.5);
  --mrp-glass-bg: rgba(23, 23, 23, 0.85);
  --mrp-glass-blur: blur(10px);
}
```

---

## 5. Uygulayıcıya (Frontend Subagent) Bırakılan Detaylar
1. `App.vue`: CSS değişkenlerinin Frappe Desk ve KTA değişkenleriyle senkronize edilmesi.
2. `MrpToolbar.vue`: Filtre ve arama kutularının Frappe standart `form-control` stillerine kavuşturulması, butonların `btn-default` / KTA cam stiline uydurulması.
3. `MrpMatrixTable.vue`: Dondurulmuş başlık ve sütunların tam opak tutulması; tablo çizgi ve hover renklerinin `var(--border-color)` ve `var(--mrp-cell-hover)` ile güncellenmesi.
4. `MrpWeekCell.vue`: Tablodaki PO, Yolda, Antrepo, Gümrük rozetlerinin yukarıdaki ayrışık renk tablosuna göre güncellenmesi.
5. `MrpItemIdentity.vue`: Stok, Tutar, Tedarik boru hattı etiketlerinin tablodaki renklerle %100 uyumlu hale getirilmesi.
6. `MrpDetailDrawer.vue`: Çekmece panelinin KTA cam stili ve Frappe Desk renkleriyle uyumlu kılınması.
7. **320px Responsive Uyumu:** `@media (max-width: 576px)` ve `@media (max-width: 320px)` kurallarıyla mobil ekranlarda buton, input ve çekmece düzenlerinin kesintisiz çalışması.
8. Derleme: `bench build --app erpnextkta --production` çalıştırılarak derleme doğrulaması yapılması.
