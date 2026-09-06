<template>
  <div v-if="server" class="space-y-8">
    <section class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <NuxtLink to="/" class="text-sm text-moss">← все серверы</NuxtLink>
        <h1 class="mt-2 font-display text-3xl">{{ server.name }}</h1>
        <p class="font-mono text-copper">{{ server.address }}:25565</p>
        <p class="text-sm text-parchment/60">
          {{ server.server_type }} {{ server.game_version }} · {{ server.status }}
        </p>
      </div>
      <div class="flex gap-2">
        <button class="rounded bg-moss px-4 py-2 text-ink" @click="power('start')">Старт</button>
        <button class="rounded border border-white/20 px-4 py-2" @click="power('stop')">Стоп</button>
        <button class="rounded border border-copper/50 px-4 py-2 text-copper" @click="power('restart')">
          Рестарт
        </button>
      </div>
    </section>

    <section class="rounded-2xl border border-white/10 bg-stone/60 p-6">
      <h2 class="font-display text-2xl">Каталог модов</h2>
      <form class="mt-4 flex flex-wrap gap-2" @submit.prevent="search">
        <input
          v-model="query"
          class="min-w-[16rem] flex-1 rounded border border-white/10 bg-ink px-3 py-2"
          placeholder="sodium, lithium, worldedit…"
        />
        <button class="rounded bg-copper px-4 py-2 text-ink">Искать</button>
      </form>
      <p v-if="searchError" class="mt-3 text-red-400">{{ searchError }}</p>
      <ul class="mt-6 space-y-3">
        <li
          v-for="hit in hits"
          :key="`${hit.source}-${hit.external_id}`"
          class="flex items-center justify-between gap-4 rounded-lg border border-white/5 bg-ink/60 p-3"
        >
          <div>
            <p class="font-medium">{{ hit.name }}</p>
            <p class="text-xs uppercase text-moss">{{ hit.source }}</p>
            <p class="text-sm text-parchment/60">{{ hit.description }}</p>
            <p v-if="hit.distribution_blocked" class="text-sm text-copper">
              Распространение через API запрещено — положите jar в /downloads.
            </p>
          </div>
          <button
            class="shrink-0 rounded border border-moss px-3 py-1 text-sm"
            :disabled="hit.distribution_blocked"
            @click="install(hit)"
          >
            Установить
          </button>
        </li>
      </ul>
    </section>

    <section>
      <h2 class="font-display text-2xl">Установлено</h2>
      <ul class="mt-4 divide-y divide-white/10 rounded-xl border border-white/10">
        <li
          v-for="mod in installed"
          :key="mod.id"
          class="flex items-center justify-between px-4 py-3"
        >
          <span>{{ mod.name }} <span class="text-xs text-parchment/50">{{ mod.source }}</span></span>
          <button class="text-sm text-red-400" @click="remove(mod.id)">Удалить</button>
        </li>
      </ul>
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
type Hit = {
  source: "MODRINTH" | "CURSEFORGE" | "CUSTOM";
  external_id: string;
  name: string;
  description: string;
  distribution_blocked: boolean;
};
type Installed = { id: number; name: string; source: string };

const route = useRoute();
const { request } = useApi();
const server = ref<Server | null>(null);
const hits = ref<Hit[]>([]);
const installed = ref<Installed[]>([]);
const query = ref("");
const searchError = ref("");

const loaderMap: Record<string, string> = {
  FABRIC: "fabric",
  FORGE: "forge",
  NEOFORGE: "neoforge",
  PAPER: "paper",
  PURPUR: "paper",
  VANILLA: "paper",
};

onMounted(load);

async function load() {
  const id = String(route.params.id);
  server.value = await request<Server>(`/api/v1/servers/${id}`);
  installed.value = await request<Installed[]>(`/api/v1/servers/${id}/mods`);
}

async function power(action: string) {
  const id = String(route.params.id);
  await request(`/api/v1/servers/${id}/power`, {
    method: "POST",
    body: JSON.stringify({ action }),
  });
  await load();
}

async function search() {
  if (!server.value) return;
  searchError.value = "";
  const loader = loaderMap[server.value.server_type] || "fabric";
  const params = new URLSearchParams({
    query: query.value,
    loader,
    game_version: server.value.game_version,
  });
  try {
    hits.value = await request<Hit[]>(`/api/v1/mods/search?${params}`);
  } catch (err) {
    searchError.value = err instanceof Error ? err.message : "Поиск не удался";
  }
}

async function install(hit: Hit) {
  const id = String(route.params.id);
  try {
    await request(`/api/v1/servers/${id}/mods`, {
      method: "POST",
      body: JSON.stringify({
        source: hit.source,
        external_id: hit.external_id,
      }),
    });
    await load();
  } catch (err) {
    searchError.value = err instanceof Error ? err.message : "Установка не удалась";
  }
}

async function remove(modId: number) {
  const id = String(route.params.id);
  await request(`/api/v1/servers/${id}/mods/${modId}`, { method: "DELETE" });
  await load();
}
</script>
