"""
Calcula métricas del pipeline entrenado en TP1 sobre el dataset original y las deja en mini-tps/tp1/modelo/metricas.json, 
junto al modelo. Se corre sobre el dataset completo porque el split de train/test original no se guardó junto al modelo, 
así que el pipeline ya vio parte de estos datos durante el entrenamiento. Sirve como 
referencia ilustrativa.
"""
import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
)

TP1_DIR = Path(__file__).resolve().parent.parent / "tp1"
sys.path.insert(0, str(TP1_DIR))

CONTENIDO = joblib.load(TP1_DIR / "modelo" / "modelo.joblib")
pipeline = CONTENIDO["pipeline"]
version = CONTENIDO["version"]
umbral = CONTENIDO["umbral"]
features = CONTENIDO["features"]

df = pd.read_csv(Path(__file__).resolve().parent / "dataset" / "healthcare-dataset-stroke-data.csv")
X = df[features]
y = df["stroke"]

proba = pipeline.predict_proba(X)[:, 1]
pred = (proba >= umbral).astype(int)

metricas = {
    "accuracy": round(accuracy_score(y, pred), 4),
    "precision": round(precision_score(y, pred), 4),
    "recall": round(recall_score(y, pred), 4),
    "f1_score": round(f1_score(y, pred), 4),
    "roc_auc": round(roc_auc_score(y, proba), 4),
}

salida = {
    "nombre": "predictor_acv",
    "version": version,
    "umbral": umbral,
    "metricas": metricas,
}

destino = TP1_DIR / "modelo" / "metricas.json"
destino.write_text(json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Métricas guardadas en {destino}")
print(json.dumps(metricas, indent=2))
