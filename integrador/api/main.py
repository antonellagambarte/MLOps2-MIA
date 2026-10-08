"""
API de prediccion de accidente cerebrovascular (adaptado de mini-TP1)

La API no carga el modelo: valida la entrada y le pide la prediccion al servicio
gRPC, que es el unico que corre inferencia. REST queda como puerta externa y gRPC
como motor interno, que es el diseno planteado en el mini-TP 3.
"""
import os
from typing import Literal, Optional

from fastapi import APIRouter, FastAPI, HTTPException
from mlflow.tracking import MlflowClient
from pydantic import BaseModel, Field
from strawberry.fastapi import GraphQLRouter

import cliente_grpc
from esquema_graphql import schema as schema_graphql

NOMBRE_MODELO = os.getenv("NOMBRE_MODELO", "predictor_acv")
ALIAS_MODELO = os.getenv("ALIAS_MODELO", "champion")
URI_MODELO = f"models:/{NOMBRE_MODELO}@{ALIAS_MODELO}"

app = FastAPI(title="Predictor de accidente cerebrovascular")


def champion():
    """La version con alias champion. Solo para los endpoints de metadata."""
    try:
        return MlflowClient().get_model_version_by_alias(NOMBRE_MODELO, ALIAS_MODELO)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo consultar {URI_MODELO}. {type(error).__name__}: {error}",
        )


@app.get("/health")
def chequeo_health():
    # Ahora que la API no predice, estar sana es poder llegar al que predice.
    cliente_grpc.verificar_disponible()
    return {"status": "healthy", "inferencia": cliente_grpc.DESTINO}


# --- DEFINICION DE ENTRADA ---
class Caracteristicas(BaseModel):
    gender: Literal["Male", "Female", "Other"] = Field(
        ..., description="Género del paciente"
    )
    age: float = Field(
        ..., ge=0, le=100, description="Edad del paciente en años"
    )
    hypertension: Literal[0, 1] = Field(
        ..., description="Hipertensión: 0 = No, 1 = Sí"
    )
    heart_disease: Literal[0, 1] = Field(
        ..., description="Enfermedad cardíaca: 0 = No, 1 = Sí"
    )
    ever_married: Literal["Yes", "No"] = Field(
        ..., description="Si estuvo casado alguna vez"
    )
    work_type: Literal[
        "Private", "Self-employed", "Govt_job", "children", "Never_worked"
    ] = Field(..., description="Tipo de empleo")
    Residence_type: Literal["Urban", "Rural"] = Field(
        ..., description="Zona de residencia"
    )
    avg_glucose_level: float = Field(
        ..., gt=0, le=400, description="Nivel promedio de glucosa en sangre"
    )
    bmi: Optional[float] = Field(
        default=None, gt=0, le=100,
        description="Índice de masa corporal. Si no se envía, se imputa por grupo etario.",
    )
    smoking_status: Literal[
        "formerly smoked", "never smoked", "smokes", "Unknown"
    ] = Field(..., description="Estado de tabaquismo")


# --- DEFINICION DE SALIDA ---
class Prediccion(BaseModel):
    prediccion: int
    probabilidad: float
    version_modelo: str
    descripcion: str


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
    version = champion()
    return InfoModelo(
        nombre=NOMBRE_MODELO,
        version=version.version,
        umbral=float(version.tags.get("umbral", 0.5)),
        # Las features son las que acepta la API, no hay que ir a buscarlas al lake.
        features=list(Caracteristicas.model_fields),
    )


@router_v1.get("/model/metrics", response_model=MetricasModelo)
def metricas_modelo():
    metricas = MlflowClient().get_run(champion().run_id).data.metrics
    return MetricasModelo(**metricas)


@router_v1.post("/predict", response_model=Prediccion)
def predecir(paciente: Caracteristicas):
    # La version y la descripcion las pone el servicio gRPC: el que predice es el
    # que sabe con que modelo lo hizo.
    respuesta = cliente_grpc.predecir(paciente.model_dump())
    return Prediccion(
        prediccion=respuesta.prediccion,
        probabilidad=respuesta.probabilidad,
        version_modelo=respuesta.version_modelo,
        descripcion=respuesta.descripcion,
    )


app.include_router(router_v1)

app.include_router(GraphQLRouter(schema_graphql), prefix="/graphql")
