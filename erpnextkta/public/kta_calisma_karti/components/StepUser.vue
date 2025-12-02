<script setup>
import { ref, computed } from 'vue';

const props = defineProps({
  // Employee listesi:
  // { name: "EMP-0001", employee_name: "UFUK KARAMALLI", user_id: "ufuk@...", department: "..."}
  users: {
    type: Array,
    default: () => []
  },
  // v-model:selectedUser -> Employee.name (EMP-0001)
  selectedUser: {
    type: String,
    default: null
  }
});

const emit = defineEmits(['update:selectedUser']);

// Arama kutusu
const searchText = ref('');

// Filtrelenmiş liste
const filteredUsers = computed(() => {
  const q = searchText.value.trim().toLowerCase();
  if (!q) return props.users || [];

  return (props.users || []).filter((u) => {
    const name = (u.employee_name || '').toLowerCase();
    const userId = (u.user_id || '').toLowerCase();
    const empName = (u.name || '').toLowerCase();
    return (
      name.includes(q) ||
      userId.includes(q) ||
      empName.includes(q)
    );
  });
});

function selectUser(name) {
  emit('update:selectedUser', name);
}

function isSelected(emp) {
  return props.selectedUser === emp.name;
}

// Baş harflerden avatar label
function getInitials(emp) {
  const full = emp.employee_name || emp.name || '';
  const parts = full.split(' ').filter(Boolean);
  if (!parts.length) return '?';
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}
</script>

<template>
  <section class="step-user">
    <div class="step-user__header">
      <div>
        <h2 class="step-user__title">5️⃣ Operatör</h2>
        <p class="step-user__subtitle">
          Bu Çalışma Kartı ile ilişkilendirilecek <strong>operatörü (Employee)</strong> seç.
          Sadece <strong>aktif</strong> ve <strong>User bağlı</strong> çalışanlar listelenir.
        </p>
      </div>

      <div
        v-if="users.length"
        class="step-user__count"
      >
        {{ users.length }} çalışan
      </div>
    </div>

    <!-- Arama kutusu -->
    <div class="step-user__search-row">
      <input
        v-model="searchText"
        type="text"
        class="step-user__search-input"
        placeholder="İsim / e-posta ile ara..."
      />
    </div>

    <!-- Liste boşsa -->
    <div
      v-if="!filteredUsers.length"
      class="step-user__empty"
    >
      <span v-if="users.length === 0">
        Uygun çalışan bulunamadı. Employee kayıtlarını kontrol edin.
      </span>
      <span v-else>
        Filtreye uygun çalışan bulunamadı. Arama kriterini değiştirin.
      </span>
    </div>

    <!-- Çalışan listesi -->
    <div
      v-else
      class="step-user__list"
    >
      <button
        v-for="emp in filteredUsers"
        :key="emp.name"
        type="button"
        class="step-user__item"
        :class="{ 'step-user__item--selected': isSelected(emp) }"
        @click="selectUser(emp.name)"
      >
        <div class="step-user__avatar">
          {{ getInitials(emp) }}
        </div>

        <div class="step-user__info">
          <div class="step-user__name-row">
            <span class="step-user__name">
              {{ emp.employee_name || emp.name }}
            </span>
            <span v-if="emp.department" class="step-user__department">
              {{ emp.department }}
            </span>
          </div>
          <div v-if="emp.user_id" class="step-user__email">
            {{ emp.user_id }}
          </div>
        </div>

        <div class="step-user__badge">
          {{ isSelected(emp) ? 'Seçili' : 'Seç' }}
        </div>
      </button>
    </div>

    <!-- Seçili özet -->
    <div
      v-if="selectedUser"
      class="step-user__summary"
    >
      <div class="step-user__summary-title">
        Seçili Operatör:
      </div>
      <div class="step-user__summary-body">
        <!-- Seçili employee objesini bulup gösteriyoruz -->
        <template v-for="emp in users" :key="emp.name">
          <template v-if="emp.name === selectedUser">
            <div class="step-user__summary-name">
              {{ emp.employee_name || emp.name }}
            </div>
            <div v-if="emp.user_id" class="step-user__summary-row">
              <span class="step-user__label">User:</span>
              <span>{{ emp.user_id }}</span>
            </div>
            <div v-if="emp.department" class="step-user__summary-row">
              <span class="step-user__label">Departman:</span>
              <span>{{ emp.department }}</span>
            </div>
          </template>
        </template>
      </div>
    </div>
  </section>
</template>

<style scoped>
.step-user {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.step-user__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.step-user__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #111827;
}

.step-user__subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  color: #4b5563;
}

.step-user__count {
  font-size: 0.75rem;
  color: #6b7280;
  white-space: nowrap;
}

.step-user__search-row {
  display: flex;
  margin-top: 0.25rem;
}

.step-user__search-input {
  flex: 1 1 auto;
  font-size: 0.85rem;
  padding: 0.4rem 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid #d1d5db;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.step-user__search-input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.15);
}

.step-user__empty {
  font-size: 0.8rem;
  color: #4b5563;
  background: #f9fafb;
  border: 1px dashed #d1d5db;
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
}

/* Liste alanı */
.step-user__list {
  max-height: 260px;
  border-radius: 0.5rem;
  border: 1px solid #e5e7eb;
  overflow-y: auto;
  background: #ffffff;
}

.step-user__item {
  width: 100%;
  border: 0;
  border-bottom: 1px solid #e5e7eb;
  background: transparent;
  padding: 0.45rem 0.6rem;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  cursor: pointer;
  text-align: left;
  font-size: 0.85rem;
  transition: background 0.12s ease, box-shadow 0.12s ease;
}

.step-user__item:last-child {
  border-bottom: none;
}

.step-user__item:hover {
  background: #f9fafb;
}

.step-user__item--selected {
  background: #eff6ff;
  box-shadow: inset 2px 0 0 #2563eb;
}

.step-user__avatar {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 600;
  background: #e5e7eb;
  color: #374151;
}

.step-user__item--selected .step-user__avatar {
  background: #2563eb;
  color: #ffffff;
}

.step-user__info {
  flex: 1 1 auto;
  min-width: 0;
}

.step-user__name-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.step-user__name {
  font-weight: 600;
  color: #111827;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step-user__department {
  font-size: 0.7rem;
  color: #6b7280;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  padding: 0.05rem 0.4rem;
  white-space: nowrap;
}

.step-user__email {
  font-size: 0.75rem;
  color: #4b5563;
}

.step-user__badge {
  flex: 0 0 auto;
  font-size: 0.7rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  border: 1px solid #d1d5db;
  background: #f9fafb;
  color: #4b5563;
  white-space: nowrap;
}

/* Seçili özet */
.step-user__summary {
  margin-top: 0.25rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  font-size: 0.8rem;
  color: #1e3a8a;
}

.step-user__summary-title {
  font-weight: 600;
  margin-bottom: 0.15rem;
}

.step-user__summary-body {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.step-user__summary-name {
  font-weight: 600;
}

.step-user__summary-row {
  display: flex;
  gap: 0.25rem;
}

.step-user__label {
  font-weight: 500;
}
</style>