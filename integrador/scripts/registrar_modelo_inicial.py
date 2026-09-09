"""
Sube a MLflow el modelo entrenado en Aprendizaje de Máquina I (el mismo que sirve
el mini-TP 1) y lo deja marcado como champion.

Es un puente de arranque: deja la plataforma con un modelo servible antes de que
exista el DAG de entrenamiento. Cuando ese DAG corra, va a registrar la versión 2
y a mover el alias champion solo, sin que este script vuelva a usarse.

Se corre una vez, desde la raíz del repo y con el stack levantado:

    uv run python integrador/scripts/registrar_modelo_inicial.py
"""
import json
import os
import sys
from pathlib import Path

# MLflow imprime emojis y la consola de Windows usa cp1252, que no los soporta.
sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[2]
TP1 = RAIZ / "mini-tps" / "tp1"

# El pipeline serializado referencia las clases de preprocesamiento.py por su
# módulo, así que joblib necesita poder importarlo para deserializarlo.
sys.path.insert(0, str(TP1))

# Coordenadas de la plataforma vistas desde afuera de Docker (puertos publicados).
os.environ.setdefault("MLFLOW_TRACKING_URI", "http://localhost:5000")
os.environ.setdefault("MLFLOW_S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "mlops")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "mlops12345")

import joblib  # noqa: E402
import mlflow  # noqa: E402
import pandas as pd  # noqa: E402
from mlflow.tracking import MlflowClient  # noqa: E402

NOMBRE_REGISTRADO = "predictor_acv"
EXPERIMENTO = "acv"

# Un paciente de ejemplo. MLflow lo usa para deducir el esquema de entrada y
# salida del modelo, que queda guardado junto al artefacto.
PACIENTE_EJEMPLO = pd.DataFrame([{
    "gender": "Male",
    "age": 67.0,
    "hypertension": 0,
    "heart_disease": 1,
    "ever_married": "Yes",
    "work_type": "Private",
    "Residence_type": "Urban",
    "avg_glucose_level": 228.69,
    "bmi": 36.6,
    "smoking_status": "formerly smoked",
}])


def main():
    contenido = joblib.load(TP1 / "modelo" / "modelo.joblib")
    pipeline = contenido["pipeline"]
    umbral = contenido["umbral"]
    features = contenido["features"]

    datos = json.loads((TP1 / "modelo" / "metricas.json").read_text(encoding="utf-8"))
    metricas = datos["metricas"]

    mlflow.set_experiment(EXPERIMENTO)

    with mlflow.start_run(run_name="modelo_aprendizaje_maquina_i") as run:
        mlflow.log_params({
            "algoritmo": "XGBoost",
            "umbral": umbral,
            "version_original": datos["version"],
            "origen": "entrenado en Aprendizaje de Maquina I, importado a la plataforma",
        })
        mlflow.log_metrics(metricas)
        mlflow.log_dict({"features": features}, "features.json")

        mlflow.sklearn.log_model(
            sk_model=pipeline,
            name="model",
            # Viaja junto al modelo: sin esto, quien lo cargue no puede
            # deserializar el ImputadorBMIPorEdad ni la función limpiar.
            code_paths=[str(TP1 / "preprocesamiento.py")],
            # MLflow 3 serializa con skops por defecto, que no soporta clases ni
            # funciones propias: el pipeline tiene ImputadorBMIPorEdad y limpiar.
            serialization_format="cloudpickle",
            input_example=PACIENTE_EJEMPLO,
            registered_model_name=NOMBRE_REGISTRADO,
        )
        print(f"run_id: {run.info.run_id}")

    cliente = MlflowClient()
    version = max(
        int(v.version)
        for v in cliente.search_model_versions(f"name='{NOMBRE_REGISTRADO}'")
    )

    # El umbral viaja como tag de la versión: así la API lo lee del registro en
    # vez de tenerlo hardcodeado, y cada versión puede tener el suyo.
    cliente.set_model_version_tag(NOMBRE_REGISTRADO, str(version), "umbral", str(umbral))
    cliente.set_registered_model_alias(NOMBRE_REGISTRADO, "champion", version)

    print(f"registrado {NOMBRE_REGISTRADO} version {version} con alias champion")
    print(f"la API lo va a pedir como: models:/{NOMBRE_REGISTRADO}@champion")


if __name__ == "__main__":
    main()
