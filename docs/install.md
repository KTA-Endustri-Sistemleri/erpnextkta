---
layout: default
title: "Kurulum"
---

<main class="container modules-page install-page" markdown="1">

# 🚀 Kurulum Rehberi

Bu sayfa **erpnextkta** uygulamasının ERPNext üzerine nasıl kurulacağını kısaca açıklar.
Adımlar; yeni bir ERPNext kurulumu üzerine app ekleme, siteye yükleme ve güncelleme
işlemlerini kapsar.

<hr class="modules-divider" />

<section class="module-card" markdown="1">

## 1️⃣ Gereksinimler

**Yazılım Gereksinimleri**

- Python 3.10+  
- Node.js 18+  
- Redis  
- MariaDB 10.6+  
- Bench CLI 5.x  
- ERPNext 15.x (Frappe 15 ile birlikte)

**Sunucu Önerisi (örnek)**

- Ubuntu 22.04 LTS  
- 2–4 CPU, 4–8 GB RAM  
- Üretim ortamında HTTPS (Nginx / Traefik vb. ile)

</section>

<section class="module-card" markdown="1">

## 2️⃣ Uygulamayı İndirme

Var olan bir bench içine **erpnextkta** uygulamasını eklemek için:

```bash
cd /path/to/frappe-bench

bench get-app https://github.com/KTA-Endustri-Sistemleri/erpnextkta.git
```

Belirli bir branch kullanmak isterseniz:

```bash
bench get-app erpnextkta --branch main
```

</section>

<section class="module-card" markdown="1">

## 3️⃣ Site Üzerine Kurulum

Uygulama bench içine alındıktan sonra istediğiniz siteye yükleyin:

```bash
bench --site yoursite.com install-app erpnextkta
```

Kurulum sonrası:

- Gerekli DocType ve ayarlar oluşturulur  
- Manufacturing genişletmeleri aktif hale gelir  
- Menüde yeni modüller görülebilir

</section>

<section class="module-card" markdown="1">

## 4️⃣ Güncelleme ve Migrasyon

Yeni sürüme geçmek veya repo’dan son değişiklikleri almak için:

```bash
cd /path/to/frappe-bench

# Tüm bench için genel güncelleme
bench update --reset
```

Sadece erpnextkta için repo güncellemesi yaptıysanız mutlaka migrate çalıştırın:

```bash
bench --site yoursite.com migrate
bench --site yoursite.com clear-cache
```

</section>

<section class="module-card" markdown="1">

## 5️⃣ Geliştirme Ortamı (Opsiyonel)

Yerel geliştirme için tipik akış:

```bash
# 1) Bench'i başlat
bench start

# 2) Ayrı bir terminalde
bench --site sitename migrate
bench --site sitename clear-cache
```

Developer mode açık olduğunda Vue/JS değişiklikleri hot-reload ile yenilenir.

</section>

</main>