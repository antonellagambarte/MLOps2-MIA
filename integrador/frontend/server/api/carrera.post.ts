import { CLIENTES } from "./../utils/protocolos"

// Se mide como el mini-TP 3: N llamadas seguidas por protocolo y el promedio por
// llamada. Un bloque por protocolo, no alternado.
//
// La primera llamada de cada bloque queda afuera del cronometro: la primera a
// GraphQL arma el esquema y la primera a gRPC abre el canal HTTP/2, y en el
// notebook esos arranques ya estaban pagados por las celdas anteriores.
const ORDEN = ["rest", "graphql", "grpc"]

export default defineEventHandler(async (event) => {
  const { paciente, n } = await readBody(event)
  const vueltas = Math.min(Math.max(Number(n) || 200, 5), 500)

  const medias: Record<string, number> = {}
  const empezoTodo = performance.now()

  for (const id of ORDEN) {
    const control: any = await CLIENTES[id](paciente)
    if (!control.ok) {
      throw createError({
        statusCode: 400,
        statusMessage: `La carrera necesita un paciente valido: ${id} lo rechazo`,
      })
    }

    const empezo = performance.now()
    for (let vuelta = 0; vuelta < vueltas; vuelta++) await CLIENTES[id](paciente)
    medias[id] = (performance.now() - empezo) / vueltas
  }

  const total = performance.now() - empezoTodo

  const resumen = ORDEN.map((id) => ({
    id,
    ms: medias[id],
    veces: medias[id] / medias.grpc,
  }))

  return { vueltas, total, resumen }
})
