<script setup>
import { detalleHttp, porGraphql, porRest } from "#shared/protocolos"
import { PACIENTES } from "./pacientes"

const INVALIDO = PACIENTES.find((caso) => caso.invalido)

const PROTOCOLOS = [
  {
    id: "rest",
    nombre: "REST",
    nota: "POST /v1/predict · JSON sobre HTTP/1.1",
    rechazo: "corta con HTTP 422 y el detalle de Pydantic",
  },
  {
    id: "graphql",
    nombre: "GraphQL",
    nota: "mutation predecir",
    rechazo: "responde HTTP 200 y pone el rechazo en errors[]",
  },
  {
    id: "grpc",
    nombre: "gRPC",
    nota: "rpc Predecir · Protocol Buffers sobre HTTP/2, servicio aparte",
    rechazo: "corta con INVALID_ARGUMENT, y los enum del .proto ni dejan enviar un valor inventado",
  },
]

const elegido = ref(0)
const paciente = computed(() => PACIENTES[elegido.value])

const modelo = ref(null)
const resultados = ref({})
const esperando = ref({})

const coinciden = computed(() => {
  const listos = PROTOCOLOS
    .map((protocolo) => resultados.value[protocolo.id])
    .filter((respuesta) => respuesta?.ok)
  if (listos.length < PROTOCOLOS.length) return null
  const probabilidades = new Set(listos.map((respuesta) => respuesta.resultado.probabilidad))
  return probabilidades.size === 1 ? listos[0].resultado.probabilidad : null
})


const { apiPublica } = useRuntimeConfig().public

function llamar(id, paciente) {
  if (id === "rest") return porRest(apiPublica, paciente)
  if (id === "graphql") return porGraphql(apiPublica, paciente)
  return pedir("/api/grpc/predecir", { method: "POST", body: { paciente } })
}

async function pedir(ruta, opciones) {
  try {
    return await $fetch(ruta, opciones)
  } catch (error) {
    if (error.data) return error.data
    return {
      ok: false,
      ms: 0,
      status: `HTTP ${error.status ?? 0}`,
      detalle: [{ campo: "", mensaje: String(error) }],
    }
  }
}

async function predecir(id) {
  esperando.value = { ...esperando.value, [id]: true }
  try {
    const respuesta = await llamar(id, paciente.value.datos)
    resultados.value = { ...resultados.value, [id]: respuesta }
  } catch (error) {
    resultados.value = {
      ...resultados.value,
      [id]: { ok: false, ms: 0, status: "error", detalle: [{ campo: "", mensaje: String(error) }] },
    }
  } finally {
    esperando.value = { ...esperando.value, [id]: false }
  }
}

async function predecirTodos() {
  for (const protocolo of PROTOCOLOS) await predecir(protocolo.id)
}

const desdeLaMaquina = ref(null)

const peorDelScript = computed(() =>
  desdeLaMaquina.value
    ? Math.max(...desdeLaMaquina.value.resumen.map((medicion) => medicion.ms))
    : 1,
)

const lote = ref(null)
const enviandoLote = ref(false)

async function enviarLote() {
  enviandoLote.value = true
  lote.value = null
  try {
    const pacientes = PACIENTES.slice(0, 3).map((caso) => caso.datos)
    lote.value = await pedir("/api/lote", { method: "POST", body: { pacientes } })
  } finally {
    enviandoLote.value = false
  }
}

const SECCIONES = [
  { id: "prediccion", nombre: "Predicción", nota: "REST · GraphQL · gRPC" },
  { id: "latencia", nombre: "Latencia", nota: "" },
  { id: "lote", nombre: "Lote", nota: "PredecirLote gRPC" },
  { id: "seguridad", nombre: "Seguridad", nota: "token, límite y auditoría" },
]

const seccion = ref("prediccion")
const barraAbierta = ref(true)

const CASOS = [
  {
    id: "sinToken", etiqueta: "sin token", rol: null, roto: false, espera: 401,
    freno: "autenticación — no pasa la primera puerta",
  },
  {
    id: "rolMalo", etiqueta: "token con rol invitado", rol: "invitado", roto: false, espera: 403,
    freno: "autorización — pasa autenticación, falla el rol",
  },
  {
    id: "invalido", etiqueta: "analista + age: 150", rol: "analista", roto: true, espera: 422,
    freno: "validación — pasa autenticación y rol, falla el contrato",
  },
  {
    id: "conToken", etiqueta: "analista + paciente válido", rol: "analista", roto: false, espera: 200,
    freno: "pasa los tres",
  },
]

