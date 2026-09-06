export default defineNuxtConfig({
  compatibilityDate: "2024-11-01",
  ssr: false,
  modules: ["@nuxtjs/tailwindcss", "@pinia/nuxt"],
  pinia: { storesDirs: ["./stores"] },
  css: ["~/assets/css/main.css"],
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || "",
      siteUrl: process.env.NUXT_PUBLIC_SITE_URL || "https://shnenepepe.online",
    },
  },
  app: {
    head: {
      title: "SHNPP — панель модов",
      htmlAttrs: { lang: "ru" },
      meta: [
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        {
          name: "description",
          content: "Управление модами и серверами Minecraft на shnenepepe.ru",
        },
      ],
    },
  },
})
