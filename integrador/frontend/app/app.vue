<script setup>
import { PACIENTES } from "./pacientes"

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
    nota: "mutation predecir · Strawberry, en el mismo proceso que REST",
    rechazo: "responde HTTP 200 y pone el rechazo en errors[] — así funciona GraphQL",
  },
  {
    id: "grpc",
    nombre: "gRPC",
    nota: "rpc Predecir · Protocol Buffers sobre HTTP/2, servicio aparte",
    rechazo: "corta con INVALID_ARGUMENT, y los enum del .proto ni dejan enviar un valor inventado",
  },
]

const CAMPOS_META = ["name", "version", "auc", "accuracy", "f1", "precision", "recall"]

const elegido = ref(0)
const paciente = computed(() => PACIENTES[elegido.value])

const modelo = ref(null)
const resultados = ref({})
const esperando = ref({})

// Las tres probabilidades tienen que ser el mismo número: es un modelo, no tres.
const coinciden = computed(() => {
  const listos = PROTOCOLOS.map((p) => resultados.value[p.id]).filter((r) => r?.ok)
  if (listos.length < PROTOCOLOS.length) return null
  const probabilidades = new Set(listos.map((r) => r.resultado.probabilidad))
  return probabilidades.size === 1 ? listos[0].resultado.probabilidad : null
})

async function predecir(id) {
  esperando.value = { ...esperando.value, [id]: true }
  try {
    const r = await $fetch(`/api/${id}/predecir`, {
      method: "POST",
      body: { paciente: paciente.value.datos },
    })
    resultados.value = { ...resultados.value, [id]: r }
  } catch (e) {
    resultados.value = {
      ...resultados.value,
      [id]: { ok: false, ms: 0, status: "error", detalle: [{ campo: "", mensaje: String(e) }] },
    }
  } finally {
    esperando.value = { ...esperando.value, [id]: false }
  }
}

async function predecirTodos() {
  for (const p of PROTOCOLOS) await predecir(p.id)
}

const campos = ref(["version", "f1"])
const meta = ref(null)
const midiendoMeta = ref(false)

async function compararMetadata() {
  if (!campos.value.length) return
  midiendoMeta.value = true
  try {
    meta.value = await $fetch("/api/metadata", { method: "POST", body: { campos: campos.value } })
  } finally {
    midiendoMeta.value = false
  }
}

const vueltas = ref(200)   // el mismo n que el notebook: con menos, el numero baila
const carrera = ref(null)
const corriendo = ref(false)

async function correrCarrera() {
  corriendo.value = true
  carrera.value = null
  try {
    carrera.value = await $fetch("/api/carrera", {
      method: "POST",
      body: { n: vueltas.value, paciente: paciente.value.datos },
    })
  } finally {
    corriendo.value = false
  }
}

const peor = computed(() =>
  carrera.value ? Math.max(...carrera.value.resumen.map((r) => r.ms)) : 1,
)

const lote = ref(null)
const enviandoLote = ref(false)

async function enviarLote() {
  enviandoLote.value = true
  lote.value = null
  try {
    // Solo los válidos: el inválido cortaría el stream a mitad de camino.
    const pacientes = PACIENTES.slice(0, 3).map((p) => p.datos)
    lote.value = await $fetch("/api/lote", { method: "POST", body: { pacientes } })
  } finally {
    enviandoLote.value = false
  }
}

const SECCIONES = [
  { id: "prediccion", nombre: "Predicción", nota: "REST · GraphQL · gRPC" },
  { id: "metadata", nombre: "Metadata", nota: "REST contra GraphQL" },
  { id: "latencia", nombre: "Latencia", nota: "los tres, 200 veces" },
  { id: "lote", nombre: "Lote", nota: "server-streaming, solo gRPC" },
  { id: "seguridad", nombre: "Seguridad", nota: "token, límite y auditoría" },
]

const seccion = ref("prediccion")
const barraAbierta = ref(true)

const ROLES = ["analista", "admin", "invitado"]

