<template>
  <div class="p-4">
    <button class="mb-3 rounded bg-[#5a9e4b] px-3 py-1 text-black" @click="make">Создать сейчас</button>
    <div v-for="b in rows" :key="b.id" class="border-b border-[#2a2a2a] py-2">{{ b.kind }} · {{ b.created_at }}</div>
  </div>
</template>
<script setup lang="ts">
definePageMeta({ layout: "server" });
const route = useRoute();
const { request } = useApi();
const rows = ref<any[]>([]);
async function load() {
  rows.value = await request(`/api/v1/servers/${route.params.id}/backups`);
}
async function make() {
  await request(`/api/v1/servers/${route.params.id}/backups`, { method: "POST" });
  await load();
}
onMounted(load);
</script>
