"""
Gold ML user features (feature store simulado por usuario y mes).

Construye variables temporales de comportamiento financiero sobre
user_monthly_finance, contexto macro y el puente hacia el modelo de
riesgo crediticio (modelo reducido).

Alcance: demostrativo. Solo 3 usuarios tienen transacciones vinculadas
(63 filas). NO es una base de entrenamiento.

Reglas:
- Sin fuga de datos: toda ventana usa solo el mes actual y meses
  anteriores, nunca meses futuros.
- Las ventanas usan rangeBetween sobre un indice numerico de mes, por lo
  que toleran meses faltantes.
- Los ratios de comportamiento se calculan solo con datos de
  transacciones (denominador total_credits), no con salary_monthly,
  porque salario y transacciones no estan en la misma escala.
- El salario se usa solo para el puente con el modelo de prestamos,
  convertido a USD con el tipo de cambio de cada mes.
"""

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F


MONTHLY_GOLD_PATH = "/opt/project/data/gold/user_monthly_finance"
MACRO_GOLD_PATH = "/opt/project/data/gold/monthly_macro_context"
PROFILE_GOLD_PATH = "/opt/project/data/gold/user_financial_profile"
LOAN_ML_GOLD_PATH = "/opt/project/data/gold/loan_ml_dataset"

OUTPUT_PATH = "/opt/project/data/gold/ml_user_features"

ANOMALY_ZSCORE_THRESHOLD = 2.0
ANOMALY_MIN_PRIOR_MONTHS = 3
# Piso de la desviacion estandar como fraccion del promedio previo.
# Evita z-scores inflados cuando el historial es muy estable o corto:
# con umbral 2.0 y piso 0.20, un mes debe superar en al menos 40%
# su promedio historico para marcarse como anomalia.
ANOMALY_STD_FLOOR_PCT = 0.20

MARITAL_STATUS_MAPPING = {
    "Soltero": "Single",
    "Casado": "Married",
    "Divorciado": "Divorced",
    "Union libre": "Married",  # Supuesto documentado (ml_feature_dictionary.md, 11.2)
}


