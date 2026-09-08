# TP 1 — API REST de predicción de ACV

API hecha con FastAPI que sirve el modelo de predicción de accidente
cerebrovascular (desarrollado en aprendizaje de máquina I).

El modelo es un XGBoost entrenado sobre el [Stroke Prediction Dataset](https://www.kaggle.com/datasets/fedesoriano/stroke-prediction-dataset).

El umbral de decisión es 0.4 en vez del 0.5 por defecto.

## Cómo correrlo

El entorno se arma una sola vez desde la raíz del repo (ver README de ahí).
Después, parado en `mini-tps/tp1/`:

```bash
uv run uvicorn api:app --reload --port 8080
```

Ese comando no termina: el servidor se queda corriendo y ocupa la terminal.
La documentación interactiva queda en http://localhost:8080/docs

Para probarlo hay que abrir una segunda terminal, también parado en `mini-tps/tp1/`:

```bash
uv run python cliente_prueba.py
```

Hace tres llamadas: el health check, un paciente válido (200) y uno con varios
campos fuera de rango, que devuelve 422 con el detalle de qué falló.

## Endpoints

`GET /health` — devuelve si el modelo está cargado y qué versión es.

`POST /v1/predict` — recibe los datos de un paciente y devuelve:

```json
{
  "prediccion": 1,
  "probabilidad": 0.4751546382904053,
  "version_modelo": "1.0.0",
  "descripcion": "Tiene riesgo de ACV"
}
```

`GET /v1/model` — datos del modelo: nombre, versión, umbral y features.

`GET /v1/model/metrics` — métricas del modelo: accuracy, precision, recall, f1_score y roc_auc.

## Datos de entrada

Son las 10 variables del dataset original:

| Campo               | Valores                                                  |
| ------------------- | -------------------------------------------------------- |
| `gender`            | Male, Female, Other                                      |
| `age`               | 0 a 100                                                  |
| `hypertension`      | 0 o 1                                                    |
| `heart_disease`     | 0 o 1                                                    |
| `ever_married`      | Yes, No                                                  |
| `work_type`         | Private, Self-employed, Govt_job, children, Never_worked |
| `Residence_type`    | Urban, Rural                                             |
| `avg_glucose_level` | mayor a 0, hasta 400                                     |
| `bmi`               | mayor a 0, hasta 100 (opcional)                          |
| `smoking_status`    | formerly smoked, never smoked, smokes, Unknown           |
