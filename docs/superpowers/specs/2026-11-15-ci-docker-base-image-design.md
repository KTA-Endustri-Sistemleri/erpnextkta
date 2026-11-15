# Design Document: Pre-built Docker İmajı ile CI Süresini Kısaltma

**Tarih:** 2026-11-15  
**Durum:** Taslak / Kullanıcı Onayına Sunuldu  
**Kapsam:**
- `docker/ci/Dockerfile` (Yeni)
- `.github/workflows/docker-ci-base.yml` (Yeni: Base imajı build & publish iş akışı)
- `.github/workflows/tests.yml` (Güncelleme: Hazır imajı kullanarak adımları sadeleştirme)

---

## 1. Intent and The Why (Gerekçe ve Amaç)

Mevcut GitHub Actions CI iş akışında (`tests.yml`) her pull request ve commit için boş `ubuntu:22.04` konteynerinden başlanmakta; sistem paketleri, Node.js, Python, Frappe Bench, ERPNext ve diğer 7 adet uygulamanın tamamı sıfırdan indirilip kurulmaktadır.

### Mevcut Süre Analizi:
- **Toplam Koşu:** ~8 dakika 20 saniye
- **Gerçek Test Süresi:** ~60 saniye (%12)
- **Kurulum ve Hazırlık:** ~7 dakika 20 saniye (%88)

Bu tasarımın amacı; değişmeyen tüm işletim sistemi paketlerini, Frappe Bench'i, ERPNext/HRMS gibi devasa bağımlılıkları ve Python sanal ortamını önceden derlenmiş tek bir Docker base imajında toplayarak CI süresini **8.5 dakikadan ~1.5 - 2 dakikaya** indirmektir.

---

## 2. Goals & Non-Goals

### Goals (Hedefler)
1. **Hazır Base Docker İmajı:**
   - Ubuntu 22.04 tabanlı, Node.js v20, Python 3.10, MariaDB Client ve derleme araçlarını içeren,
   - `/home/frappe/frappe-bench` altında `version-15` Frappe, ERPNext, HRMS, Payments ve yerel e-belge uygulamaları kurulu ve Python gereksinimleri (`env`) eksiksiz hazır bir Dockerfile oluşturulması.
2. **Otomatik İmaj Yayınlama (`docker-ci-base.yml`):**
   - GitHub Container Registry (`ghcr.io/kta-endustri-sistemleri/frappe-ci-base:v15`) üzerine otomatik imaj derleyip pushlayan GitHub Actions iş akışı kurulması.
   - İmajın haftalık/aylık veya manuel (`workflow_dispatch`) tetiklenebilmesi.
3. **`tests.yml` Sadeleştirmesi ve Hızlandırma:**
   - `container: ubuntu:22.04` yerine `ghcr.io/.../frappe-ci-base:v15` kullanılması.
   - `Bootstrap Container` (38 sn), `Setup Python` ve `bench init` (32 sn) adımlarının kaldırılması.
   - 8 repo yerine sadece test edilecek `erpnextkta` ve private `kta_system_utils` uygulamalarının bağlanması.
   - Tüm uygulamaları derleyen genel `bench build` (~50 sn) yerine, frontend kod kalitesini ve derlenebilirliğini garanti altına almak için yalnızca kurala uygun olarak `bench build --app erpnextkta --production` (~6 sn) çalıştırılması.
4. **Hızlı DB Şablonu (Opsiyonel / Hızlandırıcı):**
   - Base imaj içerisine `test_site` için önceden oluşturulmuş bir DB şeması (`template_db.sql.gz`) konularak `bench new-site` + `install-app` (2.5 - 3 dk) sürecinin doğrudan `mariadb test_site < template_db.sql` ile 10 saniyeye indirilmesi.

### Non-Goals (Kapsam Dışı)
- Canlı sunucu (production deploy) Docker imajlarını değiştirmek (bu geliştirme yalnızca CI test altyapısı içindir).
- Birim testlerin mantığını veya test edilen kodları değiştirmek.

---

## 3. Approaches (Değerlendirilen Yaklaşımlar)

1. **Yaklaşım 1 (Seçilen): Pre-built Docker İmajı (GitHub Container Registry - GHCR):**
   - *Tanım:* Tüm ağır bağımlılıklar GHCR üzerindeki imajda toplanır. CI koşusunda saniyeler içinde imaj çekilir.
   - *Avantajı:* En radikal hızlanma (8.5 dk $\rightarrow$ 1.5 - 2 dk).
   - *Kullanıcı Tercihi:* Kullanıcı tarafından en mantıklı çözüm olarak seçildi.
2. **Yaklaşım 2: GitHub Actions Cache + SQL Dump:**
   - *Neden Seçilmedi:* Cache limitleri (10 GB) ve GitHub Actions runner'larındaki cache indirme/açma I/O darboğazları nedeniyle Docker imajı kadar deterministik ve hızlı değildir.
3. **Yaklaşım 3: Yalnızca Quick Wins (Sığ klon ve build kaldırma):**
   - *Neden Seçilmedi:* Süreyi sadece 8.5 dakikadan 6 dakikaya indirebilirdi, gerçek sorunu (baştan kurulumu) çözmüyordu.

---

## 4. Detailed Specification (Teknik Tasarım)

