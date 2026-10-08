"""Carga el modelo champion y lo mantiene al dia.
"""
import json
import os
import threading
import time

import boto3
import mlflow
import numpy as np
from mlflow.tracking import MlflowClient

from src import predict as model_predict

NOMBRE_MODELO = os.getenv("NOMBRE_MODELO", "predictor_acv")
ALIAS_MODELO = os.getenv("ALIAS_MODELO", "champion")
URI_MODELO = f"models:/{NOMBRE_MODELO}@{ALIAS_MODELO}"
INTERVALO_RECARGA = float(os.getenv("INTERVALO_RECARGA_SEG", "30"))

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


def vigilar_champion():
    """Dispara check_model() cada tanto, igual que el servidor gRPC y el worker.
    """
    while True:
        time.sleep(INTERVALO_RECARGA)
        check_model()


def predecir(paciente: dict):
    """Puntúa un paciente ya validado. Devuelve (clase, probabilidad, versión, descripción)."""
    if model is None:
        raise RuntimeError(f"No se pudo cargar {URI_MODELO}. {error_carga}")
    clase, probabilidad = model_predict.run(paciente, data_dict, model, umbral)
    descripcion = "Tiene riesgo de ACV" if clase == 1 else "No tiene riesgo de ACV"
    return clase, probabilidad, version_model, descripcion


cargar()
threading.Thread(target=vigilar_champion, daemon=True).start()
