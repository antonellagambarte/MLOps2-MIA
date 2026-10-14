import { credentials, loadPackageDefinition } from "@grpc/grpc-js"
import { loadSync } from "@grpc/proto-loader"

// La misma tabla que grpc_service/mapas.py, al revés: texto -> enum del .proto.
const ENUMS: Record<string, Record<string, string>> = {
  gender: {
    Male: "GENERO_MALE",
    Female: "GENERO_FEMALE",
    Other: "GENERO_OTHER",
  },
  ever_married: {
    Yes: "ESTADO_CIVIL_YES",
    No: "ESTADO_CIVIL_NO",
  },
  work_type: {
    Private: "TIPO_TRABAJO_PRIVATE",
    "Self-employed": "TIPO_TRABAJO_SELF_EMPLOYED",
    Govt_job: "TIPO_TRABAJO_GOVT_JOB",
    children: "TIPO_TRABAJO_CHILDREN",
    Never_worked: "TIPO_TRABAJO_NEVER_WORKED",
  },
  Residence_type: {
    Urban: "TIPO_RESIDENCIA_URBAN",
    Rural: "TIPO_RESIDENCIA_RURAL",
  },
  smoking_status: {
    "formerly smoked": "TABAQUISMO_FORMERLY_SMOKED",
    "never smoked": "TABAQUISMO_NEVER_SMOKED",
    smokes: "TABAQUISMO_SMOKES",
    Unknown: "TABAQUISMO_UNKNOWN",
  },
}

let cliente: any = null

// Una sola conexión para todo el proceso: abrirla por pedido agregaría el
// handshake de HTTP/2 a cada medición de latencia.
function conectar() {
  if (cliente) return cliente
  const { grpcTarget, protoPath } = useRuntimeConfig()
  // keepCase para que Residence_type y avg_glucose_level no pasen a camelCase.
  const definicion = loadSync(protoPath, { keepCase: true, enums: String, defaults: true })
  const paquete: any = loadPackageDefinition(definicion)
  cliente = new paquete.scoring.Scoring(grpcTarget, credentials.createInsecure())
  return cliente
}

/** Traduce un paciente al mensaje del .proto. Devuelve también lo que no se pudo codificar. */
export function aCaso(paciente: Record<string, any>) {
  const caso: Record<string, any> = {}
  const imposibles: string[] = []

  for (const [campo, valor] of Object.entries(paciente)) {
    const tabla = ENUMS[campo]
    if (!tabla) {
      // bmi ausente se omite: el servidor lo detecta con HasField.
      if (valor !== null) caso[campo] = valor
      continue
    }
    const enumerado = tabla[valor]
    if (enumerado) {
      caso[campo] = enumerado
    } else {
      // No hay enum para ese valor: se omite y llega como 0, que validar() rechaza.
      imposibles.push(`${campo}: el .proto no define un enum para "${valor}"`)
    }
  }

  return { caso, imposibles }
}

/** Predice un caso por el método unary. Devuelve la misma forma que REST y GraphQL. */
export function predecirUnary(caso: Record<string, any>): Promise<any> {
  return new Promise((resolve) => {
    conectar().Predecir(caso, (error: any, rta: any) => {
      if (error) resolve({ ok: false, error })
      else resolve({ ok: true, rta })
    })
  })
}

/** Manda un lote y resuelve cuando el servidor cerró el stream, anotando cuándo llegó cada uno. */
export function predecirLote(casos: Record<string, any>[]): Promise<any> {
  return new Promise((resolve) => {
    const empezo = performance.now()
    const llegadas: any[] = []
    const stream = conectar().PredecirLote({ casos })

    stream.on("data", (rta: any) => {
      llegadas.push({ ...rta, ms: performance.now() - empezo })
    })
    stream.on("error", (error: any) => resolve({ ok: false, error, llegadas }))
    stream.on("end", () => resolve({ ok: true, llegadas }))
  })
}
