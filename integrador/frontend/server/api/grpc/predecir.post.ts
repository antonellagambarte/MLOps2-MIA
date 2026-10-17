import { porGrpc } from "../../utils/protocolos"

export default defineEventHandler(async (event) => {
  const { paciente } = await readBody(event)
  return await porGrpc(paciente)
})
