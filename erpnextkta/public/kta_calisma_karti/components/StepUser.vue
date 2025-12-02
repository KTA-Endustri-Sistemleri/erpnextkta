<script setup>
const props = defineProps({
  // Artık burada Employee listesi var:
  // { name: "EMP-0001", employee_name: "UFUK KARAMALLI", user_id: "ufuk..." }
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

function onChange(event) {
  emit('update:selectedUser', event.target.value || null);
}
</script>

<template>
  <section class="space-y-3">
    <h2 class="font-semibold text-lg">5️⃣ Operatör / Çalışan Seçimi</h2>
    <p class="text-sm text-gray-600">
      Bu Çalışma Kartı ile ilişkilendirilecek <strong>operatörü (Employee)</strong> seç.
    </p>

    <select
      class="w-full border rounded px-3 py-2"
      :value="selectedUser"
      @change="onChange"
    >
      <option disabled value="">Operatör seçin...</option>

      <option
        v-for="emp in users"
        :key="emp.name"
        :value="emp.name"
      >
        <!-- Kullanıcıya sadece isim (ve istersen user_id) göster -->
        {{ emp.employee_name }}
        <span v-if="emp.user_id"> ({{ emp.user_id }})</span>
      </option>
    </select>
  </section>
</template>