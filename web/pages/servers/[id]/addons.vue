<template>
  <div class="p-4">
    <div class="mb-3 flex justify-between">
      <span>{{ mods.length }} шт.</span>
      <NuxtLink :to="`/servers/${id}/addons/add`" class="rounded bg-[#5a9e4b] px-3 py-1 text-black">Найти</NuxtLink>
    </div>
    <div v-for="m in mods" :key="m.id" class="flex justify-between border-b border-[#2a2a2a] py-2">
      <span>{{ m.name }}</span>
      <span>{{ m.enabled ? "вкл" : "выкл" }}</span>
    </div>
  </div>
</template>
<script setup lang="ts">
definePageMeta({ layout: "server" });
const route = useRoute();
const { request } = useApi();
const id = computed(() => String(route.params.id));
const mods = ref<any[]>([]);
onMounted(async () => {
  mods.value = await request(`/api/v1/servers/${id.value}/mods`);
});
</script>
