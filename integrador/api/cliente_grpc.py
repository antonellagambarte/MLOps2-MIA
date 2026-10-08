"""Cliente del servicio gRPC de inferencia.

La API no predice: valida con Pydantic, traduce al contrato del .proto y delega.
Es el diseno del mini-TP 3, con REST como puerta externa y gRPC como motor interno.
"""
import os

import grpc
from fastapi import HTTPException

import scoring_pb2
import scoring_pb2_grpc
from mapas import INVERSOS

DESTINO = os.getenv("GRPC_DESTINO", "grpc:50051")
# Sin timeout, un servicio colgado deja el request esperando para siempre.
TIMEOUT = float(os.getenv("GRPC_TIMEOUT_SEG", "5"))

# Un canal para todo el proceso: es thread-safe y reconecta solo.
_canal = grpc.insecure_channel(DESTINO)
_stub = scoring_pb2_grpc.ScoringStub(_canal)

ESTADOS_HTTP = {
    grpc.StatusCode.INVALID_ARGUMENT: 422,
    grpc.StatusCode.UNAVAILABLE: 503,
    grpc.StatusCode.DEADLINE_EXCEEDED: 504,
}


def _mensaje(paciente):
    """El espejo de a_diccionario() del servidor: texto a enum."""
    mensaje = scoring_pb2.Caracteristicas(
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
    # Aparte porque en el .proto bmi es optional: no asignarlo es "no vino".
    if paciente["bmi"] is not None:
        mensaje.bmi = paciente["bmi"]
    return mensaje


def predecir(paciente):
    """Pide la prediccion al servicio y traduce su codigo de error a HTTP."""
    try:
        return _stub.Predecir(_mensaje(paciente), timeout=TIMEOUT)
    except grpc.RpcError as error:
        raise HTTPException(
            status_code=ESTADOS_HTTP.get(error.code(), 502),
            detail=f"El servicio de inferencia en {DESTINO} respondio "
                   f"{error.code().name}: {error.details()}",
        )


def verificar_disponible():
    """Para /health: el canal llega al servicio de inferencia."""
    try:
        grpc.channel_ready_future(_canal).result(timeout=TIMEOUT)
    except grpc.FutureTimeoutError:
        raise HTTPException(
            status_code=503,
            detail=f"Sin conexion con el servicio de inferencia en {DESTINO}",
        )
