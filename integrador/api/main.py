import os
from typing import Literal, Optional

import mlflow
import pandas as pd
from fastapi import APIRouter, FastAPI, HTTPException
from mlflow.models import Model
from mlflow.tracking import MlflowClient
from pydantic import BaseModel, Field
from strawberry.fastapi import GraphQLRouter

from esquema_graphql import schema as schema_graphql

NOMBRE_MODELO = os.getenv("NOMBRE_MODELO", "predictor_acv")
ALIAS_MODELO = os.getenv("ALIAS_MODELO", "champion")
URI_MODELO = f"models:/{NOMBRE_MODELO}@{ALIAS_MODELO}"

# --- CARGA DEL MODELO ---
pipeline = None
VERSION_MODELO = None
UMBRAL = None
FEATURES = []
RUN_ID = None
ERROR_CARGA = None


def cargar_modelo():
    global pipeline, VERSION_MODELO, UMBRAL, FEATURES, RUN_ID, ERROR_CARGA
    try:
        cliente = MlflowClient()
        version = cliente.get_model_version_by_alias(NOMBRE_MODELO, ALIAS_MODELO)

        pipeline = mlflow.sklearn.load_model(URI_MODELO)
        VERSION_MODELO = version.version
        RUN_ID = version.run_id
        # El umbral viaja como tag de la versión: cada modelo trae el suyo.
        UMBRAL = float(version.tags.get("umbral", 0.5))

        # Las features salen de la firma que MLflow guardó junto al modelo.
        esquema = Model.load(URI_MODELO).get_input_schema()
        FEATURES = list(esquema.input_names()) if esquema else []

        ERROR_CARGA = None
    except Exception as error:
        ERROR_CARGA = f"{type(error).__name__}: {error}"


cargar_modelo()

app = FastAPI(title="Predictor de accidente cerebrovascular")


@app.get("/health")
def chequeo_health():
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo cargar {URI_MODELO}. {ERROR_CARGA}",
        )
    return {
        "status": "healthy",
        "modelo_cargado": True,
        "version_modelo": VERSION_MODELO,
        "umbral": UMBRAL,
    }


# --- DEFINICIÓN DE ENTRADA ---


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


# --- DEFINICIÓN DE SALIDA ---
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


def verificar_modelo():
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo cargar {URI_MODELO}. {ERROR_CARGA}",
        )


# --- ENDPOINTS DE MODELO ---

@router_v1.get("/model", response_model=InfoModelo)
def info_modelo():
    verificar_modelo()
    return InfoModelo(
        nombre=NOMBRE_MODELO,
        version=VERSION_MODELO,
        umbral=UMBRAL,
        features=FEATURES,
    )


@router_v1.get("/model/metrics", response_model=MetricasModelo)
def metricas_modelo():
    verificar_modelo()
    metricas = MlflowClient().get_run(RUN_ID).data.metrics
    return MetricasModelo(**metricas)


@router_v1.post("/predict", response_model=Prediccion)
def predecir(paciente: Caracteristicas):
    verificar_modelo()
    df = pd.DataFrame([paciente.model_dump()])

    try:
        probabilidad = pipeline.predict_proba(df)[0, 1]
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al ejecutar el modelo: {error}",
        )

    clase = int(probabilidad >= UMBRAL)

    return Prediccion(
        prediccion=clase,
        descripcion="Tiene riesgo de ACV" if clase == 1 else "No tiene riesgo de ACV",
        probabilidad=probabilidad,
        version_modelo=VERSION_MODELO,
    )


app.include_router(router_v1)

app.include_router(GraphQLRouter(schema_graphql), prefix="/graphql")
