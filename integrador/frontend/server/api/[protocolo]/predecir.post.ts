import { CLIENTES } from "../../utils/protocolos"

// El tramo de la ruta elige el cliente: /api/rest/predecir, /api/grpc/predecir...
export default defineEventHandler(async (event) => {
  const protocolo = getRouterParam(event, "protocolo") as string
  const cliente = CLIENTES[protocolo]
  if (!cliente) throw createError({ statusCode: 404, message: `protocolo desconocido: ${protocolo}` })

  const { paciente } = await readBody(event)
  return await cliente(paciente)
})
