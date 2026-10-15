import { partir, porGraphql, porRest } from "#shared/protocolos"
import { aCaso, CODIGOS_GRPC, predecirUnary } from "./grpc"

// Los clientes de REST y GraphQL estan en shared/protocolos.ts porque el navegador
// tambien los usa. Aca queda el de gRPC, que solo puede correr del lado del servidor.

export { detalleHttp } from "#shared/protocolos"

export async function porGrpc(paciente: Record<string, any>) {
  const { caso, imposibles } = aCaso(paciente)

  const empezo = performance.now()
  const respuesta: any = await predecirUnary(caso)
  const ms = performance.now() - empezo

  if (!respuesta.ok) {
    const { code, details, message } = respuesta.error
    return {
      ok: false,
      ms,
      status: `${code} · ${CODIGOS_GRPC[code] ?? "ERROR"}`,
      detalle: partir(String(details ?? message), " "),
      imposibles,
    }
  }

  const salida = respuesta.rta
  return {
    ok: true,
    ms,
    resultado: {
      prediccion: salida.prediccion,
      probabilidad: salida.probabilidad,
      version_modelo: salida.version_modelo,
      descripcion: salida.descripcion,
    },
  }
}

// Los tres medidos desde el mismo lugar, que es lo que hace comparable a la carrera.
export const CLIENTES: Record<string, (paciente: Record<string, any>) => Promise<any>> = {
  rest: (paciente) => porRest(useRuntimeConfig().apiBase, paciente),
  graphql: (paciente) => porGraphql(useRuntimeConfig().apiBase, paciente),
  grpc: porGrpc,
}
