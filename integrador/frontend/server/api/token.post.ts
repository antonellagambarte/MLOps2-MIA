// Solo emite el token, para poder mostrarlo en pantalla antes de usarlo.
export default defineEventHandler(async (event) => {
  const { apiBase, apiKeyTokens } = useRuntimeConfig()
  const { rol } = await readBody(event)

  return await $fetch(`${apiBase}/v1/secure/token`, {
    method: "POST",
    headers: { "X-API-Key": apiKeyTokens },
    body: { usuario: "antonella", rol },
  })
})
