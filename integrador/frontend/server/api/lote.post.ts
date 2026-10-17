import { aCaso, predecirLote } from "../utils/grpc"

export default defineEventHandler(async (event) => {
  const { pacientes } = await readBody(event)
  const casos = pacientes.map((paciente: any) => aCaso(paciente).caso)

  const empezo = performance.now()
  const respuesta = await predecirLote(casos)
  const ms = performance.now() - empezo

  if (!respuesta.ok) {
    const { details, message } = respuesta.error
    return { ok: false, ms, status: String(details ?? message), llegadas: respuesta.llegadas }
  }
  return { ok: true, ms, llegadas: respuesta.llegadas }
})
