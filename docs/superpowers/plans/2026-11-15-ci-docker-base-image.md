# Pre-built Docker İmajı ile Hızlı CI Altyapısı Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GitHub Actions CI iş akışında (`tests.yml`) her koşuda sıfırdan yapılan ~7 dakikalık paket ve uygulama kurulumlarını önceden derlenmiş bir Docker base imajında toplayarak CI süresini 8.5 dakikadan ~1.5 - 2 dakikaya indirmek ve `bench build --app erpnextkta --production` ile frontend derlemesini garanti altına almak.

**Architecture:** 
1. `docker/ci/Dockerfile` ile Ubuntu 22.04 + Node 20 + Python 3.10 + Frappe v15 + ERPNext + HRMS ve diğer kamu açık uygulamaları barındıran base imaj tanımlanır.
2. `.github/workflows/docker-ci-base.yml` iş akışı, bu imajı GitHub Container Registry (`ghcr.io/kta-endustri-sistemleri/frappe-ci-base:v15`) üzerine build & push eder.
3. `.github/workflows/tests.yml` iş akışı, boş Ubuntu yerine bu hazır imajı kullanacak şekilde refactor edilir; gereksiz 4-5 adım elenir; testlerden hemen önce `bench build --app erpnextkta --production` adımı eklenir.

**Tech Stack:** Docker, GitHub Actions, GitHub Container Registry (GHCR), Frappe Framework v15, ERPNext, esbuild

**Spec:** [docs/superpowers/specs/2026-11-15-ci-docker-base-image-design.md](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/docs/superpowers/specs/2026-11-15-ci-docker-base-image-design.md)

## Global Constraints
- Target branch is `main`.
- Current working branch: `feat/ci-docker-base-image`.
- Never use `yarn build` directly; always run `bench build --app erpnextkta --production`.
- Commit messages must strictly follow Conventional Commits ($\le 72$ chars).
- Mandatory PR template from `.github/PULL_REQUEST_TEMPLATE.md` must be used.
- Confidentiality: Never expose sensitive company names, PAT tokens or private secrets in public Docker layers.

## Review Focus
1. **İzin ve Kullanıcı (User Permissions):** Docker konteyneri içinde `frappe` kullanıcısının bench komutlarını çalıştırma ve dizin yazma izinleri tam olmalıdır.
2. **Konteyner Ağ ve Servis İletişimi:** CI runner'ında çalışan `mariadb`, `redis-cache` ve `redis-queue` servis konteynerlerine sorunsuz erişim sağlanmalıdır.
3. **Private Repo Güvenliği:** `kta_system_utils` private reposu Dockerfile içine statik yazılmamalı, CI runtime sırasında `KTA_SYSTEM_UTILS_PAT` ile çekilmelidir.
4. **Fallback Güvencesi:** Eğer GHCR imajı henüz ilk kez basılmamışsa veya imaj indirmede bir problem olursa akışın yönetilebilir olması.
5. **Frontend Build Doğrulaması:** `bench build --app erpnextkta --production` adımı testlerden önce hatasız çalışarak bozuk Vue/JS paketlerini yakalamalıdır.

---

### Task 1: Dockerfile Hazırlığı (`docker/ci/Dockerfile`)

**Files:**
- Create: `docker/ci/Dockerfile`

- [x] **Step 1.1: `docker/ci/Dockerfile` dosyasını oluştur**
  - Base: `ubuntu:22.04`
  - Sistem paketleri: Node 20, Yarn, Python 3.10, MariaDB client, build-essential, libmysqlclient-dev, cron, tzdata
  - `frappe` kullanıcısı oluştur ve sudo grubuna ata
  - `/home/frappe/frappe-bench` altında `bench init` çalıştır
  - `payments`, `hrms`, `erpnext`, `trtaxoffices`, `trtcmb`, `trebelge` uygulamalarını `--depth 1` ile bench içine al
  - Python sanal ortamında `setuptools<81` ve `tzdata` kur

- [x] **Step 1.2: Dockerfile sözdizimi ve adımlarını doğrula**
  - Dosyanın katman sıralamasını ve izin yapılandırmasını kontrol et.

---

### Task 2: Base İmajı Derleyip GHCR'a Basan İş Akışı (`.github/workflows/docker-ci-base.yml`)

**Files:**
- Create: `.github/workflows/docker-ci-base.yml`

- [x] **Step 2.1: `docker-ci-base.yml` iş akışını oluştur**
  - `workflow_dispatch` (manuel tetikleme) ve `push` (yalnızca `docker/ci/**` değiştiğinde) tetikleyicilerini tanımla.
  - `permissions: packages: write, contents: read` ata.
  - `docker/setup-buildx-action` ve `docker/login-action` ile `ghcr.io` oturumu aç (`GITHUB_TOKEN` kullanarak).
  - `docker/build-push-action` ile `ghcr.io/kta-endustri-sistemleri/frappe-ci-base:v15` etiketini pushla.

---

### Task 3: `.github/workflows/tests.yml` Dosyasının Refactor Edilmesi

**Files:**
- Modify: `.github/workflows/tests.yml`

- [x] **Step 3.1: Hazır Docker imajını konteyner olarak tanımla**
  - `container: ubuntu:22.04` yerine `ghcr.io/kta-endustri-sistemleri/frappe-ci-base:v15` tanımla.
  - `credentials: username: ${{ github.actor }}, password: ${{ secrets.GITHUB_TOKEN }}` ekle.

- [x] **Step 3.2: Gereksiz kurulum adımlarını ayıkla**
  - `Bootstrap Container` (apt-get vb.), `Setup Python` ve `Setup bench and DB` (bench init) adımlarını kaldır.
  - Sadece MariaDB bağlantı kontrolünü bırak.

- [x] **Step 3.3: Uygulama kurulumunu ve frontend derlemesini ekle**
  - Sadece private `kta_system_utils` ve `erpnextkta` reposunu bağla.
  - `new-site` ve app yüklemelerini çalıştır.
  - Testlerden hemen önce `bench build --app erpnextkta --production` adımını ekle.

---

### Task 4: Doğrulama, Git Commit ve PR Hazırlığı

**Files:**
- Modify/Create: İlgili tüm CI dosyaları
- Branch: `feat/ci-docker-base-image`

- [x] **Step 4.1: Dosyaları stage et ve Conventional Commit oluştur**
  - Commit mesajı: `feat(ci): add pre-built docker base image workflow and speed up ci`

- [x] **Step 4.2: Origin'e pushla ve PR şablonunu hazırla**
  - `git push -u origin feat/ci-docker-base-image`
  - `.github/PULL_REQUEST_TEMPLATE.md` ile kopyalanabilir PR açıklamasını oluştur.
