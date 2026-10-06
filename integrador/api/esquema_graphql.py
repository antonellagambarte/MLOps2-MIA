"""
Esquema GraphQL con los metadatos del modelo.
División de roles con REST: REST predice (POST /v1/predict), GraphQL responde
qué modelo está corriendo y con qué métricas.
"""
import os

import strawberry
from mlflow.tracking import MlflowClient

NOMBRE_MODELO = os.getenv("NOMBRE_MODELO", "predictor_acv")
ALIAS_MODELO = os.getenv("ALIAS_MODELO", "champion")


@strawberry.type
class Metrics:
    auc: float
    accuracy: float
    f1: float
    precision: float
    recall: float


@strawberry.type
class Model:
    name: str
    version: str
    # Private: lo necesita el resolver de metrics
    run_id: strawberry.Private[str]

    @strawberry.field
    def metrics(self) -> Metrics:
        valores = MlflowClient().get_run(self.run_id).data.metrics
        return Metrics(
            auc=valores["roc_auc"],
            accuracy=valores["accuracy"],
            f1=valores["f1_score"],
            precision=valores["precision"],
            recall=valores["recall"],
        )


@strawberry.type
class Query:
    @strawberry.field
    def model(self) -> Model:
        version = MlflowClient().get_model_version_by_alias(
            NOMBRE_MODELO, ALIAS_MODELO
        )
        return Model(
            name=NOMBRE_MODELO,
            version=version.version,
            run_id=version.run_id,
        )


schema = strawberry.Schema(Query)
