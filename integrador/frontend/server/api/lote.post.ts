import { aCaso, predecirLote } from "../utils/grpc"

export default defineEventHandler(async (event) => {
  const { pacientes } = await readBody(event)
  const casos = pacientes.map((p: any) => aCaso(p).caso)

  // Lo que interesa es cuando llego cada prediccion, no el total del lote.
  const empezo = performance.now()
  const r = await predecirLote(casos)
  const ms = performance.now() - empezo

  if (!r.ok) {
    return { ok: false, ms, status: String(r.error.details ?? r.error.message), llegadas: r.llegadas }
  }
  return { ok: true, ms, llegadas: r.llegadas }
})
