<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import StepWorkOrder from './components/StepWorkOrder.vue';
import StepJobCard from './components/StepJobCard.vue';
import StepOperation from './components/StepOperation.vue';
import StepWorkstation from './components/StepWorkstation.vue';
import StepUser from './components/StepUser.vue';
import StepIndicator from './components/StepIndicator.vue';
import StepJobCardSearch from './components/StepJobCardSearch.vue';

/* -------------------------------------------------------
 *  MODE & STATE
 * -----------------------------------------------------*/

// Arama tipi: 'WO' (Work Order) veya 'JC' (Job Card)
const searchMode = ref('WO'); // 'WO' | 'JC'

// Aktif step sayısı mode'a göre değişecek
const currentStep = ref(1);
const totalSteps = computed(() =>
  searchMode.value === 'WO' ? 5 : 3
);

// Step 1 (WO modu): Work Order
const workOrderBarcode = ref('');
const workOrder = ref(null); // { name, production_item, qty, ... }

// Step 1 (JC modu): Job Card barkodu
const jobCardBarcode = ref('');

// Step 2 (WO modu) veya Step 1 (JC modu sonrası hesaplanan):
const jobCards = ref([]);
const selectedJobCardName = ref(null);

// Operasyon
const operations = ref([]);
const selectedOperationName = ref(null);

// İş İstasyonu
const selectedWorkstation = ref(null);
const workstationAutoFilled = ref(false);

// Operatör (Employee)
const users = ref([]);
const selectedUser = ref(null); // Employee.name (EMP-0001 vb.)

// Genel state
const loading = ref(false);
const errorMessage = ref(null);

// Oluşturulan Çalışma Kartı
const createdDoc = ref(null);

// Hata modallarını susturmak için global flag
const isAppQuiet = ref(false);
let originalMsgprint = null;

/* -------------------------------------------------------
 *  DERIVED
 * -----------------------------------------------------*/

const selectedJobCard = computed(() => {
  return jobCards.value.find(jc => jc.name === selectedJobCardName.value) || null;
});

const selectedOperation = computed(() => {
  return (
    operations.value.find((op) => op.name === selectedOperationName.value) || null
  );
});

const selectedEmployee = computed(() => {
  return users.value.find(emp => emp.name === selectedUser.value) || null;
});

// Step indicator açıklamaları (mode'a göre içerik)
const steps = computed(() => {
  const wo = workOrder.value;
  const jc = selectedJobCard.value;
  const op = selectedOperation.value;
  const emp = selectedEmployee.value;
  const ws = selectedWorkstation.value;

  // WO MODE: 5 ADIM
  if (searchMode.value === 'WO') {
    let step1Desc = 'Work Order barkodu';
    if (wo && wo.name) step1Desc = wo.name;

    let step2Desc = 'Seçilecek İş Kartı';
    if (jc) step2Desc = jc.name;

    let step3Desc = 'Varsayılan veya manuel istasyon';
    if (ws) step3Desc = ws;

    let step4Desc = 'Operasyon seçimi';
    if (op && op.calisma_karti_op) step4Desc = op.calisma_karti_op;
    else if (selectedOperationName.value) step4Desc = selectedOperationName.value;

    let step5Desc = 'Operatör (Employee) seçimi';
    if (emp) step5Desc = emp.employee_name || emp.name;

    return [
      { id: 1, label: 'İş Emri',      description: step1Desc },
      { id: 2, label: 'İş Kartı',     description: step2Desc },
      { id: 3, label: 'İş İstasyonu', description: step3Desc },
      { id: 4, label: 'Operasyon',    description: step4Desc },
      { id: 5, label: 'Operatör',     description: step5Desc },
    ];
  }

  // JC MODE: 3 ADIM
  let step1Desc = 'İş Kartı barkodu / adı';
  if (jc) {
    const parts = [jc.name];
    if (jc.work_order) parts.push(jc.work_order);
    step1Desc = parts.join(' · ');
  }

  let step2Desc = 'Operasyon seçimi';
  if (op && op.calisma_karti_op) step2Desc = op.calisma_karti_op;
  else if (selectedOperationName.value) step2Desc = selectedOperationName.value;

  let step3Desc = 'Operatör (Employee) seçimi';
  if (emp) step3Desc = emp.employee_name || emp.name;

  return [
    { id: 1, label: 'İş Kartı',  description: step1Desc },
    { id: 2, label: 'Operasyon', description: step2Desc },
    { id: 3, label: 'Operatör',  description: step3Desc },
  ];
});

