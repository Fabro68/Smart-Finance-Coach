from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F


LOANS_GOLD_PATH = "/opt/project/data/gold/loan_risk_training"
OUTPUT_PATH = "/opt/project/data/gold/loan_ml_dataset"

TRAIN_FRACTION = 0.70
VALIDATION_FRACTION = 0.85  # limite acumulado: 0.70 a 0.85 = validation

BINARY_COLUMNS = ["has_mortgage", "has_dependents", "has_cosigner"]


spark = (
    SparkSession.builder
    .appName("gold_loan_ml_dataset")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")


try:
    df = spark.read.format("delta").load(LOANS_GOLD_PATH)

    # --- Variables binarias Yes/No -> 1/0 ---------------------------------
    for column in BINARY_COLUMNS:
        df = df.withColumn(
            column,
            F.when(F.col(column) == "Yes", F.lit(1))
            .when(F.col(column) == "No", F.lit(0))
            .cast("int"),
        )

    # --- Cuota mensual estimada (amortizacion) ----------------------------
    monthly_rate = F.col("interest_rate") / F.lit(1200.0)
    n_payments = F.col("loan_term").cast("double")

    df = df.withColumn(
        "estimated_monthly_payment",
        F.when(
            monthly_rate > 0,
            F.col("loan_amount")
            * monthly_rate
            / (F.lit(1.0) - F.pow(F.lit(1.0) + monthly_rate, -n_payments)),
        ).otherwise(F.col("loan_amount") / n_payments),
    )

    df = df.withColumn(
        "payment_to_income_ratio",
        F.when(
            F.col("income") > 0,
            F.col("estimated_monthly_payment")
            / (F.col("income") / F.lit(12.0)),
        ),
    )

    # --- Split determinista y estratificado por default -------------------
    split_window = (
        Window.partitionBy("default")
        .orderBy(F.xxhash64("loan_id"))
    )

    df = df.withColumn("_rank", F.percent_rank().over(split_window))
    df = df.withColumn(
        "split",
        F.when(F.col("_rank") < TRAIN_FRACTION, F.lit("train"))
        .when(F.col("_rank") < VALIDATION_FRACTION, F.lit("validation"))
        .otherwise(F.lit("test")),
    )

    # --- Columnas finales (sin redundantes ni gold_created_at) ------------
    final_df = df.select(
        "loan_id",
        "split",
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
        "education",
        "employment_type",
        "marital_status",
        "loan_purpose",
        "has_mortgage",
        "has_dependents",
        "has_cosigner",
        "default",
        F.current_timestamp().alias("gold_created_at"),
    )

    (
        final_df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .save(OUTPUT_PATH)
    )

    # --- Resumen de ejecucion --------------------------------------------
    result = spark.read.format("delta").load(OUTPUT_PATH)
    total = result.count()

    print("\nGold loan_ml_dataset completed successfully.")
    print(f"Total rows: {total}")
    print(f"Distinct loan IDs: {result.select('loan_id').distinct().count()}")

    null_count = result.select([
        F.sum(F.col(c).isNull().cast("int")).alias(c)
        for c in result.columns
    ]).first()
    print(f"Columns with nulls: "
          f"{ {k: v for k, v in null_count.asDict().items() if v} }")

    print("\nSplit summary:")
    (
        result.groupBy("split")
        .agg(
            F.count("*").alias("rows"),
            F.round(F.count("*") / F.lit(total) * 100, 2).alias("pct_rows"),
            F.sum("default").alias("defaults"),
            F.round(F.avg("default") * 100, 4).alias("default_rate_pct"),
        )
        .orderBy("split")
        .show()
    )

    print("Payment ratio summary:")
    result.select(
        "estimated_monthly_payment", "payment_to_income_ratio"
    ).summary("min", "50%", "max", "mean").show()

finally:
    spark.stop()