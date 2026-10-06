"""
ETL de los datos de ACV
"""
import datetime
import sys

from airflow.decorators import dag, task

sys.path.append("/opt/airflow/dags")

texto_markdown = """
### Proceso ETL para los datos de ACV

Toma el CSV original del [Stroke Prediction Dataset](https://www.kaggle.com/datasets/fedesoriano/stroke-prediction-dataset),
lo sube a `s3://data/raw/`, genera las variables dummy, lo separa en entrenamiento
y prueba (estratificado), imputa los nulos de `bmi` y estandariza las columnas.
Los datasets finales quedan en `s3://data/final/`.

Todo lo que la API necesita para reproducir estas transformaciones sobre un
paciente nuevo (columnas después del one-hot, medianas de imputación, media y
desvío del escalado) queda en `s3://data/data_info/data.json`.
"""

default_args = {
    "owner": "Antonella Gambarte",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": datetime.timedelta(minutes=5),
    "dagrun_timeout": datetime.timedelta(minutes=15),
}


@dag(
    dag_id="etl_acv",
    description="ETL de los datos de ACV: dummies, split, imputación y escalado.",
    doc_md=texto_markdown,
    tags=["ETL", "ACV"],
    default_args=default_args,
    schedule=None,
    catchup=False,
)
def etl_acv():

    @task(task_id="subir_csv_original")
    def subir_csv_original():
        """Sube el CSV original al Data Lake, si todavía no está."""
        import awswrangler as wr
        import pandas as pd

        import utils.constants as consts

        local_path = f"{consts.OPT_DATASET}{consts.ORIG_DATA_NAME}"
        s3_path = f"{consts.S3}{consts.BUCKET_RAW}{consts.ORIG_DATA_NAME}"

        try:
            wr.s3.head_object(s3_path)
            print(f"El archivo ya existe en S3: {s3_path}")
        except Exception:
            df = pd.read_csv(local_path)
            # id es un identificador de paciente, no una variable predictora.
            df = df.drop(columns=["id"])
            wr.s3.to_csv(df=df, path=s3_path, index=False)
            print(f"Archivo subido a S3: {s3_path}")

    @task(task_id="generar_dummies")
    def generar_dummies():
        """Saca duplicados y convierte las categóricas a one-hot. Deja en
        data.json la lista de columnas antes y después, que la API va a usar."""
        import datetime

        import awswrangler as wr
        import boto3
        import numpy as np
        import pandas as pd
        from airflow.models import Variable

        import utils.constants as consts
        import utils.etl_utils as etl

        data_original_path = f"{consts.S3}{consts.BUCKET_RAW}{consts.ORIG_DATA_NAME}"
        data_end_path = f"{consts.S3}{consts.BUCKET_RAW}{consts.END_DATA_NAME}"

        dataset = wr.s3.read_csv(data_original_path)
        dataset.drop_duplicates(inplace=True, ignore_index=True)

        with open(f"{consts.OPT_DAGS}{consts.CATEGORICAL_FEATURES_FILE}", "r") as f:
            categorical_features = [line.strip() for line in f if line.strip()]
        dataset[categorical_features] = dataset[categorical_features].astype(str)

        # dtype=int para que las dummies queden como 0/1 y no como True/False.
        dataset_with_dummies = pd.get_dummies(
            data=dataset, columns=categorical_features, drop_first=True, dtype=int
        )
        wr.s3.to_csv(df=dataset_with_dummies, path=data_end_path, index=False)

        # Metadata del dataset, para la API
        client = boto3.client("s3")
        data_dict = etl.get_metadata_info(client)

        target_col = Variable.get(consts.TARGET_COLUMN, default_var=consts.TARGET_COLUMN_DEFAULT)
        dataset_log = dataset.drop(columns=target_col)
        dataset_with_dummies_log = dataset_with_dummies.drop(columns=target_col)

        data_dict["columns"] = dataset_log.columns.to_list()
        data_dict["columns_after_dummy"] = dataset_with_dummies_log.columns.to_list()
        data_dict["target_col"] = target_col
        data_dict["categorical_columns"] = categorical_features
        data_dict["columns_dtypes"] = {k: str(v) for k, v in dataset_log.dtypes.to_dict().items()}
        data_dict["columns_dtypes_after_dummy"] = {
            k: str(v) for k, v in dataset_with_dummies_log.dtypes.to_dict().items()
        }
        data_dict["categories_values_per_categorical"] = {
            c: np.sort(dataset_log[c].unique()).tolist() for c in categorical_features
        }
        data_dict["date"] = datetime.datetime.today().strftime("%Y/%m/%d-%H:%M:%S")

        etl.save_metadata_info(client, data_dict)

    @task(task_id="crear_experimento_mlflow")
    def crear_experimento_mlflow():
        """Abre un run de ETL en MLflow y registra los datasets."""
        import datetime

        import awswrangler as wr
        import mlflow
        from airflow.models import Variable

        import utils.constants as consts

        dataset = wr.s3.read_csv(f"{consts.S3}{consts.BUCKET_RAW}{consts.ORIG_DATA_NAME}")
        dataset_with_dummies = wr.s3.read_csv(f"{consts.S3}{consts.BUCKET_RAW}{consts.END_DATA_NAME}")
        target_col = Variable.get(consts.TARGET_COLUMN, default_var=consts.TARGET_COLUMN_DEFAULT)

        mlflow.set_tracking_uri(consts.MLFLOW_TRACKING_URI)
        experiment = mlflow.set_experiment(consts.MLFLOW_EXPERIMENT)

        marca = datetime.datetime.today().strftime("%Y/%m/%d-%H:%M:%S")
        with mlflow.start_run(
            run_name=f"ETL_run_{marca}",
            experiment_id=experiment.experiment_id,
            tags={"experimento": "etl", "dataset": "stroke prediction"},
        ):
            mlflow.log_input(
                mlflow.data.from_pandas(
                    dataset, source=consts.KAGGLE_DATASET_URL,
                    targets=target_col, name="stroke_data_complete",
                ),
                context="Dataset",
            )
            mlflow.log_input(
                mlflow.data.from_pandas(
                    dataset_with_dummies, source=consts.KAGGLE_DATASET_URL,
                    targets=target_col, name="stroke_data_complete_with_dummies",
                ),
                context="Dataset",
            )

    @task(task_id="separar_dataset")
    def separar_dataset():
        """Separa en entrenamiento y prueba, estratificando por la clase (que está
        muy desbalanceada: menos del 5% de positivos)."""
        import awswrangler as wr
        from airflow.models import Variable
        from sklearn.model_selection import train_test_split

        import utils.constants as consts

        dataset = wr.s3.read_csv(f"{consts.S3}{consts.BUCKET_RAW}{consts.END_DATA_NAME}")

        test_size = float(Variable.get(consts.TEST_SIZE_VARIABLE, default_var=consts.TEST_SIZE_DEFAULT))
        target_col = Variable.get(consts.TARGET_COLUMN, default_var=consts.TARGET_COLUMN_DEFAULT)

        X = dataset.drop(columns=target_col)
        y = dataset[[target_col]]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, stratify=y, random_state=consts.RANDOM_SEED
        )

        final = f"{consts.S3}{consts.BUCKET_FINAL}"
        wr.s3.to_csv(df=X_train, path=f"{final}{consts.TRAIN}/X_{consts.TRAIN}.csv", index=False)
        wr.s3.to_csv(df=X_test, path=f"{final}{consts.TEST}/X_{consts.TEST}.csv", index=False)
        wr.s3.to_csv(df=y_train, path=f"{final}{consts.TRAIN}/y_{consts.TRAIN}.csv", index=False)
        wr.s3.to_csv(df=y_test, path=f"{final}{consts.TEST}/y_{consts.TEST}.csv", index=False)

    @task(task_id="imputar_nulos")
    def imputar_nulos():
        """Imputa los nulos de bmi con la mediana de su grupo etario.
        """
        import awswrangler as wr
        import boto3
        import pandas as pd

        import utils.constants as consts
        import utils.etl_utils as etl

        path_train = f"{consts.S3}{consts.BUCKET_FINAL}{consts.TRAIN}/X_{consts.TRAIN}.csv"
        path_test = f"{consts.S3}{consts.BUCKET_FINAL}{consts.TEST}/X_{consts.TEST}.csv"
        X_train = wr.s3.read_csv(path_train)
        X_test = wr.s3.read_csv(path_test)

        def grupo_etario(df):
            return pd.cut(
                df["age"], bins=consts.BINS_EDAD, labels=consts.LABELS_EDAD, right=False
            ).astype(str)

        # Medianas aprendidas solo en train
        medianas = X_train.groupby(grupo_etario(X_train))["bmi"].median()
        mediana_global = float(X_train["bmi"].median())

        for df in (X_train, X_test):
            relleno = grupo_etario(df).map(medianas).astype(float).fillna(mediana_global)
            df["bmi"] = df["bmi"].fillna(relleno)

        wr.s3.to_csv(df=X_train, path=path_train, index=False)
        wr.s3.to_csv(df=X_test, path=path_test, index=False)

        client = boto3.client("s3")
        data_dict = etl.get_metadata_info(client)
        data_dict["bmi_bins_edad"] = consts.BINS_EDAD
        data_dict["bmi_labels_edad"] = consts.LABELS_EDAD
        data_dict["bmi_mediana_por_grupo"] = {k: float(v) for k, v in medianas.items()}
        data_dict["bmi_mediana_global"] = mediana_global
        etl.save_metadata_info(client, data_dict)

    @task(task_id="normalizar")
    def normalizar():
        """Estandariza las columnas: fit en train, transform en test. Deja la media
        y el desvío en data.json y completa el run de ETL en MLflow."""
        import awswrangler as wr
        import boto3
        import mlflow
        import pandas as pd
        from sklearn.preprocessing import StandardScaler

        import utils.constants as consts
        import utils.etl_utils as etl

        path_train = f"{consts.S3}{consts.BUCKET_FINAL}{consts.TRAIN}/X_{consts.TRAIN}.csv"
        path_test = f"{consts.S3}{consts.BUCKET_FINAL}{consts.TEST}/X_{consts.TEST}.csv"
        X_train = wr.s3.read_csv(path_train)
        X_test = wr.s3.read_csv(path_test)

        sc_X = StandardScaler(with_mean=True, with_std=True)
        X_train = pd.DataFrame(sc_X.fit_transform(X_train), columns=X_train.columns)
        X_test = pd.DataFrame(sc_X.transform(X_test), columns=X_test.columns)

        wr.s3.to_csv(df=X_train, path=path_train, index=False)
        wr.s3.to_csv(df=X_test, path=path_test, index=False)

        client = boto3.client("s3")
        data_dict = etl.get_metadata_info(client)
        data_dict["standard_scaler_mean"] = sc_X.mean_.tolist()
        data_dict["standard_scaler_std"] = sc_X.scale_.tolist()
        etl.save_metadata_info(client, data_dict)

        mlflow.set_tracking_uri(consts.MLFLOW_TRACKING_URI)
        experiment = mlflow.set_experiment(consts.MLFLOW_EXPERIMENT)
        ultimo_etl = mlflow.search_runs(
            [experiment.experiment_id],
            filter_string="tags.experimento = 'etl'",
            order_by=["start_time DESC"],
            max_results=1,
            output_format="list",
        )[0]

        with mlflow.start_run(run_id=ultimo_etl.info.run_id):
            mlflow.log_param("Train observations", X_train.shape[0])
            mlflow.log_param("Test observations", X_test.shape[0])
            mlflow.log_param("Standard Scaler feature names", list(sc_X.feature_names_in_))
            mlflow.log_param("Standard Scaler mean values", sc_X.mean_.round(4).tolist())
            mlflow.log_param("Standard Scaler scale values", sc_X.scale_.round(4).tolist())

    (
        subir_csv_original()
        >> generar_dummies()
        >> crear_experimento_mlflow()
        >> separar_dataset()
        >> imputar_nulos()
        >> normalizar()
    )


dag = etl_acv()