const seguro = ref({})
const rafaga = ref(null)
const auditoria = ref(null)
const rechazoAuditoria = ref(null)
const esperandoSeguro = ref({})

function codigo(respuesta) {
  return respuesta.ok ? 200 : Number(String(respuesta.status).replace(/\D/g, "")) || 0
}

async function emitirToken(rol, usuario = "antonella") {
  return await $fetch("/api/token", { method: "POST", body: { rol, usuario } })
}

async function predecirSeguro(jwt, paciente) {
  const empezo = performance.now()
  try {
    const resultado = await $fetch(`${apiPublica}/v1/secure/predict`, {
      method: "POST",
      headers: jwt ? { Authorization: `Bearer ${jwt}` } : {},
      body: paciente,
    })
    return { ok: true, ms: performance.now() - empezo, resultado }
  } catch (error) {
    return {
      ok: false,
      ms: performance.now() - empezo,
      status: `HTTP ${error.status ?? 0}`,
      detalle: detalleHttp(error),
    }
  }
}

async function probar(caso) {
  esperandoSeguro.value = { ...esperandoSeguro.value, [caso.id]: true }
  try {
    const emitido = caso.rol ? await emitirToken(caso.rol) : null
    const paciente = (caso.roto ? INVALIDO : PACIENTES[0]).datos
    seguro.value = {
      ...seguro.value,
      [caso.id]: await predecirSeguro(emitido?.token, paciente),
    }
  } finally {
    esperandoSeguro.value = { ...esperandoSeguro.value, [caso.id]: false }
  }
}

async function correrTodos() {
  for (const caso of CASOS) await probar(caso)
}

async function golpear() {
  esperandoSeguro.value = { ...esperandoSeguro.value, rafaga: true }
  rafaga.value = null
  try {
    const emitido = await emitirToken("analista", "rafaga")

    const codigos = []
    for (let intento = 0; intento < 6; intento++) {
      codigos.push(codigo(await predecirSeguro(emitido.token, PACIENTES[0].datos)))
    }
    rafaga.value = codigos
  } finally {
    esperandoSeguro.value = { ...esperandoSeguro.value, rafaga: false }
  }
}

async function verAuditoria(rol) {
  const emitido = await emitirToken(rol, "auditoria")
  try {
    auditoria.value = await $fetch(`${apiPublica}/v1/secure/auditoria`, {
      headers: { Authorization: `Bearer ${emitido.token}` },
    })
    rechazoAuditoria.value = null
  } catch (error) {
    auditoria.value = null
    rechazoAuditoria.value = {
      rol,
      status: `HTTP ${error.status ?? 0}`,
      mensaje: error.data?.detail ?? String(error),
    }
  }
}

watch(elegido, () => { resultados.value = {} })

onMounted(async () => {
  try {
    modelo.value = await $fetch("/api/health")
  } catch {
    modelo.value = null
  }
  try {
    desdeLaMaquina.value = await $fetch("/medicion.json")
  } catch {
    desdeLaMaquina.value = null
  }
})
</script>

