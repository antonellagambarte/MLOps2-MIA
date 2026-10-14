// La auditoria la lee solo admin, asi que el token se pide con ese rol.
export default defineEventHandler(async () => {
  const { apiBase, apiKeyTokens } = useRuntimeConfig()

  const emitido: any = await $fetch(`${apiBase}/v1/secure/token`, {
    method: "POST",
    headers: { "X-API-Key": apiKeyTokens },
    body: { usuario: "antonella", rol: "admin" },
  })

  return await $fetch(`${apiBase}/v1/secure/auditoria`, {
    headers: { Authorization: `Bearer ${emitido.token}` },
  })
})
