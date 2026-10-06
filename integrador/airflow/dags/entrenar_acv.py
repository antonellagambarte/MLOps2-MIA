"""Entrena el XGBoost de ACV y lo registra en MLflow (champion / challenger)."""
import datetime
import sys

from airflow.decorators import dag, task

sys.path.append("/opt/airflow/dags")

texto_markdown = """
### Entrenamiento del modelo de ACV

Lee los datos que dejó `etl_acv` en `s3://data/final/`, entrena un XGBoost con los
hiperparámetros encontrados con Optuna, evalúa sobre test
y registra el modelo en MLflow como `predictor_acv`.
"""

# Encontrados con Optuna en Aprendizaje de Máquina I
HIPERPARAMETROS = {
    "n_estimators": 159,
    "max_depth": 2,
    "learning_rate": 0.025114838333174724,
    "subsample": 0.6687725508326033,
    "colsample_bytree": 0.8494426687781611,
    "gamma": 0.8191119399276152,
    "reg_alpha": 4.250546809865612,
    "reg_lambda": 3.0479748148985557,
    "scale_pos_weight": 7.78234395395035,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "random_state": 42,
}

default_args = {
    "owner": "Antonella Gambarte",
    "depends_on_past": False,
    "retries": 0,
    "retry_delay": datetime.timedelta(minutes=5),
    "dagrun_timeout": datetime.timedelta(minutes=15),
}


@dag(
    dag_id="entrenar_acv",
    description="Entrena el XGBoost de ACV y lo registra en MLflow (champion / challenger).",
    doc_md=texto_markdown,
    tags=["Train", "ACV", "Register"],
    default_args=default_args,
    schedule=None,
    catchup=False,
)
def entrenar_acv():

    @task(task_id="entrenar_y_registrar")
    def entrenar_y_registrar():
        import logging

        import awswrangler as wr
        import mlflow
        from mlflow.entities import ViewType
        from mlflow.exceptions import RestException
        from mlflow.tracking import MlflowClient
        from sklearn.metrics import (
            accuracy_score, f1_score, precision_score, recall_score, roc_auc_score,
        )
        from xgboost import XGBClassifier

        import utils.constants as consts

        log = logging.getLogger("airflow.task")

        def _entrenar():
            final = f"{consts.S3}{consts.BUCKET_FINAL}"
            X_train = wr.s3.read_csv(f"{final}{consts.TRAIN}/X_{consts.TRAIN}.csv")
            y_train = wr.s3.read_csv(f"{final}{consts.TRAIN}/y_{consts.TRAIN}.csv").squeeze()
            X_test = wr.s3.read_csv(f"{final}{consts.TEST}/X_{consts.TEST}.csv")
            y_test = wr.s3.read_csv(f"{final}{consts.TEST}/y_{consts.TEST}.csv").squeeze()
            log.info(f"_entrenar: train {X_train.shape}, test {X_test.shape}")

            modelo = XGBClassifier(**HIPERPARAMETROS)
            modelo.fit(X_train, y_train)

            probabilidades = modelo.predict_proba(X_test)[:, 1]
            predicciones = (probabilidades >= consts.UMBRAL).astype(int)

            metricas = {
                "accuracy": accuracy_score(y_test, predicciones),
                "precision": precision_score(y_test, predicciones, zero_division=0),
                "recall": recall_score(y_test, predicciones),
                "f1_score": f1_score(y_test, predicciones),
                "roc_auc": roc_auc_score(y_test, probabilidades),
            }
            log.info(f"_entrenar: métricas {metricas}")
            return modelo, metricas, X_train.head(3)

        def _registrar(modelo, metricas, ejemplo):
            mlflow.set_tracking_uri(consts.MLFLOW_TRACKING_URI)
            client = MlflowClient()

            borrados = [
                e for e in client.search_experiments(view_type=ViewType.DELETED_ONLY)
                if e.name == consts.MLFLOW_EXPERIMENT
            ]
            if borrados:
                client.restore_experiment(borrados[0].experiment_id)
            mlflow.set_experiment(consts.MLFLOW_EXPERIMENT)

            with mlflow.start_run(run_name="xgboost-challenger") as run:
                run_id = run.info.run_id
                mlflow.log_params(HIPERPARAMETROS)
                mlflow.log_param("umbral", consts.UMBRAL)
                mlflow.log_metrics(metricas)
                mlflow.sklearn.log_model(
                    sk_model=modelo,
                    name="model",
                    input_example=ejemplo,
                    serialization_format="cloudpickle",
                    registered_model_name=consts.MODEL_NAME,
                )

            versiones = client.search_model_versions(
                f"name = '{consts.MODEL_NAME}' and run_id = '{run_id}'"
            )
            challenger = sorted(versiones, key=lambda m: int(m.version))[-1].version

            client.set_model_version_tag(consts.MODEL_NAME, challenger, "stage", "challenger")
            client.set_model_version_tag(consts.MODEL_NAME, challenger, "umbral", str(consts.UMBRAL))
            client.set_model_version_tag(consts.MODEL_NAME, challenger, "model_class", type(modelo).__name__)
            for nombre, valor in metricas.items():
                client.set_model_version_tag(consts.MODEL_NAME, challenger, nombre, repr(float(valor)))
            client.set_registered_model_alias(consts.MODEL_NAME, "challenger", challenger)

            def _promover():
                client.set_registered_model_alias(consts.MODEL_NAME, consts.MODEL_ALIAS, challenger)
                client.set_model_version_tag(consts.MODEL_NAME, challenger, "stage", "champion")

            try:
                champion = client.get_model_version_by_alias(consts.MODEL_NAME, consts.MODEL_ALIAS)
                f1_champion = float(champion.tags.get("f1_score", 0.0))
                log.info(
                    f"_registrar: champion v{champion.version} f1={f1_champion} | "
                    f"challenger v{challenger} f1={metricas['f1_score']}"
                )
                if metricas["f1_score"] > f1_champion:
                    _promover()
                    log.info(f"_registrar: PROMOVIDO challenger v{challenger} -> CHAMPION")
                else:
                    log.info(f"_registrar: se mantiene CHAMPION v{champion.version}")
            except RestException:
                _promover()
                log.info(f"_registrar: no había champion, v{challenger} pasa a CHAMPION")

        modelo, metricas, ejemplo = _entrenar()
        _registrar(modelo, metricas, ejemplo)

    entrenar_y_registrar()


dag = entrenar_acv()
