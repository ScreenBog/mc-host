<template>
  <div class="p-4 text-sm">
    <p class="text-[#8a8a8a]">Группы как у Aternos: игра, мир, сеть. Сырой ini — во вкладке Файлы.</p>
    <button class="mt-3 rounded bg-[#5a9e4b] px-3 py-1 text-black" @click="save">Сохранить</button>
  </div>
</template>
<script setup lang="ts">
definePageMeta({ layout: "server" });
const route = useRoute();
const { request } = useApi();
async function save() {
  await request(`/api/v1/servers/${route.params.id}/settings`, { method: "PUT", body: JSON.stringify({}) });
}
</script>