### 4.1. Dockerfile (`docker/ci/Dockerfile`)
```dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 1. Sistem Paketleri
RUN echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4 && \
    apt-get update && apt-get install -y --no-install-recommends \
    sudo curl git build-essential pkg-config libmysqlclient-dev \
    python3-dev python3-pip python3-setuptools python3-venv cron tzdata mariadb-client && \
    ln -fs /usr/share/zoneinfo/UTC /etc/localtime && \
    dpkg-reconfigure --frontend noninteractive tzdata && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g yarn && \
    pip3 install --no-cache-dir frappe-bench && \
    useradd -m -s /bin/bash frappe && \
    echo "frappe ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

USER frappe
WORKDIR /home/frappe

# 2. Frappe Bench ve Sabit Bağımlılıkların Kurulumu
RUN bench init --frappe-branch version-15 --skip-redis-config-generation --skip-assets /home/frappe/frappe-bench && \
    cd /home/frappe/frappe-bench && \
    bench get-app payments --branch version-15 --resolve-deps && \
    bench get-app hrms --branch version-15 --resolve-deps && \
    bench get-app erpnext https://github.com/frappe/erpnext --branch version-15 --resolve-deps && \
    bench get-app https://github.com/Framras/trtaxoffices.git --branch version-15 && \
    bench get-app https://github.com/Framras/trtcmb.git --branch version-15 && \
    bench get-app https://github.com/Framras/trebelge.git --branch version-15 && \
    ./env/bin/pip install --no-cache-dir --force-reinstall 'setuptools<81' && \
    ./env/bin/pip install --no-cache-dir tzdata

WORKDIR /home/frappe/frappe-bench
```

### 4.2. Base İmaj Derleme İş Akışı (`.github/workflows/docker-ci-base.yml`)
- Yalnızca `workflow_dispatch` (manuel) veya `schedule` (ayda bir) çalışır.
- `docker/build-push-action@v5` kullanarak GitHub Container Registry'e (`ghcr.io/kta-endustri-sistemleri/frappe-ci-base:v15`) imajı yayınlar.
- Gerekli token: `GITHUB_TOKEN` (`packages: write`).

### 4.3. Güncellenen Test İş Akışı (`.github/workflows/tests.yml`)
```yaml
jobs:
  tests:
    name: Server
    runs-on: ubuntu-latest
    container:
      image: ghcr.io/kta-endustri-sistemleri/frappe-ci-base:v15
      credentials:
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    services:
      redis-cache: ...
      redis-queue: ...
      mariadb: ...

    steps:
      - name: Checkout erpnextkta
        uses: actions/checkout@v4
        with:
          path: /home/frappe/frappe-bench/apps/erpnextkta

      - name: Setup Site & Install Test Apps
        working-directory: /home/frappe/frappe-bench
        run: |
          sudo -H -u frappe bench get-app https://${{ secrets.KTA_SYSTEM_UTILS_PAT }}@github.com/KTA-Endustri-Sistemleri/kta_system_utils.git --branch version-15
          sudo -H -u frappe bench set-config -g db_host mariadb
          sudo -H -u frappe bench set-config -g redis_cache redis://redis-cache:6379
          sudo -H -u frappe bench set-config -g redis_queue redis://redis-queue:6379
          sudo -H -u frappe bench new-site --db-root-password root --admin-password admin test_site \
            --install-app payments --install-app hrms --install-app erpnext \
            --install-app trtaxoffices --install-app trtcmb --install-app trebelge \
            --install-app kta_system_utils --install-app erpnextkta
          sudo -H -u frappe bench --site test_site set-config allow_tests true

      - name: Build erpnextkta Frontend
        working-directory: /home/frappe/frappe-bench
        run: sudo -H -u frappe bench build --app erpnextkta --production

      - name: Seed Infrastructure
        working-directory: /home/frappe/frappe-bench
        run: sudo -H -u frappe bench --site test_site execute erpnextkta.tests.test_utils.before_tests

      - name: Run Tests
        working-directory: /home/frappe/frappe-bench
        run: sudo -E -u frappe bench --site test_site run-tests --app erpnextkta
```

---

## 5. Beklenen Sonuçlar ve Tasarruf Tablosu

| Metrik | Mevcut Durum | Yeni Durum (Pre-built İmaj) | Tasarruf |
| :--- | :---: | :---: | :---: |
| OS Paket Kurulumu | 38 sn | **0 sn** (İmajda hazır) | -38 sn |
| Bench Init + Node/Python | 32 sn | **0 sn** (İmajda hazır) | -32 sn |
| 6 Büyük Repo Klonlama | ~90 sn | **0 sn** (İmajda hazır) | -90 sn |
| Pip Paket Derlemeleri | ~60 sn | **0 sn** (İmajda hazır) | -60 sn |
| Frontend Build (Yalnızca app) | ~45-50 sn (Tüm uygulamalar) | **~6 sn** (`--app erpnextkta --production`) | -40 sn |
| Site Kurulumu & Test Koşusu | ~3.5 dk | ~1.5 dk | -2 dk |
| **Toplam CI Koşu Süresi** | **~8 dk 20 sn** | **~1 dk 45 sn - 2 dk** | **~%75 Hızlanma** |

---

## 6. Güvenlik ve Gizlilik
- Base imaj yalnızca açık kaynaklı ve lisanslı paketleri (`frappe`, `erpnext`, `hrms` vb.) içerir.
- Şirkete özel ticari kod veya PAT anahtarları imaj katmanlarına yazılmaz; private repolar (`kta_system_utils` ve `erpnextkta`) CI runner'ında runtime sırasında bağlanır.
