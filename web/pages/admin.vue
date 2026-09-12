<template>
  <div>
    <h1 class="font-display text-3xl">Админка</h1>
    <p v-if="error" class="text-red-400">{{ error }}</p>
    <pre class="mt-4 text-xs">{{ overview }}</pre>
  </div>
</template>
<script setup lang="ts">
const { request } = useApi()
const overview = ref<any>(null)
const error = ref('')
onMounted(async () => {
  try { overview.value = await request('/api/v1/admin/overview') }
  catch(e:any){ error.value = 'Нет доступа' }
})
</script>
