<template>
  <div class="space-y-8">
    <section class="rounded-2xl border border-white/10 bg-stone/70 p-8">
      <p class="text-sm uppercase tracking-[0.2em] text-moss">shnenepepe.ru · порт 25565</p>
      <h1 class="mt-3 font-display text-4xl text-parchment">Серверы, которые засыпают сами</h1>
      <p class="mt-4 max-w-2xl text-parchment/70">
        Покупка и питание — в Telegram-боте. Здесь тонкая настройка модов: поиск Modrinth и
        CurseForge, зависимости, ручная загрузка jar.
      </p>
      <p v-if="!auth.token" class="mt-6 text-copper">
        Войдите по Magic Link из бота командой /panel.
      </p>
    </section>

    <section v-if="auth.token">
      <h2 class="mb-4 font-display text-2xl">Ваши серверы</h2>
      <p v-if="error" class="text-red-400">{{ error }}</p>
      <div class="grid gap-4 md:grid-cols-2">
        <NuxtLink
          v-for="server in servers"
          :key="server.id"
          :to="`/servers/${server.id}`"
          class="rounded-xl border border-white/10 bg-ink p-5 transition hover:border-moss"
        >
          <div class="flex items-center justify-between">
            <h3 class="font-medium">{{ server.name }}</h3>
            <span class="text-xs uppercase text-moss">{{ server.status }}</span>
          </div>
          <p class="mt-2 font-mono text-sm text-copper">{{ server.address }}</p>
          <p class="mt-1 text-sm text-parchment/60">
            {{ server.server_type }} {{ server.game_version }}
          </p>
        </NuxtLink>
      </div>
      <p v-if="!servers.length && !error" class="text-parchment/50">Серверов нет.</p>
    </section>
  </div>
</template>

<script setup lang="ts">
type Server = {
  id: string;
  name: string;
  address: string;
  status: string;
  server_type: string;
  game_version: string;
};

const auth = useAuthStore();
const { request } = useApi();
const servers = ref<Server[]>([]);
const error = ref("");

onMounted(async () => {
  auth.hydrate();
  if (!auth.token) return;
  try {
    servers.value = await request<Server[]>("/api/v1/servers");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Ошибка загрузки";
  }
});
</script>
