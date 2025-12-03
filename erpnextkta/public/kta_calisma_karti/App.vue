<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import StepWorkOrder from './components/StepWorkOrder.vue';
import StepJobCard from './components/StepJobCard.vue';
import StepOperation from './components/StepOperation.vue';
import StepWorkstation from './components/StepWorkstation.vue';
import StepUser from './components/StepUser.vue';
import StepIndicator from './components/StepIndicator.vue';

// ---- STATE ----
const currentStep = ref(1);
const totalSteps = 5;

// Step 1: Work Order
const workOrderBarcode = ref('');
const workOrder = ref(null); // { name, production_item, qty, ... }

// Step 2: Job Card
const jobCards = ref([]);
const selectedJobCardName = ref(null);

// Step 3: Operation
const operations = ref([]);
const selectedOperationName = ref(null);

// Step 4: Workstation
const selectedWorkstation = ref(null);
// Step 4: Auto-fill highlight flag
const workstationAutoFilled = ref(false);

// Step 5: User
const users = ref([]);
const selectedUser = ref(null); // Employee.name (EMP-0001 vb.)

const loading = ref(false);
const errorMessage = ref(null);

// ✅ Oluşturulan Çalışma Kartı
const createdDoc = ref(null);

// ---- DERIVED ----
const selectedJobCard = computed(() => {
  return jobCards.value.find(jc => jc.name === selectedJobCardName.value) || null;
});

const selectedOperation = computed(() => {
  return (
    operations.value.find(
      (op) => op.calisma_karti_op === selectedOperationName.value
    ) || null
  );
});

const selectedEmployee = computed(() => {
  return users.value.find(emp => emp.name === selectedUser.value) || null;
});

// 🔹 Step indicator açıklamaları
const steps = computed(() => {
  const wo = workOrder.value;
  const jc = selectedJobCard.value;
  const op = selectedOperation.value;
  const emp = selectedEmployee.value;
  const ws = selectedWorkstation.value;

  // 1) İş Emri
  let step1Desc = 'Work Order barkodu';
  if (wo && wo.name) {
    step1Desc = wo.name;
  }

  // 2) İş Kartı
  let step2Desc = 'Seçilecek İş Kartı';
  if (jc) {
    const parts = [jc.name];
    step2Desc = parts.join(' · ');
  }

  // 3) İş İstasyonu
  let step3Desc = 'Varsayılan veya manuel istasyon';
  if (ws) {
    step3Desc = ws;
  }

  // 4) Operasyon
  let step4Desc = 'Operasyon seçimi';
  if (op && op.calisma_karti_op) {
    step4Desc = op.calisma_karti_op;
  } else if (selectedOperationName.value) {
    step4Desc = selectedOperationName.value;
  }

  // 5) Operatör (Employee)
  let step5Desc = 'Operatör (Employee) seçimi';
  if (emp) {
    step5Desc = emp.employee_name || emp.name;
  }

  return [
    { id: 1, label: 'İş Emri',      description: step1Desc },
    { id: 2, label: 'İş Kartı',     description: step2Desc },
    { id: 3, label: 'İş İstasyonu', description: step3Desc },
    { id: 4, label: 'Operasyon',    description: step4Desc },
    { id: 5, label: 'Operatör',     description: step5Desc },
  ];
});

// ---- HELPER: frappe.call'ı Promise'e sardık ----
function callFrappe(method, args = {}) {
  return new Promise((resolve, reject) => {
    frappe.call({
      method,
      args,
      callback: (r) => {
        resolve(r.message);
      },
      error: (err) => {
        reject(err);
      }
    });
  });
}

// ✅ Merkezi loading helper: min süre garantili
async function withLoading(taskFn, minMs = 700) {
  loading.value = true;
  const delay = new Promise(resolve => setTimeout(resolve, minMs));
  try {
    const result = await taskFn();
    await delay;
    return result;
  } finally {
    loading.value = false;
  }
}

