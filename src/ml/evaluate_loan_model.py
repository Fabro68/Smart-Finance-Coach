"""
Evaluacion final en test de los modelos de riesgo crediticio elegidos
(Semana 18).

Modelos elegidos en validation (ver models/validation_results.json):
- full__logistic: modelo de riesgo crediticio general.
- reduced__logistic: modelo reducido para aplicar a usuarios en el
  simulador (Semana 19).

Reglas:
- El split test se usa UNA sola vez, solo para los modelos elegidos.
- El umbral de decision viene de validation (maximo F1); no se ajusta
  con test.
- No se reentrena con train + validation: el modelo guardado es
  exactamente el evaluado.

Salidas (fuera de git, carpeta models/):
- models/loan_risk_full.joblib
- models/loan_risk_reduced.joblib
- models/test_results.json
- models/model_card.json

Uso (entorno local, despues de train_loan_model.py):
    python src/ml/evaluate_loan_model.py
"""

import json
import shutil
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

from loan_features import (
    FEATURE_SETS,
    PROJECT_ROOT,
    get_split,
    load_loan_dataset,
)


MODELS_DIR = PROJECT_ROOT / "models"
CANDIDATES_DIR = MODELS_DIR / "candidates"
VALIDATION_RESULTS_PATH = MODELS_DIR / "validation_results.json"
TEST_RESULTS_PATH = MODELS_DIR / "test_results.json"
MODEL_CARD_PATH = MODELS_DIR / "model_card.json"

SELECTED = {
    "full": {
        "candidate": "full__logistic",
        "final_name": "loan_risk_full.joblib",
        "purpose": "General credit risk model (Loan Default dataset).",
    },
    "reduced": {
        "candidate": "reduced__logistic",
        "final_name": "loan_risk_reduced.joblib",
        "purpose": (
            "Reduced model applied to project users in the simulator "
            "(illustrative scenario only)."
        ),
    },
}

METRIC_KEYS = ["roc_auc", "pr_auc", "brier", "log_loss"]


def test_metrics(y_true, proba, threshold):
    """Metricas en test con el umbral fijo de validation."""
    y_pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    return {
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "pr_auc": float(average_precision_score(y_true, proba)),
        "brier": float(brier_score_loss(y_true, proba)),
        "log_loss": float(log_loss(y_true, proba)),
        "mean_predicted_proba": float(np.mean(proba)),
        "threshold": float(threshold),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "confusion_matrix": {
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        },
    }


def calibration_table(y_true, proba, bins=10):
    """Probabilidad media predicha vs tasa real por decil de riesgo."""
    frame = pd.DataFrame({"y": np.asarray(y_true), "p": proba})
    frame["decile"] = pd.qcut(frame["p"], q=bins, labels=False, duplicates="drop") + 1

    table = (
        frame.groupby("decile")
        .agg(rows=("y", "size"), mean_predicted=("p", "mean"), observed_rate=("y", "mean"))
        .reset_index()
    )
    return table


def logistic_coefficients(pipeline):
    """Coeficientes de la regresion logistica por variable transformada."""
    names = pipeline.named_steps["preprocessor"].get_feature_names_out()
    coefs = pipeline.named_steps["model"].coef_[0]

    table = pd.DataFrame({"feature": names, "coefficient": coefs})
    table["abs"] = table["coefficient"].abs()
    return table.sort_values("abs", ascending=False).drop(columns="abs")


