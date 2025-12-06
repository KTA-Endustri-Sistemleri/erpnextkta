## ERPNEXTKTA - Custom App

# 📦 Semantic Release & Conventional Commit Rehberi
**ERPNextKTA – Otomatik Versiyonlama, Yayın Süreci ve Commit Standartları**

Bu proje, otomatik versiyonlama, otomatik tag oluşturma, otomatik CHANGELOG üretimi ve GitHub Release entegrasyonu için **python-semantic-release** kullanmaktadır.  
Buna ek olarak, commit mesajları tamamen **Conventional Commits** standardına göre yazılmalıdır.

Bu iki yapı birlikte çalışarak:  
✔ Versiyonlamayı otomatize eder  
✔ Changelog'u otomatik üretir  
✔ Dağıtımı standartlaştırır  
✔ Kod kalitesini artırır  
✔ Production ERPNext uygulaması için net bir sürüm takibi sağlar  

---

## 🚀 Özellikler

- Commit mesajlarına göre **otomatik versiyon artırma**
- `erpnextkta/__init__.py` içindeki `__version__` değerinin otomatik güncellenmesi
- Otomatik **Git tag** (ör. `v0.4.0`, `v1.0.0`)
- Otomatik **CHANGELOG.md**
- Otomatik **GitHub Release**
- Lokal makinede Node.js gerekmez
- CI/CD (GitHub Actions) ile tam entegre
- ERPNext/Frappe ile uyumlu sürüm takibi

---

## 🧩 Semantic Release Çalışma Mantığı

Semantic Release commit mesajlarını analiz eder ve üç tip değişiklikten birine göre sürüm artırır:

| Commit Prefix          | Versiyon Türü         | Semantic-release davranışı |
|------------------------|------------------------|-----------------------------|
| `fix:`                 | Patch (x.y.z → x.y.z+1) | Hata düzeltmesi |
| `feat:`                | Minor (x.y.z → x.y+1.0) | Yeni özellik |
| `BREAKING CHANGE:`     | Major (x.y.z → x+1.0.0) | Geriye dönük uyumsuz değişiklik |

Commit mesajları **Conventional Commits** standardına uygun olmalıdır.

---

## ✔️ Versiyon Bilgisi

Sürüm numarası yalnızca:

```
erpnextkta/__init__.py
```

dosyasında yönetilir:

```python
__version__ = "0.0.1"
```

Semantic Release bu değeri otomatik değiştirir.

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

`.github/workflows/release.yml`:

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

Commit mesajı formatı:

```
<type>(scope): <short summary>

<body - optional>

BREAKING CHANGE: <description - optional>
```

---

### Commit Türleri

| Type     | Açıklama | Semantic Release |
|----------|----------|------------------|
| feat     | Yeni özellik | minor bump |
| fix      | Hata düzeltme | patch bump |
| refactor | Yapısal değişiklik | bump yok |
| perf     | Performans | bump yok |
| docs     | Dokümantasyon | bump yok |
| style    | Format | bump yok |
| test     | Testler | bump yok |
| chore    | Yapılandırma | bump yok |
| ci       | CI/CD | bump yok |

---

### Önerilen Scope’lar

- `job-card`
- `work-order`
- `qr-scanner`
- `doctype:<name>`
- `client`
- `server`
- `api`
- `hooks`

---

### Örnek Commit Mesajları

#### Patch
```
fix(work-order): incorrect status calculation when job cards paused
```

#### Minor
```
feat(job-card): add operator assignment validation
```

#### Major
```
feat(api): new time log schema

BREAKING CHANGE: old time_logs format is no longer supported
```

#### Refactor
```
refactor(qr): extract scanner state logic
```

#### Docs
```
docs: update semantic release installation guide
```

---

## 🚫 Kaçınılması Gereken Commit Mesajları

- `update code`
- `fixing issues`
- `temp`
- `deneme`
- `aaa`
- `final`

---

## 📦 Production Deploy

- Git tag oluşturulduğunda production `git pull` ile yeni sürüm otomatik alınır.  
- ERPNext App Versions ekranı otomatik güncellenir.  
- CHANGELOG.md güncellenmiş olur.

---

## 🎉 Sonuç

Bu yapı sayesinde:

- Manuel versiyon artırma yok  
- Manuel tag yok  
- Otomatik changelog  
- Standart commit formatı  
- Daha güvenli deployment süreci  
- ERPNext/Frappe ile tam entegre bir geliştirme standardı

#### License

MIT