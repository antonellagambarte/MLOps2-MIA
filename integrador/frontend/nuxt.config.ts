export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: false },

  // Sin `public`: estas direcciones solo las ve el servidor de Nuxt.
  runtimeConfig: {
    apiBase: "http://fastapi:8800",
    grpcTarget: "grpc:50051",
    protoPath: "/proto/scoring.proto",
  },

  // En Windows los eventos del filesystem no cruzan al contenedor.
  vite: { server: { watch: { usePolling: true } } },
  nitro: { watchOptions: { usePolling: true, interval: 300 } },
})
