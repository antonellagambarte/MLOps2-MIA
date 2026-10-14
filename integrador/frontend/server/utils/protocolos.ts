import { aCaso, predecirUnary } from "./grpc"

// Los tres clientes devuelven la misma forma: { ok, ms, resultado } o
// { ok, ms, status, detalle }.

// Strawberry nombra los campos en camelCase; el input se llama residence_type.
const CAMPOS_GRAPHQL: Record<string, string> = {
  heart_disease: "heartDisease",
  ever_married: "everMarried",
  work_type: "workType",
  Residence_type: "residenceType",
  avg_glucose_level: "avgGlucoseLevel",
  smoking_status: "smokingStatus",
}

const MUTACION = `mutation($paciente: PacienteInput!) {
  predecir(paciente: $paciente) {
    prediccion
    probabilidad
    versionModelo
    descripcion
  }
}`

const CODIGOS: Record<number, string> = {
  2: "UNKNOWN",
  3: "INVALID_ARGUMENT",
  14: "UNAVAILABLE",
}

export function detalleHttp(e: any) {
  return Array.isArray(e.data?.detail)
    ? e.data.detail.map((d: any) => ({ campo: d.loc.slice(1).join("."), mensaje: d.msg }))
    : [{ campo: "", mensaje: e.data?.detail ?? String(e) }]
}


function partir(mensaje: string, separadorDeCampo: string) {
  return mensaje.split("; ").map((t) => {
    const [campo, ...resto] = t.split(separadorDeCampo)
    return { campo, mensaje: resto.join(separadorDeCampo) }
  })
}

export async function porRest(paciente: Record<string, any>) {
  const { apiBase } = useRuntimeConfig()
  const empezo = performance.now()
  try {
    const resultado = await $fetch(`${apiBase}/v1/predict`, { method: "POST", body: paciente })
    return { ok: true, ms: performance.now() - empezo, resultado }
  } catch (e: any) {
    const ms = performance.now() - empezo
    return { ok: false, ms, status: `HTTP ${e.status ?? 0}`, detalle: detalleHttp(e) }
  }
}

export async function porGraphql(paciente: Record<string, any>) {
  const { apiBase } = useRuntimeConfig()
  const variables = Object.fromEntries(
    Object.entries(paciente).map(([k, v]) => [CAMPOS_GRAPHQL[k] ?? k, v]),
  )

  const empezo = performance.now()
  const rta: any = await $fetch(`${apiBase}/graphql`, {
    method: "POST",
    body: { query: MUTACION, variables: { paciente: variables } },
  })
  const ms = performance.now() - empezo

  // GraphQL no usa codigos de estado: el rechazo llega como 200 con errors[].
  if (rta.errors) {
    return {
      ok: false,
      ms,
      status: "HTTP 200 · errors[]",
      detalle: partir(rta.errors[0].message, ": "),
    }
  }

  const p = rta.data.predecir
  return {
    ok: true,
    ms,
    resultado: {
      prediccion: p.prediccion,
      probabilidad: p.probabilidad,
      version_modelo: p.versionModelo,
      descripcion: p.descripcion,
    },
  }
}

export async function porGrpc(paciente: Record<string, any>) {
  const { caso, imposibles } = aCaso(paciente)

  const empezo = performance.now()
  const r: any = await predecirUnary(caso)
  const ms = performance.now() - empezo

  if (!r.ok) {
    const texto = String(r.error.details ?? r.error.message)
    return {
      ok: false,
      ms,
      status: `${r.error.code} · ${CODIGOS[r.error.code] ?? "ERROR"}`,
      detalle: partir(texto, " "),
      imposibles,
    }
  }

  return {
    ok: true,
    ms,
    resultado: {
      prediccion: r.rta.prediccion,
      probabilidad: r.rta.probabilidad,
      version_modelo: r.rta.version_modelo,
      descripcion: r.rta.descripcion,
    },
  }
}

export const CLIENTES: Record<string, (p: Record<string, any>) => Promise<any>> = {
  rest: porRest,
  graphql: porGraphql,
  grpc: porGrpc,
}