spark = (
    SparkSession.builder
    .appName("gold_ml_user_features")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")


try:
    # ========================================================
    # LOAD GOLD SOURCES
    # ========================================================

    monthly_df = (
        spark.read.format("delta")
        .load(MONTHLY_GOLD_PATH)
        .select(
            "user_id",
            "year_month",
            "salary_monthly",
            "consumer_spending",
            "total_debits",
            "total_credits",
            "credit_card_payments",
            "transactional_balance",
        )
    )

    macro_df = (
        spark.read.format("delta")
        .load(MACRO_GOLD_PATH)
        .select(
            "year_month",
            "cpi_index",
            "annual_inflation_pct",
            F.col("interest_rate").alias("macro_interest_rate"),
            "average_exchange_rate",
        )
    )

    profile_df = (
        spark.read.format("delta")
        .load(PROFILE_GOLD_PATH)
        .select(
            "user_id",
            "edad",
            "estado_civil",
            "dependientes",
        )
    )

    # Rango de ingreso visto en entrenamiento (solo split train).
    income_range = (
        spark.read.format("delta")
        .load(LOAN_ML_GOLD_PATH)
        .filter(F.col("split") == "train")
        .agg(
            F.min("income").alias("min_income"),
            F.max("income").alias("max_income"),
        )
        .first()
    )

    train_income_min = income_range["min_income"]
    train_income_max = income_range["max_income"]

    # ========================================================
    # MONTH INDEX AND WINDOWS
    # ========================================================

    month_date = F.to_date(F.col("year_month"), "yyyy-MM")

    df = monthly_df.withColumn(
        "month_idx",
        F.year(month_date) * 12 + F.month(month_date),
    )

    user_order = Window.partitionBy("user_id").orderBy("month_idx")

    window_3m = user_order.rangeBetween(-2, 0)
    window_6m = user_order.rangeBetween(-5, 0)
    window_history = user_order.rangeBetween(Window.unboundedPreceding, 0)
    window_prior = user_order.rangeBetween(Window.unboundedPreceding, -1)

    # ========================================================
    # SPENDING AND INCOME FEATURES
    # ========================================================

    count_3m = F.count("consumer_spending").over(window_3m)

    df = (
        df
        .withColumn(
            "history_months",
            F.count("*").over(window_history),
        )
        .withColumn(
            "avg_spend_3m",
            F.avg("consumer_spending").over(window_3m),
        )
        .withColumn(
            "avg_spend_6m",
            F.avg("consumer_spending").over(window_6m),
        )
        .withColumn(
            "spend_std_3m",
            F.when(
                count_3m >= 2,
                F.stddev_samp("consumer_spending").over(window_3m),
            ),
        )
        .withColumn(
            "avg_income_3m",
            F.avg("total_credits").over(window_3m),
        )
        .withColumn(
            "income_std_3m",
            F.when(
                count_3m >= 2,
                F.stddev_samp("total_credits").over(window_3m),
            ),
        )
    )

    # Variacion contra el mes inmediato anterior (solo si es consecutivo).
    previous_spend = F.lag("consumer_spending").over(user_order)
    previous_idx = F.lag("month_idx").over(user_order)

    df = df.withColumn(
        "spend_mom_pct",
        F.when(
            (F.col("month_idx") - previous_idx == 1)
            & (previous_spend > 0),
            (F.col("consumer_spending") - previous_spend) / previous_spend,
        ),
    )

    # ========================================================
    # SAVINGS AND DEBT RATIOS (TRANSACTION-ONLY)
    # ========================================================

    credits_3m = F.sum("total_credits").over(window_3m)
    debits_3m = F.sum("total_debits").over(window_3m)
    card_payments_3m = F.sum("credit_card_payments").over(window_3m)

    df = (
        df
        .withColumn(
            "savings_rate_3m",
            F.when(
                credits_3m > 0,
                (credits_3m - debits_3m) / credits_3m,
            ),
        )
        .withColumn(
            "debt_payment_ratio_3m",
            F.when(
                credits_3m > 0,
                card_payments_3m / credits_3m,
            ),
        )
        .withColumn(
            "negative_balance_months_6m",
            F.sum(
                (F.col("transactional_balance") < 0).cast("int")
            ).over(window_6m),
        )
    )

    # ========================================================
    # SPENDING ANOMALIES (Z-SCORE VS PRIOR MONTHS ONLY)
    # ========================================================

    prior_count = F.count("consumer_spending").over(window_prior)
    prior_mean = F.avg("consumer_spending").over(window_prior)
    prior_std = F.stddev_samp("consumer_spending").over(window_prior)

    df = (
        df
        .withColumn("_prior_count", prior_count)
        .withColumn("_prior_mean", prior_mean)
        .withColumn("_prior_std", prior_std)
        .withColumn(
            "_effective_std",
            F.greatest(
                F.col("_prior_std"),
                F.col("_prior_mean") * F.lit(ANOMALY_STD_FLOOR_PCT),
            ),
        )
        .withColumn(
            "spend_zscore",
            F.when(
                (F.col("_prior_count") >= ANOMALY_MIN_PRIOR_MONTHS)
                & (F.col("_effective_std") > 0),
                (F.col("consumer_spending") - F.col("_prior_mean"))
                / F.col("_effective_std"),
            ),
        )
        .withColumn(
            # 1 = gasto inusualmente alto; 0 = normal;
            # NULL = historial insuficiente para evaluar.
            "is_spend_anomaly",
            F.when(
                F.col("spend_zscore").isNotNull(),
                (F.col("spend_zscore") >= ANOMALY_ZSCORE_THRESHOLD).cast("int"),
            ),
        )
        .withColumn(
            "anomaly_count_6m",
            F.sum(
                F.coalesce(F.col("is_spend_anomaly"), F.lit(0))
            ).over(window_6m),
        )
    )

    # ========================================================
    # MACRO CONTEXT (BROADCAST JOIN, NO FORWARD-FILL)
    # ========================================================

    # Sin imputacion: si falta un mes macro, las columnas quedan en NULL
    # y validate_gold_layer.py hace fallar el pipeline.
    df = df.join(
        F.broadcast(macro_df),
        on="year_month",
        how="left",
    )

    # ========================================================
    # BRIDGE TO LOAN RISK MODEL (REDUCED MODEL INPUTS)
    # ========================================================

    marital_mapping_expr = F.create_map(
        *[
            F.lit(value)
            for pair in MARITAL_STATUS_MAPPING.items()
            for value in pair
        ]
    )

    df = (
        df
        .join(profile_df, on="user_id", how="left")
        .withColumn("age", F.col("edad"))
        .withColumn(
            "marital_status_model",
            marital_mapping_expr[F.col("estado_civil")],
        )
        .withColumn(
            "has_dependents",
            (F.col("dependientes") > 0).cast("int"),
        )
        .withColumn(
            "annual_income_usd",
            F.when(
                F.col("average_exchange_rate") > 0,
                F.col("salary_monthly") * F.lit(12.0)
                / F.col("average_exchange_rate"),
            ),
        )
        .withColumn(
            "income_outside_training_range",
            (
                (F.col("annual_income_usd") < F.lit(train_income_min))
                | (F.col("annual_income_usd") > F.lit(train_income_max))
            ).cast("int"),
        )
    )

    # ========================================================
    # FINAL COLUMNS
    # ========================================================

    final_df = df.select(
        "user_id",
        "year_month",
        "history_months",
        # Base mensual (trazabilidad)
        "consumer_spending",
        "total_credits",
        "total_debits",
        "credit_card_payments",
        "transactional_balance",
        # Comportamiento
        "avg_spend_3m",
        "avg_spend_6m",
        "spend_std_3m",
        "avg_income_3m",
        "income_std_3m",
        "spend_mom_pct",
        "savings_rate_3m",
        "debt_payment_ratio_3m",
        "negative_balance_months_6m",
        # Anomalias
        "spend_zscore",
        "is_spend_anomaly",
        "anomaly_count_6m",
        # Macro
        "cpi_index",
        "annual_inflation_pct",
        "macro_interest_rate",
        "average_exchange_rate",
        # Puente hacia el modelo reducido
        "age",
        "marital_status_model",
        "has_dependents",
        "salary_monthly",
        "annual_income_usd",
        "income_outside_training_range",
        F.current_timestamp().alias("gold_created_at"),
    )

    (
        final_df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .save(OUTPUT_PATH)
    )

    # ========================================================
    # EXECUTION SUMMARY
    # ========================================================

    result = spark.read.format("delta").load(OUTPUT_PATH)

    print("\nGold ml_user_features completed successfully.")
    print(f"Total rows: {result.count()}")
    print(f"Distinct users: {result.select('user_id').distinct().count()}")
    print(
        f"Training income range (USD, split train): "
        f"{train_income_min} - {train_income_max}"
    )
    print(
        f"Anomaly rule: z-score >= {ANOMALY_ZSCORE_THRESHOLD} "
        f"with >= {ANOMALY_MIN_PRIOR_MONTHS} prior months, "
        f"std floor = {ANOMALY_STD_FLOOR_PCT:.0%} of prior mean"
    )

    print("\nMonths without macro data: "
          f"{result.filter(F.col('average_exchange_rate').isNull()).count()}")

    print("\nDetected spending anomalies:")
    (
        result
        .filter(F.col("is_spend_anomaly") == 1)
        .select(
            "user_id",
            "year_month",
            F.round("consumer_spending", 2).alias("consumer_spending"),
            F.round("spend_zscore", 2).alias("spend_zscore"),
        )
        .orderBy("user_id", "year_month")
        .show(truncate=False)
    )

    print("Bridge summary per user:")
    (
        result
        .groupBy("user_id", "age", "marital_status_model", "has_dependents")
        .agg(
            F.round(F.min("annual_income_usd"), 0).alias("min_income_usd"),
            F.round(F.max("annual_income_usd"), 0).alias("max_income_usd"),
            F.sum("income_outside_training_range").alias("months_outside_range"),
        )
        .orderBy("user_id")
        .show(truncate=False)
    )

    print("Latest month per user:")
    latest_window = Window.partitionBy("user_id").orderBy(F.desc("year_month"))
    (
        result
        .withColumn("_rn", F.row_number().over(latest_window))
        .filter(F.col("_rn") == 1)
        .select(
            "user_id",
            "year_month",
            F.round("avg_spend_3m", 2).alias("avg_spend_3m"),
            F.round("income_std_3m", 2).alias("income_std_3m"),
            F.round("savings_rate_3m", 4).alias("savings_rate_3m"),
            F.round("debt_payment_ratio_3m", 4).alias("debt_ratio_3m"),
            "negative_balance_months_6m",
            "anomaly_count_6m",
        )
        .orderBy("user_id")
        .show(truncate=False)
    )

finally:
    spark.stop()
