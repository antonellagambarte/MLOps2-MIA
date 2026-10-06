"""
Transforma un paciente crudo en la fila que espera el modelo, y predice.

Reproduce, paso a paso, lo que el DAG etl_acv hizo sobre el dataset completo,
usando los valores que ese DAG dejó en data.json
"""
import pandas as pd


def run(features_dict, data_dict, model, umbral, debug=False):
    features_df = pd.DataFrame(features_dict, index=[0])
    features_df["bmi"] = pd.to_numeric(features_df["bmi"], errors="coerce")

    if pd.isna(features_df.loc[0, "bmi"]):
        grupo = pd.cut(
            features_df["age"],
            bins=data_dict["bmi_bins_edad"],
            labels=data_dict["bmi_labels_edad"],
            right=False,
        ).astype(str).iloc[0]
        features_df.loc[0, "bmi"] = data_dict["bmi_mediana_por_grupo"].get(
            grupo, data_dict["bmi_mediana_global"]
        )

    for categorical_col in data_dict["categorical_columns"]:
        features_df[categorical_col] = features_df[categorical_col].astype(str)
        categories = data_dict["categories_values_per_categorical"][categorical_col]
        features_df[categorical_col] = pd.Categorical(
            features_df[categorical_col], categories=categories
        )

    if debug:
        print("\n--- 1. Después de forzar tipos categóricos ---")
        features_df.info()

    features_df = pd.get_dummies(
        data=features_df,
        columns=data_dict["categorical_columns"],
        drop_first=True,
        dtype=int,
    )
    features_df.columns = features_df.columns.str.replace(" ", "_", regex=False)

    if debug:
        print("\n--- 2. Después de get_dummies ---")
        features_df.info()

    features_df = features_df.reindex(columns=data_dict["columns_after_dummy"], fill_value=0)

    if debug:
        print("\n--- 3. Después de reindexar ---")
        print(features_df.head(1))

    features_df = (features_df - data_dict["standard_scaler_mean"]) / data_dict["standard_scaler_std"]

    probabilidad = float(model.predict_proba(features_df)[0, 1])
    prediccion = int(probabilidad >= umbral)

    if debug:
        print(f"\nProbabilidad: {probabilidad:.4f} · umbral {umbral} · predicción {prediccion}")

    return prediccion, probabilidad
