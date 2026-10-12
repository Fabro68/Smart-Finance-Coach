from pyspark.sql import SparkSession
from pyspark.sql import functions as F


ECONOMIC_PATH = "/opt/project/data/silver/economic_data"

GOLD_OUTPUT_PATH = (
    "/opt/project/data/gold/"
    "monthly_macro_context"
)


spark = (
    SparkSession.builder
    .appName("gold_monthly_macro_context")
    .getOrCreate()
)


try:
    # ========================================================
    # LOAD SILVER ECONOMIC DATA
    # ========================================================

    economic_df = (
        spark.read
        .format("delta")
        .load(ECONOMIC_PATH)
        .select(
            "fecha",
            "indice_precios",
            "inflacion_anual_pct",
            "tasa_interes",
            "tipo_cambio_promedio",
        )
    )


    # ========================================================
    # BUILD MONTHLY MACRO CONTEXT
    # ========================================================

    gold_df = (
        economic_df
        .withColumn(
            "year_month",
            F.date_format(
                F.col("fecha"),
                "yyyy-MM",
            ),
        )
        .withColumnRenamed(
            "indice_precios",
            "cpi_index",
        )
        .withColumnRenamed(
            "inflacion_anual_pct",
            "annual_inflation_pct",
        )
        .withColumnRenamed(
            "tasa_interes",
            "interest_rate",
        )
        .withColumnRenamed(
            "tipo_cambio_promedio",
            "average_exchange_rate",
        )
        .withColumn(
            "gold_created_at",
            F.current_timestamp(),
        )
    )


    # ========================================================
    # FINAL COLUMN ORDER
    # ========================================================

    gold_df = (
        gold_df
        .select(
            "year_month",
            "fecha",
            "cpi_index",
            "annual_inflation_pct",
            "interest_rate",
            "average_exchange_rate",
            "gold_created_at",
        )
        .orderBy(
            "year_month"
        )
    )


    # ========================================================
    # WRITE GOLD DELTA TABLE
    # ========================================================

    (
        gold_df
        .write
        .format("delta")
        .mode("overwrite")
        .option(
            "overwriteSchema",
            "true",
        )
        .save(
            GOLD_OUTPUT_PATH
        )
    )


    # ========================================================
    # EXECUTION SUMMARY
    # ========================================================

    total_rows = (
        gold_df.count()
    )

    distinct_months = (
        gold_df
        .select("year_month")
        .distinct()
        .count()
    )

    first_month = (
        gold_df
        .agg(
            F.min("year_month")
        )
        .first()[0]
    )

    last_month = (
        gold_df
        .agg(
            F.max("year_month")
        )
        .first()[0]
    )


    print(
        "Gold monthly macro context "
        "completed successfully."
    )

    print(
        f"Total rows: "
        f"{total_rows}"
    )

    print(
        f"Distinct months: "
        f"{distinct_months}"
    )

    print(
        f"Period: "
        f"{first_month} to {last_month}"
    )

    print(
        "Gold output: "
        f"{GOLD_OUTPUT_PATH}"
    )


finally:
    spark.stop()