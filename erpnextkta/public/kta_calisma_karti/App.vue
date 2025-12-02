<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import StepWorkOrder from './components/StepWorkOrder.vue';
import StepJobCard from './components/StepJobCard.vue';
import StepOperation from './components/StepOperation.vue';
import StepWorkstation from './components/StepWorkstation.vue';
import StepUser from './components/StepUser.vue';

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
  return (
    operations.value.find(
      (op) => op.calisma_karti_op === selectedOperationName.value
    ) || null
  );
});

// ---- HELPER: frappe.call'ı Promise'e sardık ----
function callFrappe(method, args = {}) {
  return new Promise((resolve, reject) => {
    frappe.call({
      method,
      args,
      callback: (r) => {
        // r.message genelde payload
        resolve(r.message);
      },
      error: (err) => {
        // err.messages vs. olabilir, basitçe fırlatıyoruz
        reject(err);
      }
    });
  });
}

// ---- VALIDATION ----
const isStepValid = computed(() => {
  switch (currentStep.value) {
    case 1:
      return !!workOrder.value;
    case 2:
      return !!selectedJobCard.value;
    case 3:
      // sadece bir operasyon seçilmiş olması yeterli
      return !!selectedOperationName.value;
    case 4:
      return !!selectedWorkstation.value;
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

  loading.value = true;
  errorMessage.value = null;

  try {
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
  } catch (err) {
    console.error(err);
    // frappe.call error objesi farklı formatta olabilir; basitçe mesaj çekiyoruz
    errorMessage.value =
      (err && err.message) ||
      (err && err._server_messages) ||
      'Work Order alınırken hata oluştu.';
    workOrder.value = null;
    jobCards.value = [];
    selectedJobCardName.value = null;
  } finally {
    loading.value = false;
  }
}

// 2) Work Order’a bağlı Job Card listesi (frappe.client.get_list)
async function fetchJobCardsForWorkOrder() {
  if (!workOrder.value || !workOrder.value.name) return;

  loading.value = true;
  errorMessage.value = null;

  try {
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
  } catch (err) {
    console.error(err);
    errorMessage.value =
      (err && err.message) ||
      'Job Card listesi alınırken hata oluştu.';
    jobCards.value = [];
    selectedJobCardName.value = null;
  } finally {
    loading.value = false;
  }
}

// 3) Operasyon listesi (KTA Calisma Karti Operasyonlari)
async function fetchOperations() {
  loading.value = true;
  errorMessage.value = null;

  try {
    const list = await callFrappe('frappe.client.get_list', {
      doctype: 'KTA Calisma Karti Operasyonlari',
      fields: ['calisma_karti_op'],
      limit_page_length: 500
    });

    operations.value = list || [];
  } catch (err) {
    console.error(err);
    errorMessage.value =
      (err && err.message) ||
      'Operasyon listesi alınırken hata oluştu.';
    operations.value = [];
    selectedOperationName.value = null;
  } finally {
    loading.value = false;
  }
}

// 4) Kullanıcı listesi (User)
async function fetchUsers() {
  loading.value = true;
  errorMessage.value = null;

  try {
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
  } catch (err) {
    console.error(err);
    errorMessage.value =
      (err && err.message) ||
      'Kullanıcı listesi alınırken hata oluştu.';
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

// ---- SUBMIT: Calisma Karti create (create_calisma_karti) ----
async function submitWorkCard() {
  if (!isStepValid.value) return;

  // Doctype field namelerine göre payload
  const payload = {
    custom_work_order: workOrder.value.name,
    is_karti: selectedJobCard.value.name,
    operasyon: selectedOperationName.value,
    is_istasyonu: selectedWorkstation.value,
    operator: selectedUser.value // field adını Doctype’a göre güncelle
  };

  loading.value = true;
  errorMessage.value = null;

  try {
    const msg = await callFrappe(
      'erpnextkta.kta_calisma_karti.api.create_calisma_karti',
      payload
    );

    const docname = msg && msg.name ? msg.name : JSON.stringify(msg);

    frappe.msgprint({
      title: __('İşlem Başarılı'),
      message: __('Çalışma Kartı oluşturuldu: {0}', [docname]),
      indicator: 'green'
    });

    resetWizard();
  } catch (err) {
    console.error(err);
    errorMessage.value =
      (err && err.message) ||
      'Çalışma Kartı oluşturulurken hata oluştu.';
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

// ---- CHILD EVENTS ----
function handleWorkOrderBarcodeSubmit() {
  // Barkod okutulup Enter gelince
  fetchWorkOrderByBarcode();
}

// Job Card değişince workstation sync
watch(selectedJobCardName, () => {
  syncWorkstationFromJobCard();
});

// İlk açılışta operasyon + kullanıcı listeleri
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
/* İstersen burada minimal stil verebilirsin */
</style>