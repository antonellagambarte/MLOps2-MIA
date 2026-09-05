"""
Transformaciones que se le aplican a los datos del paciente antes de predecir.
Son las mismas que se usaron al entrenar; van junto al modelo.joblib.
"""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

COLUMNAS_NUMERICAS = [
    "age", "hypertension", "heart_disease",
    "ever_married", "avg_glucose_level", "bmi",
]
COLUMNAS_CATEGORICAS = [
    "gender", "work_type", "Residence_type", "smoking_status",
]

# Grupos etarios para imputar bmi (definido así en aprendizaje de maáquina I)
BINS_EDAD = [0, 25, 40, 60, 200]
LABELS_EDAD = ["0-25", "25-40", "40-60", "60+"]


class ImputadorBMIPorEdad(BaseEstimator, TransformerMixin):
    """Imputa bmi con la mediana de su grupo etario, aprendida solo en train."""

    def fit(self, X, y=None):
        df = X.copy()
        grupo = pd.cut(df["age"], bins=BINS_EDAD, labels=LABELS_EDAD,
                       right=False).astype(str)
        self.medianas_ = df.groupby(grupo, observed=True)["bmi"].median()
        self.mediana_global_ = float(df["bmi"].median())
        return self

    def transform(self, X):
        df = X.copy()
        df["bmi"] = pd.to_numeric(df["bmi"], errors="coerce")
        grupo = pd.cut(df["age"], bins=BINS_EDAD, labels=LABELS_EDAD,
                       right=False).astype(str)
        relleno = grupo.map(self.medianas_).astype(
            float).fillna(self.mediana_global_)
        df["bmi"] = df["bmi"].fillna(relleno).astype(float)
        return df


def limpiar(X):
    """Agrupa categorías, mapea ever_married y aplica log1p a bmi."""
    df = X.copy()
    df["gender"] = df["gender"].replace("Other", "Female")
    df["work_type"] = df["work_type"].replace("Never_worked", "children")
    if not pd.api.types.is_numeric_dtype(df["ever_married"]):
        df["ever_married"] = df["ever_married"].map({"No": 0, "Yes": 1})
    df["ever_married"] = df["ever_married"].astype(float)
    df["bmi"] = np.log1p(df["bmi"])
    return df