const activeCustomerGroups = computed(() => {
  // Prefer Work Order (WO mode), fallback to selected Job Card (JC mode)
  const wo = workOrder.value;
  const jc = selectedJobCard.value;

  const fromWo = wo?.customer_groups || (wo?.customer_group ? [wo.customer_group] : []);
  const fromJc = jc?.customer_groups || (jc?.customer_group ? [jc.customer_group] : []);

  const raw = (fromWo.length ? fromWo : fromJc).filter(Boolean);
  return Array.from(new Set(raw));
});

// Eğer operasyonun customer_group alanı doluysa, sadece o gruba ait olan WO/JC'lere göster.
// Eğer boşsa (generic operasyon), herkese göster.
const filteredOperations = computed(() => {
  const ops = operations.value || [];
  const groups = activeCustomerGroups.value;

  return ops.filter((op) => {
    const cg = op?.customer_group || null;
    // Operasyon genel kullanıma açıksa (kısıt yoksa) kabul et:
    if (!cg) return true;
    // Operasyon kısıtlıysa, sepetteki gruplardan biriyle eşleşmeli:
    return groups.includes(cg);
  });
});

/* -------------------------------------------------------
 *  HELPERS
 * -----------------------------------------------------*/

function callFrappe(method, args = {}) {
  return new Promise((resolve, reject) => {
    frappe.call({
      method,
      args,
      quiet: true,
      callback: (r) => {
        // Her ihtimale karşı temizle
        if (window.frappe) frappe.messages = [];
        resolve(r.message);
      },
      error: (err) => {
        if (window.frappe) frappe.messages = [];
        reject(err);
      }
    });
  });
}

/**
 * Frappe hata objesinden temiz mesaj ayıran yardımcı
 */
function getErrorMessage(err, defaultMsg) {
  if (!err) return defaultMsg;
  let rawMsg = '';

  // 1. Ham mesajı ayıkla
  if (typeof err === 'string') {
    rawMsg = err;
  } else if (err._server_messages) {
    try {
      const msgs = typeof err._server_messages === 'string'
        ? JSON.parse(err._server_messages)
        : err._server_messages;
      rawMsg = msgs.map(m => {
        try {
          const p = typeof m === 'string' ? JSON.parse(m) : m;
          return p.message || m;
        } catch { return m; }
      }).join(' ');
    } catch { rawMsg = String(err._server_messages); }
  } else {
    rawMsg = err.message || err.statusText || defaultMsg;
  }

  // 2. Teknik gürültüyü temizle ve Türkçeleştir
  let cleanMsg = rawMsg;

  // Bilinen Frappe kalıplarını Türkçeleştir
  const patterns = [
    { reg: /Work Order (.*) not found/i, repl: 'İş Emri bulunamadı.' },
    { reg: /Job Card (.*) not found/i, repl: 'İş Kartı bulunamadı.' },
    { reg: /Employee (.*) not found/i, repl: 'Personel kaydı bulunamadı.' },
    { reg: /Operation (.*) not found/i, repl: 'Operasyon bulunamadı.' },
    { reg: /Not permitted/i, repl: 'Bu işlem için yetkiniz yok.' },
    { reg: /Insufficient Permission/i, repl: 'Yetki yetersiz.' }
  ];

  for (const p of patterns) {
    if (p.reg.test(cleanMsg)) {
      cleanMsg = p.repl;
      break; 
    }
  }

  // Eğer hala İngilizce "not found" falan varsa genel bir temizlik yap
  if (cleanMsg.toLowerCase().includes('not found')) {
    return defaultMsg;
  }

  // Çok uzun/teknik mesajları default'a çek (Örn: SQL hataları)
  if (cleanMsg.includes('Traceback') || cleanMsg.includes('OperationalError')) {
    return defaultMsg;
  }

  return cleanMsg;
}

