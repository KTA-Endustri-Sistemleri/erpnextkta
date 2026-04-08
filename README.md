# 📦 ERPNEXTKTA – Custom App

ERPNextKTA, KTA Endüstri Sistemleri için geliştirilen ERPNext/Frappe tabanlı özelleştirilmiş bir üretim, kalite ve operasyon yönetimi uygulamasıdır.

Uygulama; iş emirleri, iş kartları, operasyon akışları, üretim planlama, kesim formları, tarama sistemleri (QR Scanner) ve şirket içi özel süreçlerin tamamını dijitalleştirmek amacıyla tasarlanmıştır.

---

<details>
<summary><strong>👥 1) Kullanıcılar İçin</strong></summary>

<br>

Bu bölüm, ERPNextKTA uygulamasını kullanacak <strong>son kullanıcılar</strong> için sade bir genel bakış sunar.

## 🎯 ERPNextKTA Nedir?

ERPNextKTA, standart ERPNext işleyişine ek olarak aşağıdaki alanlarda kapsamlı geliştirmeler içerir:

### 🔧 Üretim & Operasyon Yönetimi  
- Gelişmiş <strong>İş Kartı (Job Card)</strong> akışı  
- Çoklu operatör desteği  
- Alt operasyon tanımlama  
- Detaylı zaman ve adet kayıtları  
- Üretim saha süreçlerinde hız ve doğruluk artışı  

### 🏭 Kesim & Forma Yönetimi  
- Müşteri gruplarına göre otomatik dosya klasörleme  
- Kesim formlarının ürün ve BOM'lara otomatik eşlenmesi  
- PDF işleme & otomatik adlandırma  

### 📦 Stok & Lojistik  
- Gelişmiş negatif stok kuralları  
- Üretimden otomatik giriş/çıkış hareketleri  
- Üretim planlama için veri hazırlığı  

### 📱 QR Scanner Entegrasyonu  
- Masaüstü + Mobil tarama desteği  
- Duplicate ve hız kontrol mekanizması  
- Otomatik hata yönetimi & kullanıcıya anlık geri bildirim  

### 📊 Yönetici Araçları  
- Özel raporlar  
- İç süreçlere uygun iş akışları  
- Kullanıcı dostu ekranlar  
- Dinamik yetki yönetimi (Admin Rolleri Konfigürasyonu)

</details>

---

<details>
<summary><strong>🧑‍💻 2) Geliştiriciler İçin</strong></summary>

<br>

Bu bölüm, projeye katkıda bulunacak veya geliştirme ortamında çalışacak geliştiricilere yöneliktir.  
Tüm semantic-release, CI/CD, versiyonlama, commit standartları ve proje teknik detayları burada yer alır.

---

# 📦 Semantic Release & Conventional Commit Rehberi  
**ERPNextKTA – Otomatik Versiyonlama, Yayın Süreci ve Commit Standartları**

Bu proje, otomatik versiyonlama, otomatik tag oluşturma, otomatik CHANGELOG üretimi ve GitHub Release entegrasyonu için <strong>python-semantic-release</strong> kullanmaktadır.  
Buna ek olarak, commit mesajları tamamen <strong>Conventional Commits</strong> standardına göre yazılmalıdır.

Bu iki yapı birlikte çalışarak:  
✔ Versiyonlamayı otomatize eder  
✔ Changelog'u otomatik üretir  
✔ Dağıtımı standartlaştırır  
✔ Kod kalitesini artırır  
✔ Production ERPNext uygulaması için net bir sürüm takibi sağlar  

---

## 🚀 Özellikler

- Commit mesajlarına göre <strong>otomatik versiyon artırma</strong>
- <code>erpnextkta/__init__.py</code> içindeki <code>__version__</code> değerinin otomatik güncellenmesi
- Otomatik <strong>Git tag</strong> (ör. <code>v0.4.0</code>, <code>v1.0.0</code>)
- Otomatik <strong>CHANGELOG.md</strong>
- Otomatik <strong>GitHub Release</strong>
- Lokal makinede Node.js gerekmez
- CI/CD (GitHub Actions) ile tam entegre
- ERPNext/Frappe ile uyumlu sürüm takibi

---

## 🧩 Semantic Release Çalışma Mantığı

Semantic Release commit mesajlarını analiz eder ve üç tip değişiklikten birine göre sürüm artırır:

| Commit Prefix          | Versiyon Türü           | Semantic-release davranışı        |
|------------------------|-------------------------|-----------------------------------|
| <code>fix:</code>      | Patch (x.y.z → x.y.z+1) | Hata düzeltmesi                   |
| <code>feat:</code>     | Minor (x.y.z → x.y+1.0) | Yeni özellik                      |
| <code>BREAKING CHANGE:</code> | Major (x.y.z → x+1.0.0) | Geriye dönük uyumsuz değişiklik |

Commit mesajları <strong>Conventional Commits</strong> standardına uygun olmalıdır.

---

## ✔️ Versiyon Bilgisi

Sürüm numarası yalnızca:

```text
erpnextkta/__init__.py
```

dosyasında tutulur:

```python
__version__ = "0.0.1"
```

Semantic Release bu değeri otomatik günceller.

---

## 📁 Yapılandırma (pyproject.toml)

