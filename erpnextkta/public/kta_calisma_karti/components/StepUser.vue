<script setup>
const props = defineProps({
  users: {
    type: Array,
    default: () => []
  },
  // v-model:selectedUser -> "selectedUser"
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
    <h2 class="font-semibold text-lg">5️⃣ Kullanıcı Seçimi</h2>
    <p class="text-sm text-gray-600">
      Bu Çalışma Kartı ile ilişkilendirilecek <strong>kullanıcıyı</strong> seç.
      Liste, sistemde görme yetkin olan kullanıcıları içermelidir.
    </p>

    <select
      class="w-full border rounded px-3 py-2"
      :value="selectedUser"
      @change="onChange"
    >
      <option disabled value="">Kullanıcı seçin...</option>
      <option
        v-for="u in users"
        :key="u.name"
        :value="u.name"
      >
        <!-- Tercihe göre name / full_name / email gösterebilirsin -->
        {{ u.full_name || u.name }}
      </option>
    </select>
  </section>
</template>