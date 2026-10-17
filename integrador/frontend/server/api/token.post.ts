export default defineEventHandler(async (event) => {
  const { apiBase, apiKeyTokens } = useRuntimeConfig()
  const { rol, usuario } = await readBody(event)

  return await $fetch(`${apiBase}/v1/secure/token`, {
    method: "POST",
    headers: { "X-API-Key": apiKeyTokens },
    body: { usuario: usuario ?? "antonella", rol },
  })
})
