<template>
  <div class="space-y-6">
    <h1 class="font-display text-3xl">Новый сервер</h1>
    <p class="text-sm text-parchment/60">Шаг {{ step }} / 4</p>
    <section v-if="step===1" class="grid gap-3 md:grid-cols-2">
      <button class="rounded-xl border border-white/10 p-6" @click="edition='JAVA'; step=2">Java</button>
      <button class="rounded-xl border border-white/10 p-6" @click="edition='BEDROCK'; step=2">Bedrock</button>
    </section>
    <section v-else-if="step===2" class="grid gap-3 md:grid-cols-3">
      <button v-for="s in software" :key="s.id" class="rounded-xl border border-white/10 p-4 text-left" @click="pickSoft(s)">
        <b>{{ s.name }}</b>
        <p class="text-sm text-parchment/60">{{ s.blurb }}</p>
      </button>
    </section>
    <section v-else-if="step===3">
      <button v-for="v in versions" :key="v" class="mr-2 mb-2 rounded border border-copper/40 px-3 py-1" @click="pickVer(v)">{{ v }}</button>
    </section>
    <section v-else class="space-y-3">
      <input v-model="name" class="w-full rounded bg-ink p-2" placeholder="Название">
      <input v-model="subdomain" class="w-full rounded bg-ink p-2" placeholder="поддомен">
      <button class="rounded bg-moss px-4 py-2 text-ink" @click="create">Создать</button>
      <p class="text-red-400">{{ error }}</p>
    </section>
  </div>
</template>
<script setup lang="ts">
const step = ref(1)
const edition = ref('JAVA')
const software = ref<any[]>([])
const versions = ref<string[]>([])
const picked = ref('')
const version = ref('')
const name = ref('')
const subdomain = ref('')
const error = ref('')
const { request } = useApi()
watch(step, async (s) => {
  if (s===2) software.value = await request(`/api/v1/software?edition=${edition.value}`)
})
async function pickSoft(s:any){
  picked.value = s.id
  const d = await request<any>(`/api/v1/software/${s.id}/versions`)
  versions.value = d.versions
  step.value = 3
}
function pickVer(v:string){ version.value=v; step.value=4 }
async function create(){
  try{
    const srv = await request<any>('/api/v1/servers', { method:'POST', body: JSON.stringify({
      name:name.value, subdomain:subdomain.value, server_type:picked.value, game_version:version.value, edition:edition.value, plan_id:'starter'
    })})
    navigateTo(`/servers/${srv.id}`)
  }catch(e:any){ error.value = e.message }
}
</script>
