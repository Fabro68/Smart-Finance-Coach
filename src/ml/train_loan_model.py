"""
Entrenamiento y comparacion de modelos de riesgo crediticio (Semana 18).

Entrena 3 modelos (regresion logistica, XGBoost, LightGBM) sobre 3
configuraciones de variables (full, full_no_rate, reduced) y los compara
en el split validation.

Reglas:
- Sin pesos de clase: las probabilidades quedan calibradas a la tasa real
  de incumplimiento. El desbalance se maneja con el umbral de decision.
- El preprocesamiento se ajusta solo con train.
- El split test NO se usa aqui. La seleccion final y la evaluacion en
  test van en un paso aparte.
- La parada temprana de XGBoost y LightGBM usa validation, por lo que
  las metricas de validation son ligeramente optimistas.

Salidas (fuera de git, carpeta models/):
- models/validation_results.json
- models/candidates/<feature_set>__<model>.joblib

Uso (entorno local):
    python src/ml/train_loan_model.py
"""

import json
import time
from datetime import datetime, timezone

import joblib
import lightgbm as lgb
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from loan_features import (
    FEATURE_SETS,
    PROJECT_ROOT,
    build_preprocessor,
    feature_columns,
    get_split,
    load_loan_dataset,
)


RANDOM_STATE = 42
EARLY_STOPPING_ROUNDS = 100
MAX_TREES = 2000

MODELS_DIR = PROJECT_ROOT / "models"
CANDIDATES_DIR = MODELS_DIR / "candidates"
RESULTS_PATH = MODELS_DIR / "validation_results.json"


# ============================================================
# MODEL FACTORIES
# ============================================================

def make_logistic():
    return LogisticRegression(max_iter=2000)


def make_xgboost():
    return XGBClassifier(
        n_estimators=MAX_TREES,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        eval_metric="aucpr",
        early_stopping_rounds=EARLY_STOPPING_ROUNDS,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )


def make_lightgbm():
    return lgb.LGBMClassifier(
        n_estimators=MAX_TREES,
        learning_rate=0.05,
        num_leaves=31,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        metric="average_precision",
        random_state=RANDOM_STATE,
        n_jobs=-1,
        verbose=-1,
    )


MODELS = {
    "logistic": {"factory": make_logistic, "scale_numeric": True},
    "xgboost": {"factory": make_xgboost, "scale_numeric": False},
    "lightgbm": {"factory": make_lightgbm, "scale_numeric": False},
}


# ============================================================
# TRAINING
# ============================================================

def fit_model(model_name, model, X_train, y_train, X_val, y_val):
    """Ajusta el modelo; los de arboles usan validation para parar temprano."""
    if model_name == "xgboost":
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        return int(model.best_iteration) + 1

    if model_name == "lightgbm":
        # LightGBM 4.7: eval_set esta deprecado; se usa eval_X / eval_y.
        model.fit(
            X_train,
            y_train,
            eval_X=X_val,
            eval_y=y_val,
            callbacks=[
                lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False),
                lgb.log_evaluation(0),
            ],
        )
        return int(model.best_iteration_)

    model.fit(X_train, y_train)
    return None


# ============================================================
# METRICS
# ============================================================