// Cada caso es un control distinto. "elegido" usa el rol de los botones de arriba.
const CASOS = [
  { id: "sinToken", etiqueta: "sin token", espera: 401, rol: null, roto: false },
  { id: "rolMalo", etiqueta: "rol invitado", espera: 403, rol: "invitado", roto: false },
  { id: "invalido", etiqueta: "age: 150", espera: 422, rol: "elegido", roto: true },
  { id: "conToken", etiqueta: "con token", espera: 200, rol: "elegido", roto: false },
]

const rolElegido = ref("analista")
const token = ref(null)
const seguro = ref({})
const rafaga = ref(null)
const auditoria = ref(null)
const esperandoSeguro = ref({})

function codigo(r) {
  return r.ok ? 200 : Number(String(r.status).replace(/\D/g, "")) || 0
}

async function pedirToken() {
  token.value = await $fetch("/api/token", { method: "POST", body: { rol: rolElegido.value } })
}

async function probar(caso) {
  esperandoSeguro.value = { ...esperandoSeguro.value, [caso.id]: true }
  try {
    const r = await $fetch("/api/secure", {
      method: "POST",
      body: {
        rol: caso.rol === "elegido" ? rolElegido.value : caso.rol,
        paciente: (caso.roto ? PACIENTES[3] : PACIENTES[0]).datos,
      },
    })
    seguro.value = { ...seguro.value, [caso.id]: r }
  } finally {
    esperandoSeguro.value = { ...esperandoSeguro.value, [caso.id]: false }
  }
}

async function golpear() {
  esperandoSeguro.value = { ...esperandoSeguro.value, rafaga: true }
  rafaga.value = null
  try {
    const codigos = []
    for (let i = 0; i < 6; i++) {
      // Usuario aparte: el limite es por usuario, asi la rafaga no consume el de los otros casos.
      const r = await $fetch("/api/secure", {
        method: "POST",
        body: { rol: rolElegido.value, usuario: "rafaga", paciente: PACIENTES[0].datos },
      })
      codigos.push(codigo(r))
    }
    rafaga.value = codigos
  } finally {
    esperandoSeguro.value = { ...esperandoSeguro.value, rafaga: false }
  }
}

async function verAuditoria() {
  auditoria.value = await $fetch("/api/auditoria")
}

watch(elegido, () => { resultados.value = {} })

onMounted(async () => {
  try {
    modelo.value = await $fetch("/api/health")
  } catch (e) {
    modelo.value = null
  }
})
</script>

