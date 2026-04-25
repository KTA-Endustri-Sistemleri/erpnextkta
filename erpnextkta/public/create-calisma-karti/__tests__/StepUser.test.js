import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import StepUser from '../components/StepUser.vue';

const SAMPLE_USERS = [
  { name: 'EMP-001', employee_name: 'Ahmet Yılmaz', user_id: 'ahmet@firma.com', department: 'Üretim' },
  { name: 'EMP-002', employee_name: 'Fatma Kaya',   user_id: 'fatma@firma.com', department: 'Kalite' },
  { name: 'EMP-003', employee_name: 'Mehmet Demir', user_id: 'mehmet@firma.com', department: 'Üretim' },
];

describe('StepUser', () => {
  it('tüm kullanıcıları listeler', () => {
    const wrapper = mount(StepUser, { props: { users: SAMPLE_USERS, selectedUser: null } });
    const items = wrapper.findAll('.step-user__item');
    expect(items).toHaveLength(3);
  });

  it('kullanıcı sayısını gösterir', () => {
    const wrapper = mount(StepUser, { props: { users: SAMPLE_USERS, selectedUser: null } });
    expect(wrapper.text()).toContain('3 çalışan');
  });

  it('boş liste mesajı gösterir', () => {
    const wrapper = mount(StepUser, { props: { users: [], selectedUser: null } });
    expect(wrapper.find('.step-user__empty').exists()).toBe(true);
    expect(wrapper.text()).toContain('Employee kayıtlarını kontrol edin');
  });

  it('isim ile arama filtresi çalışır', async () => {
    const wrapper = mount(StepUser, { props: { users: SAMPLE_USERS, selectedUser: null } });
    await wrapper.find('.step-user__search-input').setValue('Ahmet');
    expect(wrapper.findAll('.step-user__item')).toHaveLength(1);
    expect(wrapper.text()).toContain('Ahmet Yılmaz');
  });

  it('user_id (email) ile arama çalışır', async () => {
    const wrapper = mount(StepUser, { props: { users: SAMPLE_USERS, selectedUser: null } });
    await wrapper.find('.step-user__search-input').setValue('fatma@');
    expect(wrapper.findAll('.step-user__item')).toHaveLength(1);
    expect(wrapper.text()).toContain('Fatma Kaya');
  });

  it('arama sonucu yoksa "Filtreye uygun çalışan bulunamadı" gösterir', async () => {
    const wrapper = mount(StepUser, { props: { users: SAMPLE_USERS, selectedUser: null } });
    await wrapper.find('.step-user__search-input').setValue('ZZZZZ');
    expect(wrapper.text()).toContain('Filtreye uygun çalışan bulunamadı');
  });

  it('kullanıcıya tıklanınca update:selectedUser emit edilir', async () => {
    const wrapper = mount(StepUser, { props: { users: SAMPLE_USERS, selectedUser: null } });
    await wrapper.findAll('.step-user__item')[0].trigger('click');
    expect(wrapper.emitted('update:selectedUser')).toBeTruthy();
    expect(wrapper.emitted('update:selectedUser')[0]).toEqual(['EMP-001']);
  });

  it('seçili kullanıcı --selected class alır', () => {
    const wrapper = mount(StepUser, { props: { users: SAMPLE_USERS, selectedUser: 'EMP-002' } });
    const items = wrapper.findAll('.step-user__item');
    expect(items[1].classes()).toContain('step-user__item--selected');
    expect(items[0].classes()).not.toContain('step-user__item--selected');
  });

  it('seçili kullanıcı özeti (summary) gösterilir', () => {
    const wrapper = mount(StepUser, { props: { users: SAMPLE_USERS, selectedUser: 'EMP-001' } });
    expect(wrapper.find('.step-user__summary').exists()).toBe(true);
    expect(wrapper.text()).toContain('Ahmet Yılmaz');
  });

  it('seçili yoksa summary gizlidir', () => {
    const wrapper = mount(StepUser, { props: { users: SAMPLE_USERS, selectedUser: null } });
    expect(wrapper.find('.step-user__summary').exists()).toBe(false);
  });

  // getInitials davranışı — badge/avatar üzerinden dolaylı test
  it('tek kelimeli isim için avatar tek harf gösterir', () => {
    const users = [{ name: 'EMP-010', employee_name: 'Ahmet', user_id: null, department: null }];
    const wrapper = mount(StepUser, { props: { users, selectedUser: null } });
    expect(wrapper.find('.step-user__avatar').text()).toBe('A');
  });

  it('iki kelimeli isim için avatar ilk+son harf gösterir', () => {
    const wrapper = mount(StepUser, { props: { users: SAMPLE_USERS, selectedUser: null } });
    const avatars = wrapper.findAll('.step-user__avatar');
    expect(avatars[0].text()).toBe('AY'); // Ahmet Yılmaz
    expect(avatars[1].text()).toBe('FK'); // Fatma Kaya
  });
});
