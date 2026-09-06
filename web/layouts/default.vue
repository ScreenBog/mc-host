<template>
  <div class="min-h-screen">
    <header class="border-b border-white/10 bg-ink/80 backdrop-blur">
      <div class="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <NuxtLink to="/" class="font-display text-xl tracking-wide text-parchment">
          SHNPP
        </NuxtLink>
        <nav class="flex items-center gap-4 text-sm">
          <span class="text-parchment/60">панель модов</span>
          <button
            v-if="auth.token"
            class="rounded border border-copper/50 px-3 py-1 text-copper"
            @click="auth.logout()"
          >
            Выйти
          </button>
        </nav>
      </div>
    </header>
    <main class="mx-auto max-w-6xl px-4 py-8">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
const auth = useAuthStore();
onMounted(() => auth.hydrate());
</script>