```toml
[tool.semantic_release]
version_variables = ["erpnextkta/__init__.py:__version__"]
commit_parser = "conventional"
tag_format = "v{version}"

[tool.semantic_release.remote]
name = "origin"
type = "github"
token = { env = "GH_TOKEN" }
ignore_token_for_push = false
insecure = false
branch = "main"
```

---

## 🤖 GitHub Actions Pipeline

<code>.github/workflows/release.yml</code>:

```yaml
name: Semantic Release

on:
  push:
    branches:
      - main

permissions:
  contents: write

jobs:
  release:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install python-semantic-release
        run: |
          python -m pip install --upgrade pip
          pip install python-semantic-release

      - name: Run Semantic Release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          semantic-release version --push --vcs-release
```

---

## ✍️ Conventional Commit Rehberi

Commit formatı:

```text
<type>(scope): <summary>

<body - optional>

BREAKING CHANGE: <description - optional>
```

---

### Commit Türleri

| Type     | Açıklama           | Semantic Release |
|----------|--------------------|------------------|
| feat     | Yeni özellik       | minor bump       |
| fix      | Hata düzeltme      | patch bump       |
| refactor | Yapısal değişiklik | bump yok         |
| perf     | Performans         | bump yok         |
| docs     | Dokümantasyon      | bump yok         |
| style    | Format             | bump yok         |
| test     | Testler            | bump yok         |
| chore    | Yapılandırma       | bump yok         |
| ci       | CI/CD              | bump yok         |

---

### Önerilen Scope’lar

- <code>job-card</code>
- <code>work-order</code>
- <code>qr-scanner</code>
- <code>doctype:&lt;name&gt;</code>
- <code>client</code>
- <code>server</code>
- <code>api</code>
- <code>hooks</code>

---

### Örnek Commit Mesajları

#### Patch

```text
fix(work-order): incorrect status calculation when job cards paused
```

#### Minor

```text
feat(job-card): add operator assignment validation
```

#### Major

```text
feat(api): new time log schema

BREAKING CHANGE: old time_logs format is no longer supported
```

#### Refactor

```text
refactor(qr): extract scanner state logic
```

#### Docs

```text
docs: update semantic release installation guide
```

---

## 🚫 Kaçınılması Gereken Commit Mesajları

- <code>update code</code>
- <code>fixing issues</code>
- <code>temp</code>
- <code>deneme</code>
- <code>aaa</code>
- <code>final</code>

---

## 📦 Production Deploy

- Git tag oluşturulduğunda production <code>git pull</code> ile yeni sürümü otomatik alır  
- ERPNext <strong>App Versions</strong> ekranı otomatik güncellenir  
- <code>CHANGELOG.md</code> güncel olur  

---

# 🛠️ Test Otomasyonu ve Kalite Kontrol (QA)

ERPNextKTA projesi, kod kalitesini korumak ve regresyonu önlemek için kapsamlı bir test altyapısına sahiptir.

## 🧪 Birim Testleri (Unit Tests)

Uygulamanın mantıksal doğruluğunu test etmek için Frappe'nin yerleşik test runner'ı kullanılır.

### Manuel Test Çalıştırma
Spesifik bir modülü test etmek için:
```bash
bench --site [site-adı] run-tests --module erpnextkta.kta_calisma_karti.doctype.calisma_karti.test_calisma_karti
```

### VS Code Entegrasyonu
`.code-workspace` dosyasındaki tanımlı görevler sayesinde:
- **KTA: Run Specific Test (Local)**: Terminale girmeden doğrudan aktif testi koşturur.
- **KTA: Local CI Simulation (act)**: GitHub ortamını yerelde simüle eder.

---

## 🤖 CI/CD ve Otomatik Testler

Her `push` ve `Pull Request` işleminde `.github/workflows/tests.yml` akışı otomatik olarak tetiklenir.

### İşleyiş:
1.  **Ortam Hazırlığı:** Ubuntu konteyner üzerinde MariaDB ve Redis servisleri ayağa kaldırılır.
2.  **Bağımlılıkların Kurulumu:** ERPNext ve gerekli tüm yan uygulamalar (trtaxoffices vb.) temiz bir şekilde kurulur.
3.  **Otomatik Test Koşumu:** Tüm unit testler izole bir veri tabanı üzerinde koşturulur.
4.  **Sonuç Raporlama:** Başarısız testler Pull Request aşamasında bloklanır.

---

## 🎭 Yerel CI Simülasyonu (`act`)

GitHub sunucularına kod göndermeden önce tüm test sürecini kendi makinenizde (Docker üzerinde) deneyebilirsiniz.

### Ön Gereksinimler:
- Docker yüklü olmalıdır.
- `act` aracı sistemde kurulu olmalıdır.

### Çalıştırma:
```bash
act -j tests
```
*Not: Yerel Redis/MariaDB portlarıyla çakışma yaşanmaması için workflow dosyasında port remapping (33066, 11001, 13001) uygulanmıştır.*

---

## 🎉 Sonuç

Bu yapı sayesinde:

- Manuel versiyon artırma yok  
- Manuel tag yok  
- Otomatik changelog  
- Standart commit formatı  
- Daha güvenli deployment  
- ERPNext/Frappe ile tam uyumlu bir geliştirme süreci  

</details>