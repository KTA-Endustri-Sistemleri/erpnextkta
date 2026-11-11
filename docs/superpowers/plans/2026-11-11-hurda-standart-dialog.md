# Hurda Standart Dialog Dönüşümü Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Çalışma Kartı Hurda modülündeki özel Vue modalı (`CkHurdaModal.vue`) kaldırılarak, Krimp, IDC ve Barkod modüllerinde kullanılan standart `frappe.prompt` ve `useHurdaDialogs` composable mimarisine dönüştürülmesi.

**Architecture:** Frontend tarafında `hurdaFields` prompt tanımı güncellenir ve `useHurdaDialogs` composable'ı oluşturulur. `HurdaView.vue` doğrudan bu composable'ı kullanacak şekilde sadeleştirilir ve artık gereksiz hale gelen `CkHurdaModal.vue` bileşeni projeden silinir. Backend'deki kademeli sequence mirası (`get_allowed_items_with_groups`) ile mevcut ve önceki operasyonların hammaddelerinin filtrelenmesi ve otomatik birim/depo atama mantığı aynen korunur.

**Tech Stack:** TypeScript, Vue 3, Frappe Framework (`frappe.prompt`, `frappe.confirm`), Python (Frappe ORM).

**Spec:** Kullanıcı ile yapılan tasarım mutabakatı (Hurda Nedeni için `Select`, Parça No için `Link`, `useHurdaDialogs` mimarisi).

## Global Constraints

- Frontend derlemesi daima `bench build --app erpnextkta --production` komutu ile yapılmalıdır (`yarn build` asla doğrudan çalıştırılmamalıdır).
- Tüm kullanıcı arayüzü metinleri `__("...")` çeviri sarmalayıcısı ile yazılmalıdır.
- Buton, başlık ve etiketlerde Title Case standardı korunmalıdır.
- Parça seçiminde `search_allowed_hurda_items` filtresi kullanılarak mevcut ve önceki operasyonların hammaddeleri listelenmeye devam etmelidir.

## Review Focus

1. **Parça filtreleme:** `parca_no` Link alanında `search_allowed_hurda_items` sorgusunun doğru `calisma_karti` parametresiyle çağrılması ve sadece izinli BOM kalemlerini getirmesi.
2. **Hurda nedeni listesi:** `hurda_nedeni` Select alanının `get_hurda_nedeni_options` API'sinden gelen güncel masraf merkezleriyle doldurulması ve varsayılan boş seçenek içermesi.
3. **Miktar doğrulaması:** `miktar` alanının ondalık klavye uyumlu (`applyDecimalInputMode`) ve zorunlu (`reqd: 1`) olması.
4. **Düzenleme (Edit) modu:** Düzenleme penceresi açıldığında mevcut satırdaki `parca_no`, `hurda_nedeni`, `miktar` ve `aciklama` değerlerinin form alanlarına eksiksiz yüklenmesi.
5. **Silme onayı:** Hurda satırı silinirken `frappe.confirm` ile onay alınması ve silme sonrası bildirim gösterilmesi.

---

### Task 1: Hurda Prompt Tanımının Güncellenmesi (`hurda.ts`)

**Files:**
- Modify: `erpnextkta/public/view-calisma-karti/composables/prompts/hurda.ts`

**Interfaces:**
- Produces: `hurdaFields(defaults: any)` -> array of Frappe field definitions (`parca_no`, `hurda_nedeni`, `miktar`, `aciklama`).

- [x] **Step 1: `hurdaFields` fonksiyonunu standart alanlarla güncelle**
  - `parca_no`: Link to `Item`, get_query filters `{ calisma_karti: defaults.calisma_karti_name }`, description: `__("Mevcut ve önceki operasyonlara ait izinli BOM hammaddeleri")`.
  - `hurda_nedeni`: Select fieldtype, options: `defaults.hurda_nedenleri || [""]`, reqd: 1, default: `defaults.hurda_nedeni || ""`.
  - `miktar`: Float fieldtype, reqd: 1, default: `defaults.miktar ?? ""`.
  - `aciklama`: Small Text fieldtype, reqd: 0, default: `defaults.aciklama || ""`.
  - Gereksiz `birim` ve `depo` alanlarını formdan kaldır (backend bunları otomatik atamaktadır).