def main():
    if not VALIDATION_RESULTS_PATH.exists():
        print("Missing models/validation_results.json. Run train_loan_model.py first.")
        sys.exit(1)

    validation = json.loads(VALIDATION_RESULTS_PATH.read_text(encoding="utf-8"))
    validation_by_key = {
        f"{r['feature_set']}__{r['model']}": r for r in validation["results"]
    }

    print("Loading loan_ml_dataset...")
    data = load_loan_dataset()

    train_part = data[data["split"] == "train"]
    train_income_range = [
        float(train_part["income"].min()),
        float(train_part["income"].max()),
    ]
    test_prevalence = float(data.loc[data["split"] == "test", "default"].mean())

    test_results = {}
    card_models = {}

    for feature_set, spec in SELECTED.items():
        candidate = spec["candidate"]
        candidate_path = CANDIDATES_DIR / f"{candidate}.joblib"

        if not candidate_path.exists() or candidate not in validation_by_key:
            print(f"Missing candidate {candidate}. Run train_loan_model.py first.")
            sys.exit(1)

        pipeline = joblib.load(candidate_path)
        val = validation_by_key[candidate]
        threshold = val["best_f1_threshold"]

        X_test, y_test = get_split(data, "test", feature_set)
        proba = pipeline.predict_proba(X_test)[:, 1]

        metrics = test_metrics(y_test, proba, threshold)
        calibration = calibration_table(y_test, proba)

        # ---------------- Report ----------------
        print(f"\n=== {candidate.upper()} (test, threshold from validation = {threshold:.3f}) ===")
        print(f"{'metric':<10} {'validation':>11} {'test':>8} {'diff':>8}")
        for key in METRIC_KEYS:
            diff = metrics[key] - val[key]
            print(f"{key:<10} {val[key]:>11.4f} {metrics[key]:>8.4f} {diff:>+8.4f}")

        cm = metrics["confusion_matrix"]
        print(
            f"\nAt threshold {threshold:.3f}: precision={metrics['precision']:.4f}  "
            f"recall={metrics['recall']:.4f}  F1={metrics['f1']:.4f}"
        )
        print(f"Confusion matrix: TN={cm['tn']}  FP={cm['fp']}  FN={cm['fn']}  TP={cm['tp']}")
        print(
            f"Mean predicted P(default)={metrics['mean_predicted_proba']:.4f}  "
            f"vs test prevalence={test_prevalence:.4f}"
        )

        print("\nCalibration by risk decile (1 = lowest risk):")
        print(
            calibration.to_string(
                index=False,
                formatters={
                    "mean_predicted": "{:.4f}".format,
                    "observed_rate": "{:.4f}".format,
                },
            )
        )

        coefficients = None
        if feature_set == "full":
            coefficients = logistic_coefficients(pipeline)
            print(
                "\nLogistic coefficients (numeric: standardized; "
                "categorical: one-hot 0/1; + increases risk):"
            )
            print(coefficients.to_string(index=False, float_format="{:+.4f}".format))

        # ---------------- Final artifact ----------------
        final_path = MODELS_DIR / spec["final_name"]
        shutil.copy2(candidate_path, final_path)

        test_results[candidate] = {
            **metrics,
            "calibration_by_decile": calibration.to_dict(orient="records"),
            **(
                {"coefficients": coefficients.to_dict(orient="records")}
                if coefficients is not None
                else {}
            ),
        }

        card_models[feature_set] = {
            "artifact": str(final_path.relative_to(PROJECT_ROOT)),
            "source_candidate": candidate,
            "algorithm": "LogisticRegression (no class weights)",
            "purpose": spec["purpose"],
            "numeric_features": FEATURE_SETS[feature_set]["numeric"],
            "categorical_features": FEATURE_SETS[feature_set]["categorical"],
            "decision_threshold": threshold,
            "threshold_rule": "max F1 on validation",
            "validation_metrics": {k: val[k] for k in METRIC_KEYS},
            "test_metrics": {k: metrics[k] for k in METRIC_KEYS},
            "test_precision_recall_f1": {
                k: metrics[k] for k in ("precision", "recall", "f1")
            },
        }

    now = datetime.now(timezone.utc).isoformat()

    TEST_RESULTS_PATH.write_text(
        json.dumps(
            {
                "created_at": now,
                "evaluated_split": "test",
                "test_prevalence": test_prevalence,
                "results": test_results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    MODEL_CARD_PATH.write_text(
        json.dumps(
            {
                "created_at": now,
                "project": "Smart Finance Coach (academic, BBVA x Tecmilenio)",
                "training_data": "Gold loan_ml_dataset, split train",
                "training_rows": int(len(train_part)),
                "training_default_rate": float(train_part["default"].mean()),
                "training_income_range_usd": train_income_range,
                "models": card_models,
                "warnings": [
                    "Synthetic public dataset with weak linear relationships; modest performance.",
                    "No verified link between loans and project users.",
                    "User-level predictions are illustrative scenarios, not real individual credit risk.",
                    "Predictions for incomes outside training_income_range_usd are unreliable.",
                    "interest_rate may partly encode the lender's own risk assessment (possible leakage).",
                    "P(default) is separate from the rule-based financial_risk_level KPI.",
                    "Not financial advice.",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nFinal models saved to: {MODELS_DIR}")
    print(f"Test results: {TEST_RESULTS_PATH}")
    print(f"Model card: {MODEL_CARD_PATH}")


if __name__ == "__main__":
    main()
