# MRP Birleşik Kontrol Çubuğu ve Filtreleme Düzeltmesi (Option A) Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MRP sayfasındaki çalışmayan hammadde ve tedarikçi filtrelerini (backend ve frontend katmanında) düzeltmek ve dikeyde fazla yer kaplayan hantal `MrpFilterBar` ile `MrpToolbar`'ı modern, kompakt ve tek satırlı birleşik bir kontrol çubuğunda toplamak.

**Architecture:** 
1. **Backend (`kta-mrp`):** `erpnextkta/kta_mrp/mrp_engine/service.py` içindeki `get_material_requirements_data` fonksiyonunda `materials_list` sonuçlarına `filters.hammadde`, `filters.supplier` ve `filters.item_group` filtrelerini uygulayarak sunucu yanıtını süzmek.
2. **Frontend State (`frontend-public`):** `erpnextkta/public/material-requirement/composables/useMrpState.ts` içindeki `filteredMaterials` computed fonksiyonuna `filters.supplier`, `filters.hammadde` ve `filters.item_group` kontrollerini eklemek (anlık reaktif istemci taraflı süzme).
3. **UI / UX (`frontend-public`):** `MrpFilterBar.vue` ve `MrpToolbar.vue` bileşenlerini tek bir kompakt çubuk halinde yeniden tasarlamak. `MrpFilterPopover.vue` alt bileşeniyle gelişmiş filtreleri (Tedarikçi, Hammadde, Ürün Grubu, Gruplama Şekli) zarif bir popover içinde sunmak, dikey alanı matrise bırakmak.

**Tech Stack:** Python (Frappe Framework v15), Vue 3 + TypeScript, Tailwind-inspired CSS variables (`--mrp-*`).

---

## Global Constraints
- Koordinatör kuralı: Uygulama kodları doğrudan düzenlenmez; `kta-mrp` ve `frontend-public` alt ajanları kullanılır.
- Tek Vue dosyası 500 satırı aşamaz. Gelişmiş filtre formu gerekirse `MrpFilterPopover.vue` olarak ayrılır.
- 100% Light & Dark tema uyumluluğu (`[data-theme="dark"]`, `--mrp-*` değişkenleri).
- Üretim derlemesi: Yalnızca `bench build --app erpnextkta --production`.
- Ticari veri gizliliği: Commit, PR veya dokümanlarda hiçbir gerçek firma adı veya fiyat yer alamaz.

---

## Tasks

### Görev 1: Backend Filtreleme Mantığının Düzeltilmesi (`kta-mrp`)
**Sahiplik:** `kta-mrp` (`erpnextkta/kta_mrp/**`)

- [ ] **Adım 1.1:** `erpnextkta/kta_mrp/mrp_engine/service.py` içinde `get_material_requirements_data` fonksiyonunu incele.
- [ ] **Adım 1.2:** `materials_list` oluşturulduktan sonra veya sırasında `filters.hammadde`, `filters.supplier` ve `filters.item_group` parametrelerine göre süzme mantığı ekle:
  ```python
  if filters.get("hammadde"):
      h = filters.get("hammadde").strip().lower()
      materials_list = [m for m in materials_list if h in m["item_code"].lower() or h in m["item_name"].lower()]
  if filters.get("supplier"):
      s = filters.get("supplier").strip().lower()
      materials_list = [m for m in materials_list if s in (m.get("supplier") or "").lower()]
  if filters.get("item_group"):
      ig = filters.get("item_group").strip().lower()
      materials_list = [m for m in materials_list if ig in (m.get("item_group") or "").lower()]
  ```
- [ ] **Adım 1.3:** Summary sayaçlarının (`total_items`, `shortage_count`, vb.) filtrelenmiş `materials_list` üzerinden doğru hesaplandığını doğrula.
- [ ] **Adım 1.4:** `ruff check` ve `ruff format --check` çalıştır.

---

### Görev 2: Frontend State ve İstemci Taraflı Filtreleme Mantığı (`frontend-public`)
**Sahiplik:** `frontend-public` (`erpnextkta/public/material-requirement/**`)

- [ ] **Adım 2.1:** `composables/useMrpState.ts` içindeki `filteredMaterials` computed süzgecine `filters.supplier`, `filters.hammadde` ve `filters.item_group` kontrollerini ekle:
  - Kullanıcı arama kutusuna yazdığında veya gelişmiş filtreleri girdiğinde anlık reaktif filtreleme sağla.
- [ ] **Adım 2.2:** `activeFilterCount` adında reaktif bir computed property ekle (aktif gelişmiş filtre sayısını gösteren rozet için).
- [ ] **Adım 2.3:** Filtre sıfırlama (`resetFilters`) fonksiyonunun tüm filtreleri temizlediğini doğrula.

---

### Görev 3: Birleşik Kontrol Çubuğu UI Tasarımı (Option A) (`frontend-public`)
**Sahiplik:** `frontend-public` (`erpnextkta/public/material-requirement/**`)

- [ ] **Adım 3.1:** Gelişmiş filtreler için `MrpFilterPopover.vue` bileşeni oluştur (Tedarikçi, Hammadde, Ürün Grubu, Gruplama Şekli, Ufuk/Tarih sıfırlama, Sıfırla ve Yenile butonları). Popover dışına tıklandığında kapanma (`click-outside`) desteği ekle.
- [ ] **Adım 3.2:** `MrpToolbar.vue` bileşenini Option A tasarımına göre yenile:
  - **Sol Blok:** Canlı Akıllı Arama (`filters.search_query`), Haftalık Gösterim Seçici Dropdown (Önerilen Sipariş / Net / Brüt / Projeksiyon).
  - **Orta Blok:** Mevcut şık durum hapları (`Tümü`, `Acil Eksikler`, `Tüm Eksikler`, `Açık PO`, `Antrepo`, `Gümrük`, `Yolda`).
  - **Sağ Blok:** Kompakt Planlama Ufku Rozeti (Örn: `📅 12 Hafta`), Filtreler Popover Butonu (aktif filtre rozeti ile), Sıralama ve Dışa Aktarma butonları.
- [ ] **Adım 3.3:** `App.vue` içindeki hantal `MrpFilterBar` çağrısını kaldır / entegre et. `MrpFilterBar.vue` bileşenini temizle veya birleşik kontrol çubuğuna entegre et.
- [ ] **Adım 3.4:** Hem Light hem Dark temada tam renk uyumunu (`--mrp-*` değişkenleri) sağla.

---

### Görev 4: Derleme ve Kalite Kontrol (Coordinator)
- [ ] **Adım 4.1:** `bench build --app erpnextkta --production` çalıştır ve hatasız derlendiğini doğrula.
- [ ] **Adım 4.2:** Ruff linter kontrollerini çalıştır.
- [ ] **Adım 4.3:** Değişiklikleri doğrula ve kullanıcıya sun.
