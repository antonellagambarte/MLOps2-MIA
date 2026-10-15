import { porGrpc } from "../../utils/protocolos"

// La unica prediccion que pasa por el servidor: el navegador no habla gRPC. REST y
// GraphQL los pide directo a la API, asi reciben su codigo de estado sin intermediarios.
export default defineEventHandler(async (event) => {
  const { paciente } = await readBody(event)
  return await porGrpc(paciente)
})
