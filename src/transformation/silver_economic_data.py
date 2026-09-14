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


CPI_PATH = "/opt/project/data/bronze/economic/cpi"
INTEREST_PATH = "/opt/project/data/bronze/economic/interest_rate"
FX_PATH = "/opt/project/data/bronze/economic/exchange_rate"

SILVER_PATH = "/opt/project/data/silver/economic_data"


spark = (
    SparkSession.builder
    .appName("silver_economic_data")
    .getOrCreate()
)


# ============================================================
# CPI / Índice de precios
# ============================================================

df_cpi_bronze = spark.read.format("delta").load(CPI_PATH)

df_cpi = (
    df_cpi_bronze
    .select(
        to_date(col("observation_date")).alias("fecha"),
        col("MEXCPALTT01IXNBM").cast("double").alias("indice_precios"),
    )
)

# Se necesita conservar todo el histórico antes de filtrar,
# porque la inflación anual utiliza el valor de 12 meses atrás.
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

df_interest_bronze = spark.read.format("delta").load(INTEREST_PATH)

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

df_fx_bronze = spark.read.format("delta").load(FX_PATH)

df_fx_daily = (
    df_fx_bronze
    .select(
        to_date(col("observation_date")).alias("fecha_diaria"),
        col("DEXMXUS").cast("double").alias("tipo_cambio"),
    )
    .filter(col("tipo_cambio").isNotNull())
)


# Convertimos los valores diarios a promedio mensual.
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


# ============================================================
# Escritura en Silver Delta Lake
# ============================================================

df_silver.write \
    .format("delta") \
    .mode("overwrite") \
    .save(SILVER_PATH)


print("Silver economic data transformation completed successfully.")
print(f"Rows written: {df_silver.count()}")
print(f"Output path: {SILVER_PATH}")

df_silver.printSchema()

print("\nSample records:")
df_silver.show(10, truncate=False)


spark.stop()