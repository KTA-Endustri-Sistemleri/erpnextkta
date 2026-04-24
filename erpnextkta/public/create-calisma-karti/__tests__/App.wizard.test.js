/**
 * App.vue — Computed property ve wizard navigasyon testleri.
 *
 * App.vue'yu mount edip defineExpose üzerinden erişilen
 * internal state/computed'ları test eder.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import App from '../App.vue';

// Teleport + child component stub'ları
const STUBS = {
  Teleport: true,
  Transition: true,
  StepWorkOrder: true,
  StepJobCard: true,
  StepOperation: true,
  StepWorkstation: true,
  StepUser: true,
  StepIndicator: true,
  StepJobCardSearch: true,
};

async function mountApp() {
  const wrapper = mount(App, {
    global: { stubs: STUBS },
    attachTo: document.body,
  });
  // onMounted fetchUsers() çağrısının çözülmesini bekle
  await flushPromises();
  return wrapper;
}

// ──────────────────────────────────────────────────────────────────────────────
// totalSteps computed
// ──────────────────────────────────────────────────────────────────────────────
describe('totalSteps', () => {
  it('WO modunda 5 adım döner', async () => {
    const wrapper = await mountApp();
    expect(wrapper.vm.totalSteps).toBe(5);
  });

  it('JC moduna geçince 3 adım döner', async () => {
    const wrapper = await mountApp();
    wrapper.vm.setSearchMode('JC');
    await flushPromises();
    expect(wrapper.vm.totalSteps).toBe(3);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// isStepValid computed — WO modu
// ──────────────────────────────────────────────────────────────────────────────
describe('isStepValid — WO modu', () => {
  it('Step 1: workOrder null iken false', async () => {
    const wrapper = await mountApp();
    expect(wrapper.vm.currentStep).toBe(1);
    expect(wrapper.vm.workOrder).toBeNull();
    expect(wrapper.vm.isStepValid).toBe(false);
  });

  it('Step 1: workOrder set iken true', async () => {
    const wrapper = await mountApp();
    wrapper.vm.workOrder = { name: 'MFG-WO-001', production_item: 'ITEM-A' };
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(true);
  });

  it('Step 2: selectedJobCard olmadan false', async () => {
    const wrapper = await mountApp();
    wrapper.vm.workOrder = { name: 'MFG-WO-001' };
    wrapper.vm.currentStep = 2;
    wrapper.vm.selectedJobCardName = null;
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(false);
  });

  it('Step 2: selectedJobCard set iken true', async () => {
    const wrapper = await mountApp();
    wrapper.vm.workOrder = { name: 'MFG-WO-001' };
    wrapper.vm.jobCards = [{ name: 'JC-001', workstation: 'IST-01' }];
    wrapper.vm.currentStep = 2;
    wrapper.vm.selectedJobCardName = 'JC-001';
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(true);
  });

  it('Step 3: selectedWorkstation olmadan false', async () => {
    const wrapper = await mountApp();
    wrapper.vm.currentStep = 3;
    wrapper.vm.selectedWorkstation = null;
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(false);
  });

  it('Step 3: selectedWorkstation set iken true', async () => {
    const wrapper = await mountApp();
    wrapper.vm.currentStep = 3;
    wrapper.vm.selectedWorkstation = 'IST-01';
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(true);
  });

  it('Step 4: selectedOperationName olmadan false', async () => {
    const wrapper = await mountApp();
    wrapper.vm.currentStep = 4;
    wrapper.vm.selectedOperationName = null;
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(false);
  });

  it('Step 4: selectedOperationName set iken true', async () => {
    const wrapper = await mountApp();
    wrapper.vm.currentStep = 4;
    wrapper.vm.selectedOperationName = 'KTA-OP-001';
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(true);
  });

  it('Step 5: selectedUser olmadan false', async () => {
    const wrapper = await mountApp();
    wrapper.vm.currentStep = 5;
    wrapper.vm.selectedUser = null;
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(false);
  });

  it('Step 5: selectedUser set iken true', async () => {
    const wrapper = await mountApp();
    wrapper.vm.currentStep = 5;
    wrapper.vm.selectedUser = 'EMP-001';
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(true);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// isStepValid computed — JC modu
// ──────────────────────────────────────────────────────────────────────────────
describe('isStepValid — JC modu', () => {
  it('Step 1: selectedJobCard olmadan false', async () => {
    const wrapper = await mountApp();
    wrapper.vm.setSearchMode('JC');
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(false);
  });

  it('Step 1: selectedJobCard set iken true', async () => {
    const wrapper = await mountApp();
    wrapper.vm.setSearchMode('JC');
    wrapper.vm.jobCards = [{ name: 'JC-001', work_order: 'WO-001' }];
    wrapper.vm.selectedJobCardName = 'JC-001';
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(true);
  });

  it('Step 2: selectedOperationName olmadan false', async () => {
    const wrapper = await mountApp();
    wrapper.vm.setSearchMode('JC');
    wrapper.vm.currentStep = 2;
    wrapper.vm.selectedOperationName = null;
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(false);
  });

  it('Step 3: selectedUser olmadan false', async () => {
    const wrapper = await mountApp();
    wrapper.vm.setSearchMode('JC');
    wrapper.vm.currentStep = 3;
    wrapper.vm.selectedUser = null;
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(false);
  });

  it('Step 3: selectedUser set iken true', async () => {
    const wrapper = await mountApp();
    wrapper.vm.setSearchMode('JC');
    wrapper.vm.currentStep = 3;
    wrapper.vm.selectedUser = 'EMP-002';
    await flushPromises();
    expect(wrapper.vm.isStepValid).toBe(true);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// filteredOperations computed
// ──────────────────────────────────────────────────────────────────────────────
describe('filteredOperations', () => {
  const GENERAL_OP  = { name: 'OP-GEN', calisma_karti_op: 'Genel', customer_group: null };
  const RESTRICTED  = { name: 'OP-MUS', calisma_karti_op: 'Özel',  customer_group: 'Müşteri A' };

  it('customer_group yoksa tüm operasyonlar döner', async () => {
    const wrapper = await mountApp();
    wrapper.vm.operations = [GENERAL_OP, RESTRICTED];
    wrapper.vm.workOrder = null;
    wrapper.vm.selectedJobCardName = null;
    await flushPromises();
    // No WO/JC groups → activeCustomerGroups = []
    // GENERAL_OP: no group → pass; RESTRICTED: has group but groups is empty → fail
    expect(wrapper.vm.filteredOperations).toHaveLength(1);
    expect(wrapper.vm.filteredOperations[0].name).toBe('OP-GEN');
  });

  it('WO customer_group eşleşince kısıtlı operasyon da görünür', async () => {
    const wrapper = await mountApp();
    wrapper.vm.operations = [GENERAL_OP, RESTRICTED];
    wrapper.vm.workOrder = { name: 'WO-001', customer_group: 'Müşteri A', customer_groups: ['Müşteri A'] };
    await flushPromises();
    expect(wrapper.vm.filteredOperations).toHaveLength(2);
  });

  it('WO customer_group farklıysa kısıtlı operasyon gizlenir', async () => {
    const wrapper = await mountApp();
    wrapper.vm.operations = [GENERAL_OP, RESTRICTED];
    wrapper.vm.workOrder = { name: 'WO-001', customer_group: 'Müşteri B', customer_groups: ['Müşteri B'] };
    await flushPromises();
    expect(wrapper.vm.filteredOperations).toHaveLength(1);
    expect(wrapper.vm.filteredOperations[0].name).toBe('OP-GEN');
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// activeCustomerGroups computed
// ──────────────────────────────────────────────────────────────────────────────
describe('activeCustomerGroups', () => {
  it('WO varken WO customer_group kullanılır', async () => {
    const wrapper = await mountApp();
    wrapper.vm.workOrder = { customer_group: 'Grup A', customer_groups: ['Grup A'] };
    await flushPromises();
    expect(wrapper.vm.activeCustomerGroups).toContain('Grup A');
  });

  it('WO yoksa JC customer_group kullanılır', async () => {
    const wrapper = await mountApp();
    wrapper.vm.workOrder = null;
    wrapper.vm.jobCards = [{ name: 'JC-001', customer_group: 'Grup B', customer_groups: ['Grup B'] }];
    wrapper.vm.selectedJobCardName = 'JC-001';
    await flushPromises();
    expect(wrapper.vm.activeCustomerGroups).toContain('Grup B');
  });

  it('İkisi de yoksa boş dizi döner', async () => {
    const wrapper = await mountApp();
    wrapper.vm.workOrder = null;
    wrapper.vm.selectedJobCardName = null;
    await flushPromises();
    expect(wrapper.vm.activeCustomerGroups).toEqual([]);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Navigation: goNext / goBack
// ──────────────────────────────────────────────────────────────────────────────
describe('goNext / goBack', () => {
  it('goNext: step geçersizken currentStep değişmez', async () => {
    const wrapper = await mountApp();
    expect(wrapper.vm.currentStep).toBe(1);
    wrapper.vm.goNext();
    await flushPromises();
    expect(wrapper.vm.currentStep).toBe(1);
  });

  it('goNext: step geçerliyken currentStep artar', async () => {
    const wrapper = await mountApp();
    wrapper.vm.workOrder = { name: 'WO-001' };
    await flushPromises();
    wrapper.vm.goNext();
    await flushPromises();
    expect(wrapper.vm.currentStep).toBe(2);
  });

  it('goNext: son stepte currentStep değişmez', async () => {
    const wrapper = await mountApp();
    wrapper.vm.currentStep = 5;
    wrapper.vm.selectedUser = 'EMP-001';
    await flushPromises();
    wrapper.vm.goNext();
    await flushPromises();
    expect(wrapper.vm.currentStep).toBe(5);
  });

  it('goBack: step 1\'den geri gidilemez', async () => {
    const wrapper = await mountApp();
    expect(wrapper.vm.currentStep).toBe(1);
    wrapper.vm.goBack();
    await flushPromises();
    expect(wrapper.vm.currentStep).toBe(1);
  });

  it('goBack: step 3\'ten 2\'ye döner', async () => {
    const wrapper = await mountApp();
    wrapper.vm.currentStep = 3;
    await flushPromises();
    wrapper.vm.goBack();
    await flushPromises();
    expect(wrapper.vm.currentStep).toBe(2);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// setSearchMode
// ──────────────────────────────────────────────────────────────────────────────
describe('setSearchMode', () => {
  it('JC\'ye geçince state tamamen sıfırlanır', async () => {
    const wrapper = await mountApp();
    // Bazı state doldur
    wrapper.vm.workOrder = { name: 'WO-001' };
    wrapper.vm.selectedJobCardName = 'JC-001';
    wrapper.vm.currentStep = 3;
    await flushPromises();

    wrapper.vm.setSearchMode('JC');
    await flushPromises();

    expect(wrapper.vm.searchMode).toBe('JC');
    expect(wrapper.vm.currentStep).toBe(1);
    expect(wrapper.vm.workOrder).toBeNull();
    expect(wrapper.vm.selectedJobCardName).toBeNull();
    expect(wrapper.vm.selectedOperationName).toBeNull();
    expect(wrapper.vm.errorMessage).toBeNull();
    expect(wrapper.vm.createdDoc).toBeNull();
  });

  it('Aynı moda tekrar geçince state değişmez', async () => {
    const wrapper = await mountApp();
    wrapper.vm.workOrder = { name: 'WO-001' };
    await flushPromises();
    wrapper.vm.setSearchMode('WO'); // zaten WO modundayız
    await flushPromises();
    expect(wrapper.vm.workOrder).not.toBeNull();
  });

  it('WO\'ya geri dönünce totalSteps 5 olur', async () => {
    const wrapper = await mountApp();
    wrapper.vm.setSearchMode('JC');
    await flushPromises();
    wrapper.vm.setSearchMode('WO');
    await flushPromises();
    expect(wrapper.vm.totalSteps).toBe(5);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// resetWizard
// ──────────────────────────────────────────────────────────────────────────────
describe('resetWizard', () => {
  it('tüm state initial değere döner', async () => {
    const wrapper = await mountApp();
    wrapper.vm.workOrder = { name: 'WO-001' };
    wrapper.vm.currentStep = 4;
    wrapper.vm.selectedUser = 'EMP-002';
    wrapper.vm.errorMessage = 'Bir hata oluştu';
    wrapper.vm.createdDoc = { name: 'CK-001' };
    await flushPromises();

    wrapper.vm.resetWizard();
    await flushPromises();

    expect(wrapper.vm.currentStep).toBe(1);
    expect(wrapper.vm.workOrder).toBeNull();
    expect(wrapper.vm.selectedUser).toBeNull();
    expect(wrapper.vm.errorMessage).toBeNull();
    expect(wrapper.vm.createdDoc).toBeNull();
    expect(wrapper.vm.workOrderBarcode).toBe('');
    expect(wrapper.vm.jobCardBarcode).toBe('');
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// steps computed — WO / JC
// ──────────────────────────────────────────────────────────────────────────────
describe('steps computed', () => {
  it('WO modunda 5 adım döner', async () => {
    const wrapper = await mountApp();
    expect(wrapper.vm.steps).toHaveLength(5);
  });

  it('JC modunda 3 adım döner', async () => {
    const wrapper = await mountApp();
    wrapper.vm.setSearchMode('JC');
    await flushPromises();
    expect(wrapper.vm.steps).toHaveLength(3);
  });

  it('WO set edilince step1 description güncellenir', async () => {
    const wrapper = await mountApp();
    wrapper.vm.workOrder = { name: 'MFG-WO-001' };
    await flushPromises();
    expect(wrapper.vm.steps[0].description).toBe('MFG-WO-001');
  });
});
