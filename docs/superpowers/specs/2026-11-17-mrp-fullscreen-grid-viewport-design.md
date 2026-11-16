# MRP Matrisi: Tam Ekran Grid (Viewport-Constrained) ve Page-Head Kaldırma Tasarım Şartnamesi

- **Tarih:** 2026-11-17
- **Talep:** Material Requirement sayfasındaki 20 saniye süren dikey sayfa scrollunun sonlandırılması; tablonun Google Sheets / Excel tarzında tüm tarayıcı penceresine tam oturması (`100vh`), sayfa başlığının (`.page-head`) kaldırılarak dikey alanın maksimize edilmesi, tablonun kendi içinde bağımsız dikey (sağda) ve yatay (tabanda) kaydırma çubuklarına sahip olması.
- **Yazar:** Coordinator (Tech Lead)
- **Uygulayıcı Uzman Ajan:** `frontend-public`

---

## 1. Amaç ve Kapsam

### 1.1 Mevcut Sorun
- `MrpMatrixTable.vue` içerisinde `.mrp-table-viewport` sınıfı `overflow-y: clip; max-height: none;` olarak tanımlıdır.
- Yüzlerce hammadde satırı bulunduğunda tablo dikeyde 10.000+ piksel uzamakta, kullanıcı tablonun altına ulaşmak için tüm tarayıcı penceresini uzun süre kaydırmak zorunda kalmaktadır.
- Yatay scroll çubuğu tablonun en altında kaldığından, üst satırlardaki hammaddeye bakarken sağdaki haftaları görmek için önce sayfanın en dibine inip scrollu kaydırmak gerekmektedir.
- Frappe'nin standart `.page-head` alanı ~60px gereksiz dikey alan kaplamaktadır.

### 1.2 Hedef Çözüm
- Frappe `.page-head` alanı `display: none !important` ile tamamen gizlenir.
- Dış sayfa seviyesindeki dikey kaydırma (`body / html / .page-container`) kilitlenir (`overflow: hidden`).
- `.mrp-app-container` kalan tüm tarayıcı yüksekliğini tam olarak doldurur (`height: calc(100vh - var(--navbar-height, 48px))`).
- `.mrp-toolbar` üstte sabit (compact) kalır.
- `.mrp-matrix-container` ve `.mrp-table-viewport` kalan alanı esnek (`flex: 1; min-height: 0;`) doldurur; hem `overflow-x: auto` hem `overflow-y: auto` alır.
- Tablo başlıkları (`thead th`) karmaşık `calc(...)` formülleri yerine doğrudan tablo konteyneri içinde `position: sticky; top: 0;` ile sabitlenir.
- Sol hammadde bilgi kolonu (`.mrp-th-fixed`, `.mrp-td-fixed`) `position: sticky; left: 0;` ile yatay kaydırmada sabit kalır.
- Sol-üst kesişim hücresi `position: sticky; top: 0; left: 0; z-index: 35;` ile her iki eksende çakılı kalır.

---

## 2. Mimari ve Stil Değişiklikleri

### 2.1 Frappe Desk Sıfırlaması (`App.vue`)
[`erpnextkta/public/material-requirement/App.vue`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/material-requirement/App.vue):
```css
/* Page-Head'i tamamen yok et */
[data-page-route="material-requirement"] .page-head {
  display: none !important;
}

/* Dış tarayıcı scrollunu kilitle */
[data-page-route="material-requirement"] body,
[data-page-route="material-requirement"] .page-container,
[data-page-route="material-requirement"] .page-content,
[data-page-route="material-requirement"] .layout-main,
[data-page-route="material-requirement"] .layout-main-section-wrapper,
[data-page-route="material-requirement"] .layout-main-section,
[data-page-route="material-requirement"] .page-body.container {
  overflow: hidden !important;
  height: calc(100vh - var(--navbar-height, 48px)) !important;
  max-height: calc(100vh - var(--navbar-height, 48px)) !important;
  margin: 0 !important;
  padding: 0 !important;
}

/* App Container */
.mrp-app-container {
  height: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 8px 12px 8px 12px;
  box-sizing: border-box;
}
```

### 2.2 Araç Çubuğu Düzenlemesi (`MrpToolbar.vue`)
[`erpnextkta/public/material-requirement/components/MrpToolbar.vue`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/material-requirement/components/MrpToolbar.vue):
- `position: sticky; top: ...` yerine normal akışta flex öğesi (`flex-shrink: 0;`) yapılır.
- `margin-bottom: 8px;` ile kompakt tutulur.

### 2.3 Matris Tablosu ve Viewport Düzenlemesi (`MrpMatrixTable.vue`)
[`erpnextkta/public/material-requirement/components/matrix/MrpMatrixTable.vue`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/material-requirement/components/matrix/MrpMatrixTable.vue):
```css
.mrp-matrix-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  background: var(--mrp-card-bg);
  border: 1px solid var(--mrp-border);
  border-radius: 8px;
  box-shadow: var(--mrp-shadow);
}

.mrp-table-viewport {
  flex: 1;
  min-height: 0;
  width: 100%;
  height: 100%;
  overflow-x: auto;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  position: relative;
}

/* Sticky Headers (Viewport Context) */
.mrp-th-sticky-top {
  position: sticky;
  top: 0;
  z-index: 25;
  background-color: var(--mrp-header-bg, #f8f8f8);
  border-bottom: 2px solid var(--mrp-border);
}

.mrp-th-fixed {
  position: sticky;
  left: 0;
  z-index: 30;
  width: 340px;
  min-width: 340px;
  max-width: 340px;
  background-color: var(--mrp-header-bg, #f8f8f8);
  border-right: 2px solid var(--mrp-border);
}

.mrp-th-fixed.mrp-th-sticky-top {
  position: sticky;
  top: 0;
  left: 0;
  z-index: 35;
  background-color: var(--mrp-header-bg, #f8f8f8);
}

.mrp-td-fixed {
  position: sticky;
  left: 0;
  z-index: 10;
  width: 340px;
  min-width: 340px;
  max-width: 340px;
  background-color: var(--mrp-card-bg);
  border-right: 2px solid var(--mrp-border);
  border-bottom: 1px solid var(--mrp-border);
}
```

---

## 3. Doğrulama ve Kabul Kriterleri

1. Sayfa açıldığında tarayıcının dış scroll çubuğu tamamen kaybolmalı; sayfa `100vh - navbar` yüksekliğine tam oturmalıdır.
2. Frappe'nin gri/boş `.page-head` başlığı görünmemeli, sayfa doğrudan MRP araç çubuğu ile başlamalıdır.
3. Yüzlerce hammadde olsa bile tablo içinde dikey kaydırma akıcı çalışmalı, dikey kaydırma çubuğu tablonun sağında görünmelidir.
4. Yatay kaydırma çubuğu tablonun en altında (tarayıcı tabanında) her an görünür ve erişilebilir olmalıdır.
5. Dikey kaydırmada `thead th` başlıkları `top: 0` noktasında kusursuz çakılı kalmalı, hiçbir zemin saydamlığı veya alttan sızma olmamalıdır.
6. Yatay kaydırmada sol `Hammadde Bilgisi` sütunu `left: 0` noktasında kusursuz çakılı kalmalıdır.
7. Mobil (320px) ve tablet ekranlarda yatay taşma yapmamalı, esnek grid düzeni korunmalıdır.
8. `bench build --app erpnextkta --production` hatasız derlenmelidir.
