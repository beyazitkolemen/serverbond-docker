// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  devtools: { enabled: true },
  nitro: {
    preset: 'node-server'
  },
  runtimeConfig: {
    // Private keys (only available on server-side)
    apiSecret: '123',
    // Public keys (exposed to client-side)
    public: {
      apiBase: process.env.API_BASE || '/api'
    }
  },
  css: ['~/assets/css/main.css'],
  modules: [
    '@nuxtjs/tailwindcss'
  ]
})
