"""
API de predicción de accidente cerebrovascular (adaptado de mini-TP1)
"""
import json
import os
from typing import Literal, Optional
import boto3
import mlflow
import numpy as np
from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException
from mlflow.tracking import MlflowClient
from pydantic import BaseModel, Field
from strawberry.fastapi import GraphQLRouter

from esquema_graphql import schema as schema_graphql
from src import predict as model_predict

NOMBRE_MODELO = os.getenv("NOMBRE_MODELO", "predictor_acv")
ALIAS_MODELO = os.getenv("ALIAS_MODELO", "champion")
URI_MODELO = f"models:/{NOMBRE_MODELO}@{ALIAS_MODELO}"

# --- CARGA DEL MODELO ---
# Se carga al arrancar. Si falla, la API igual levanta y /health lo reporta.
model = None
version_model = None
run_id_model = None
umbral = None
data_dict = None
error_carga = None


def load_model(model_name: str, alias: str):
    """Trae el modelo desde MLflow y la metadata del ETL (data.json) desde S3.

    Devuelve (modelo, versión, run_id, umbral, data_dict). MLflow entrega la
    dirección del artefacto. El archivo se baja de MinIO.
    """
    client_mlflow = MlflowClient()
    model_data_mlflow = client_mlflow.get_model_version_by_alias(model_name, alias)
    model_ml = mlflow.sklearn.load_model(model_data_mlflow.source)
    version_model_ml = model_data_mlflow.version
    umbral_ml = float(model_data_mlflow.tags.get("umbral", 0.5))

    # Metadata del ETL: categorías, columnas, medianas y escalado
    s3 = boto3.client("s3")
    result_s3 = s3.get_object(Bucket="data", Key="data_info/data.json")
    data_dictionary = json.loads(result_s3["Body"].read().decode())
    data_dictionary["standard_scaler_mean"] = np.array(data_dictionary["standard_scaler_mean"])
    data_dictionary["standard_scaler_std"] = np.array(data_dictionary["standard_scaler_std"])

    print(f"Modelo {model_name}@{alias} cargado: versión {version_model_ml}, umbral {umbral_ml}")
    return model_ml, version_model_ml, model_data_mlflow.run_id, umbral_ml, data_dictionary


def cargar():
    global model, version_model, run_id_model, umbral, data_dict, error_carga
    try:
        model, version_model, run_id_model, umbral, data_dict = load_model(NOMBRE_MODELO, ALIAS_MODELO)
        error_carga = None
    except Exception as error:
        error_carga = f"{type(error).__name__}: {error}"
        print(f"No se pudo cargar el modelo: {error_carga}")


def check_model():
    """Corre en segundo plano después de cada predicción: si el champion cambió
    de versión (porque el DAG de entrenamiento promovió uno nuevo), lo recarga
    sin reiniciar la API."""
    try:
        nueva_version = MlflowClient().get_model_version_by_alias(NOMBRE_MODELO, ALIAS_MODELO).version
        if nueva_version != version_model:
            cargar()
    except Exception:
        pass


cargar()

app = FastAPI(title="Predictor de accidente cerebrovascular")


def verificar_modelo():
    """Corta con 503 si el modelo no está cargado"""
    if model is None:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo cargar {URI_MODELO}. {error_carga}",
        )


@app.get("/health")
def chequeo_health():
    verificar_modelo()
    return {
        "status": "healthy",
        "modelo_cargado": True,
        "version_modelo": version_model,
        "umbral": umbral,
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


# --- ENDPOINTS DE MODELO ---

@router_v1.get("/model", response_model=InfoModelo)
def info_modelo():
    verificar_modelo()
    return InfoModelo(
        nombre=NOMBRE_MODELO,
        version=version_model,
        umbral=umbral,
        features=data_dict["columns"],
    )


@router_v1.get("/model/metrics", response_model=MetricasModelo)
def metricas_modelo():
    verificar_modelo()
    metricas = MlflowClient().get_run(run_id_model).data.metrics
    return MetricasModelo(**metricas)


@router_v1.post("/predict", response_model=Prediccion)
def predecir(paciente: Caracteristicas, background_tasks: BackgroundTasks):
    verificar_modelo()

    try:
        clase, probabilidad = model_predict.run(paciente.model_dump(), data_dict, model, umbral)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al ejecutar el modelo: {error}",
        )

    # Después de responder, chequea si hay un champion nuevo
    background_tasks.add_task(check_model)

    return Prediccion(
        prediccion=clase,
        descripcion="Tiene riesgo de ACV" if clase == 1 else "No tiene riesgo de ACV",
        probabilidad=probabilidad,
        version_modelo=version_model,
    )


app.include_router(router_v1)

app.include_router(GraphQLRouter(schema_graphql), prefix="/graphql")
