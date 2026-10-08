"""Puntua cada paciente que llega al topic y vigila el drift por ventana."""
import io
import json
import os
import threading
import time
from collections import deque
from datetime import date

import boto3
import mlflow
import numpy as np
from kafka import KafkaConsumer, KafkaProducer
from mlflow.tracking import MlflowClient
import joblib
import pandas as pd

from src import predict as model_predict

BROKER = os.getenv("REDPANDA_BROKER", "redpanda:9092")
TOPIC_PACIENTES = os.getenv("TOPIC_PACIENTES", "pacientes")
TOPIC_ALERTAS = os.getenv("TOPIC_ALERTAS", "alertas")
NOMBRE_MODELO = os.getenv("NOMBRE_MODELO", "predictor_acv")
ALIAS_MODELO = os.getenv("ALIAS_MODELO", "champion")
BUCKET = os.getenv("BUCKET_DATOS", "data")

VENTANA_SEG = float(os.getenv("VENTANA_SEG", "1.0"))
CORTE = int(os.getenv("CORTE", "200"))
LOTE_LAKE = int(os.getenv("LOTE_LAKE", "200"))
MEDIA_GLUCOSA_ENTRENAMIENTO = float(os.getenv("MEDIA_GLUCOSA_ENTRENAMIENTO", "106"))
UMBRAL_DRIFT = float(os.getenv("UMBRAL_DRIFT", "130"))
INTERVALO_RECARGA = float(os.getenv("INTERVALO_RECARGA_SEG", "30"))

# (modelo, version, umbral, datos). Se reemplaza entero, no campo por campo, para que
# el bucle de eventos nunca lea el modelo nuevo con la metadata vieja.
estado = None


def cargar_modelo():
    """Pregunta a MLflow que version es champion y baja ese modelo del lake."""
    version = MlflowClient().get_model_version_by_alias(NOMBRE_MODELO, ALIAS_MODELO)
    s3 = boto3.client("s3")

    key = f"models/v{version.version}/predictor_acv.pkl"
    modelo = joblib.load(io.BytesIO(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()))

    datos = json.loads(s3.get_object(Bucket=BUCKET, Key="data_info/data.json")["Body"].read())
    datos["standard_scaler_mean"] = np.array(datos["standard_scaler_mean"])
    datos["standard_scaler_std"] = np.array(datos["standard_scaler_std"])

    umbral = float(version.tags.get("umbral", 0.5))
    print(f"Modelo cargado del lake: s3://{BUCKET}/{key} | version {version.version} | umbral {umbral}")
    return modelo, version.version, umbral, datos


def vigilar_champion():
    """Recarga el modelo si el DAG promovio otro champion, sin frenar el consumo."""
    global estado
    while True:
        time.sleep(INTERVALO_RECARGA)
        try:
            version = MlflowClient().get_model_version_by_alias(
                NOMBRE_MODELO, ALIAS_MODELO
            ).version
            if version != estado[1]:
                estado = cargar_modelo()
        except Exception as error:
            print(f"No se pudo chequear el champion: {error}")


def proxima_parte(s3, prefijo):
    """Sigue numerando donde quedo, para no pisar partes de una corrida anterior."""
    respuesta = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefijo)
    return respuesta.get("KeyCount", 0)


def aterrizar_en_el_lake(s3, eventos):
    """Deja el lote de eventos puntuados en la zona raw, particionado por fecha."""
    prefijo = f"raw/eventos/fecha={date.today().isoformat()}/"
    key = f"{prefijo}parte-{proxima_parte(s3, prefijo):03d}.parquet"

    buffer = io.BytesIO()
    pd.DataFrame(eventos).to_parquet(buffer, index=False)
    s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())
    print(f"  -> {len(eventos)} eventos a s3://{BUCKET}/{key}")


def metricas(ventana):
    """Throughput, p95 y media de glucosa sobre lo que hay en la ventana."""
    tiempos = [e["t"] for e in ventana]
    span = max(tiempos) - min(tiempos)
    return {
        "eventos": len(ventana),
        "throughput": len(ventana) / span if span > 0 else float(len(ventana)),
        "p95": float(np.percentile([e["latencia_ms"] for e in ventana], 95)),
        "media_glucosa": float(np.mean([e["glucosa"] for e in ventana])),
    }


def main():
    global estado
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
    estado = cargar_modelo()
    threading.Thread(target=vigilar_champion, daemon=True).start()
    s3 = boto3.client("s3")

    consumidor = KafkaConsumer(
        TOPIC_PACIENTES,
        bootstrap_servers=BROKER,
        group_id="worker-acv",
        auto_offset_reset="earliest",
        value_deserializer=lambda b: json.loads(b.decode()),
    )
    productor = KafkaProducer(
        bootstrap_servers=BROKER,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    print(f"Escuchando '{TOPIC_PACIENTES}'. Las alertas salen por '{TOPIC_ALERTAS}'.")

    ventana = deque()
    pendientes = []
    procesados = 0

    for mensaje in consumidor:
        # Una sola lectura por evento: el vigilante pudo haberlo cambiado.
        modelo, version, umbral, datos = estado
        paciente = mensaje.value["paciente"]
        t_evento = mensaje.value["t"]

        t0 = time.perf_counter()
        clase, probabilidad = model_predict.run(paciente, datos, modelo, umbral)
        latencia_ms = (time.perf_counter() - t0) * 1000

        ventana.append({
            "t": t_evento,
            "glucosa": paciente["avg_glucose_level"],
            "prediccion": clase,
            "latencia_ms": latencia_ms,
        })
        while ventana and t_evento - ventana[0]["t"] > VENTANA_SEG:
            ventana.popleft()

        pendientes.append({
            **paciente,
            "prediccion": clase,
            "probabilidad": probabilidad,
            "version_modelo": str(version),
            "t": t_evento,
        })
        procesados += 1

        if procesados % CORTE == 0:
            m = metricas(ventana)
            print(
                f"evento {procesados:5d} | ventana={m['eventos']:3d} "
                f"| {m['throughput']:6.0f} ev/s | p95 {m['p95']:6.2f} ms "
                f"| glucosa media {m['media_glucosa']:6.1f}"
            )
            if m["media_glucosa"] > UMBRAL_DRIFT:
                alerta = {
                    "tipo": "drift_glucosa",
                    "media_ventana": m["media_glucosa"],
                    "media_entrenamiento": MEDIA_GLUCOSA_ENTRENAMIENTO,
                    "umbral": UMBRAL_DRIFT,
                    "eventos_en_ventana": m["eventos"],
                    "evento": procesados,
                    "t": t_evento,
                }
                productor.send(TOPIC_ALERTAS, alerta)
                productor.flush()
                print(f"  !! ALERTA de drift: {m['media_glucosa']:.1f} > {UMBRAL_DRIFT}")

        if len(pendientes) >= LOTE_LAKE:
            aterrizar_en_el_lake(s3, pendientes)
            pendientes = []


if __name__ == "__main__":
    main()
