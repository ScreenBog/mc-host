<template>
  <div class="p-4">
    <p class="mb-2 text-sm text-[#8a8a8a]">{{ path || "/" }}</p>
    <div v-for="e in entries" :key="e.path" class="flex justify-between border-b border-[#2a2a2a] py-2">
      <button @click="open(e)">{{ e.dir ? "📁" : "📄" }} {{ e.name }}</button>
      <span class="text-[#8a8a8a]">{{ e.size }}</span>
    </div>
    <textarea v-if="editor !== null" v-model="editor" class="mt-4 h-64 w-full bg-black p-2 font-mono text-xs" />
    <button v-if="editor !== null" class="mt-2 rounded bg-[#5a9e4b] px-3 py-1 text-black" @click="save">Сохранить</button>
  </div>
</template>
<script setup lang="ts">
definePageMeta({ layout: "server" });
const route = useRoute();
const { request } = useApi();
const path = ref("");
const entries = ref<any[]>([]);
const editor = ref<string | null>(null);
const filePath = ref("");
async function load() {
  const d = await request<any>(`/api/v1/servers/${route.params.id}/files?path=${encodeURIComponent(path.value)}`);
  entries.value = d.entries;
}
async function open(e: any) {
  if (e.dir) {
    path.value = e.path;
    editor.value = null;
    await load();
    return;
  }
  if (!e.text) return;
  filePath.value = e.path;
  const d = await request<any>(`/api/v1/servers/${route.params.id}/files/content?path=${encodeURIComponent(e.path)}`);
  editor.value = d.content;
}
async function save() {
  await request(`/api/v1/servers/${route.params.id}/files/content?path=${encodeURIComponent(filePath.value)}`, {
    method: "PUT",
    body: JSON.stringify({ content: editor.value }),
  });
}
onMounted(load);
</script>
