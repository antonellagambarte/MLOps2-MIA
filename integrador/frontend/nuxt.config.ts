export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: false },

  runtimeConfig: {
    apiBase: "http://fastapi:8800",
    grpcTarget: "grpc:50051",
    protoPath: "/proto/scoring.proto",
    apiKeyTokens: "clave-de-servicio-local",
    public: {
      apiPublica: "http://localhost:8800",
    },
  },

  // En Windows los eventos del filesystem no cruzan al contenedor.
  vite: { server: { watch: { usePolling: true } } },
  nitro: { watchOptions: { usePolling: true, interval: 300 } },
})
