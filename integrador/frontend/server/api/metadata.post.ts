// Solo se comparan los campos que los dos protocolos pueden dar: GraphQL no
// expone umbral ni features, e incluirlos inflaria a REST sin motivo.
const METRICAS = ["auc", "accuracy", "f1", "precision", "recall"]

export default defineEventHandler(async (event) => {
  const { apiBase } = useRuntimeConfig()
  const { campos } = await readBody(event)

  const pideMetricas = campos.some((c: string) => METRICAS.includes(c))
  const pideInfo = campos.some((c: string) => c === "name" || c === "version")

  let restBytes = 0
  let restLlamadas = 0
  const restDatos: Record<string, any> = {}
  const empezoRest = performance.now()

  if (pideInfo) {
    const texto: string = await $fetch(`${apiBase}/v1/model`, { responseType: "text" })
    restBytes += texto.length
    restLlamadas += 1
    const d = JSON.parse(texto)
    if (campos.includes("name")) restDatos.name = d.nombre
    if (campos.includes("version")) restDatos.version = d.version
  }
  if (pideMetricas) {
    const texto: string = await $fetch(`${apiBase}/v1/model/metrics`, { responseType: "text" })
    restBytes += texto.length
    restLlamadas += 1
    const d = JSON.parse(texto)
    const nombres: Record<string, string> = {
      auc: "roc_auc", accuracy: "accuracy", f1: "f1_score",
      precision: "precision", recall: "recall",
    }
    for (const c of campos) {
      if (METRICAS.includes(c)) restDatos[c] = d[nombres[c]]
    }
  }
  const restMs = performance.now() - empezoRest

  const pedidos = campos.filter((c: string) => !METRICAS.includes(c))
  const metricas = campos.filter((c: string) => METRICAS.includes(c))
  const seleccion = [
    ...pedidos,
    metricas.length ? `metrics { ${metricas.join(" ")} }` : "",
  ].filter(Boolean).join(" ")

  const query = `{ model { ${seleccion} } }`
  const empezoGql = performance.now()
  const texto: string = await $fetch(`${apiBase}/graphql`, {
    method: "POST",
    body: { query },
    responseType: "text",
  })
  const gqlMs = performance.now() - empezoGql

  const cuerpo = JSON.parse(texto)
  const modelo = cuerpo.data?.model ?? {}
  const gqlDatos = { ...modelo, ...(modelo.metrics ?? {}) }
  delete gqlDatos.metrics

  return {
    rest: { llamadas: restLlamadas, bytes: restBytes, ms: restMs, datos: restDatos },
    graphql: { llamadas: 1, bytes: texto.length, ms: gqlMs, datos: gqlDatos, query },
  }
})
