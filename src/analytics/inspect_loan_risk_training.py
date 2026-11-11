from pyspark.sql import SparkSession
from pyspark.sql import functions as F


LOAN_GOLD_PATH = "/opt/project/data/gold/loan_risk_training"
TARGET = "default"
EXCLUDE = {"loan_id", "gold_created_at", TARGET}

NUMERIC_TYPES = ("int", "bigint", "smallint", "tinyint", "double", "float")


spark = (
    SparkSession.builder
    .appName("inspect_loan_risk_training")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")


try:
    df = spark.read.format("delta").load(LOAN_GOLD_PATH)
    total = df.count()

    print("\n=== 1. ESQUEMA ===")
    for name, dtype in df.dtypes:
        print(f"{name:<25} {dtype}")

    print("\n=== 2. VOLUMEN E IDENTIFICADOR ===")
    print(f"Filas: {total}")
    print(f"loan_id distintos: {df.select('loan_id').distinct().count()}")

    print("\n=== 3. NULOS POR COLUMNA ===")
    df.select([
        F.sum(F.col(c).isNull().cast("int")).alias(c)
        for c in df.columns
    ]).show(vertical=True, truncate=False)

    print("\n=== 4. DISTRIBUCION DE LA VARIABLE OBJETIVO ===")
    (
        df.groupBy(TARGET)
        .agg(
            F.count("*").alias("filas"),
            F.round(F.count("*") / F.lit(total) * 100, 4).alias("porcentaje"),
        )
        .orderBy(TARGET)
        .show()
    )

    numeric_cols = [
        c for c, t in df.dtypes
        if c not in EXCLUDE
        and (t in NUMERIC_TYPES or t.startswith("decimal"))
    ]
    categorical_cols = [
        c for c, t in df.dtypes
        if c not in EXCLUDE and c not in numeric_cols
    ]

    print("\n=== 5. VARIABLES NUMERICAS: RESUMEN ===")
    print(numeric_cols)
    (
        df.select(numeric_cols)
        .summary("min", "25%", "50%", "75%", "max", "mean")
        .show(truncate=False)
    )

    print("\n=== 6. CORRELACION CON default (Pearson) ===")
    corr_row = df.select([
        F.corr(F.col(c).cast("double"), F.col(TARGET).cast("double")).alias(c)
        for c in numeric_cols
    ]).first()
    corrs = sorted(
        corr_row.asDict().items(),
        key=lambda kv: abs(kv[1]) if kv[1] is not None else 0,
        reverse=True,
    )
    for name, value in corrs:
        shown = f"{value:+.4f}" if value is not None else "None"
        print(f"{name:<25} {shown}")

    print("\n=== 7. VARIABLES CATEGORICAS: TASA DE default POR VALOR ===")
    print(categorical_cols)
    for c in categorical_cols:
        print(f"\n--- {c} ---")
        (
            df.groupBy(c)
            .agg(
                F.count("*").alias("filas"),
                F.round(F.avg(F.col(TARGET).cast("double")) * 100, 2)
                .alias("tasa_default_pct"),
            )
            .orderBy(F.desc("filas"))
            .show(20, truncate=False)
        )

finally:
    spark.stop()