def evaluate(y_true, proba):
    """Metricas de ordenamiento, calibracion y umbral de maximo F1."""
    precision, recall, thresholds = precision_recall_curve(y_true, proba)

    # precision/recall tienen un elemento mas que thresholds.
    p, r = precision[:-1], recall[:-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        f1 = np.where(p + r > 0, 2 * p * r / (p + r), 0.0)
    best = int(np.argmax(f1))

    return {
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "pr_auc": float(average_precision_score(y_true, proba)),
        "brier": float(brier_score_loss(y_true, proba)),
        "log_loss": float(log_loss(y_true, proba)),
        "mean_predicted_proba": float(np.mean(proba)),
        "best_f1_threshold": float(thresholds[best]),
        "best_f1": float(f1[best]),
        "precision_at_best_f1": float(p[best]),
        "recall_at_best_f1": float(r[best]),
    }


# ============================================================
# MAIN
# ============================================================

def main():
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading loan_ml_dataset...")
    data = load_loan_dataset()

    results = []

    for feature_set in FEATURE_SETS:
        X_train, y_train = get_split(data, "train", feature_set)
        X_val, y_val = get_split(data, "validation", feature_set)

        for model_name, spec in MODELS.items():
            start = time.time()

            preprocessor = build_preprocessor(
                feature_set,
                scale_numeric=spec["scale_numeric"],
            )
            Xt_train = preprocessor.fit_transform(X_train)
            Xt_val = preprocessor.transform(X_val)

            model = spec["factory"]()
            n_trees = fit_model(
                model_name, model, Xt_train, y_train, Xt_val, y_val
            )

            proba = model.predict_proba(Xt_val)[:, 1]
            metrics = evaluate(y_val, proba)
            elapsed = time.time() - start

            # Pipeline con piezas ya ajustadas: listo para predecir sobre
            # un DataFrame con las columnas originales.
            pipeline = Pipeline(
                steps=[("preprocessor", preprocessor), ("model", model)]
            )
            artifact = CANDIDATES_DIR / f"{feature_set}__{model_name}.joblib"
            joblib.dump(pipeline, artifact)

            results.append(
                {
                    "feature_set": feature_set,
                    "model": model_name,
                    "n_input_features": len(feature_columns(feature_set)),
                    "n_trees": n_trees,
                    "train_seconds": round(elapsed, 1),
                    "artifact": str(artifact.relative_to(PROJECT_ROOT)),
                    **metrics,
                }
            )

            print(
                f"  {feature_set:<13} {model_name:<9} "
                f"PR-AUC={metrics['pr_auc']:.4f}  "
                f"ROC-AUC={metrics['roc_auc']:.4f}  "
                f"({elapsed:.1f}s)"
            )

    prevalence = float(data.loc[data["split"] == "validation", "default"].mean())

    output = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluated_split": "validation",
        "validation_prevalence": prevalence,
        "random_state": RANDOM_STATE,
        "class_weights": "none",
        "note": (
            "Early stopping uses validation; validation metrics are "
            "slightly optimistic. Test split not used."
        ),
        "results": results,
    }

    RESULTS_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    # ---------------- Summary table ----------------
    print(
        f"\n=== VALIDATION RESULTS "
        f"(prevalence = random PR-AUC = {prevalence:.4f}) ===\n"
    )
    header = (
        f"{'feature_set':<13} {'model':<9} {'trees':>5} "
        f"{'ROC-AUC':>8} {'PR-AUC':>7} {'Brier':>7} {'LogLoss':>8} "
        f"{'meanP':>6} {'thr':>6} {'F1':>6} {'Prec':>6} {'Recall':>6}"
    )
    print(header)
    print("-" * len(header))

    for row in sorted(results, key=lambda r: r["pr_auc"], reverse=True):
        trees = "-" if row["n_trees"] is None else str(row["n_trees"])
        print(
            f"{row['feature_set']:<13} {row['model']:<9} {trees:>5} "
            f"{row['roc_auc']:>8.4f} {row['pr_auc']:>7.4f} "
            f"{row['brier']:>7.4f} {row['log_loss']:>8.4f} "
            f"{row['mean_predicted_proba']:>6.3f} "
            f"{row['best_f1_threshold']:>6.3f} {row['best_f1']:>6.4f} "
            f"{row['precision_at_best_f1']:>6.4f} "
            f"{row['recall_at_best_f1']:>6.4f}"
        )

    print(f"\nResults saved to: {RESULTS_PATH}")
    print(f"Candidate pipelines saved to: {CANDIDATES_DIR}")


if __name__ == "__main__":
    main()
