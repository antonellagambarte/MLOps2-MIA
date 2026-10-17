import { credentials, loadPackageDefinition } from "@grpc/grpc-js"
import { loadSync } from "@grpc/proto-loader"

export const CODIGOS_GRPC: Record<number, string> = {
  2: "UNKNOWN",
  3: "INVALID_ARGUMENT",
  14: "UNAVAILABLE",
}

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

function conectar() {
  if (cliente) return cliente
  const { grpcTarget, protoPath } = useRuntimeConfig()
  const definicion = loadSync(protoPath, { keepCase: true, enums: String, defaults: true })
  const paquete: any = loadPackageDefinition(definicion)
  cliente = new paquete.scoring.Scoring(grpcTarget, credentials.createInsecure())
  return cliente
}

export function aCaso(paciente: Record<string, any>) {
  const caso: Record<string, any> = {}
  const imposibles: string[] = []

  for (const [campo, valor] of Object.entries(paciente)) {
    const tabla = ENUMS[campo]
    if (!tabla) {
      if (valor !== null) caso[campo] = valor
      continue
    }
    const enumerado = tabla[valor]
    if (enumerado) {
      caso[campo] = enumerado
    } else {
      imposibles.push(`${campo}: el .proto no define un enum para "${valor}"`)
    }
  }

  return { caso, imposibles }
}

export function predecirUnary(caso: Record<string, any>): Promise<any> {
  return new Promise((resolve) => {
    conectar().Predecir(caso, (error: any, rta: any) => {
      if (error) resolve({ ok: false, error })
      else resolve({ ok: true, rta })
    })
  })
}

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
