<template>
  <div class="mx-auto max-w-4xl p-4">
    <div class="mb-4 flex items-center justify-between">
      <h1 class="text-lg font-semibold">Серверы</h1>
      <NuxtLink to="/create" class="rounded bg-[#5a9e4b] px-3 py-1 text-sm text-black">Создать</NuxtLink>
    </div>
    <p v-if="!auth.token" class="text-sm text-[#8a8a8a]">Войдите через бота → Панель модов.</p>
    <div v-else class="divide-y divide-[#2a2a2a] rounded border border-[#2a2a2a]">
      <NuxtLink v-for="s in servers" :key="s.id" :to="`/servers/${s.id}`" class="flex justify-between px-3 py-3">
        <span>{{ s.status }} · {{ s.name }}</span>
        <code class="text-sm">{{ s.address }}</code>
      </NuxtLink>
    </div>
  </div>
</template>
<script setup lang="ts">
const auth = useAuthStore();
const { request } = useApi();
const servers = ref<any[]>([]);
onMounted(async () => {
  auth.hydrate();
  if (!auth.token) return;
  servers.value = await request("/api/v1/servers");
});
</script>
