<template>
  <div class="p-4">
    <input v-model="q" class="w-full rounded border border-[#2a2a2a] bg-[#151515] px-2 py-1" placeholder="lithium…" @input="onType" />
    <div class="mt-3 grid gap-2 md:grid-cols-3">
      <div v-for="h in hits" :key="h.external_id" class="rounded border border-[#2a2a2a] p-3">
        <b>{{ h.name }}</b>
        <button class="mt-2 block rounded bg-[#5a9e4b] px-2 py-1 text-black" @click="install(h)">Установить</button>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
definePageMeta({ layout: "server" });
const route = useRoute();
const { request } = useApi();
const q = ref("");
const hits = ref<any[]>([]);
let t: number | undefined;
let ac: AbortController | undefined;
function onType() {
  clearTimeout(t);
  t = window.setTimeout(search, 300);
}
async function search() {
  ac?.abort();
  ac = new AbortController();
  const id = String(route.params.id);
  const s = await request<any>(`/api/v1/servers/${id}`);
  let loader = String(s.server_type).toLowerCase();
  if (["purpur", "spigot"].includes(loader)) loader = "paper";
  hits.value = await request(
    `/api/v1/mods/search?query=${encodeURIComponent(q.value)}&loader=${loader}&game_version=${s.game_version}&limit=20`
  );
}
async function install(h: any) {
  await request(`/api/v1/servers/${route.params.id}/addons/install`, {
    method: "POST",
    body: JSON.stringify({ source: h.source, external_id: h.external_id, name: h.name }),
  });
}
</script>
