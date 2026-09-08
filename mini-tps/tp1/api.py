import json
from pathlib import Path
import joblib
from fastapi import FastAPI, APIRouter, HTTPException
import preprocesamiento
from typing import Literal, Optional
from pydantic import BaseModel, Field
import pandas as pd

# --- CARGA DE MODELO ---
BASE_DIR = Path(__file__).resolve().parent
CONTENIDO_JOBLIB = joblib.load(BASE_DIR / "modelo" / "modelo.joblib")

pipeline = CONTENIDO_JOBLIB["pipeline"]
VERSION_MODELO = CONTENIDO_JOBLIB["version"]
UMBRAL = CONTENIDO_JOBLIB["umbral"]
FEATURES = CONTENIDO_JOBLIB["features"]
METRICAS_PATH = BASE_DIR / "modelo" / "metricas.json"

app = FastAPI(title="Predictor de accidente cerebrovascular")


@app.get("/health")
def chequeo_health():
    return {
        "status": "healthy",
        "modelo_cargado": pipeline is not None,
        "version_modelo": VERSION_MODELO,
        "umbral": UMBRAL
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


# --- METADATA DEL MODELO (para la comparación con GraphQL del mini-TP2) ---
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
# Dos endpoints: info_modelo devuelve los datos del modelo y metricas_modelo sus métricas (para mini-TP2).

@router_v1.get("/model", response_model=InfoModelo)
def info_modelo():

    # --- PARA TOMAR DATOS DEL ARCHIVO DE MÉTRICAS ---
    datos = json.loads(METRICAS_PATH.read_text(encoding="utf-8"))
    return InfoModelo(
        nombre=datos["nombre"],
        version=datos["version"],
        umbral=datos["umbral"],
        features=FEATURES,
    )


@router_v1.get("/model/metrics", response_model=MetricasModelo)
def metricas_modelo():
    datos = json.loads(METRICAS_PATH.read_text(encoding="utf-8"))
    return MetricasModelo(**datos["metricas"])


@router_v1.post("/predict", response_model=Prediccion)
def predecir(paciente: Caracteristicas):
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