<template>
  <main>
    <svg class="sprite" aria-hidden="true">
      <symbol id="i-prediccion" viewBox="0 0 20 20"><polygon points="6 4 17 10 6 16" /></symbol>
      <symbol id="i-metadata" viewBox="0 0 20 20"><circle cx="10" cy="10" r="7.2" /><line x1="10" y1="9" x2="10" y2="14" /><line x1="10" y1="6.2" x2="10" y2="6.3" /></symbol>
      <symbol id="i-latencia" viewBox="0 0 20 20"><circle cx="10" cy="10.6" r="6.8" /><polyline points="10 6.8 10 10.6 12.8 12.2" /><line x1="7.6" y1="2.2" x2="12.4" y2="2.2" /></symbol>
      <symbol id="i-lote" viewBox="0 0 20 20"><rect x="2.8" y="3.6" width="14.4" height="12.8" rx="1.8" /><line x1="2.8" y1="8" x2="17.2" y2="8" /><line x1="2.8" y1="12" x2="17.2" y2="12" /></symbol>
      <symbol id="i-seguridad" viewBox="0 0 20 20"><rect x="4.2" y="8.8" width="11.6" height="8.4" rx="1.8" /><path d="M7 8.8V6.6a3 3 0 0 1 6 0v2.2" /></symbol>
    </svg>

    <header>
      <div>
        <h1>Predictor de ACV</h1>
        <p class="sub">Un modelo, cuatro protocolos — cliente de prueba de la plataforma</p>
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
            v-for="s in SECCIONES"
            :key="s.id"
            :class="{ activo: s.id === seccion }"
            :title="s.nombre"
            @click="seccion = s.id"
          >
            <svg class="icono" aria-hidden="true"><use :href="'#i-' + s.id" /></svg>
            <span class="rotulo">
              <b>{{ s.nombre }}</b>
              <span>{{ s.nota }}</span>
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
            v-for="(p, i) in PACIENTES"
            :key="p.nombre"
            :class="{ activo: i === elegido }"
            @click="elegido = i"
          >{{ p.nombre }}</button>
        </div>
        <p class="detalle">{{ paciente.detalle }}</p>

        <dl>
          <template v-for="(v, k) in paciente.datos" :key="k">
            <dt>{{ k }}</dt>
            <dd :class="{ nulo: v === null }">{{ v === null ? "— (se imputa)" : v }}</dd>
          </template>
        </dl>

        <button class="ancho" @click="predecirTodos">predecir por los tres</button>

        <p v-if="coinciden !== null" class="coinciden">
          los tres coinciden<br><b>{{ coinciden }}</b>
        </p>
      </section>

      <div class="protocolos">
        <section v-for="p in PROTOCOLOS" :key="p.id" class="panel">
          <div class="cabeza">
            <div>
              <h2>{{ p.nombre }}</h2>
              <p class="detalle">{{ p.nota }}</p>
            </div>
            <button :disabled="esperando[p.id]" @click="predecir(p.id)">
              {{ esperando[p.id] ? "…" : "predecir" }}
            </button>
          </div>

          <template v-if="resultados[p.id]">
            <div v-if="resultados[p.id].ok" class="salida">
              <p class="veredicto" :class="{ riesgo: resultados[p.id].resultado.prediccion === 1 }">
                {{ resultados[p.id].resultado.descripcion }}
              </p>
              <dl>
                <dt>probabilidad</dt>
                <dd class="prob">{{ resultados[p.id].resultado.probabilidad }}</dd>
                <dt>versión</dt>
                <dd>v{{ resultados[p.id].resultado.version_modelo }}</dd>
              </dl>
            </div>

            <div v-else class="salida rechazo">
              <p class="veredicto">rechazado · {{ resultados[p.id].status }}</p>
              <ul>
                <li v-for="d in resultados[p.id].detalle" :key="d.campo">
                  <code>{{ d.campo }}</code> {{ d.mensaje }}
                </li>
              </ul>
              <p v-for="i in resultados[p.id].imposibles" :key="i" class="nota imposible">{{ i }}</p>
              <p class="nota">{{ p.rechazo }} · {{ resultados[p.id].ms.toFixed(1) }} ms</p>
            </div>
          </template>
        </section>
      </div>
    </div>

    <section v-if="seccion === 'metadata'" class="panel ancha">
      <h2>Leer la metadata del modelo · REST contra GraphQL</h2>
      <p class="detalle">
        La misma lectura por los dos protocolos. Elegí qué campos querés: REST manda todo
        lo que tiene el endpoint, y suma una llamada si además pedís métricas. Solo están
        los campos que los dos pueden dar, para que la comparación sea pareja.
      </p>

      <div class="casillas">
        <label v-for="c in CAMPOS_META" :key="c">
          <input v-model="campos" type="checkbox" :value="c"> {{ c }}
        </label>
      </div>

      <button :disabled="midiendoMeta || !campos.length" @click="compararMetadata">
        {{ midiendoMeta ? "midiendo…" : "comparar" }}
      </button>

      <div v-if="meta" class="duelo">
        <div v-for="(d, nombre) in meta" :key="nombre" class="tarjeta">
          <h3>{{ nombre }}</h3>
          <dl>
            <dt>llamadas</dt><dd>{{ d.llamadas }}</dd>
            <dt>bytes</dt><dd>{{ d.bytes }}</dd>
            <dt>tiempo</dt><dd>{{ d.ms.toFixed(1) }} ms</dd>
          </dl>
          <pre v-if="d.query">{{ d.query }}</pre>
          <pre v-else>{{ d.llamadas > 1 ? "GET /v1/model\nGET /v1/model/metrics" : "GET /v1/model" }}</pre>
        </div>
      </div>
      <p v-if="meta" class="nota">
        los dos devolvieron exactamente lo mismo:
        <code>{{ Object.keys(meta.graphql.datos).join(", ") }}</code>
      </p>
    </section>

    <section v-if="seccion === 'latencia'" class="panel ancha">
      <h2>Latencia de los tres · la misma predicción, {{ vueltas }} veces cada uno</h2>
      <p class="detalle">
        Medido como en el mini-TP 3: las {{ vueltas }} llamadas de un protocolo seguidas, y
        el promedio por llamada. La primera de cada bloque no se cuenta, porque paga el
        arranque (GraphQL arma el esquema, gRPC abre el canal). Paciente:
        <b>{{ paciente.nombre }}</b>.
      </p>

      <div class="controles">
        <label>vueltas <input v-model.number="vueltas" type="number" min="5" max="200" step="5"></label>
        <button :disabled="corriendo" @click="correrCarrera">
          {{ corriendo ? "corriendo…" : "correr" }}
        </button>
      </div>

      <table v-if="carrera" class="barras">
        <thead>
          <tr><th>protocolo</th><th>ms por llamada</th><th>contra gRPC</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="r in carrera.resumen" :key="r.id">
            <td><b>{{ r.id }}</b></td>
            <td>{{ r.ms.toFixed(3) }} ms</td>
            <td>{{ r.veces.toFixed(2) }}×</td>
            <td class="pista">
              <span class="barra" :style="{ width: (r.ms / peor * 100) + '%' }"></span>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="carrera" class="nota">
        {{ carrera.vueltas }} vueltas × 3 protocolos en {{ (carrera.total / 1000).toFixed(1) }} s
      </p>
    </section>

    <section v-if="seccion === 'lote'" class="panel ancha">
      <h2>Un lote por server-streaming · solo gRPC</h2>
      <p class="detalle">
        El <code>.proto</code> tiene un segundo método, <code>PredecirLote</code>, que
        devuelve <code>stream Prediccion</code>: las respuestas salen de a una mientras el
        servidor las calcula, sin esperar a que termine el lote. Ni REST ni GraphQL hacen esto.
      </p>

      <button :disabled="enviandoLote" @click="enviarLote">
        {{ enviandoLote ? "enviando…" : "enviar los 3 pacientes válidos" }}
      </button>

      <table v-if="lote && lote.llegadas && lote.llegadas.length" class="barras">
        <thead><tr><th>#</th><th>probabilidad</th><th>llegó a los</th><th></th></tr></thead>
        <tbody>
          <tr v-for="(l, i) in lote.llegadas" :key="i">
            <td><b>{{ i + 1 }}</b></td>
            <td class="prob">{{ l.probabilidad }}</td>
            <td>{{ l.ms.toFixed(1) }} ms</td>
            <td class="pista">
              <span class="barra" :style="{ width: (l.ms / lote.ms * 100) + '%' }"></span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
    <section v-if="seccion === 'seguridad'" class="panel ancha">
      <h2>Seguridad · la puerta protegida</h2>
      <p class="detalle">
        <code>POST /v1/secure/predict</code> — el mismo modelo detrás de un token con rol,
        un límite de 5 consultas por minuto y auditoría de cada predicción.
        <code>/v1/predict</code> queda abierto y sin tocar.
      </p>

      <div class="controles">
        <div class="tabs">
          <button
            v-for="r in ROLES"
            :key="r"
            :class="{ activo: r === rolElegido }"
            @click="rolElegido = r"
          >{{ r }}</button>
        </div>
        <button @click="pedirToken">pedir token</button>
      </div>

      <p v-if="token" class="token">
        <code>{{ token.token.slice(0, 44) }}…</code>
        <span>vence en {{ token.expira_en / 60 }} min</span>
      </p>

      <table class="barras">
        <tbody>
          <tr v-for="c in CASOS" :key="c.id">
            <td>
              <button :disabled="esperandoSeguro[c.id]" @click="probar(c)">probar</button>
            </td>
            <td>{{ c.etiqueta }}</td>
            <td v-if="seguro[c.id]">
              <span class="codigo" :class="{ mal: codigo(seguro[c.id]) >= 400 }">
                {{ codigo(seguro[c.id]) }}
              </span>
            </td>
            <td v-else class="gris">espera {{ c.espera }}</td>
            <td>
              <template v-if="seguro[c.id]">
                <span v-if="seguro[c.id].ok" class="prob">
                  {{ seguro[c.id].resultado.probabilidad }}
                  &nbsp;v{{ seguro[c.id].resultado.version_modelo }}
                </span>
                <span v-else>
                  {{ seguro[c.id].detalle.map((d) => (d.campo ? d.campo + ": " : "") + d.mensaje).join(" · ") }}
                </span>
              </template>
            </td>
          </tr>

          <tr>
            <td>
              <button :disabled="esperandoSeguro.rafaga" @click="golpear">probar</button>
            </td>
            <td>6 en un minuto</td>
            <td v-if="rafaga">
              <span class="codigo mal">429</span>
            </td>
            <td v-else class="gris">espera 429</td>
            <td>
              <span v-for="(c, i) in rafaga" :key="i" class="codigo" :class="{ mal: c >= 400 }">
                {{ c }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="controles" style="margin-top:1.1rem">
        <button @click="verAuditoria">ver la auditoría</button>
        <span class="detalle" style="margin:0">solo el rol <code>admin</code> puede leerla</span>
      </div>

      <table v-if="auditoria?.length" class="barras">
        <thead><tr><th>hora</th><th>usuario</th><th>huella de la consulta</th><th>pred</th><th>modelo</th></tr></thead>
        <tbody>
          <tr v-for="(a, i) in auditoria" :key="i">
            <td>{{ a.ts.slice(11, 19) }}</td>
            <td>{{ a.usuario }}</td>
            <td><code>{{ a.hash_entrada.slice(0, 16) }}…</code></td>
            <td>{{ a.prediccion }}</td>
            <td>v{{ a.version_modelo }}</td>
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

/* El encabezado y la lateral quedan fijos; el scroll vive adentro del contenido. */
main { height: 100vh; display: grid; grid-template-rows: auto 1fr; }

.cuerpo {
  display: grid; grid-template-columns: 230px 1fr; min-height: 0;
  /* El navegador interpola grid-template-columns, asi que el plegado no salta. */
  transition: grid-template-columns .22s ease;
}
.cuerpo.plegada { grid-template-columns: 3.9rem 1fr; }

.contenido { overflow-y: auto; min-height: 0; padding: 1.3rem 1.5rem 4rem; }
/* Para que en una pantalla muy ancha el contenido no se estire de punta a punta. */
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
/* Mismo boton y mismo lugar este abierta o plegada: solo cambia lo que abre. */
.tirador {
  justify-self: start; width: 2.4rem; padding: .4rem 0;
  background: transparent; border: 1px solid var(--borde);
  color: var(--gris); font-weight: 400; font-size: 1.05rem; line-height: 1;
}
.tirador:hover { color: var(--texto); border-color: var(--acento); }

/* Plegada quedan solo los iconos: el rotulo se desvanece pero sigue en el DOM,
   asi se puede animar y el lector de pantalla lo sigue leyendo. */
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

.casillas { display: flex; gap: .4rem 1.1rem; flex-wrap: wrap; margin-bottom: 1rem; color: var(--gris); }
.casillas label { cursor: pointer; }

.duelo { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1.1rem; }
.tarjeta { background: #141a23; border: 1px solid var(--borde); border-radius: 8px; padding: .9rem 1rem; }
.tarjeta pre {
  margin: .8rem 0 0; padding: .6rem .7rem; overflow-x: auto;
  background: #0d1218; border-radius: 6px; color: var(--gris);
  font-size: .82rem; line-height: 1.4;
}

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

.token { margin: 0 0 1rem; display: flex; gap: .8rem; align-items: center; flex-wrap: wrap; }
.token code { background: #0d1218; padding: .35rem .6rem; border-radius: 6px; font-size: .82rem; }
.token span { color: var(--gris); font-size: .86rem; }

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
  .cuerpo, .cuerpo.plegada, .columnas, .duelo { grid-template-columns: 1fr; }
  .lateral, .cuerpo.plegada .lateral { border-right: 0; border-bottom: 1px solid var(--borde); overflow: visible; padding: 1.3rem .9rem; }
  .cuerpo.plegada .rotulo { opacity: 1; }
  .cuerpo.plegada .lateral nav button { padding: .6rem .8rem; }
  .contenido { overflow: visible; }
}
</style>