// ---- VALIDATION ----
const isStepValid = computed(() => {
  switch (currentStep.value) {
    case 1:
      return !!workOrder.value;
    case 2:
      return !!selectedJobCard.value;
    case 3:
      return !!selectedWorkstation.value;
    case 4:
      // sadece bir operasyon seçilmiş olması yeterli
      return !!selectedOperationName.value;
    case 5:
      return !!selectedUser.value;
    default:
      return false;
  }
});

// ---- API CALLS ----

// 1) Barkod -> Work Order
async function fetchWorkOrderByBarcode() {
  if (!workOrderBarcode.value.trim()) return;

  errorMessage.value = null;

  try {
    await withLoading(async () => {
      const msg = await callFrappe(
        'erpnextkta.kta_calisma_karti.api.get_work_order_by_barcode',
        { barcode: workOrderBarcode.value.trim() }
      );

      workOrder.value = msg || null;

      if (!workOrder.value || !workOrder.value.name) {
        throw new Error('Work Order bulunamadı.');
      }

      // İş Emri bulundu → Job Card listesi
      await fetchJobCardsForWorkOrder();
      currentStep.value = 2;
    }, 800); // WO adımı için min 800ms overlay
  } catch (err) {
    console.error(err);
    errorMessage.value =
      (err && err.message) ||
      (err && err._server_messages) ||
      'Work Order alınırken hata oluştu.';
    workOrder.value = null;
    jobCards.value = [];
    selectedJobCardName.value = null;
  }
}

// 2) Work Order’a bağlı Job Card listesi (frappe.client.get_list)
// Burada loading yönetmiyoruz; üstten (fetchWorkOrderByBarcode) geliyor.
async function fetchJobCardsForWorkOrder() {
  if (!workOrder.value || !workOrder.value.name) return;

  const list = await callFrappe('frappe.client.get_list', {
    doctype: 'Job Card',
    filters: {
      work_order: workOrder.value.name
    },
    fields: ['name', 'operation', 'workstation'],
    limit_page_length: 500
  });

  jobCards.value = list || [];

  if (jobCards.value.length === 1) {
    selectedJobCardName.value = jobCards.value[0].name;
  }
}

// 3) Operasyon listesi (KTA Calisma Karti Operasyonlari)
async function fetchOperations() {
  errorMessage.value = null;

  try {
    await withLoading(async () => {
      const list = await callFrappe('frappe.client.get_list', {
        doctype: 'KTA Calisma Karti Operasyonlari',
        fields: ['calisma_karti_op'],
        limit_page_length: 500
      });

      operations.value = list || [];
      selectedOperationName.value = null;
    }, 500); // min 500ms overlay
  } catch (err) {
    console.error(err);
    errorMessage.value =
      (err && err.message) ||
      'Operasyon listesi alınırken hata oluştu.';
    operations.value = [];
    selectedOperationName.value = null;
  }
}

// 4) Kullanıcı listesi (Employee)
async function fetchUsers() {
  errorMessage.value = null;

  try {
    await withLoading(async () => {
      const list = await callFrappe('frappe.client.get_list', {
        doctype: 'Employee',
        filters: {
          status: 'Active',           // aktif çalışanlar
          user_id: ['is', 'set']
        },
        fields: ['name', 'employee_name', 'user_id', 'department'],
        limit_page_length: 500
      });

      users.value = list || [];
      selectedUser.value = null;
    }, 500);
  } catch (err) {
    console.error(err);
    errorMessage.value =
      (err && err.message) ||
      'Kullanıcı listesi alınırken hata oluştu.';
    users.value = [];
    selectedUser.value = null;
  }
}

// ---- Workstation sync ----
function syncWorkstationFromJobCard() {
  if (selectedJobCard.value && selectedJobCard.value.workstation) {
    selectedWorkstation.value = selectedJobCard.value.workstation;
    // kısa süreli highlight için bayrağı aç
    workstationAutoFilled.value = true;
    setTimeout(() => {
      workstationAutoFilled.value = false;
    }, 1200); // 1.2 sn sonra highlight söner
  } else {
    selectedWorkstation.value = null;
  }
}

