<template>
  <div class="flex min-h-screen bg-[#121212] text-[#e6e6e6]">
    <aside class="hidden w-[200px] shrink-0 border-r border-[#2a2a2a] bg-[#1a1a1a] p-3 md:block">
      <NuxtLink to="/" class="mb-4 block font-semibold tracking-wide">SHNPP</NuxtLink>
      <NuxtLink to="/" class="block rounded px-2 py-2 text-sm">← Серверы</NuxtLink>
      <NuxtLink v-for="item in items" :key="item.to" :to="item.to" class="block rounded px-2 py-2 text-sm">
        {{ item.label }}
      </NuxtLink>
    </aside>
    <div class="min-w-0 flex-1">
      <slot />
    </div>
  </div>
</template>
<script setup lang="ts">
const route = useRoute();
const id = computed(() => String(route.params.id || ""));
const items = computed(() => [
  { to: `/servers/${id.value}`, label: "Обзор" },
  { to: `/servers/${id.value}/console`, label: "Консоль" },
  { to: `/servers/${id.value}/options`, label: "Настройки" },
  { to: `/servers/${id.value}/addons`, label: "Моды" },
  { to: `/servers/${id.value}/files`, label: "Файлы" },
  { to: `/servers/${id.value}/world`, label: "Мир" },
  { to: `/servers/${id.value}/backups`, label: "Бэкапы" },
  { to: `/servers/${id.value}/access`, label: "Доступ" },
]);
</script>
