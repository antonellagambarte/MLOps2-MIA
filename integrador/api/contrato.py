"""Contrato de entrada y salida de una prediccion.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


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


class Prediccion(BaseModel):
    prediccion: int
    probabilidad: float
    version_modelo: str
    descripcion: str