// ---- SUBMIT: Calisma Karti create (create_calisma_karti) ----
async function submitWorkCard() {
  if (!isStepValid.value) return;

  const payload = {
    custom_work_order: workOrder.value.name,
    is_karti: selectedJobCard.value.name,
    operasyon: selectedOperationName.value,
    is_istasyonu: selectedWorkstation.value,
    operator: selectedUser.value
  };

  errorMessage.value = null;

  try {
    await withLoading(async () => {
      const msg = await callFrappe(
        'erpnextkta.kta_calisma_karti.api.create_calisma_karti',
        payload
      );

      // Oluşan dokümanı state'e al
      if (msg && msg.name) {
        createdDoc.value = msg;
      } else {
        createdDoc.value = { name: msg && msg.name ? msg.name : '' };
      }
      // Success ekranı wizard içinde gösteriliyor
    }, 900); // submit sırasında min 900ms overlay
  } catch (err) {
    console.error(err);
    errorMessage.value =
      (err && err.message) ||
      'Çalışma Kartı oluşturulurken hata oluştu.';
  }
}

// ---- NAV ----
function goNext() {
  if (!isStepValid.value) return;
  if (currentStep.value < totalSteps) {
    currentStep.value++;
  }
}

function goBack() {
  if (currentStep.value > 1) {
    currentStep.value--;
  }
}

function resetWizard() {
  currentStep.value = 1;
  workOrderBarcode.value = '';
  workOrder.value = null;

  // Job Cardlar her Work Order'a bağlı, bunları temizlemek mantıklı
  jobCards.value = [];
  selectedJobCardName.value = null;

  // ❗ Operasyon ve kullanıcı listelerini SİLME, sadece seçimleri temizle
  selectedOperationName.value = null;

  selectedWorkstation.value = null;
  workstationAutoFilled.value = false;

  selectedUser.value = null;

  errorMessage.value = null;
  createdDoc.value = null;
}

function goToCreatedDoc() {
  if (!createdDoc.value || !createdDoc.value.name) return;
  // ERPNext form route
  frappe.set_route('Form', 'Calisma Karti', createdDoc.value.name);
}

function startNewWorkCard() {
  resetWizard();
}

// ---- CHILD EVENTS ----
function handleWorkOrderBarcodeSubmit() {
  // Barkod okutulup Enter gelince
  fetchWorkOrderByBarcode();
}

// ---- GLOBAL ENTER HANDLER ----
function handleEnter(event) {
  if (loading.value) return;

  // Textarea veya buton üzerindeyken Enter'ı yok say
  const tag = (event.target && event.target.tagName) || '';
  if (tag === 'TEXTAREA' || tag === 'BUTTON') return;

  // 1. adım: her zaman barkodu dene (boşsa zaten hiçbir şey yapmayacak)
  if (currentStep.value === 1) {
    if (workOrderBarcode.value.trim()) {
      handleWorkOrderBarcodeSubmit();
    }
    return;
  }

  // Diğer adımlar için önce valid mi bak
  if (!isStepValid.value) return;

  if (currentStep.value < totalSteps) {
    goNext();
  } else {
    // Son adım: submit
    submitWorkCard();
  }
}

// Global keydown listener
function onGlobalKeydown(e) {
  if (e.key === 'Enter') {
    handleEnter(e);
  }
}

// Job Card değişince workstation sync
watch(selectedJobCardName, () => {
  syncWorkstationFromJobCard();
});

