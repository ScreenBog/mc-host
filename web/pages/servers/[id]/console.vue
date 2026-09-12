<template>
  <div class="p-4">
    <pre class="max-h-[420px] overflow-auto bg-black p-2 font-mono text-xs">{{ log }}</pre>
    <form class="mt-2 flex gap-2" @submit.prevent="send">
      <input v-model="cmd" class="flex-1 rounded border border-[#2a2a2a] bg-[#151515] px-2 py-1" />
      <button class="rounded bg-[#5a9e4b] px-3 py-1 text-black">Отправить</button>
    </form>
  </div>
</template>
<script setup lang="ts">
definePageMeta({ layout: "server" });
const route = useRoute();
const { request } = useApi();
const log = ref("");
const cmd = ref("");
const id = computed(() => String(route.params.id));
async function load() {
  const d = await request<any>(`/api/v1/servers/${id.value}/console?lines=80`);
  log.value = d.lines || "";
}
async function send() {
  await request(`/api/v1/servers/${id.value}/console`, { method: "POST", body: JSON.stringify({ command: cmd.value }) });
  cmd.value = "";
  await load();
}
onMounted(load);
</script>