// Merkezi loading helper (min süre garantili)
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

// Küçük helper: seçimden sonra focus'u boşalt (boşluğa tıklamış gibi)
function releaseFocusAfterSelection() {
  const el = document.activeElement;
  if (el && typeof el.blur === 'function') {
    el.blur();
  }
}

/* -------------------------------------------------------
 *  VALIDATION (mode'a göre)
 * -----------------------------------------------------*/

const isStepValid = computed(() => {
  if (searchMode.value === 'WO') {
    switch (currentStep.value) {
      case 1:
        return !!workOrder.value;
      case 2:
        return !!selectedJobCard.value;
      case 3:
        return !!selectedWorkstation.value;
      case 4:
        return !!selectedOperationName.value;
      case 5:
        return !!selectedUser.value;
      default:
        return false;
    }
  } else {
    // JC MODE: 3 step
    switch (currentStep.value) {
      case 1:
        return !!selectedJobCard.value;        // Job Card seçilmiş / bulunmuş mu
      case 2:
        return !!selectedOperationName.value;  // Operasyon seçildi mi
      case 3:
        return !!selectedUser.value;           // Operatör seçildi mi
      default:
        return false;
    }
  }
});

/* -------------------------------------------------------
 *  API CALLS
 * -----------------------------------------------------*/

// 1A) WO MODE: Barkod -> Work Order
async function fetchWorkOrderByBarcode() {
  if (!workOrderBarcode.value.trim()) return;
  errorMessage.value = null;

  try {
    await withLoading(async () => {
      let barcode = workOrderBarcode.value.trim();
      if (!barcode) return;

      // Smart Prefix: 2026-01110 -> MFG-WO-2026-01110
      if (/^\d{4}-\d+$/.test(barcode)) {
        barcode = `MFG-WO-${barcode}`;
        workOrderBarcode.value = barcode;
      }

      const msg = await callFrappe(
        'erpnextkta.kta_calisma_karti.api.get_work_order_by_barcode',
        { barcode }
      );

      workOrder.value = msg || null;

      if (!workOrder.value || !workOrder.value.name) {
        throw new Error('Work Order bulunamadı.');
      }

      // İş Emri bulundu → Job Card listesi
      await fetchJobCardsForWorkOrder();
      currentStep.value = 2;
    }, 800);
  } catch (err) {
    console.error(err);
    errorMessage.value = getErrorMessage(err, 'Work Order alınırken hata oluştu.');
    workOrder.value = null;
    jobCards.value = [];
    selectedJobCardName.value = null;
  }
}

// 1B) JC MODE: Barkod / ad -> Job Card (erken WO kontrolü backend'de)
async function fetchJobCardByBarcode() {
  if (!jobCardBarcode.value.trim()) return;
  errorMessage.value = null;

  try {
    await withLoading(async () => {
      let barcode = jobCardBarcode.value.trim();
      if (!barcode) return;

      // Smart Prefix: JOB16115 -> PO-JOB16115
      if (/^JOB\d+$/i.test(barcode)) {
        barcode = `PO-${barcode.toUpperCase()}`;
        jobCardBarcode.value = barcode;
      }

      const msg = await callFrappe(
        'erpnextkta.kta_calisma_karti.api.get_job_card_by_barcode',
        { barcode }
      );

      // Beklenen çıktı (örnek):
      // {
      //   job_card: "JC-00001",
      //   work_order: "WO-00001",
      //   workstation: "IST-01",
      //   production_item: "ITEM-0001",
      //   for_quantity: 100,
      //   ...
      // }
      // (WO Completed / Stopped ise bu fonksiyon zaten frappe.throw ile hata fırlatmış olacak)

      if (!msg) {
        throw new Error('İş Kartı alınamadı.');
      }

      const jcName = msg.job_card || msg.name;
      if (!jcName) {
        throw new Error('İş Kartı bulunamadı.');
      }

      const jc = {
        name: jcName,
        work_order: msg.work_order || msg.work_order_name || null,
        workstation: msg.workstation || null,
        production_item: msg.production_item || null,
        for_quantity: msg.for_quantity || msg.qty || null,
        customer_group: msg.customer_group || null,
        customer_groups: msg.customer_groups || [],
      };

      // Job Card state
      jobCards.value = [jc];
      selectedJobCardName.value = jc.name;

      // Work Order state (StepIndicator vs. için)
      workOrder.value = jc.work_order
        ? {
            name: jc.work_order,
            production_item: jc.production_item,
            qty: jc.for_quantity,
            customer_group: jc.customer_group,
            customer_groups: jc.customer_groups,
          }
        : null;

      // İş istasyonu otomatik
      selectedWorkstation.value = jc.workstation || null;

      // JC flow'da 1. adım tamam → Operasyona geç
      await fetchOperationsForJobCard(jcName);
      currentStep.value = 2;
    }, 800);
  } catch (err) {
    console.error(err);
    errorMessage.value = getErrorMessage(err, 'İş Kartı alınırken hata oluştu.');
    jobCards.value = [];
    selectedJobCardName.value = null;
    workOrder.value = null;
    selectedWorkstation.value = null;
  }
}

