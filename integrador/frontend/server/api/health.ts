export default defineEventHandler(async () => {
  const { apiBase } = useRuntimeConfig()

  const empezo = performance.now()
  const salud = await $fetch(`${apiBase}/health`)
  const ms = performance.now() - empezo

  return { salud, ms }
})
