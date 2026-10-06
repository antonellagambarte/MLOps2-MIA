"""Lectura y escritura de la metadata del dataset en S3.

Ese archivo (`data_info/data.json`) es el contrato entre el ETL y la API: guarda
las columnas despues del one-hot, las medianas usadas para imputar y la media y
el desvio del escalado, para que la API pueda aplicar las mismas transformaciones
a cada paciente que llega.
"""
import json

import boto3
import botocore.exceptions

import utils.constants as consts


def get_metadata_info(client: boto3.client) -> dict:
    """Trae la metadata del dataset desde S3. Si todavia no existe, devuelve {}."""
    try:
        client.head_object(Bucket=consts.BUCKET, Key=consts.DATA_INFO_PATH)
        result = client.get_object(Bucket=consts.BUCKET, Key=consts.DATA_INFO_PATH)
        text = result["Body"].read().decode()
        data_dict = json.loads(text)
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] not in ("NoSuchKey", "404"):
            raise e
        data_dict = {}
    return data_dict


def save_metadata_info(client: boto3.client, data_dict: dict):
    """Guarda la metadata del dataset en S3."""
    client.put_object(
        Bucket=consts.BUCKET,
        Key=consts.DATA_INFO_PATH,
        Body=json.dumps(data_dict, indent=2),
    )
