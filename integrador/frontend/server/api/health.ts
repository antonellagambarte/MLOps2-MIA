export default defineEventHandler(async () => {
  const { apiBase } = useRuntimeConfig()

  // El tiempo se mide alrededor de la llamada al servicio.
  const empezo = performance.now()
  const salud = await $fetch(`${apiBase}/health`)
  const ms = performance.now() - empezo

  return { salud, ms }
})
