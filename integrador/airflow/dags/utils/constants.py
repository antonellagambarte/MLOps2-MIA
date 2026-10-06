"""Rutas y constantes compartidas por los DAGs. Viene del TP de MLOps I."""

# Rutas
S3 = "s3://"
BUCKET = "data"
BUCKET_RAW = "data/raw/"
BUCKET_FINAL = "data/final/"
ORIG_DATA_NAME = "healthcare-dataset-stroke-data.csv"
END_DATA_NAME = "stroke_dummies.csv"
DATA_INFO_PATH = "data_info/data.json"
OPT_DATASET = "/opt/airflow/dataset/"
OPT_DAGS = "/opt/airflow/dags/"
CATEGORICAL_FEATURES_FILE = "files/categorical_features.txt"

MLFLOW_TRACKING_URI = "http://mlflow:5000"
MLFLOW_EXPERIMENT = "acv"
KAGGLE_DATASET_URL = "https://www.kaggle.com/datasets/fedesoriano/stroke-prediction-dataset"

# Modelo
MODEL_NAME = "predictor_acv"
MODEL_ALIAS = "champion"
UMBRAL = 0.4

# Datos
RANDOM_SEED = 42
TARGET_COLUMN = "target_col_stroke"
TARGET_COLUMN_DEFAULT = "stroke"
TEST_SIZE_VARIABLE = "test_size_stroke"
TEST_SIZE_DEFAULT = 0.2
TRAIN = "train"
TEST = "test"

# Grupos etarios para imputar bmi (definidos en Aprendizaje de Maquina I)
BINS_EDAD = [0, 25, 40, 60, 200]
LABELS_EDAD = ["0-25", "25-40", "40-60", "60+"]
