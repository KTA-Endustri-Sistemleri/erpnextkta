<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import StepWorkOrder from './components/StepWorkOrder.vue';
import StepJobCard from './components/StepJobCard.vue';
import StepOperation from './components/StepOperation.vue';
import StepWorkstation from './components/StepWorkstation.vue';
import StepUser from './components/StepUser.vue';

const BASE_URL = "http://kta-dev-v15.erpnext.com:8001"; // Gerekirse değiştirin

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

// Step 5: User
const users = ref([]);
const selectedUser = ref(null); // Link User (ör: "user@domain.com" ya da "Full Name")

const loading = ref(false);
const errorMessage = ref(null);

// ---- DERIVED ----
const selectedJobCard = computed(() => {
  return jobCards.value.find(jc => jc.name === selectedJobCardName.value) || null;
});

const selectedOperation = computed(() => {
  return operations.value.find(op => op.name === selectedOperationName.value) || null;
});

// ---- VALIDATION ----
const isStepValid = computed(() => {
  switch (currentStep.value) {
    case 1:
      // custom_work_order
      return !!workOrder.value;
    case 2:
      // is_karti
      return !!selectedJobCard.value;
    case 3:
      // operasyon
      return !!selectedOperation.value;
    case 4:
      // is_istasyonu
      return !!selectedWorkstation.value;
    case 5:
      // kullanıcı
      return !!selectedUser.value;
    default:
      return false;
  }
});

// ---- API CALLS ----

// 1) Barkod -> Work Order
async function fetchWorkOrderByBarcode() {
  if (!workOrderBarcode.value.trim()) return;

  loading.value = true;
  errorMessage.value = null;

  try {
    // Burada backend tarafında status/docstatus filtrelerini de uygulayabilirsin.
    const res = await fetch(
      `${BASE_URL}/api/method/erpnextkta.kta_calisma_karti.api.get_work_order_by_barcode?barcode=${encodeURIComponent(
        workOrderBarcode.value.trim()
      )}`,
      { credentials: 'include' }
    );

    if (!res.ok) {
      throw new Error('Work Order bulunamadı veya yetkiniz yok.');
    }

    const data = await res.json();
    workOrder.value = data.message || null;

    if (!workOrder.value || !workOrder.value.name) {
      throw new Error('Work Order bulunamadı.');
    }

    // İş Emri bulundu → Job Card listesi
    await fetchJobCardsForWorkOrder();
    currentStep.value = 2;
  } catch (err) {
    console.error(err);
    errorMessage.value = err.message || 'Work Order alınırken hata oluştu.';
    workOrder.value = null;
    jobCards.value = [];
    selectedJobCardName.value = null;
  } finally {
    loading.value = false;
  }
}

// 2) Work Order’a bağlı Job Card listesi
async function fetchJobCardsForWorkOrder() {
  if (!workOrder.value || !workOrder.value.name) return;

  loading.value = true;
  errorMessage.value = null;

  try {
    const filters = encodeURIComponent(
      JSON.stringify([['work_order', '=', workOrder.value.name]])
    );

    const res = await fetch(
      `${BASE_URL}/api/resource/Job Card?filters=${filters}`,
      { credentials: 'include' }
    );

    if (!res.ok) {
      throw new Error('Job Card listesi alınamadı.');
    }

    const data = await res.json();
    jobCards.value = data.data || [];

    if (jobCards.value.length === 1) {
      selectedJobCardName.value = jobCards.value[0].name;
    }
  } catch (err) {
    console.error(err);
    errorMessage.value = err.message || 'Job Card listesi alınırken hata oluştu.';
    jobCards.value = [];
    selectedJobCardName.value = null;
  } finally {
    loading.value = false;
  }
}

// 3) Operasyon listesi
async function fetchOperations() {
  loading.value = true;
  errorMessage.value = null;

  try {
    const res = await fetch(
      `${BASE_URL}/api/resource/KTA Calisma Karti Operasyonlari`,
      { credentials: 'include' }
    );

    if (!res.ok) {
      throw new Error('Operasyon listesi alınamadı.');
    }

    const data = await res.json();
    operations.value = data.data || [];
  } catch (err) {
    console.error(err);
    errorMessage.value = err.message || 'Operasyon listesi alınırken hata oluştu.';
    operations.value = [];
    selectedOperationName.value = null;
  } finally {
    loading.value = false;
  }
}

// 4) Kullanıcı listesi (görebildiği kullanıcılar)
// Frappe permission tree zaten User listesini kısıtlayacağı için
// normal /api/resource/User ile listeleyebilirsin.
async function fetchUsers() {
  loading.value = true;
  errorMessage.value = null;

  try {
    // örnek: sadece aktif sistem kullanıcıları
    const filters = encodeURIComponent(
      JSON.stringify([['enabled', '=', 1]])
    );
    const fields = encodeURIComponent(JSON.stringify(['name', 'full_name', 'email']));

    const res = await fetch(
      `${BASE_URL}/api/resource/User?filters=${filters}&fields=${fields}`,
      { credentials: 'include' }
    );

    if (!res.ok) {
      throw new Error('Kullanıcı listesi alınamadı.');
    }

    const data = await res.json();
    users.value = data.data || [];
  } catch (err) {
    console.error(err);
    errorMessage.value = err.message || 'Kullanıcı listesi alınırken hata oluştu.';
    users.value = [];
    selectedUser.value = null;
  } finally {
    loading.value = false;
  }
}

