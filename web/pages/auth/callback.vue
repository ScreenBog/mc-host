<template>
  <div class="rounded-xl border border-white/10 bg-stone p-8 text-center">
    <p v-if="error" class="text-red-400">{{ error }}</p>
    <p v-else>Входим в панель…</p>
  </div>
</template>

<script setup lang="ts">
const route = useRoute();
const config = useRuntimeConfig();
const auth = useAuthStore();
const error = ref("");

onMounted(async () => {
  const token = String(route.query.token || "");
  if (!token) {
    error.value = "Нет токена в ссылке";
    return;
  }
  try {
    const data = await $fetch<{ access_token: string }>(
      `${config.public.apiBase}/api/v1/auth/callback?token=${encodeURIComponent(token)}`
    );
    auth.setToken(data.access_token);
    await navigateTo("/");
  } catch {
    error.value = "Ссылка недействительна или истекла. Запросите новую в боте.";
  }
});
</script>