// İlk açılışta operasyon + kullanıcı listeleri + global Enter listener
onMounted(() => {
  fetchOperations();
  fetchUsers();
  window.addEventListener('keydown', onGlobalKeydown, { capture: true });
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeydown, { capture: true });
});
</script>
<template>
  <div class="w-full max-w-2xl mx-auto p-4 space-y-4">
    <!-- WIZARD MODU -->
  <template v-if="!createdDoc">
    <div class="flex flex-col gap-1">
      <StepIndicator
        :current-step="currentStep"
        :steps="steps"
      />
    </div>

    <div
      v-if="errorMessage"
      class="p-2 text-sm text-red-700 border border-red-300 rounded bg-red-50"
    >
      {{ errorMessage }}
    </div>

    <div class="wizard-card space-y-4">
      <Transition name="fade-step" mode="out-in">
        <div :key="currentStep">
          <!-- STEP 1: Work Order -->
          <StepWorkOrder
            v-if="currentStep === 1"
            v-model:barcode="workOrderBarcode"
            :work-order="workOrder"
            :loading="loading"
            @submit="handleWorkOrderBarcodeSubmit"
          />

          <!-- STEP 2: Job Card -->
          <StepJobCard
            v-else-if="currentStep === 2"
            :job-cards="jobCards"
            :selected-job-card-obj="selectedJobCard"
            v-model:selectedJobCard="selectedJobCardName"
          />

          <!-- STEP 3: Workstation -->
          <StepWorkstation
            v-else-if="currentStep === 3"
            :job-card="selectedJobCard"
            v-model:workstation="selectedWorkstation"
            :auto-filled="workstationAutoFilled"
          />

          <!-- STEP 4: Operation -->
          <StepOperation
            v-else-if="currentStep === 4"
            :operations="operations"
            v-model:selectedOperation="selectedOperationName"
          />

          <!-- STEP 5: User -->
          <StepUser
            v-else-if="currentStep === 5"
            :users="users"
            v-model:selectedUser="selectedUser"
          />
        </div>
      </Transition>

      <!-- LOADING OVERLAY -->
      <div v-if="loading" class="wizard-card__overlay">
        <div class="wizard-card__spinner"></div>
      </div>
    </div>

    <!-- NAVIGATION BAR -->
    <div class="wizard-nav">
      <div class="wizard-nav__left">
        <!-- Back Button (sadece step > 1 iken göster) -->
        <button
          v-if="currentStep > 1"
          type="button"
          class="nav-btn nav-btn--secondary"
          :disabled="loading"
          @click="goBack"
        >
          ← Geri
        </button>
      </div>

      <div class="wizard-nav__right">
        <!-- Next Button -->
        <button
          v-if="currentStep < totalSteps"
          type="button"
          class="nav-btn nav-btn--primary"
          :disabled="!isStepValid || loading"
          @click="goNext"
        >
          İleri →
        </button>

        <!-- Submit Button -->
        <button
          v-else
          type="button"
          class="nav-btn nav-btn--success"
          :disabled="!isStepValid || loading"
          @click="submitWorkCard"
        >
          {{ loading ? "Gönderiliyor..." : "Çalışma Kartını Oluştur" }}
        </button>
      </div>
    </div>
  </template>
  <!-- SUCCESS MODU -->
  <template v-else>
    <div class="wizard-card success-card">
      <div class="success-card__header">
        <div class="success-card__icon">✓</div>
        <div class="success-card__text">
          <h2 class="success-card__title">Çalışma Kartı oluşturuldu</h2>
          <p class="success-card__subtitle">
            Yeni Çalışma Kartı başarıyla kaydedildi.
          </p>
        </div>
      </div>

      <div
        v-if="createdDoc && createdDoc.name"
        class="success-card__doc"
      >
        <span class="success-card__doc-label">Doküman:</span>
        <span class="success-card__doc-value">{{ createdDoc.name }}</span>
      </div>

      <div class="success-card__actions">
        <button
          type="button"
          class="success-btn success-btn--primary"
          @click="goToCreatedDoc"
        >
          Çalışma Kartına Git
        </button>

        <button
          type="button"
          class="success-btn success-btn--secondary"
          @click="startNewWorkCard"
        >
          Yeni Çalışma Kartı Başlat
        </button>
      </div>
    </div>
  </template>
  </div>
</template>

