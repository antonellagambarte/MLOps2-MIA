# TP 2 — REST vs GraphQL

Expone los metadatos y métricas del modelo del TP1 (`predictor_acv`) por GraphQL con Strawberry, y los compara contra los endpoints REST.

## Cómo correrlo

El entorno se arma una sola vez desde la raíz del repo (ver README de ahí). Después, parado en `mini-tps/tp2/`, abrir `mini_tp2_actividad.ipynb` (VS Code o `uv run jupyter lab`) y correrlo.

`mini-tps/tp1/modelo/metricas.json` sale de correr, parado en `mini-tps/tp2/`, `uv run python calcular_metricas.py`, que carga el pipeline de TP1, calcula las métricas sobre el dataset y lo pisa. Ya viene generado en el repo, así que no hace falta volver a correrlo para probar el notebook.

Para probar a mano en GraphiQL, con la celda de la sección 3 ya corrida, abrir http://localhost:8010/graphql y pegar:

```graphql
{ model { name version metrics { auc accuracy f1 precision recall } } }
```

## Esquema GraphQL

Tipo `Model` (`name`, `version`, `metrics`), con `metrics` resuelto como un tipo aparte `Metrics` (`auc`, `accuracy`, `f1`, `precision`, `recall`). Una sola query, `model` que devuelve los metadatos del modelo entrenado en el TP1 (leídos de `mini-tps/tp1/modelo/metricas.json`).

## Endpoints REST

`GET /v1/model` — nombre, versión, umbral y features del modelo.
`GET /v1/model/metrics` — las 5 métricas del modelo.

Definidos en `api.py` de TP1.

## REST vs GraphQL

**Vista que se compara:** nombre, versión y las 5 métricas del modelo (`auc`, `accuracy`, `f1`, `precision`, `recall`).

Armar esa vista por REST necesita pegarle a los dos endpoints, mientras que GraphQL la resuelve con una sola query — así se compara no solo el peso de la respuesta, sino también la cantidad de llamadas.

Para armar esa misma vista:

|                                          | llamadas | bytes |
| ---------------------------------------- | -------- | ----- |
| REST (`/v1/model` + `/v1/model/metrics`) | 2        | 292   |
| GraphQL                                  | 1        | 167   |

GraphQL necesitó la mitad de llamadas y transfirió menos bytes. La query pidió exactamente `name`, `version` y `metrics`, y esa fue la respuesta completa. Por REST, en cambio, esa misma vista quedó repartida en dos endpoints, así que hace falta una segunda llamada para completar la vista (under-fetching). Además `/v1/model` devuelve también `umbral` y `features`, que no hacían falta para la vista que se pretendía formar pero viajan igual porque REST no permite pedir un subconjunto de campos (over-fetching).