- [x] **Step 2: TypeScript tiplerini ve export'ları kontrol et**

---

### Task 2: `useHurdaDialogs.ts` Composable'ının Oluşturulması

**Files:**
- Create: `erpnextkta/public/view-calisma-karti/composables/dialogs/useHurdaDialogs.ts`

**Interfaces:**
- Consumes: `hurdaFields` from `../prompts/hurda`, `props` containing `doc`, `onAdd`, `onUpdate`, `onDelete`.
- Produces: `{ addHurda, editHurda, deleteHurda }`

- [x] **Step 1: `useHurdaDialogs` composable dosyasını oluştur**
  - `get_hurda_nedeni_options` API'sini çağırarak hurda nedenlerini önbelleğe alan yardımcı fonksiyon yaz.
  - `addHurda()`: `frappe.prompt` açar, form değerlerini doğrular, `props.onAdd` çağırır ve başarı mesajı gösterir.
  - `editHurda(row)`: `frappe.prompt` açar (row değerleriyle varsayılanları doldurur), `props.onUpdate` çağırır ve başarı mesajı gösterir.
  - `deleteHurda(row)`: `frappe.confirm` ile onay sorar, `props.onDelete` çağırır ve başarı mesajı gösterir.

- [x] **Step 2: `useHurdaDialogs` composable'ını `composables/dialogs/index.ts` veya doğrudan `HurdaView.vue` içinde dışa aktar**

---

### Task 3: `HurdaView.vue` Sadeleştirmesi ve `CkHurdaModal.vue` Dosyasının Kaldırılması

**Files:**
- Modify: `erpnextkta/public/view-calisma-karti/views/HurdaView.vue`
- Delete: `erpnextkta/public/view-calisma-karti/components/CkHurdaModal.vue`

**Interfaces:**
- Consumes: `useHurdaDialogs(props)` from `../composables/dialogs/useHurdaDialogs`.

- [x] **Step 1: `HurdaView.vue` bileşenini güncelle**
  - `CkHurdaModal` importunu ve `<CkHurdaModal>` etiketini kaldır.
  - `const { addHurda, editHurda, deleteHurda } = useHurdaDialogs(props)` bağla.
  - "Hurda Ekle" butonuna `@click="addHurda"` bağla.
  - Liste elemanlarındaki "Düzenle" butonuna `@click="editHurda(h)"`, "Sil" butonuna `@click="deleteHurda(h)"` bağla.
  - Kullanılmayan `showModal`, `editItem`, `handleModalSubmit` state'lerini temizle.

- [x] **Step 2: `CkHurdaModal.vue` dosyasını sil**
  - Dosyayı projeden güvenle kaldır.

---

### Task 4: Frontend Derlemesi, Testler ve Doğrulama

**Files:**
- Verification only

- [x] **Step 1: Frontend derlemesini çalıştır**
  - Komut: `bench build --app erpnextkta --production`
  - Beklenen: Hatasız derleme tamamlanması.

- [x] **Step 2: Hurda ve Çalışma Kartı testlerini çalıştır**
  - Komut: `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_calisma_karti.doctype.calisma_karti_hurda.test_calisma_karti_hurda`
  - Komut: `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_calisma_karti.doctype.calisma_karti.test_calisma_karti_unit`
  - Beklenen: Tüm testlerin yeşil (OK) geçmesi.

- [x] **Step 3: Git diff kontrolü ve özet**
  - Yapılan değişikliklerin `git status` ve `git diff` ile incelenmesi.