<style scoped>
.wizard-card {
  position: relative;  /* BUNU ekle */
  background: #ffffff;
  border-radius: 0.75rem;
  border: 1px solid #e5e7eb; /* gray-200 */
  padding: 1rem;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.06);
}
/* Basit spinner */
.wizard-card__spinner {
  width: 26px;
  height: 26px;
  border-radius: 999px;
  border: 3px solid #bfdbfe;
  border-top-color: #2563eb;
  animation: wizard-spin 0.7s linear infinite;
}

@keyframes wizard-spin {
  to {
    transform: rotate(360deg);
  }
}
.wizard-card__overlay {
  position: absolute;
  inset: 0;
  background: rgba(249, 250, 251, 0.7); /* gri transparan */
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.75rem;
  z-index: 10;
}
/* SUCCESS CARD */
.success-card {
  text-align: center;
  padding-top: 1.25rem;
  padding-bottom: 1.25rem;
}

.success-card__header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

@media (min-width: 640px) {
  .success-card__header {
    flex-direction: row;
    justify-content: center;
    gap: 0.75rem;
  }
}

.success-card__icon {
  width: 40px;
  height: 40px;
  border-radius: 999px;
  background: #22c55e;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 1.2rem;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.25);
  flex-shrink: 0;
}

.success-card__text {
  text-align: center;
}

@media (min-width: 640px) {
  .success-card__text {
    text-align: left;
  }
}

.success-card__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: #111827;
}

.success-card__subtitle {
  margin: 0.15rem 0 0;
  font-size: 0.85rem;
  color: #4b5563;
}

.success-card__doc {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: #374151;
}

.success-card__doc-label {
  font-weight: 500;
}

.success-card__doc-value {
  margin-left: 0.25rem;
  font-weight: 600;
}

/* ACTION BUTTONS */
.success-card__actions {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  justify-content: center;
}

@media (min-width: 480px) {
  .success-card__actions {
    flex-direction: row;
  }
}

.success-btn {
  min-width: 140px;
  font-size: 0.85rem;
  padding: 0.45rem 0.9rem;
  border-radius: 0.5rem;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease,
    box-shadow 0.15s ease;
}

.success-btn--primary {
  background: #16a34a;
  border-color: #16a34a;
  color: #ffffff;
}

.success-btn--primary:hover {
  background: #15803d;
  border-color: #15803d;
  box-shadow: 0 1px 3px rgba(22, 163, 74, 0.4);
}

.success-btn--secondary {
  background: #f3f4f6;
  border-color: #d1d5db;
  color: #111827;
}

.success-btn--secondary:hover {
  background: #e5e7eb;
  border-color: #9ca3af;
}
/* STEP GEÇİŞ ANİMASYONU */
.fade-step-enter-active,
.fade-step-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.fade-step-enter-from,
.fade-step-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.fade-step-enter-to,
.fade-step-leave-from {
  opacity: 1;
  transform: translateY(0);
}
/* ----------------------------- */
/* WIZARD NAVIGATION BAR         */
/* ----------------------------- */

.wizard-nav {
  margin-top: 1rem;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  flex-wrap: wrap;
}

/* Genel buton */
.nav-btn {
  padding: 0.55rem 1rem;
  font-size: 0.85rem;
  border-radius: 0.5rem;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s ease;
  min-width: 110px;
}

/* Secondary (geri) */
.nav-btn--secondary {
  background: #f3f4f6;
  border-color: #d1d5db;
  color: #374151;
}
.nav-btn--secondary:hover:enabled {
  background: #e5e7eb;
}

/* Primary (ileri) */
.nav-btn--primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}
.nav-btn--primary:hover:enabled {
  background: #1d4ed8;
  border-color: #1d4ed8;
}

/* Success (submit) */
.nav-btn--success {
  background: #16a34a;
  border-color: #16a34a;
  color: #fff;
}
.nav-btn--success:hover:enabled {
  background: #15803d;
  border-color: #15803d;
}

/* Disabled state */
.nav-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* Mobil uyumlu */
@media (max-width: 640px) {
  .wizard-nav {
    justify-content: center;
  }
  .nav-btn {
    width: 100%;
  }
}
</style>