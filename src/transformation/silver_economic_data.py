from datetime import datetime, timezone
import sys

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg,
    col,
    current_timestamp,
    lag,
    to_date,
    trunc,
)
from pyspark.sql.window import Window

sys.path.append("/opt/project/src/quality")

from audit_logger import create_run_id, write_audit_log


CPI_PATH = "/opt/project/data/bronze/economic/cpi"
INTEREST_PATH = "/opt/project/data/bronze/economic/interest_rate"
FX_PATH = "/opt/project/data/bronze/economic/exchange_rate"

SILVER_PATH = "/opt/project/data/silver/economic_data"


run_id = create_run_id()
start_time = datetime.now(timezone.utc)

spark = None
records_read = None
records_written = None

try:
    spark = (
        SparkSession.builder
        .appName("silver_economic_data")
        .getOrCreate()
    )

    # ============================================================
    # Lectura de fuentes Bronze
    # ============================================================

    df_cpi_bronze = spark.read.format("delta").load(CPI_PATH)
    df_interest_bronze = spark.read.format("delta").load(INTEREST_PATH)
    df_fx_bronze = spark.read.format("delta").load(FX_PATH)

    cpi_records = df_cpi_bronze.count()
    interest_records = df_interest_bronze.count()
    fx_records = df_fx_bronze.count()

    records_read = cpi_records + interest_records + fx_records

    # ============================================================
    # CPI / Índice de precios
    # ============================================================

    df_cpi = (
        df_cpi_bronze
        .select(
            to_date(col("observation_date")).alias("fecha"),
            col("MEXCPALTT01IXNBM").cast("double").alias("indice_precios"),
        )
    )

    # Se conserva todo el histórico antes de filtrar porque
    # la inflación anual necesita el valor de 12 meses atrás.
    window_cpi = Window.orderBy("fecha")

    df_cpi = (
        df_cpi
        .withColumn(
            "indice_precios_12m_anterior",
            lag("indice_precios", 12).over(window_cpi),
        )
        .withColumn(
            "inflacion_anual_pct",
            (
                (
                    col("indice_precios")
                    / col("indice_precios_12m_anterior")
                )
                - 1
            ) * 100,
        )
        .drop("indice_precios_12m_anterior")
        .filter(
            (col("fecha") >= "2018-01-01")
            & (col("fecha") <= "2020-03-31")
        )
    )

    # ============================================================
    # Tasa de interés
    # ============================================================

    df_interest = (
        df_interest_bronze
        .select(
            to_date(col("observation_date")).alias("fecha"),
            col("IRSTCI01MXM156N").cast("double").alias("tasa_interes"),
        )
        .filter(
            (col("fecha") >= "2018-01-01")
            & (col("fecha") <= "2020-03-31")
        )
    )

    # ============================================================
    # Tipo de cambio
    # ============================================================

    df_fx_daily = (
        df_fx_bronze
        .select(
            to_date(col("observation_date")).alias("fecha_diaria"),
            col("DEXMXUS").cast("double").alias("tipo_cambio"),
        )
        .filter(col("tipo_cambio").isNotNull())
    )

    df_fx_monthly = (
        df_fx_daily
        .withColumn(
            "fecha",
            trunc(col("fecha_diaria"), "month"),
        )
        .groupBy("fecha")
        .agg(
            avg("tipo_cambio").alias("tipo_cambio_promedio")
        )
        .filter(
            (col("fecha") >= "2018-01-01")
            & (col("fecha") <= "2020-03-31")
        )
    )

    # ============================================================
    # Integración de las tres fuentes económicas
    # ============================================================

    df_silver = (
        df_cpi
        .join(df_interest, on="fecha", how="inner")
        .join(df_fx_monthly, on="fecha", how="inner")
        .withColumn("_silver_timestamp", current_timestamp())
        .orderBy("fecha")
    )

    records_written = df_silver.count()

    # ============================================================
    # Escritura en Silver Delta Lake
    # ============================================================

    df_silver.write \
        .format("delta") \
        .mode("overwrite") \
        .save(SILVER_PATH)

    end_time = datetime.now(timezone.utc)

    write_audit_log(
        pipeline_run_id=run_id,
        process_name="silver_economic_data",
        layer="silver",
        dataset="economic_data",
        status="SUCCESS",
        start_time=start_time,
        end_time=end_time,
        records_read=records_read,
        records_written=records_written,
        message=(
            "Silver economic data transformation completed successfully. "
            f"CPI={cpi_records}, interest_rate={interest_records}, "
            f"exchange_rate={fx_records}."
        ),
    )

    print("Silver economic data transformation completed successfully.")
    print(f"CPI rows read: {cpi_records}")
    print(f"Interest rows read: {interest_records}")
    print(f"Exchange rate rows read: {fx_records}")
    print(f"Total rows read: {records_read}")
    print(f"Rows written: {records_written}")
    print(f"Output path: {SILVER_PATH}")

    df_silver.printSchema()

    print("\nSample records:")
    df_silver.show(10, truncate=False)

except Exception as error:
    end_time = datetime.now(timezone.utc)

    write_audit_log(
        pipeline_run_id=run_id,
        process_name="silver_economic_data",
        layer="silver",
        dataset="economic_data",
        status="FAILED",
        start_time=start_time,
        end_time=end_time,
        records_read=records_read,
        records_written=records_written,
        message=str(error),
    )

    raise

finally:
    if spark is not None:
        spark.stop()