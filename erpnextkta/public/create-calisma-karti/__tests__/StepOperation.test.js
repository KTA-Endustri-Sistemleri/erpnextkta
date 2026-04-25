import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import StepOperation from '../components/StepOperation.vue';

const SAMPLE_OPS = [
  { name: 'KTA-OP-001', calisma_karti_op: 'Kaynak', customer_group: null },
  { name: 'KTA-OP-002', calisma_karti_op: 'Boya',   customer_group: 'Müşteri A' },
  { name: 'KTA-OP-003', calisma_karti_op: 'Montaj', customer_group: null },
];

describe('StepOperation', () => {
  it('operasyon kartlarını listeler', () => {
    const wrapper = mount(StepOperation, { props: { operations: SAMPLE_OPS, selectedOperation: null } });
    expect(wrapper.findAll('.step-operation__card')).toHaveLength(3);
  });

  it('operasyon sayısını gösterir', () => {
    const wrapper = mount(StepOperation, { props: { operations: SAMPLE_OPS, selectedOperation: null } });
    expect(wrapper.text()).toContain('3 operasyon bulundu');
  });

  it('calisma_karti_op adını gösterir', () => {
    const wrapper = mount(StepOperation, { props: { operations: SAMPLE_OPS, selectedOperation: null } });
    expect(wrapper.text()).toContain('Kaynak');
    expect(wrapper.text()).toContain('Boya');
    expect(wrapper.text()).toContain('Montaj');
  });

  it('boş liste empty mesajı gösterir', () => {
    const wrapper = mount(StepOperation, { props: { operations: [], selectedOperation: null } });
    expect(wrapper.find('.step-operation__empty').exists()).toBe(true);
    expect(wrapper.text()).toContain('herhangi bir operasyon bulunamadı');
  });

  it('operasyona tıklanınca update:selectedOperation emit edilir', async () => {
    const wrapper = mount(StepOperation, { props: { operations: SAMPLE_OPS, selectedOperation: null } });
    await wrapper.findAll('.step-operation__card')[0].trigger('click');
    expect(wrapper.emitted('update:selectedOperation')).toBeTruthy();
    expect(wrapper.emitted('update:selectedOperation')[0]).toEqual(['KTA-OP-001']);
  });

  it('seçili operasyon --selected class alır', () => {
    const wrapper = mount(StepOperation, {
      props: { operations: SAMPLE_OPS, selectedOperation: 'KTA-OP-002' },
    });
    const cards = wrapper.findAll('.step-operation__card');
    expect(cards[1].classes()).toContain('step-operation__card--selected');
    expect(cards[0].classes()).not.toContain('step-operation__card--selected');
  });

  it('seçili operasyon badge "Seçili" gösterir', () => {
    const wrapper = mount(StepOperation, {
      props: { operations: SAMPLE_OPS, selectedOperation: 'KTA-OP-001' },
    });
    const cards = wrapper.findAll('.step-operation__card');
    expect(cards[0].find('.step-operation__badge').text()).toBe('Seçili');
    expect(cards[1].find('.step-operation__badge').text()).toBe('Seç');
  });

  it('seçili yoksa tüm badge "Seç" gösterir', () => {
    const wrapper = mount(StepOperation, { props: { operations: SAMPLE_OPS, selectedOperation: null } });
    wrapper.findAll('.step-operation__badge').forEach(badge => {
      expect(badge.text()).toBe('Seç');
    });
  });
});
