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
    descripcion
  }
}`

export function detalleHttp(error: any) {
  return Array.isArray(error.data?.detail)
    ? error.data.detail.map((problema: any) => ({
        campo: problema.loc.slice(1).join("."),
        mensaje: problema.msg,
      }))
    : [{ campo: "", mensaje: error.data?.detail ?? String(error) }]
}

export function partir(mensaje: string, separadorDeCampo: string) {
  return mensaje.split("; ").map((problema) => {
    const [campo, ...resto] = problema.split(separadorDeCampo)
    return { campo, mensaje: resto.join(separadorDeCampo) }
  })
}

export async function porRest(base: string, paciente: Record<string, any>) {
  const empezo = performance.now()
  try {
    const resultado = await $fetch(`${base}/v1/predict`, { method: "POST", body: paciente })
    return { ok: true, ms: performance.now() - empezo, resultado }
  } catch (error: any) {
    return {
      ok: false,
      ms: performance.now() - empezo,
      http: error.status ?? 502,
      status: `HTTP ${error.status ?? 0}`,
      detalle: detalleHttp(error),
    }
  }
}

export async function porGraphql(base: string, paciente: Record<string, any>) {
  const variables = Object.fromEntries(
    Object.entries(paciente).map(([campo, valor]) => [CAMPOS_GRAPHQL[campo] ?? campo, valor]),
  )

  const empezo = performance.now()
  const respuesta: any = await $fetch(`${base}/graphql`, {
    method: "POST",
    body: { query: MUTACION, variables: { paciente: variables } },
  })
  const ms = performance.now() - empezo

  if (respuesta.errors) {
    return {
      ok: false,
      ms,
      status: "HTTP 200 · errors[]",
      detalle: partir(respuesta.errors[0].message, ": "),
    }
  }

  const salida = respuesta.data.predecir
  return {
    ok: true,
    ms,
    resultado: {
      prediccion: salida.prediccion,
      probabilidad: salida.probabilidad,
      version_modelo: salida.versionModelo,
      descripcion: salida.descripcion,
    },
  }
}
