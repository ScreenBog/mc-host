<template>
  <div class="p-4">
    <div v-for="a in acl" :key="a.id">{{ a.telegram_id }} · {{ a.role }}</div>
  </div>
</template>
<script setup lang="ts">
definePageMeta({ layout: "server" });
const route = useRoute();
const { request } = useApi();
const acl = ref<any[]>([]);
onMounted(async () => {
  acl.value = await request(`/api/v1/servers/${route.params.id}/acl`);
});
</script>
