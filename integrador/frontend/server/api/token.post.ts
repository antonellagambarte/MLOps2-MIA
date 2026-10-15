// Lo unico de la puerta protegida que no puede ir directo: emitir un token pide la
// clave de servicio, y esa clave no puede estar en la pagina. El JWT que devuelve si
// es del cliente, asi que con el en mano el navegador llama a la API por su cuenta.
export default defineEventHandler(async (event) => {
  const { apiBase, apiKeyTokens } = useRuntimeConfig()
  const { rol, usuario } = await readBody(event)

  return await $fetch(`${apiBase}/v1/secure/token`, {
    method: "POST",
    headers: { "X-API-Key": apiKeyTokens },
    body: { usuario: usuario ?? "antonella", rol },
  })
})
