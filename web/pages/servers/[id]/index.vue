<template>
  <div class="p-4" v-if="s">
    <h1 class="text-lg font-semibold">{{ s.name }} · {{ s.status }}</h1>
    <p class="font-mono text-sm">{{ s.address }}</p>
    <pre class="mt-4 max-h-48 overflow-auto bg-black p-2 text-xs">{{ log }}</pre>
  </div>
</template>
<script setup lang="ts">
definePageMeta({ layout: "server" });
const route = useRoute();
const { request } = useApi();
const s = ref<any>(null);
const log = ref("");
onMounted(async () => {
  const id = String(route.params.id);
  s.value = await request(`/api/v1/servers/${id}`);
  const c = await request<any>(`/api/v1/servers/${id}/console?lines=8`);
  log.value = c.lines || "";
});
</script>
