"""Emite pacientes al topic, tomandolos de la zona raw del lake."""
import io
import json
import os
import random
import time

import boto3
import pandas as pd
from kafka import KafkaProducer

BROKER = os.getenv("REDPANDA_BROKER", "redpanda:9092")
TOPIC = os.getenv("TOPIC_PACIENTES", "pacientes")
BUCKET = os.getenv("BUCKET_DATOS", "data")
CSV_RAW = os.getenv("CSV_RAW", "raw/acv/healthcare-dataset-stroke-data.csv")
N = int(os.getenv("N_EVENTOS", "800"))
PAUSA = float(os.getenv("PAUSA", "0.02"))
DRIFT_GLUCOSA = float(os.getenv("DRIFT_GLUCOSA", "50"))


def cargar_pacientes():
    cuerpo = boto3.client("s3").get_object(Bucket=BUCKET, Key=CSV_RAW)["Body"].read()
    pacientes = pd.read_csv(io.BytesIO(cuerpo)).drop(columns=["id", "stroke"], errors="ignore")
    return pacientes.astype(object).where(pacientes.notna(), None)


def main():
    pacientes = cargar_pacientes()
    productor = KafkaProducer(
        bootstrap_servers=BROKER,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    print(f"Emitiendo {N} pacientes al topic '{TOPIC}' ({len(pacientes)} disponibles en el lake)")

    for i in range(N):
        paciente = pacientes.iloc[random.randrange(len(pacientes))].to_dict()
        if i >= N // 2:
            paciente["avg_glucose_level"] += DRIFT_GLUCOSA   # drift a mitad de camino
        productor.send(TOPIC, {"paciente": paciente, "t": time.time()})
        time.sleep(PAUSA)

    productor.flush()
    print(f"Listos {N} eventos. El drift arranco en el evento {N // 2}.")


if __name__ == "__main__":
    main()
