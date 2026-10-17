# Trabajo integrador — Plataforma de predicción de ACV

Plataforma de predicción en tiempo real sobre el modelo de **accidente cerebrovascular**
desarrollado en Aprendizaje de Máquina I. El modelo se entrena y se versiona dentro de la
plataforma, y se sirve por **cuatro protocolos** —REST, GraphQL, gRPC y streaming— más un
**endpoint protegido** con autenticación, límite de consultas y auditoría.

Nivel de la entrega: **contenedores**. La plataforma corre entera sobre Docker, levanta con un
solo comando y no necesita nada instalado en la máquina más que Docker. Lo único que corre
afuera es la medición de latencia (`comparar.py`), que necesita Python.

La presentación del trabajo está en [`presentacion.pdf`](presentacion.pdf).

## Autora

Antonella Gambarte

## Dataset y modelo

**[Stroke Prediction Dataset](https://www.kaggle.com/datasets/fedesoriano/stroke-prediction-dataset)**
(Kaggle). Diez variables clínicas y demográficas por paciente —edad, hipertensión, cardiopatía,
glucosa promedio, índice de masa corporal, tabaquismo, entre otras— y una etiqueta binaria
`stroke`. El CSV crudo está versionado en `dataset/`.

El modelo es un **XGBoost** entrenado en Aprendizaje de Máquina I. Dos decisiones que vienen de
ahí y la plataforma respeta:

- El **umbral de decisión es 0.4**, no 0.5: el dataset está muy desbalanceado y mover el umbral
  mejora el recall, que es lo que importa en un tamizaje clínico.
- El **BMI faltante se imputa por grupo etario** (0-25, 25-40, 40-60, 60+), con las medianas
  calculadas en el entrenamiento.

La métrica con la que se decide si un modelo nuevo reemplaza al que está en producción es el
**F1**.

## Servicios

El `docker compose up -d` levanta **13 contenedores** (14 contando el productor de
streaming, que va en un perfil aparte). La tabla los agrupa por función: los cuatro servicios de
Airflow aparecen en una sola fila. Las credenciales salen de `.env`, que está commiteado a propósito: son
credenciales de desarrollo local, no tienen valor fuera de esta máquina, y así el stack levanta
sin pasos previos.

| Servicio | Para qué | Dónde | Usuario |
| --- | --- | --- | --- |
| **frontend** | cliente de prueba de los protocolos | http://localhost:3000 | — |
| **fastapi** | REST, GraphQL y el endpoint protegido | http://localhost:8800 · [/docs](http://localhost:8800/docs) | — |
| **grpc** | servidor de inferencia gRPC | `localhost:50051` | — |
| **airflow** | orquestación: ETL y entrenamiento | http://localhost:8080 | `airflow` / `airflow` |
| **mlflow** | tracking y registro de modelos | http://localhost:5000 | — |
| **minio** | Data Lake S3 | http://localhost:9001 | `mlops` / `mlops12345` |
| **redpanda** | broker de streaming | `localhost:9092` | — |
| **postgres** | metadata de Airflow y de MLflow | `localhost:5433` | `mlops` / `mlops` |
| **streaming-worker** | puntúa los eventos y vigila el drift | sin puerto | — |
| `minio-init`, `airflow-init` | crean buckets y migran la base, y se apagan | — | — |
| `streaming-productor` | genera eventos de prueba (perfil `demo`) | — | — |

Entre contenedores los servicios se encuentran por nombre: `postgres:5432`, `minio:9000`,
`mlflow:5000`, `fastapi:8800`, `grpc:50051`, `redpanda:9092`.

## Flujo de trabajo principal

```mermaid
flowchart TB
    cliente(["Cliente: frontend o curl"])

    subgraph serving["Serving"]
        fastapi["<b>FastAPI</b> :8800<br/>REST · GraphQL · endpoint protegido"]
        grpc["<b>gRPC</b> :50051<br/>unary · server-streaming"]
        worker["<b>worker</b><br/>puntúa cada evento"]
    end

    redpanda["<b>Redpanda</b> :9092<br/>topics: pacientes, alertas"]
    mlflow["<b>MLflow</b> :5000<br/>registro, alias champion"]
    airflow["<b>Airflow</b> :8080<br/>etl_acv, entrenar_acv"]
    minio[("<b>MinIO</b> S3<br/>zonas del lake y modelos")]
    postgres[("<b>PostgreSQL</b><br/>metadata")]

    cliente -->|HTTP| fastapi
    cliente -->|HTTP/2| grpc
    cliente -->|eventos| redpanda
    redpanda --> worker

    airflow -->|entrena y registra| mlflow
    airflow --> minio
    mlflow --> postgres
    mlflow --> minio

    fastapi -.->|¿cuál es la champion?| mlflow
    grpc -.->|¿cuál es la champion?| mlflow
    worker -.->|¿cuál es la champion?| mlflow
```

1. **`etl_acv`** sube el CSV crudo a la zona `raw/` del lake, saca duplicados, pasa las
   categóricas a one-hot, separa train y test, imputa nulos y escala. Deja el dato listo en
   `curated/` y escribe `data_info/data.json` con todo lo que hace falta para preprocesar una
   petición igual que en el entrenamiento.
2. **`entrenar_acv`** entrena un modelo, lo registra en MLflow como una versión nueva y le pone
   el alias `challenger`. Si su F1 supera al del `champion`, **lo promueve**. Además publica el
   artefacto en `models/v<N>/predictor_acv.pkl`.
3. Los **tres procesos de serving** le preguntan a MLflow qué versión tiene el alias `champion`.
   Si cambió, se recargan solos en menos de 30 segundos, **sin reiniciar nada y sin esperar una
   petición**.
4. Un cliente pide una predicción por **REST**, **GraphQL** o **gRPC**.
5. El **productor** publica pacientes al topic `pacientes` y el **worker** los puntúa de a uno,
   calcula métricas por ventana de un segundo, detecta *drift* y avisa por el topic `alertas`.
6. El **endpoint protegido** (`/v1/secure/predict`) sirve el mismo modelo pero exige un token con
   rol, limita las consultas por minuto y deja registro de cada predicción.

## Ejecución con Docker Compose

Hace falta **Docker con Compose v2** (el comando `docker compose`) y nada más. Parado en
`integrador/`:

```bash
docker compose up -d --build
docker compose ps
```

**La primera vez hay que generar el modelo:**

1. Entrar a Airflow en http://localhost:8080 con `airflow` / `airflow`.
2. Ejecutar el DAG **`etl_acv`** y esperar que termine.
3. Ejecutar el DAG **`entrenar_acv`**.

Eso deja una versión registrada en MLflow con el alias `champion`, y los tres servicios de
serving la toman solos. Desde ese momento `http://localhost:3000` y `http://localhost:8800/docs`
quedan operativos.

Para la demo de streaming, el productor va en un perfil aparte para que no dispare eventos en
cada arranque:

```bash
docker compose --profile demo up streaming-productor
```

Para apagar todo:

```bash
docker compose down        # conserva las bases y los buckets
docker compose down -v     # borra los volúmenes: hay que repetir los pasos de la primera vez
```

## Verificación

Que estén todos arriba:

```bash
docker compose ps
```

Que el modelo esté cargado y con qué versión:

```bash
curl -s localhost:8800/health
# {"status":"healthy","modelo_cargado":true,"version_modelo":"10","umbral":0.4}
```

Los buckets y las zonas del Data Lake se ven en la consola de MinIO: http://localhost:9001

## Probar los cuatro protocolos

La forma más cómoda es **http://localhost:3000**, que tiene secciones para REST, GraphQL y
gRPC, la latencia y el endpoint protegido. Streaming no tiene sección: se ve por los logs del
worker. Para hacerlo a mano, el mismo paciente por todos los protocolos:

```bash
PACIENTE='{"gender":"Female","age":67,"hypertension":0,"heart_disease":1,
"ever_married":"Yes","work_type":"Private","Residence_type":"Urban",
"avg_glucose_level":228.69,"bmi":36.6,"smoking_status":"formerly smoked"}'
```

### REST

```bash
curl -s -X POST localhost:8800/v1/predict \
  -H "Content-Type: application/json" -d "$PACIENTE"
# {"prediccion":1,"probabilidad":0.5005481839179993,"version_modelo":"10",
#  "descripcion":"Tiene riesgo de ACV"}
```

Un paciente inválido se rechaza con **422** y el detalle campo por campo, antes de tocar el
modelo:

```bash
curl -s -X POST localhost:8800/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"gender":"Female","age":150,"work_type":"Astronauta"}'
```

### GraphQL

En `http://localhost:8800/graphql` está GraphiQL para probar a mano. La **Query** devuelve
metadata del modelo, y el campo `metrics` tiene *resolver* propio: si no se pide, no se consulta
MLflow.

```graphql
{ model { name version metrics { auc f1 recall } } }
```

La **mutation** predice, validando con el mismo contrato de Pydantic que usa REST:

```graphql
mutation {
  predecir(paciente: {
    gender: "Female", age: 67, hypertension: 0, heartDisease: 1,
    everMarried: "Yes", workType: "Private", residenceType: "Urban",
    avgGlucoseLevel: 228.69, bmi: 36.6, smokingStatus: "formerly smoked"
  }) { prediccion probabilidad versionModelo descripcion }
}
```

Los nombres van en camelCase porque así los expone Strawberry.

### gRPC

El `.proto` define dos métodos: `Predecir` (unary) y `PredecirLote`
(**server-streaming**, las respuestas salen de a una mientras el servidor calcula). El cliente
de prueba ejercita los dos y mide latencia contra REST:

```bash
docker compose exec grpc python cliente.py
```

La medición de latencia corre en el mismo contenedor que el servidor gRPC, así que gRPC no cruza la red
y REST sí: sirve para ver los dos métodos andando, no para comparar. La comparación es la de
[Comparar la latencia](#comparar-la-latencia).

Las categóricas están **tipadas con `enum`** en el `.proto`, así que un valor inventado no se
puede ni enviar: el contrato lo impide en el cliente.

### Streaming

```bash
docker compose --profile demo up streaming-productor   # en una terminal
docker compose logs -f streaming-worker                # en otra
```

El productor publica 800 pacientes al topic `pacientes` e **inyecta +50 de glucosa a mitad de
camino**. En los logs del worker se ve la media de la ventana saltar de ~107 a ~152 y salir la
alerta por el topic `alertas`. Los eventos aterrizan en el lake particionados por fecha, en
`raw/eventos/fecha=<hoy>/`.

### El endpoint protegido

```bash
TOKEN=$(curl -s -X POST localhost:8800/v1/secure/token \
  -H "X-API-Key: clave-de-servicio-local" -H "Content-Type: application/json" \
  -d '{"usuario":"antonella","rol":"analista"}' | grep -o '"token":"[^"]*' | cut -d'"' -f4)

curl -s -X POST localhost:8800/v1/secure/predict \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d "$PACIENTE"
```

Sin token devuelve **401**; con un rol que no esté habilitado, **403**; pasando las 5 consultas
por minuto, **429**. Cada predicción que pasa queda registrada, y la auditoría la lee solo el
rol `admin`:

```bash
TOKEN_ADMIN=$(curl -s -X POST localhost:8800/v1/secure/token \
  -H "X-API-Key: clave-de-servicio-local" -H "Content-Type: application/json" \
  -d '{"usuario":"antonella","rol":"admin"}' | grep -o '"token":"[^"]*' | cut -d'"' -f4)

curl -s localhost:8800/v1/secure/auditoria -H "Authorization: Bearer $TOKEN_ADMIN"
# [{"ts":"2026-10-15T18:42:07+00:00","usuario":"antonella",
#   "hash_entrada":"c96a59f2814f…","prediccion":1,"version_modelo":"10"}]
```

## Comparar la latencia

`comparar.py` manda el mismo paciente por REST, GraphQL y gRPC, 1000 veces por protocolo, y
saca el promedio por llamada. Deja el resultado en `frontend/public/medicion.json`, que es lo
que muestra la sección Latencia del frontend. Corre **desde la máquina, no desde un contenedor**, así cada protocolo
da un solo salto de red. Es lo único que corre fuera de Docker:

```bash
pip install requests grpcio grpcio-tools
python comparar.py           # o python comparar.py 200, para otra cantidad de llamadas
```

Imprime el promedio por llamada de cada protocolo y confirma que los tres devolvieron la misma
probabilidad.

## Estructura del repositorio

```
integrador/
├── docker-compose.yaml        los servicios, la red y los volúmenes
├── .env                       credenciales y puertos de desarrollo
├── comparar.py                latencia de REST, GraphQL y gRPC desde la máquina
├── presentacion.pdf           la presentación del trabajo
├── dataset/                   el CSV crudo, versionado
├── airflow/dags/
│   ├── etl_acv.py             6 tareas: del CSV crudo a curated/
│   ├── entrenar_acv.py        entrena, registra y promueve
│   └── utils/                 rutas del lake y parámetros compartidos
├── api/
│   ├── main.py                REST y el montaje de GraphQL
│   ├── modelo.py              carga del champion y recarga en caliente
│   ├── esquema_graphql.py     Query de metadata y mutation predecir
│   ├── seguridad.py           el endpoint protegido
│   ├── contrato.py            el Pydantic que comparten REST y GraphQL
│   └── src/predict.py         preprocesa con data.json y puntúa
├── grpc_service/
│   ├── scoring.proto          el contrato: enums, unary y server-streaming
│   ├── server.py              baja el modelo del lake y sirve
│   ├── cliente.py             cliente de prueba y medición de latencia
│   └── mapas.py               traducción enum ↔ texto del entrenamiento
├── streaming/
│   ├── productor.py           publica pacientes e inyecta drift
│   └── worker.py              puntúa, mide por ventana y alerta
├── frontend/                  cliente de prueba (Nuxt)
└── dockerfiles/               una imagen por servicio
```

## Carpetas y archivos clave

| Ruta | Qué hace |
| --- | --- |
| `docker-compose.yaml` | define los servicios, la red y los volúmenes. El anchor `x-airflow-common` evita repetir la configuración en los cuatro servicios de Airflow |
| `airflow/dags/etl_acv.py` | las 6 tareas del ETL. Escribe `data_info/data.json`, que es lo que permite que la inferencia preprocese **exactamente** igual que el entrenamiento |
| `airflow/dags/entrenar_acv.py` | entrena, registra y decide la promoción con `f1_challenger > f1_champion` |
| `api/modelo.py` | el estado del modelo en una tupla, y el hilo que cada 30 s pregunta si hay un champion nuevo |
| `api/contrato.py` | un solo contrato de entrada para REST, GraphQL y el endpoint protegido: los tres rechazan exactamente la misma entrada |
| `api/src/predict.py` | aplica `data.json` —one-hot, imputación por grupo etario y escalado— y puntúa con el umbral 0.4 |
| `grpc_service/scoring.proto` | el contrato tipado. Las categóricas son `enum`, el `bmi` es `optional` para distinguir "no vino" de "vino en cero" |
| `streaming/worker.py` | ventana deslizante de un segundo, throughput y p95, detección de drift y aterrizaje en el lake |
| `dockerfiles/postgres/init.sql` | crea la base `mlflow`; la base `airflow` la crea la imagen |
| `comparar.py` | mide la latencia de los tres protocolos desde la máquina y escribe `frontend/public/medicion.json`, que muestra el frontend |

## Conceptos generales importantes

**PostgreSQL guarda metadata, MinIO guarda archivos.** Es la división que ordena todo el diseño.
MLflow no entrega el modelo: entrega su dirección en S3, y el servicio lo baja por su cuenta —
por eso necesita credenciales de los dos.

**Champion y challenger.** Cada corrida de `entrenar_acv` registra una versión nueva y la marca
`challenger`. La promoción a `champion` es automática y por F1, con comparación estricta: si
empata, no promueve.

**Las cuatro zonas del Data Lake.** El bucket `data` está organizado en cuatro zonas:
`raw/` el dato crudo e inmutable en CSV, `staged/` limpio y en Parquet, `curated/` las
features listas para entrenar, y `models/v<N>/` el artefacto publicado y versionado. El número
de carpeta es la versión de MLflow, así los dos quedan atados.

**Recarga en caliente.** Los tres procesos de serving tienen un hilo que cada 30 segundos le
pregunta a MLflow qué versión es la champion. Si cambió, la bajan y la reemplazan de una sola
asignación. El modelo se actualiza **sin reiniciar el contenedor y sin que llegue tráfico**.

**El modelo vive en dos lugares, a propósito.** FastAPI lo carga desde MLflow
(`mlflow.sklearn.load_model`), como en MLOps I; el servidor gRPC y el worker bajan el `.pkl`
versionado de la zona `models/` del lake con `boto3` y `joblib`, como en MLOps II. Los tres le
preguntan a MLflow qué versión corresponde y devuelven el mismo número: `comparar.py` lo
comprueba entre FastAPI y gRPC cada vez que se corre.

## Decisiones y alcance

Lo que se decidió y por qué, y lo que quedó simplificado a propósito.

### Endpoint protegido

No reemplaza a `/v1/predict`: es un endpoint aparte, sobre el mismo modelo.

- **No hay usuarios ni login.** Con la clave de servicio (`X-API-Key`) cualquiera pide un token
  con el usuario y el rol que quiera. Es una simplificación para la demo.
- **El emisor firma cualquier rol, incluso uno sin permiso.** Quién puede predecir lo decide el
  endpoint, no el emisor; así se puede probar el 403.
- El token vence a los **15 minutos** y se firma con `JWT_SECRET`, del `.env`.
- **Los controles se aplican en orden**: token, rol, límite por minuto y contrato. El primero
  que falla define la respuesta: un rol sin permiso con `age` 150 recibe 403, no 422.
- **La auditoría guarda el hash de la entrada, no los datos del paciente.** Alcanza para
  reconocer dos consultas iguales sin almacenar información clínica.
- **El límite y la auditoría se guardan en la memoria de la API.** Si se reinicia el
  contenedor, el contador de consultas vuelve a cero y la auditoría se pierde. En producción
  irían en un almacenamiento aparte, como Redis o una base de datos.
- **La clave de servicio nunca llega al navegador.** Para pedir un token hace falta esa clave, y
  todo lo que está en una página web lo puede ver quien la abre. Por eso el frontend pide el
  token desde su servidor, y al navegador solo le llega el token.
- **CORS habilita solo el origen del frontend** (`ORIGENES_PERMITIDOS` en el `.env`). Con `*`,
  cualquier sitio podría consultar el modelo desde el navegador de quien lo visite.

### Streaming: una simulación

- **No hay una fuente real de eventos.** El productor toma pacientes al azar del CSV crudo del
  lake (`raw/acv/`) y los publica en el topic `pacientes`.
- **El drift está forzado.** Desde la mitad de la corrida (el evento 400 de 800), el productor
  le suma 50 a la glucosa para que la alerta salga en la demo.
- **La referencia del drift está fija**: media de glucosa 106 y umbral 130, como variables de
  entorno del worker (`MEDIA_GLUCOSA_ENTRENAMIENTO`, `UMBRAL_DRIFT`). No se calculan a partir del
  entrenamiento.
- **Se vigila una sola variable**, la glucosa, y la alerta se evalúa cada 200 eventos sobre la
  ventana del último segundo.
- **El tiempo que muestra el worker en sus logs es solo lo que tarda el modelo en puntuar cada
  evento.**

### Entrenamiento y promoción

- **Los hiperparámetros son fijos**: los que encontró Optuna en Aprendizaje de Máquina I. El DAG
  no vuelve a optimizar.
- **Reentrenar con los mismos datos no promueve.** El split y el XGBoost tienen semilla fija, así
  que el F1 sale idéntico, y la comparación es estricta. Las versiones 11 y 12 dieron el mismo F1
  que la 10 (0.2806) y quedaron como `challenger`. La promoción se ve en el primer entrenamiento
  o cuando cambian los datos.

### Otras

- **El navegador llama directo a REST y GraphQL; gRPC pasa por el servidor de Nuxt**, porque el
  navegador no habla gRPC.
