"""Servicio gRPC de inferencia"""
import io
import json
import os
import threading
import time
from concurrent import futures

import boto3
import grpc
import joblib
import mlflow
import numpy as np
from mlflow.tracking import MlflowClient

import scoring_pb2
import scoring_pb2_grpc
from mapas import MAPAS
from src import predict as model_predict

NOMBRE_MODELO = os.getenv("NOMBRE_MODELO", "predictor_acv")
ALIAS_MODELO = os.getenv("ALIAS_MODELO", "champion")
BUCKET = os.getenv("BUCKET_DATOS", "data")
PUERTO = int(os.getenv("GRPC_PORT", "50051"))
INTERVALO_RECARGA = float(os.getenv("INTERVALO_RECARGA_SEG", "30"))


def cargar_modelo():
    """Pregunta a MLflow qué versión es champion y baja ese modelo del lake."""
    version = MlflowClient().get_model_version_by_alias(NOMBRE_MODELO, ALIAS_MODELO)
    s3 = boto3.client("s3")

    key = f"models/v{version.version}/predictor_acv.pkl"
    modelo = joblib.load(io.BytesIO(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()))

    datos = json.loads(s3.get_object(Bucket=BUCKET, Key="data_info/data.json")["Body"].read())
    datos["standard_scaler_mean"] = np.array(datos["standard_scaler_mean"])
    datos["standard_scaler_std"] = np.array(datos["standard_scaler_std"])

    umbral = float(version.tags.get("umbral", 0.5))
    print(f"Modelo cargado del lake: s3://{BUCKET}/{key} | versión {version.version} | umbral {umbral}")
    return modelo, version.version, umbral, datos


def validar(caso):
    """Los enum sin especificar valen 0, así que un campo que falta llega como 0."""
    problemas = []
    for campo, mapa in MAPAS.items():
        if getattr(caso, campo) not in mapa:
            problemas.append(f"{campo} sin especificar o desconocido")
    if not 0 <= caso.age <= 100:
        problemas.append(f"age fuera de rango: {caso.age}")
    if not 0 < caso.avg_glucose_level <= 400:
        problemas.append(f"avg_glucose_level fuera de rango: {caso.avg_glucose_level}")
    if caso.hypertension not in (0, 1):
        problemas.append(f"hypertension debe ser 0 o 1: {caso.hypertension}")
    if caso.heart_disease not in (0, 1):
        problemas.append(f"heart_disease debe ser 0 o 1: {caso.heart_disease}")
    if caso.HasField("bmi") and not 0 < caso.bmi <= 100:
        problemas.append(f"bmi fuera de rango: {caso.bmi}")
    return problemas


def a_diccionario(caso):
    return {
        "gender": MAPAS["gender"][caso.gender],
        "age": caso.age,
        "hypertension": caso.hypertension,
        "heart_disease": caso.heart_disease,
        "ever_married": MAPAS["ever_married"][caso.ever_married],
        "work_type": MAPAS["work_type"][caso.work_type],
        "Residence_type": MAPAS["Residence_type"][caso.Residence_type],
        "avg_glucose_level": caso.avg_glucose_level,
        "bmi": caso.bmi if caso.HasField("bmi") else None,
        "smoking_status": MAPAS["smoking_status"][caso.smoking_status],
    }


class ServicioScoring(scoring_pb2_grpc.ScoringServicer):
    def __init__(self):
        self.estado = None
        self.error = None
        self._cargar()
        threading.Thread(target=self._vigilar, daemon=True).start()

    def _cargar(self):
        try:
            self.estado = cargar_modelo()
            self.error = None
        except Exception as error:
            self.error = f"{type(error).__name__}: {error}"
            print(f"No se pudo cargar el modelo: {self.error}")

    def _vigilar(self):
        """Carga el modelo si falto al arrancar, y lo recarga si promovieron otro champion."""
        while True:
            time.sleep(INTERVALO_RECARGA)
            try:
                version = MlflowClient().get_model_version_by_alias(
                    NOMBRE_MODELO, ALIAS_MODELO
                ).version
                if self.estado is None or version != self.estado[1]:
                    self._cargar()
            except Exception as error:
                print(f"No se pudo chequear el champion: {error}")

    def _predecir(self, caso, context):
        estado = self.estado
        if estado is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, f"El modelo no esta cargado. {self.error}")
        modelo, version, umbral, datos = estado

        problemas = validar(caso)
        if problemas:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "; ".join(problemas))

        clase, probabilidad = model_predict.run(a_diccionario(caso), datos, modelo, umbral)
        return scoring_pb2.Prediccion(
            prediccion=clase,
            probabilidad=probabilidad,
            version_modelo=str(version),
            descripcion="Tiene riesgo de ACV" if clase else "No tiene riesgo de ACV",
        )

    def Predecir(self, request, context):
        return self._predecir(request, context)

    def PredecirLote(self, request, context):
        for caso in request.casos:
            yield self._predecir(caso, context)


def main():
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    scoring_pb2_grpc.add_ScoringServicer_to_server(ServicioScoring(), servidor)
    servidor.add_insecure_port(f"[::]:{PUERTO}")
    servidor.start()
    print(f"Servidor gRPC escuchando en el puerto {PUERTO}")
    servidor.wait_for_termination()


if __name__ == "__main__":
    main()
