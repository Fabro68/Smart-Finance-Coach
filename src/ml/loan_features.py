"""
Definiciones compartidas para el modelo de riesgo crediticio (Semana 18).

- Carga de Gold loan_ml_dataset con deltalake (entorno local, sin Spark).
- Configuraciones de variables: full, full_no_rate y reduced.
- Preprocesamiento: One-Hot para categoricas y escalado opcional para
  numericas. El preprocesador se ajusta SOLO con el split train dentro
  del pipeline de entrenamiento.

Ver docs/ml_feature_dictionary.md (secciones 4, 6 y 11).
"""

from pathlib import Path

import pandas as pd
from deltalake import DeltaTable
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOAN_ML_PATH = PROJECT_ROOT / "data" / "gold" / "loan_ml_dataset"

ID_COLUMN = "loan_id"
SPLIT_COLUMN = "split"
TARGET = "default"
SPLITS = ("train", "validation", "test")

CATEGORICAL_ALL = [
    "education",
    "employment_type",
    "marital_status",
    "loan_purpose",
]

NUMERIC_ALL = [
    "age",
    "income",
    "loan_amount",
    "loan_to_income_ratio",
    "estimated_monthly_payment",
    "payment_to_income_ratio",
    "credit_score",
    "months_employed",
    "num_credit_lines",
    "interest_rate",
    "loan_term",
    "dti_ratio",
    "has_mortgage",
    "has_dependents",
    "has_cosigner",
]

# Variables con posible fuga: interest_rate y sus derivadas (seccion 6).
RATE_DERIVED = [
    "interest_rate",
    "estimated_monthly_payment",
    "payment_to_income_ratio",
]

FEATURE_SETS = {
    # Todas las variables candidatas.
    "full": {
        "numeric": NUMERIC_ALL,
        "categorical": CATEGORICAL_ALL,
    },
    # Prueba de fuga: sin interest_rate ni sus derivadas.
    "full_no_rate": {
        "numeric": [c for c in NUMERIC_ALL if c not in RATE_DERIVED],
        "categorical": CATEGORICAL_ALL,
    },
    # Modelo reducido: variables obtenibles del usuario + parametros del
    # escenario de credito (seccion 11.3). Aqui interest_rate es un
    # parametro elegido en el simulador, no una decision del banco.
    "reduced": {
        "numeric": [
            "age",
            "income",
            "has_dependents",
            "loan_amount",
            "loan_term",
            "interest_rate",
            "loan_to_income_ratio",
            "estimated_monthly_payment",
            "payment_to_income_ratio",
        ],
        "categorical": [
            "marital_status",
            "loan_purpose",
        ],
    },
}


def feature_columns(feature_set: str) -> list[str]:
    """Columnas de entrada (numericas + categoricas) de una configuracion."""
    config = FEATURE_SETS[feature_set]
    return config["numeric"] + config["categorical"]


def load_loan_dataset(path: Path = LOAN_ML_PATH) -> pd.DataFrame:
    """Lee Gold loan_ml_dataset y verifica columnas y splits."""
    columns = [ID_COLUMN, SPLIT_COLUMN, TARGET] + NUMERIC_ALL + CATEGORICAL_ALL
    df = DeltaTable(str(path)).to_pandas(columns=columns)

    found_splits = set(df[SPLIT_COLUMN].unique())
    if found_splits != set(SPLITS):
        raise ValueError(f"Unexpected split values: {sorted(found_splits)}")

    return df


def get_split(
    df: pd.DataFrame,
    split: str,
    feature_set: str,
) -> tuple[pd.DataFrame, pd.Series]:
    """Devuelve X (solo variables de entrada) e y para un split."""
    if split not in SPLITS:
        raise ValueError(f"Unknown split: {split}")

    part = df[df[SPLIT_COLUMN] == split]
    return part[feature_columns(feature_set)], part[TARGET]


def build_preprocessor(feature_set: str, scale_numeric: bool) -> ColumnTransformer:
    """
    One-Hot para categoricas (categorias aprendidas solo de lo que reciba
    en fit, es decir, train) y escalado opcional para numericas.

    scale_numeric=True para regresion logistica; los arboles no lo necesitan.
    """
    config = FEATURE_SETS[feature_set]

    numeric_step = StandardScaler() if scale_numeric else "passthrough"

    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_step, config["numeric"]),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                config["categorical"],
            ),
        ],
        verbose_feature_names_out=False,
    )


if __name__ == "__main__":
    # Prueba rapida: carga, tamanos por split y columnas tras el
    # preprocesamiento ajustado solo con train.
    data = load_loan_dataset()
    print(f"Loaded {len(data)} rows from {LOAN_ML_PATH}")

    for name in FEATURE_SETS:
        X_train, y_train = get_split(data, "train", name)
        X_val, _ = get_split(data, "validation", name)

        preprocessor = build_preprocessor(name, scale_numeric=False)
        preprocessor.fit(X_train)
        n_out = len(preprocessor.get_feature_names_out())

        print(
            f"{name:<13} inputs={X_train.shape[1]:>2}  "
            f"after one-hot={n_out:>2}  "
            f"train={len(X_train)}  validation={len(X_val)}  "
            f"train default rate={y_train.mean():.4%}"
        )
