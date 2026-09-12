<template>
  <div class="min-h-screen bg-[#121212] text-[#e6e6e6]">
    <slot />
  </div>
</template>
<script setup lang="ts">
const auth = useAuthStore();
onMounted(() => auth.hydrate());
</script>
