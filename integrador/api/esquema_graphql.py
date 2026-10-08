"""
Esquema GraphQL sobre el mismo modelo que sirve REST.
"""
from typing import Optional

import strawberry
from mlflow.tracking import MlflowClient
from pydantic import ValidationError

import modelo
from contrato import Caracteristicas


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
            modelo.NOMBRE_MODELO, modelo.ALIAS_MODELO
        )
        return Model(
            name=modelo.NOMBRE_MODELO,
            version=version.version,
            run_id=version.run_id,
        )


@strawberry.input
class PacienteInput:
    gender: str
    age: float
    hypertension: int
    heart_disease: int
    ever_married: str
    work_type: str
    residence_type: str
    avg_glucose_level: float
    smoking_status: str
    bmi: Optional[float] = None


@strawberry.type
class Prediccion:
    prediccion: int
    probabilidad: float
    version_modelo: str
    descripcion: str


@strawberry.type
class Mutation:
    @strawberry.mutation
    def predecir(self, paciente: PacienteInput, info: strawberry.Info) -> Prediccion:
        # El .proto de gRPC tipa las categoricas con enum; GraphQL las recibe como
        # texto, asi que la validacion la hace el mismo Pydantic que usa REST.
        try:
            validado = Caracteristicas(
                gender=paciente.gender,
                age=paciente.age,
                hypertension=paciente.hypertension,
                heart_disease=paciente.heart_disease,
                ever_married=paciente.ever_married,
                work_type=paciente.work_type,
                Residence_type=paciente.residence_type,
                avg_glucose_level=paciente.avg_glucose_level,
                bmi=paciente.bmi,
                smoking_status=paciente.smoking_status,
            )
        except ValidationError as error:
            problemas = "; ".join(
                f"{e['loc'][0]}: {e['msg']}" for e in error.errors()
            )
            raise ValueError(problemas)

        clase, probabilidad, version, descripcion = modelo.predecir(validado.model_dump())

        # Igual que REST: el chequeo del champion corre despues de responder, no en el
        # camino de la peticion. Strawberry pasa las BackgroundTasks de FastAPI por context.
        info.context["background_tasks"].add_task(modelo.check_model)

        return Prediccion(
            prediccion=clase,
            probabilidad=probabilidad,
            version_modelo=version,
            descripcion=descripcion,
        )


schema = strawberry.Schema(Query, Mutation)
