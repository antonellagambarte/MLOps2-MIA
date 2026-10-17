# -*- coding: utf-8 -*-
"""Compara la latencia de REST, GraphQL y gRPC desde máquina.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.join(AQUI, "grpc_service", "scoring.proto")
SALIDA = os.path.join(AQUI, "frontend", "public", "medicion.json")

REST_URL = "http://localhost:8800/v1/predict"
GRAPHQL_URL = "http://localhost:8800/graphql"
GRPC_HOST = "localhost:50051"

PACIENTE = {
    "gender": "Female", "age": 67, "hypertension": 0, "heart_disease": 1,
    "ever_married": "Yes", "work_type": "Private", "Residence_type": "Urban",
    "avg_glucose_level": 228.69, "bmi": 36.6, "smoking_status": "formerly smoked",
}

CAMPOS_GRAPHQL = {
    "heart_disease": "heartDisease", "ever_married": "everMarried",
    "work_type": "workType", "Residence_type": "residenceType",
    "avg_glucose_level": "avgGlucoseLevel", "smoking_status": "smokingStatus",
}
MUTACION = """mutation($paciente: PacienteInput!) {
  predecir(paciente: $paciente) { probabilidad }
}"""


def stubs():
    destino = tempfile.mkdtemp(prefix="stubs_")
    subprocess.run(
        [sys.executable, "-m", "grpc_tools.protoc",
         "-I", os.path.dirname(PROTO), "--python_out", destino,
         "--grpc_python_out", destino, PROTO],
        check=True,
    )
    sys.path.insert(0, destino)
    sys.path.insert(0, os.path.join(AQUI, "grpc_service"))


def medir(nombre, una_llamada, vueltas):
    """Un bloque de N llamadas y el promedio por llamada, en milisegundos."""
    una_llamada()

    empezo = time.perf_counter()
    for _ in range(vueltas):
        probabilidad = una_llamada()
    ms = (time.perf_counter() - empezo) / vueltas * 1000

    print("  %-8s %7.3f ms por llamada    %s" % (nombre, ms, probabilidad))
    return {"ms": ms, "probabilidad": probabilidad}


def main():
    vueltas = int(sys.argv[1]) if len(sys.argv) > 1 else 1000

    stubs()
    import grpc
    import scoring_pb2
    import scoring_pb2_grpc
    from mapas import INVERSOS

    caso = scoring_pb2.Caracteristicas(
        age=PACIENTE["age"],
        hypertension=PACIENTE["hypertension"],
        heart_disease=PACIENTE["heart_disease"],
        avg_glucose_level=PACIENTE["avg_glucose_level"],
        bmi=PACIENTE["bmi"],
        **{campo: INVERSOS[campo][PACIENTE[campo]] for campo in INVERSOS},
    )
    variables = {CAMPOS_GRAPHQL.get(k, k): v for k, v in PACIENTE.items()}

    print("\nLatencia desde esta máquina · %d llamadas por protocolo\n" % vueltas)

    canal = grpc.insecure_channel(GRPC_HOST)
    stub = scoring_pb2_grpc.ScoringStub(canal)
    try:
        resultado = {
            "rest": medir(
                "REST", lambda: requests.post(REST_URL, json=PACIENTE).json()["probabilidad"],
                vueltas),
            "graphql": medir(
                "GraphQL",
                lambda: requests.post(
                    GRAPHQL_URL, json={"query": MUTACION, "variables": {"paciente": variables}},
                ).json()["data"]["predecir"]["probabilidad"],
                vueltas),
            "grpc": medir("gRPC", lambda: stub.Predecir(caso).probabilidad, vueltas),
        }
    finally:
        canal.close()

    probabilidades = {r["probabilidad"] for r in resultado.values()}
    print("\n  los tres devolvieron %s" % ("el mismo número" if len(probabilidades) == 1
                                           else "números DISTINTOS: %s" % probabilidades))

    base = resultado["grpc"]["ms"]
    for nombre, r in resultado.items():
        r["veces"] = r["ms"] / base

    medicion = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "desde": "esta máquina, contra localhost",
        "vueltas": vueltas,
        "coinciden": len(probabilidades) == 1,
        "resumen": [{"id": n, **r} for n, r in resultado.items()],
    }

    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(medicion, f, ensure_ascii=False, indent=2)
    print("  escrito en frontend/public/medicion.json\n")


if __name__ == "__main__":
    main()
