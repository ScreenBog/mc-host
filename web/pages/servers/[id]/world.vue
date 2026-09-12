<template>
  <div class="p-4">
    <button class="rounded bg-[#5a9e4b] px-3 py-1 text-black" @click="dl">Скачать мир</button>
  </div>
</template>
<script setup lang="ts">
definePageMeta({ layout: "server" });
const route = useRoute();
const auth = useAuthStore();
async function dl() {
  const r = await fetch(`/api/v1/servers/${route.params.id}/world`, { headers: { Authorization: `Bearer ${auth.token}` } });
  const b = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(b);
  a.download = "world.zip";
  a.click();
}
</script>
