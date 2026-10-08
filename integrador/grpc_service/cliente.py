"""Cliente de prueba del servicio gRPC: unary, server-streaming y latencia contra REST.

"""
import os
import statistics
import time

import grpc
import requests

import scoring_pb2
import scoring_pb2_grpc
from mapas import INVERSOS

DESTINO = os.getenv("GRPC_DESTINO", "grpc:50051")
REST = os.getenv("REST_URL", "http://fastapi:8800/v1/predict")
N = int(os.getenv("N_MEDICIONES", "100"))

PACIENTE = {
    "gender": "Female",
    "age": 67,
    "hypertension": 0,
    "heart_disease": 1,
    "ever_married": "Yes",
    "work_type": "Private",
    "Residence_type": "Urban",
    "avg_glucose_level": 228.69,
    "bmi": 36.6,
    "smoking_status": "formerly smoked",
}


def mensaje(paciente):
    """Los mismos mapas que usa el servidor, en la direccion texto -> enum."""
    caso = scoring_pb2.Caracteristicas(
        gender=INVERSOS["gender"][paciente["gender"]],
        age=paciente["age"],
        hypertension=paciente["hypertension"],
        heart_disease=paciente["heart_disease"],
        ever_married=INVERSOS["ever_married"][paciente["ever_married"]],
        work_type=INVERSOS["work_type"][paciente["work_type"]],
        Residence_type=INVERSOS["Residence_type"][paciente["Residence_type"]],
        avg_glucose_level=paciente["avg_glucose_level"],
        smoking_status=INVERSOS["smoking_status"][paciente["smoking_status"]],
    )
    if paciente.get("bmi") is not None:
        caso.bmi = paciente["bmi"]
    return caso


def medir(llamada):
    for _ in range(20):
        llamada()  # calentar la conexion; estas no se cuentan
    tiempos = []
    for _ in range(N):
        inicio = time.perf_counter()
        llamada()
        tiempos.append((time.perf_counter() - inicio) * 1000)
    return statistics.mean(tiempos), statistics.median(tiempos), sorted(tiempos)[int(N * 0.95) - 1]


def main():
    stub = scoring_pb2_grpc.ScoringStub(grpc.insecure_channel(DESTINO))
    caso = mensaje(PACIENTE)

    print(f"--- unary: Predecir ({DESTINO}) ---")
    respuesta = stub.Predecir(caso)
    print(f"  prediccion {respuesta.prediccion} | probabilidad {respuesta.probabilidad} | "
          f"modelo v{respuesta.version_modelo} | {respuesta.descripcion}")

    print("--- server-streaming: PredecirLote (3 casos) ---")
    lote = scoring_pb2.LoteCaracteristicas(casos=[caso] * 3)
    for i, parcial in enumerate(stub.PredecirLote(lote), 1):
        print(f"  {i}: prediccion {parcial.prediccion} | probabilidad {parcial.probabilidad}")

    print(f"--- latencia, n={N} ---")
    media_grpc, p50_grpc, p95_grpc = medir(lambda: stub.Predecir(caso))
    media_rest, p50_rest, p95_rest = medir(lambda: requests.post(REST, json=PACIENTE))
    print(f"  gRPC            media {media_grpc:6.2f} ms | p50 {p50_grpc:6.2f} | p95 {p95_grpc:6.2f}")
    print(f"  REST            media {media_rest:6.2f} ms | p50 {p50_rest:6.2f} | p95 {p95_rest:6.2f}")
    print(f"  REST/gRPC: {media_rest / media_grpc:.2f}x")


if __name__ == "__main__":
    main()
