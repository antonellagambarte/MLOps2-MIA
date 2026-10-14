import { detalleHttp } from "../utils/protocolos"

// La puerta protegida. Sin rol se llama sin cabecera a proposito: es el caso del 401.
// La clave de servicio vive aca, en el servidor: el browser nunca la ve.
export default defineEventHandler(async (event) => {
  const { apiBase, apiKeyTokens } = useRuntimeConfig()
  const { rol, paciente, usuario } = await readBody(event)

  let token: string | null = null
  if (rol) {
    const emitido: any = await $fetch(`${apiBase}/v1/secure/token`, {
      method: "POST",
      headers: { "X-API-Key": apiKeyTokens },
      body: { usuario: usuario ?? "antonella", rol },
    })
    token = emitido.token
  }

  const empezo = performance.now()
  try {
    const resultado = await $fetch(`${apiBase}/v1/secure/predict`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: paciente,
    })
    return { ok: true, ms: performance.now() - empezo, resultado, token }
  } catch (e: any) {
    return {
      ok: false,
      ms: performance.now() - empezo,
      status: `HTTP ${e.status ?? 0}`,
      detalle: detalleHttp(e),
      token,
    }
  }
})