// 2) Work Order’a bağlı Job Card listesi (sadece WO modu için)
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

// Operasyon listesi — JC'ye göre filtrelenmiş
async function fetchOperationsForJobCard(jcName) {
  errorMessage.value = null;

  try {
    await withLoading(async () => {
      const list = await callFrappe(
        'erpnextkta.kta_calisma_karti.api.get_operations_for_job_card',
        { job_card: jcName }
      );

      operations.value = list || [];
      selectedOperationName.value = null;
    }, 500);
  } catch (err) {
    console.error(err);
    errorMessage.value = getErrorMessage(err, 'Operasyon listesi alınırken hata oluştu.');
    operations.value = [];
    selectedOperationName.value = null;
  }
}

// Kullanıcı listesi (Employee)
async function fetchUsers() {
  errorMessage.value = null;

  try {
    await withLoading(async () => {
      const list = await callFrappe('frappe.client.get_list', {
        doctype: 'Employee',
        filters: {
          status: 'Active',
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

/* -------------------------------------------------------
 *  WORKSTATION SYNC
 * -----------------------------------------------------*/

function syncWorkstationFromJobCard() {
  // Sadece WO modunda Job Card seçimi ile workstation doldurmak mantıklı
  if (searchMode.value === 'WO') {
    if (selectedJobCard.value && selectedJobCard.value.workstation) {
      selectedWorkstation.value = selectedJobCard.value.workstation;
      workstationAutoFilled.value = true;
      setTimeout(() => {
        workstationAutoFilled.value = false;
      }, 1200);
    } else {
      selectedWorkstation.value = null;
    }
  }
}

/* -------------------------------------------------------
 *  SUBMIT
 * -----------------------------------------------------*/

async function submitWorkCard() {
  if (!isStepValid.value) return;

  // Payload mode'a göre hazırlanacak,
  // ama her iki modda da create_calisma_karti aynı alanları istiyor.
  const jc = selectedJobCard.value;
  if (!jc) return;

  // WO her iki modda da elimizde olmalı:
  // - WO modunda zaten workOrder state'inden
  // - JC modunda Job Card'dan set ediyoruz
  const woName =
    searchMode.value === 'WO'
      ? (workOrder.value && workOrder.value.name)
      : jc.work_order;

  const workstation =
    searchMode.value === 'WO'
      ? selectedWorkstation.value
      : (jc.workstation || selectedWorkstation.value);

  const payload = {
    custom_work_order: woName,
    is_karti: jc.name,
    operasyon: selectedOperationName.value,
    is_istasyonu: workstation,
    operator: selectedUser.value,
  };

  errorMessage.value = null;

  try {
    await withLoading(async () => {
      const msg = await callFrappe(
        'erpnextkta.kta_calisma_karti.api.create_calisma_karti',
        payload
      );

      if (msg && msg.name) {
        createdDoc.value = msg;
      } else {
        createdDoc.value = { name: msg && msg.name ? msg.name : '' };
      }

      frappe.msgprint({
        title: __('İşlem Başarılı'),
        message: __('Çalışma Kartı başarıyla oluşturuldu.'),
        indicator: 'green'
      });
    }, 900);
  } catch (err) {
    console.error(err);
    errorMessage.value = getErrorMessage(err, 'Çalışma Kartı oluşturulurken hata oluştu.');
  }
}

/* -------------------------------------------------------
 *  NAV + RESET
 * -----------------------------------------------------*/

function goNext() {
  if (!isStepValid.value) return;
  if (currentStep.value < totalSteps.value) {
    currentStep.value++;
  }
}

function goBack() {
  if (currentStep.value > 1) {
    currentStep.value--;
  }
}

// Mode değiştirirken wizard'ı resetleyelim
function setSearchMode(mode) {
  if (searchMode.value === mode) return;
  searchMode.value = mode;

  currentStep.value = 1;
  workOrderBarcode.value = '';
  jobCardBarcode.value = '';
  workOrder.value = null;
  jobCards.value = [];
  selectedJobCardName.value = null;
  selectedOperationName.value = null;
  selectedWorkstation.value = null;
  workstationAutoFilled.value = false;
  selectedUser.value = null;
  errorMessage.value = null;
  createdDoc.value = null;
}

function resetWizard() {
  currentStep.value = 1;
  workOrderBarcode.value = '';
  jobCardBarcode.value = '';
  workOrder.value = null;
  jobCards.value = [];
  selectedJobCardName.value = null;
  selectedOperationName.value = null;
  selectedWorkstation.value = null;
  workstationAutoFilled.value = false;
  selectedUser.value = null;
  errorMessage.value = null;
  createdDoc.value = null;
}

function goToCreatedDoc() {
  if (!createdDoc.value || !createdDoc.value.name) return;
  frappe.set_route('Form', 'Calisma Karti', createdDoc.value.name);
}

function startNewWorkCard() {
  resetWizard();
}

/* -------------------------------------------------------
 *  ENTER FLOW
 * -----------------------------------------------------*/

// Step 1 submit handler'ları mode'a göre
function handleWorkOrderBarcodeSubmit() {
  fetchWorkOrderByBarcode();
}
function handleJobCardBarcodeSubmit() {
  fetchJobCardByBarcode();
}

// Global Enter behaviour
function handleEnter(event) {
  if (loading.value) return;

  const tag = (event.target && event.target.tagName) || '';
  if (tag === 'TEXTAREA' || tag === 'BUTTON') return;

  // STEP 1
  if (currentStep.value === 1) {
    if (searchMode.value === 'WO') {
      if (workOrderBarcode.value.trim()) {
        handleWorkOrderBarcodeSubmit();
      }
    } else {
      if (jobCardBarcode.value.trim()) {
        handleJobCardBarcodeSubmit();
      }
    }
    return;
  }

  // Diğer adımlar
  if (!isStepValid.value) return;

  if (currentStep.value < totalSteps.value) {
    goNext();
  } else {
    submitWorkCard();
  }
}

// Global keydown listener (capture ile)
function onGlobalKeydown(e) {
  if (e.key === 'Enter') {
    handleEnter(e);
  }
}

/* -------------------------------------------------------
 *  WATCHERS + LIFECYCLE
 * -----------------------------------------------------*/

watch(selectedJobCardName, (newJcName) => {
  syncWorkstationFromJobCard();
  releaseFocusAfterSelection();
  // WO mode: fetch operations filtered by this Job Card
  if (searchMode.value === 'WO' && newJcName) {
    fetchOperationsForJobCard(newJcName);
  }
});

watch(selectedWorkstation, (val) => {
  if (val) releaseFocusAfterSelection();
});

watch(selectedOperationName, (val) => {
  if (val) releaseFocusAfterSelection();
});

watch(selectedUser, (val) => {
  if (val) releaseFocusAfterSelection();
});

// İlk açılışta kullanıcı listesi + global Enter listener
onMounted(() => {
  fetchUsers();
  window.addEventListener('keydown', onGlobalKeydown, { capture: true });

  // Agresif Modal Susturma: Sihirbaz açıkken TÜM Frappe modallarını engelle
  if (window.frappe && frappe.msgprint) {
    originalMsgprint = frappe.msgprint;
    frappe.msgprint = (args) => {
      // SADECE 'green' (Başarı) olan mesajlara izin ver, gerisini yut
      if (typeof args === 'object' && (args.indicator === 'green' || args.indicator === 'success')) {
        return originalMsgprint(args);
      }
      console.warn("[App] Blocked Modal while Wizard is active:", args);
      // Mesaj kuyruğunu anında temizle
      if (frappe.messages) frappe.messages = [];
      return;
    };
  }

  // Yedek temizleyici: Bazı durumlarda Frappe mesajları kuyrukta bekletebilir
  window._msgCleaner = setInterval(() => {
    if (window.frappe && frappe.messages && frappe.messages.length > 0) {
      frappe.messages = [];
    }
  }, 250);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeydown, { capture: true });
  if (window._msgCleaner) clearInterval(window._msgCleaner);
  if (originalMsgprint && window.frappe) {
    frappe.msgprint = originalMsgprint;
  }
});
</script>
<template>
  <div class="w-full max-w-2xl mx-auto p-2 space-y-4">
    <!-- WIZARD MODU -->
    <template v-if="!createdDoc">
      <!-- MODE TOGGLE -->
      <teleport to=".kta-ck-header">
      <div class="flex justify-center gap-2 mb-1" style="width: 100%;">
        <button
          type="button"
          class="mode-pill"
          :class="{ 'mode-pill--active': searchMode === 'WO' }"
          @click="setSearchMode('WO')"
        >
          İş Emri ile
        </button>
        <button
          type="button"
          class="mode-pill"
          :class="{ 'mode-pill--active': searchMode === 'JC' }"
          @click="setSearchMode('JC')"
        >
          İş Kartı ile
        </button>
      </div>
      </teleport>
      <!-- STEP INDICATOR -->
      <div class="flex flex-col gap-1">
        <StepIndicator
          :current-step="currentStep"
          :steps="steps"
        />
      </div>

      <!-- CARD -->
      <div class="wizard-card space-y-4">
        <!-- Mobil Info Strip (321px altı için seçili WO ve Operasyon) -->
        <div v-if="currentStep > 1 && searchMode === 'WO' && (workOrder || selectedOperationName)" class="mobile-info-strip">
          <div v-if="workOrder" class="mobile-info-strip__item">
            <span class="label">WO:</span> {{ workOrder.name }}
          </div>
          <div v-if="selectedOperationName" class="mobile-info-strip__item">
            <span class="label">Op:</span> {{ selectedOperationName }}
          </div>
        </div>
        <div v-else-if="currentStep > 1 && searchMode === 'JC' && (selectedJobCardName || selectedOperationName)" class="mobile-info-strip mobile-info-strip--jc">
          <div v-if="selectedJobCardName" class="mobile-info-strip__item">
            <span class="label">JC:</span> {{ selectedJobCardName }}
          </div>
          <div v-if="selectedOperationName" class="mobile-info-strip__item">
            <span class="label">Op:</span> {{ selectedOperationName }}
          </div>
        </div>

        <Transition name="fade-step" mode="out-in">
          <!-- WO MODE: 5 adım -->
          <template v-if="searchMode === 'WO'">
            <!-- STEP 1: Work Order -->
            <StepWorkOrder
              v-if="currentStep === 1"
              v-model:barcode="workOrderBarcode"
              :work-order="workOrder"
              :loading="loading"
              @submit="handleWorkOrderBarcodeSubmit"
            />

            <!-- STEP 2: Job Card seçimi -->
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

            <!-- STEP 4: Operasyon -->
            <StepOperation
              v-else-if="currentStep === 4"
              :operations="filteredOperations"
              v-model:selectedOperation="selectedOperationName"
            />

            <!-- STEP 5: Operatör -->
            <StepUser
              v-else-if="currentStep === 5"
              :users="users"
              v-model:selectedUser="selectedUser"
            />
          </template>

          <!-- JC MODE: 3 adım -->
          <template v-else>
            <!-- STEP 1: İş Kartı barkodu / adı -->
            <StepJobCardSearch
              v-if="currentStep === 1"
              v-model:barcode="jobCardBarcode"
              :job-card="selectedJobCard"
              :loading="loading"
              @submit="handleJobCardBarcodeSubmit"
            />

            <!-- STEP 2: Operasyon -->
            <StepOperation
              v-else-if="currentStep === 2"
              :operations="filteredOperations"
              v-model:selectedOperation="selectedOperationName"
            />

            <!-- STEP 3: Operatör -->
            <StepUser
              v-else-if="currentStep === 3"
              :users="users"
              v-model:selectedUser="selectedUser"
            />
          </template>
        </Transition>

        <!-- LOADING OVERLAY -->
        <div v-if="loading" class="wizard-card__overlay">
          <div class="wizard-card__spinner"></div>
        </div>
      </div>

      <!-- HATA MESAJI (ALTTA) -->
      <Transition name="fade-error">
        <div
          v-if="errorMessage"
          class="wizard-error-alert"
        >
          <div class="wizard-error-alert__icon">!</div>
          <div class="wizard-error-alert__content">
            {{ errorMessage }}
          </div>
          <button class="wizard-error-alert__close" @click="errorMessage = null">×</button>
        </div>
      </Transition>

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

<style>
:root {
  --ck-bg: #f9fafb;
  --ck-card-bg: #ffffff;
  --ck-text: #111827;
  --ck-text-muted: #4b5563;
  --ck-border: #e5e7eb;
  --ck-input-bg: #ffffff;
  --ck-input-text: #111827;
  --ck-ghost-bg: #f3f4f6;
  --ck-accent: #2563eb;
  --ck-accent-hover: #1d4ed8;
  --ck-success: #16a34a;
  --ck-success-hover: #15803d;
}

:root[data-theme="dark"],
html[data-theme="dark"],
body.dark,
.dark {
  --ck-bg: #0f172a;
  --ck-card-bg: #1e293b;
  --ck-text: #f1f5f9;
  --ck-text-muted: #94a3b8;
  --ck-border: #334155;
  --ck-input-bg: #0f172a;
  --ck-input-text: #f1f5f9;
  --ck-ghost-bg: #1e293b;
  --ck-accent: #3b82f6;
  --ck-accent-hover: #60a5fa;
  --ck-success: #22c55e;
  --ck-success-hover: #4ade80;
}
</style>

<style scoped>
.wizard-card {
  position: relative;
  background: var(--ck-card-bg);
  border-radius: 0.75rem;
  border: 1px solid var(--ck-border);
  padding: 1rem;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.06);
}
/* MODE TOGGLE (İş Emri ile / İş Kartı ile) */
.mode-pill {
  width: 100%;
  font-size: 0.8rem;
  margin: 0em 0.4rem;
  padding: 0.35rem 0.7rem;
  border-radius: 5px;
  border: 1px solid var(--ck-border);
  background: var(--ck-ghost-bg);
  color: var(--ck-text-muted);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.mode-pill--active {
  background: var(--ck-accent);
  border-color: var(--ck-accent);
  color: #ffffff;
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.4);
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
  color: var(--ck-text);
}

.success-card__subtitle {
  margin: 0.15rem 0 0;
  font-size: 0.85rem;
  color: var(--ck-text-muted);
}

.success-card__details {
  margin: 1rem 0;
  padding: 0.75rem;
  border-radius: 0.5rem;
  background: var(--ck-ghost-bg);
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.success-card__detail-row {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.85rem;
  padding: 0.25rem 0;
}

.success-card__detail-label {
  color: var(--ck-text-muted);
  white-space: nowrap;
}

.success-card__detail-value {
  font-weight: 600;
  color: var(--ck-text);
  text-align: right;
  word-break: break-all;
}

/* 340px altı için alt alta dizilim */
@media (max-width: 340px) {
  .success-card__detail-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.1rem;
    padding: 0.4rem 0;
    border-bottom: 1px solid var(--ck-border);
  }
  .success-card__detail-row:last-child {
    border-bottom: none;
  }
  .success-card__detail-value {
    text-align: left;
  }
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
  background: var(--ck-success);
  border-color: var(--ck-success);
  color: #ffffff;
}

.success-btn--primary:hover {
  background: var(--ck-success-hover);
  border-color: var(--ck-success-hover);
  box-shadow: 0 1px 3px rgba(22, 163, 74, 0.4);
}

.success-btn--secondary {
  background: var(--ck-ghost-bg);
  border-color: var(--ck-border);
  color: var(--ck-text);
}

.success-btn--secondary:hover {
  background: var(--ck-ghost-bg);
  border-color: var(--ck-text-muted);
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
  background: var(--ck-ghost-bg);
  border-color: var(--ck-border);
  color: var(--ck-text);
}
.nav-btn--secondary:hover:enabled {
  background: var(--ck-border);
}

/* Primary (ileri) */
.nav-btn--primary {
  background: var(--ck-accent);
  border-color: var(--ck-accent);
  color: #fff;
}
.nav-btn--primary:hover:enabled {
  background: var(--ck-accent-hover);
  border-color: var(--ck-accent-hover);
}

/* Success (submit) */
.nav-btn--success {
  background: var(--ck-success);
  border-color: var(--ck-success);
  color: #fff;
}
.nav-btn--success:hover:enabled {
  background: var(--ck-success-hover);
  border-color: var(--ck-success-hover);
}

/* Disabled state */
.nav-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* MOBIL INFO STRIP (Sub-321px) */
.mobile-info-strip {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem 1rem;
  background: var(--ck-ghost-bg);
  border-radius: 0.6rem;
  border-left: 5px solid var(--ck-accent);
  margin-bottom: 1rem;
  border-top: 1px solid var(--ck-border);
  border-right: 1px solid var(--ck-border);
  border-bottom: 1px solid var(--ck-border);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

:root[data-theme="dark"] .mobile-info-strip,
html[data-theme="dark"] .mobile-info-strip,
.dark .mobile-info-strip {
  background: rgba(59, 130, 246, 0.08); /* Hafif mavi transparan arka plan */
  border-color: var(--ck-border);
  border-left-color: var(--ck-accent);
  box-shadow: 0 0 15px rgba(59, 130, 246, 0.15); /* Hafif parlama */
}

@media (min-width: 322px) {
  .mobile-info-strip {
    display: none; /* WO için 321px üstü gizle */
  }
}

@media (max-width: 640px) {
  .mobile-info-strip--jc {
    display: flex !important; /* JC için 640px'e kadar zorla göster */
  }
}

.mobile-info-strip__item {
  font-size: 0.75rem;
  color: var(--ck-text);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mobile-info-strip__item .label {
  color: var(--ck-text-muted);
  font-weight: normal;
  margin-right: 0.2rem;
}

/* HATA ALERT KUTUSU */
.wizard-error-alert {
  background: #fef2f2;
  border: 1px solid #fee2e2;
  border-radius: 0.85rem;
  padding: 0.85rem 1.1rem;
  margin-top: 1rem;
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  box-shadow: 0 4px 12px rgba(220, 38, 38, 0.08);
  animation: shake 0.4s cubic-bezier(.36,.07,.19,.97) both;
}

@keyframes shake {
  10%, 90% { transform: translate3d(-1px, 0, 0); }
  20%, 80% { transform: translate3d(2px, 0, 0); }
  30%, 50%, 70% { transform: translate3d(-3px, 0, 0); }
  40%, 60% { transform: translate3d(3px, 0, 0); }
}

:root[data-theme="dark"] .wizard-error-alert {
  background: rgba(220, 38, 38, 0.08);
  border-color: rgba(220, 38, 38, 0.2);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.wizard-error-alert__icon {
  width: 22px;
  height: 22px;
  background: #dc2626;
  color: white;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 0.85rem;
  flex-shrink: 0;
  margin-top: 1px;
}

.wizard-error-alert__content {
  flex: 1;
  font-size: 0.875rem;
  color: #991b1b;
  font-weight: 500;
  line-height: 1.5;
}

:root[data-theme="dark"] .wizard-error-alert__content {
  color: #fca5a5;
}

.wizard-error-alert__close {
  background: none;
  border: none;
  color: #dc2626;
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  opacity: 0.6;
  transition: opacity 0.2s;
}

.wizard-error-alert__close:hover {
  opacity: 1;
}

.fade-error-enter-active, .fade-error-leave-active {
  transition: all 0.3s ease;
}
.fade-error-enter-from, .fade-error-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
>>>>>>> origin/feat(kta-calisma-karti)/operation-jc-mapping
</style>