<template>
  <main>
    <svg class="sprite" aria-hidden="true">
      <symbol id="i-prediccion" viewBox="0 0 20 20"><polygon points="6 4 17 10 6 16" /></symbol>
      <symbol id="i-latencia" viewBox="0 0 20 20"><circle cx="10" cy="10.6" r="6.8" /><polyline points="10 6.8 10 10.6 12.8 12.2" /><line x1="7.6" y1="2.2" x2="12.4" y2="2.2" /></symbol>
      <symbol id="i-lote" viewBox="0 0 20 20"><rect x="2.8" y="3.6" width="14.4" height="12.8" rx="1.8" /><line x1="2.8" y1="8" x2="17.2" y2="8" /><line x1="2.8" y1="12" x2="17.2" y2="12" /></symbol>
      <symbol id="i-seguridad" viewBox="0 0 20 20"><rect x="4.2" y="8.8" width="11.6" height="8.4" rx="1.8" /><path d="M7 8.8V6.6a3 3 0 0 1 6 0v2.2" /></symbol>
    </svg>

    <header>
      <div>
        <h1>Predictor de ACV</h1>
      </div>
      <div v-if="modelo" class="chapa">
        <span>champion</span>
        <b>v{{ modelo.salud.version_modelo }}</b>
        <span>umbral {{ modelo.salud.umbral }}</span>
      </div>
    </header>

    <div class="cuerpo" :class="{ plegada: !barraAbierta }">
      <aside class="lateral">
        <button
          class="tirador"
          :title="barraAbierta ? 'Ocultar el menú' : 'Mostrar el menú'"
          @click="barraAbierta = !barraAbierta"
        >☰</button>
        <nav>
          <button
            v-for="opcion in SECCIONES"
            :key="opcion.id"
            :class="{ activo: opcion.id === seccion }"
            :title="opcion.nombre"
            @click="seccion = opcion.id"
          >
            <svg class="icono" aria-hidden="true"><use :href="'#i-' + opcion.id" /></svg>
            <span class="rotulo">
              <b>{{ opcion.nombre }}</b>
              <span>{{ opcion.nota }}</span>
            </span>
          </button>
        </nav>
      </aside>

      <div class="contenido">
    <div v-if="seccion === 'prediccion'" class="columnas">
      <section class="panel">
        <h2>Paciente</h2>
        <div class="tabs">
          <button
            v-for="(caso, indice) in PACIENTES"
            :key="caso.nombre"
            :class="{ activo: indice === elegido }"
            @click="elegido = indice"
          >{{ caso.nombre }}</button>
        </div>
        <p class="detalle">{{ paciente.detalle }}</p>

        <dl>
          <template v-for="(valor, campo) in paciente.datos" :key="campo">
            <dt>{{ campo }}</dt>
            <dd :class="{ nulo: valor === null }">{{ valor === null ? "— (se imputa)" : valor }}</dd>
          </template>
        </dl>

        <button class="ancho" @click="predecirTodos">predecir por los tres</button>

        <p v-if="coinciden !== null" class="coinciden">
          los tres coinciden<br><b>{{ coinciden }}</b>
        </p>
      </section>

      <div class="protocolos">
        <section v-for="protocolo in PROTOCOLOS" :key="protocolo.id" class="panel">
          <div class="cabeza">
            <div>
              <h2>{{ protocolo.nombre }}</h2>
              <p class="detalle">{{ protocolo.nota }}</p>
            </div>
            <button :disabled="esperando[protocolo.id]" @click="predecir(protocolo.id)">
              {{ esperando[protocolo.id] ? "…" : "predecir" }}
            </button>
          </div>

          <template v-if="resultados[protocolo.id]">
            <div v-if="resultados[protocolo.id].ok" class="salida">
              <p class="veredicto" :class="{ riesgo: resultados[protocolo.id].resultado.prediccion === 1 }">
                {{ resultados[protocolo.id].resultado.descripcion }}
              </p>
              <dl>
                <dt>probabilidad</dt>
                <dd class="prob">{{ resultados[protocolo.id].resultado.probabilidad }}</dd>
                <dt>versión</dt>
                <dd>v{{ resultados[protocolo.id].resultado.version_modelo }}</dd>
              </dl>
            </div>

            <div v-else class="salida rechazo">
              <p class="veredicto">rechazado · {{ resultados[protocolo.id].status }}</p>
              <ul>
                <li v-for="problema in resultados[protocolo.id].detalle" :key="problema.campo">
                  <code>{{ problema.campo }}</code> {{ problema.mensaje }}
                </li>
              </ul>
              <p
                v-for="aviso in resultados[protocolo.id].imposibles"
                :key="aviso"
                class="nota imposible"
              >{{ aviso }}</p>
              <p class="nota">{{ protocolo.rechazo }}</p>
            </div>
          </template>
        </section>
      </div>
    </div>

    <section v-if="seccion === 'latencia'" class="panel ancha">
      <h2>Latencia de los tres</h2>
      <p class="detalle">
        La mide <code>comparar.py</code> desde la máquina, contra <code>localhost</code>:
        un bloque de llamadas por protocolo y el promedio por llamada, descartando la
        primera de cada bloque.
      </p>

      <template v-if="desdeLaMaquina">
        <table class="barras">
          <thead>
            <tr><th>protocolo</th><th>ms por llamada</th><th>contra gRPC</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="medicion in desdeLaMaquina.resumen" :key="medicion.id">
              <td><b>{{ medicion.id }}</b></td>
              <td>{{ medicion.ms.toFixed(3) }} ms</td>
              <td>{{ medicion.veces.toFixed(2) }}×</td>
              <td class="pista">
                <span class="barra" :style="{ width: (medicion.ms / peorDelScript * 100) + '%' }"></span>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="nota">
          {{ desdeLaMaquina.vueltas }} llamadas por protocolo, el
          {{ desdeLaMaquina.fecha.slice(8, 10) }}/{{ desdeLaMaquina.fecha.slice(5, 7) }} a las
          {{ desdeLaMaquina.fecha.slice(11, 16) }}. Los tres devolvieron
          {{ desdeLaMaquina.coinciden ? "la misma probabilidad" : "probabilidades distintas" }}.
        </p>
      </template>

      <p v-else class="nota">
        Todavía no se corrió <code>python comparar.py</code>.
      </p>
    </section>

    <section v-if="seccion === 'lote'" class="panel ancha">
      <h2>Un lote por server-streaming · gRPC</h2>
      <p class="detalle">
        El <code>.proto</code> tiene un segundo método, <code>PredecirLote</code>, que
        devuelve <code>stream Prediccion</code>: las respuestas salen de a una mientras el
        servidor las calcula, sin esperar a que termine el lote.
      </p>

      <button :disabled="enviandoLote" @click="enviarLote">
        {{ enviandoLote ? "enviando…" : "enviar los 3 pacientes válidos" }}
      </button>

      <table v-if="lote && lote.llegadas && lote.llegadas.length" class="barras">
        <thead><tr><th>#</th><th>probabilidad</th><th>llegó a los</th><th></th></tr></thead>
        <tbody>
          <tr v-for="(llegada, indice) in lote.llegadas" :key="indice">
            <td><b>{{ indice + 1 }}</b></td>
            <td class="prob">{{ llegada.probabilidad }}</td>
            <td>{{ llegada.ms.toFixed(1) }} ms</td>
            <td class="pista">
              <span class="barra" :style="{ width: (llegada.ms / lote.ms * 100) + '%' }"></span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
    <section v-if="seccion === 'seguridad'" class="panel ancha">
      <h2>Seguridad · el endpoint protegido</h2>
      <p class="detalle">
        <code>POST /v1/secure/predict</code> — el mismo modelo detrás de un token con rol,
        un límite de 5 consultas por minuto y auditoría de cada predicción.
        <code>/v1/predict</code> queda abierto y sin tocar.
      </p>

      <div class="controles">
        <button @click="correrTodos">correr los cuatro controles</button>
      </div>

      <table class="barras">
        <tbody>
          <tr v-for="caso in CASOS" :key="caso.id">
            <td>
              <button :disabled="esperandoSeguro[caso.id]" @click="probar(caso)">probar</button>
            </td>
            <td>{{ caso.etiqueta }}</td>
            <td v-if="seguro[caso.id]">
              <span class="codigo" :class="{ mal: codigo(seguro[caso.id]) >= 400 }">
                {{ codigo(seguro[caso.id]) }}
              </span>
            </td>
            <td v-else class="gris">espera {{ caso.espera }}</td>
            <td>
              <template v-if="seguro[caso.id]">
                <span v-if="seguro[caso.id].ok" class="prob">
                  {{ seguro[caso.id].resultado.probabilidad }}
                  &nbsp;v{{ seguro[caso.id].resultado.version_modelo }}
                </span>
                <span v-else>
                  {{ seguro[caso.id].detalle
                       .map((problema) => (problema.campo ? problema.campo + ": " : "") + problema.mensaje)
                       .join(" · ") }}
                </span>
              </template>
            </td>
            <td class="gris">{{ caso.freno }}</td>
          </tr>

          <tr>
            <td>
              <button :disabled="esperandoSeguro.rafaga" @click="golpear">probar</button>
            </td>
            <td>analista, 6 en un minuto</td>
            <td v-if="rafaga">
              <span class="codigo mal">429</span>
            </td>
            <td v-else class="gris">espera 429</td>
            <td>
              <span
                v-for="(codigoHttp, indice) in rafaga"
                :key="indice"
                class="codigo"
                :class="{ mal: codigoHttp >= 400 }"
              >{{ codigoHttp }}</span>
            </td>
            <td class="gris">límite de tasa — pasa los tres, pero no tantas veces</td>
          </tr>
        </tbody>
      </table>

      <h3 style="margin:1.8rem 0 .5rem; font-size:1rem">Auditoría</h3>
      <div class="controles">
        <button @click="verAuditoria('admin')">leer como admin</button>
        <button @click="verAuditoria('analista')">leer como analista</button>
      </div>

      <p v-if="rechazoAuditoria" class="nota">
        rol <code>{{ rechazoAuditoria.rol }}</code> ·
        <span class="codigo mal">{{ rechazoAuditoria.status }}</span>
        {{ rechazoAuditoria.mensaje }}
      </p>

      <table v-if="auditoria?.length" class="barras">
        <thead><tr><th>hora</th><th>usuario</th><th>huella de la consulta</th><th>pred</th><th>modelo</th></tr></thead>
        <tbody>
          <tr v-for="(registro, indice) in auditoria" :key="indice">
            <td>{{ registro.ts.slice(11, 19) }}</td>
            <td>{{ registro.usuario }}</td>
            <td><code>{{ registro.hash_entrada.slice(0, 16) }}…</code></td>
            <td>{{ registro.prediccion }}</td>
            <td>v{{ registro.version_modelo }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="auditoria" class="nota">
        se guarda la huella de la consulta, no los datos del paciente
      </p>
    </section>
      </div>
    </div>
  </main>
</template>

<style>
:root {
  --fondo: #11151c;
  --panel: #1a212b;
  --borde: #2b3545;
  --texto: #e6edf6;
  --gris: #8b9bb0;
  --acento: #5eb0ff;
  --riesgo: #ffb454;
  --mal: #ff8585;
  --bien: #5ee6a8;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  height: 100vh;
  overflow: hidden;
  background: var(--fondo);
  color: var(--texto);
  font: 16px/1.5 system-ui, sans-serif;
}

main { height: 100vh; display: grid; grid-template-rows: auto 1fr; }

.cuerpo {
  display: grid; grid-template-columns: 230px 1fr; min-height: 0;
  transition: grid-template-columns .22s ease;
}
.cuerpo.plegada { grid-template-columns: 3.9rem 1fr; }

.contenido { overflow-y: auto; min-height: 0; padding: 1.3rem 1.5rem 4rem; }
.contenido > * { max-width: 1240px; }

.lateral {
  display: grid; gap: .5rem; align-content: start;
  overflow: hidden auto; min-height: 0;
  padding: 1.3rem .9rem;
  border-right: 1px solid var(--borde);
  transition: padding .22s ease;
}
.sprite { position: absolute; width: 0; height: 0; overflow: hidden; }
.lateral nav { display: grid; gap: .4rem; }
.tirador {
  justify-self: start; width: 2.4rem; padding: .4rem 0;
  background: transparent; border: 1px solid var(--borde);
  color: var(--gris); font-weight: 400; font-size: 1.05rem; line-height: 1;
}
.tirador:hover { color: var(--texto); border-color: var(--acento); }

.cuerpo.plegada .lateral { padding: 1.3rem .7rem; }
.cuerpo.plegada .lateral nav button { padding: .6rem; }
.cuerpo.plegada .rotulo { opacity: 0; }

.lateral nav button {
  display: flex; align-items: center; gap: .6rem; overflow: hidden;
  text-align: left; padding: .6rem .8rem; font-weight: 400;
  background: var(--panel); border: 1px solid var(--borde); color: var(--texto);
  transition: padding .22s ease;
}
.icono {
  width: 1.15rem; height: 1.15rem; flex: none;
  fill: none; stroke: currentColor; stroke-width: 1.6;
  stroke-linecap: round; stroke-linejoin: round;
}
.rotulo { display: grid; gap: .1rem; min-width: 0; transition: opacity .18s ease; }
.lateral nav button b { font-weight: 600; font-size: .95rem; }
.lateral nav button .rotulo span { color: var(--gris); font-size: .78rem; }
.lateral nav button.activo { border-color: var(--acento); background: #15304c; color: var(--acento); }

header {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 1rem; flex-wrap: wrap;
  padding: 1.1rem 1.5rem;
  border-bottom: 1px solid var(--borde);
}
h1 { margin: 0; font-size: 2rem; }
.sub { margin: .3rem 0 0; color: var(--gris); }

.chapa {
  display: flex; align-items: center; gap: .6rem;
  background: var(--panel); border: 1px solid var(--borde); border-radius: 999px;
  padding: .45rem 1rem; color: var(--gris); font-size: .9rem; white-space: nowrap;
}
.chapa b { color: var(--acento); font-size: 1.05rem; }

.columnas { display: grid; grid-template-columns: 340px 1fr; gap: 1.1rem; align-items: start; }
.protocolos { display: grid; gap: 1.1rem; }

.panel { background: var(--panel); border: 1px solid var(--borde); border-radius: 10px; padding: 1.1rem 1.3rem; }
.panel h2 { margin: 0 0 .3rem; font-size: 1.12rem; color: var(--acento); }
.panel h3 { margin: 0 0 .6rem; font-size: .9rem; color: var(--gris); text-transform: uppercase; letter-spacing: .05em; }

.cabeza { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.detalle { margin: 0 0 1rem; color: var(--gris); font-size: .9rem; }

.tabs { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: .8rem; }
.tabs button { background: transparent; border: 1px solid var(--borde); color: var(--gris); font-weight: 400; }
.tabs button.activo { border-color: var(--acento); color: var(--acento); background: #15304c; }

dl { display: grid; grid-template-columns: auto 1fr; gap: .3rem 1rem; margin: 0; }
dt { color: var(--gris); font-size: .9rem; }
dd { margin: 0; font-variant-numeric: tabular-nums; }
dd.nulo { color: var(--gris); font-style: italic; }

.salida { margin-top: 1rem; border-top: 1px solid var(--borde); padding-top: 1rem; }
.veredicto { margin: 0 0 .7rem; font-size: 1.1rem; font-weight: 600; }
.veredicto.riesgo { color: var(--riesgo); }
.rechazo .veredicto { color: var(--mal); }
.rechazo ul { margin: 0 0 .7rem; padding-left: 1.2rem; }
.rechazo code { color: var(--mal); }
.nota { margin: .3rem 0 0; color: var(--gris); font-size: .86rem; }
.nota.imposible { color: var(--riesgo); }

.prob { color: var(--acento); font-variant-numeric: tabular-nums; }

.coinciden {
  margin: 1rem 0 0; padding: .8rem; text-align: center;
  background: #14301f; border: 1px solid #2f6b4a; border-radius: 8px;
  color: var(--bien); font-size: .9rem;
}
.coinciden b { display: inline-block; margin-top: .3rem; font-size: 1.05rem; }

.controles { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.controles input {
  width: 5rem; background: #0d1218; border: 1px solid var(--borde); color: var(--texto);
  border-radius: 6px; padding: .45rem .6rem; font: inherit;
}

table.barras { width: 100%; border-collapse: collapse; margin-top: 1.1rem; font-variant-numeric: tabular-nums; }
table.barras th { text-align: left; color: var(--gris); font-weight: 400; font-size: .85rem; padding: 0 .8rem .5rem 0; }
table.barras td { padding: .4rem .8rem .4rem 0; border-top: 1px solid var(--borde); }
.pista { width: 45%; }
.barra { display: block; height: 10px; border-radius: 999px; background: var(--acento); min-width: 2px; }

button {
  background: var(--acento); color: #09111d; border: 0; border-radius: 6px;
  padding: .5rem 1rem; font: inherit; font-weight: 600; cursor: pointer; white-space: nowrap;
}
button:disabled { opacity: .5; cursor: default; }
button.ancho { width: 100%; margin-top: 1.1rem; }

.codigo {
  display: inline-block; min-width: 2.6rem; margin-right: .3rem; padding: .1rem .45rem;
  border-radius: 5px; background: #14301f; color: var(--bien);
  font-variant-numeric: tabular-nums; font-size: .88rem; text-align: center;
}
.codigo.mal { background: #3a1a1e; color: var(--mal); }
.gris { color: var(--gris); font-size: .88rem; }

@media (prefers-reduced-motion: reduce) {
  .cuerpo, .lateral, .lateral nav button, .rotulo { transition: none; }
}

@media (max-width: 1100px) {
  body, main { height: auto; overflow: visible; }
  .cuerpo, .cuerpo.plegada, .columnas { grid-template-columns: 1fr; }
  .lateral, .cuerpo.plegada .lateral { border-right: 0; border-bottom: 1px solid var(--borde); overflow: visible; padding: 1.3rem .9rem; }
  .cuerpo.plegada .rotulo { opacity: 1; }
  .cuerpo.plegada .lateral nav button { padding: .6rem .8rem; }
  .contenido { overflow: visible; }
}
</style>
