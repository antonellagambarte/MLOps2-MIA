"""
API de predicción de accidente cerebrovascular (adaptado de mini-TP1)

Sirve dos protocolos sobre el mismo modelo: REST para predecir y GraphQL para
consultar metadatos y también predecir. El modelo lo carga y lo mantiene al día
el módulo modelo.py, que los dos comparten.
"""
from fastapi import APIRouter, FastAPI, HTTPException
from mlflow.tracking import MlflowClient
from pydantic import BaseModel
from strawberry.fastapi import GraphQLRouter

import modelo
from contrato import Caracteristicas, Prediccion
from esquema_graphql import schema as schema_graphql

app = FastAPI(title="Predictor de accidente cerebrovascular")


def estado_cargado():
    """Devuelve el estado del modelo de una sola lectura, o corta con 503."""
    actual = modelo.estado
    if actual is None:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo cargar {modelo.URI_MODELO}. {modelo.error_carga}",
        )
    return actual


@app.get("/health")
def chequeo_health():
    _, version, _, umbral, _ = estado_cargado()
    return {
        "status": "healthy",
        "modelo_cargado": True,
        "version_modelo": version,
        "umbral": umbral,
    }


# --- METADATA DEL MODELO ---
class MetricasModelo(BaseModel):
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float


class InfoModelo(BaseModel):
    nombre: str
    version: str
    umbral: float
    features: list[str]


# --- ENRUTAMIENTO VERSIONADO ---
router_v1 = APIRouter(prefix="/v1", tags=["Modelo 1"])


# --- ENDPOINTS DE MODELO ---

@router_v1.get("/model", response_model=InfoModelo)
def info_modelo():
    _, version, _, umbral, data_dict = estado_cargado()
    return InfoModelo(
        nombre=modelo.NOMBRE_MODELO,
        version=version,
        umbral=umbral,
        features=data_dict["columns"],
    )


@router_v1.get("/model/metrics", response_model=MetricasModelo)
def metricas_modelo():
    _, _, run_id, _, _ = estado_cargado()
    metricas = MlflowClient().get_run(run_id).data.metrics
    return MetricasModelo(**metricas)


@router_v1.post("/predict", response_model=Prediccion)
def predecir(paciente: Caracteristicas):
    estado_cargado()   # 503 si todavia no hay modelo

    try:
        clase, probabilidad, version, descripcion = modelo.predecir(paciente.model_dump())
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al ejecutar el modelo: {error}",
        )

    return Prediccion(
        prediccion=clase,
        probabilidad=probabilidad,
        version_modelo=version,
        descripcion=descripcion,
    )


app.include_router(router_v1)

app.include_router(GraphQLRouter(schema_graphql), prefix="/graphql")