// ---- Workstation sync ----
function syncWorkstationFromJobCard() {
  if (selectedJobCard.value && selectedJobCard.value.workstation) {
    selectedWorkstation.value = selectedJobCard.value.workstation;
  } else {
    selectedWorkstation.value = null;
  }
}

// ---- SUBMIT: Calisma Karti create ----
async function submitWorkCard() {
  if (!isStepValid.value) return;

  // !!! Buradaki "sorumlu_kullanici" alan adını,
  // Calisma Karti doctype'ındaki gerçek fieldname'e göre güncelle.
  const payload = {
    custom_work_order: workOrder.value.name,
    is_karti: selectedJobCard.value.name,
    operasyon: selectedOperation.value.name,
    is_istasyonu: selectedWorkstation.value,
    sorumlu_kullanici: selectedUser.value // örnek field
  };

  loading.value = true;
  errorMessage.value = null;

  try {
    const res = await fetch(
      `${BASE_URL}/api/method/erpnextkta.kta_calisma_karti.api.create_calisma_karti`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    );

    if (!res.ok) {
      let msg = 'Çalışma Kartı oluşturulamadı.';
      try {
        const errData = await res.json();
        msg = errData.exc || msg;
      } catch (e) {}
      throw new Error(msg);
    }

    const data = await res.json();
    const docname = data.message && data.message.name
      ? data.message.name
      : JSON.stringify(data.message);

    alert('Çalışma Kartı oluşturuldu: ' + docname);
    resetWizard();
  } catch (err) {
    console.error(err);
    errorMessage.value = err.message || 'Çalışma Kartı oluşturulurken hata oluştu.';
  } finally {
    loading.value = false;
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
  jobCards.value = [];
  selectedJobCardName.value = null;
  operations.value = [];
  selectedOperationName.value = null;
  selectedWorkstation.value = null;
  users.value = [];
  selectedUser.value = null;
  errorMessage.value = null;
}

// ---- EVENTS FROM CHILD ----
function handleWorkOrderBarcodeSubmit() {
  // Barkod okutulup Enter gelince otomatik tetiklenir
  fetchWorkOrderByBarcode();
}

// Job Card değişince workstation sync
watch(selectedJobCardName, () => {
  syncWorkstationFromJobCard();
});

// İlk açılışta operasyon ve kullanıcı listelerini çek
onMounted(() => {
  fetchOperations();
  fetchUsers();
});
</script>

<template>
  <div class="w-full max-w-2xl mx-auto p-4 space-y-4">
    <!-- PROGRESS -->
    <div>
      <div class="flex justify-between mb-1 text-sm">
        <span>Aşama {{ currentStep }} / {{ totalSteps }}</span>
        <span v-if="workOrder && workOrder.name">WO: {{ workOrder.name }}</span>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-2">
        <div
          class="bg-blue-600 h-2 rounded-full transition-all duration-300"
          :style="{ width: (currentStep / totalSteps) * 100 + '%' }"
        />
      </div>
    </div>

    <!-- HATA MESAJI -->
    <div
      v-if="errorMessage"
      class="p-2 text-sm text-red-700 border border-red-300 rounded"
    >
      {{ errorMessage }}
    </div>

    <!-- STEPS CARD -->
    <div class="border rounded-lg p-4 bg-white shadow-sm space-y-4">
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
        v-if="currentStep === 2"
        :job-cards="jobCards"
        :selected-job-card-obj="selectedJobCard"
        v-model:selectedJobCard="selectedJobCardName"
      />

      <!-- STEP 3: Operation -->
      <StepOperation
        v-if="currentStep === 3"
        :operations="operations"
        v-model:selectedOperation="selectedOperationName"
      />

      <!-- STEP 4: Workstation -->
      <StepWorkstation
        v-if="currentStep === 4"
        :job-card="selectedJobCard"
        v-model:workstation="selectedWorkstation"
      />

      <!-- STEP 5: User -->
      <StepUser
        v-if="currentStep === 5"
        :users="users"
        v-model:selectedUser="selectedUser"
      />
    </div>

    <!-- NAV BUTTONS -->
    <div class="flex justify-between items-center">
      <button
        type="button"
        class="px-4 py-2 rounded bg-gray-300 text-sm disabled:opacity-50"
        :disabled="currentStep === 1 || loading"
        @click="goBack"
      >
        Geri
      </button>

      <button
        v-if="currentStep < totalSteps"
        type="button"
        class="px-4 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
        :disabled="!isStepValid || loading"
        @click="goNext"
      >
        İleri
      </button>

      <button
        v-else
        type="button"
        class="px-4 py-2 rounded bg-green-600 text-white text-sm disabled:opacity-50"
        :disabled="!isStepValid || loading"
        @click="submitWorkCard"
      >
        {{ loading ? 'Gönderiliyor...' : 'Çalışma Kartını Oluştur' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
/* Tailwind yoksa burada basit stil verebilirsin */
</style>