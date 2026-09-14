from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    current_timestamp,
    to_date,
    sha2,
    concat_ws,
    when,
)


BRONZE_PATH = "/opt/project/data/bronze/transactions"
SILVER_PATH = "/opt/project/data/silver/transactions"


spark = (
    SparkSession.builder
    .appName("silver_transactions")
    .getOrCreate()
)


df_bronze = spark.read.format("delta").load(BRONZE_PATH)


df_silver = (
    df_bronze
    .select(
        col("User ID").cast("int").alias("user_id"),
        to_date(col("Date"), "M/d/yyyy").alias("fecha"),
        col("Description").cast("string").alias("descripcion"),
        col("Amount").cast("double").alias("monto"),
        col("Transaction Type").cast("string").alias("tipo"),
        col("Category").cast("string").alias("categoria"),
        col("Account Name").cast("string").alias("cuenta"),
        col("_ingestion_timestamp"),
        col("_source_file"),
    )
    .withColumn(
        "transaction_id",
        sha2(
            concat_ws(
                "||",
                col("user_id").cast("string"),
                col("fecha").cast("string"),
                col("descripcion"),
                col("monto").cast("string"),
                col("tipo"),
                col("categoria"),
                col("cuenta"),
            ),
            256,
        ),
    )
    .withColumn(
        "is_user_linked",
        when(col("user_id").isNotNull(), True).otherwise(False),
    )
    .withColumn("_silver_timestamp", current_timestamp())
)


df_silver.write \
    .format("delta") \
    .mode("overwrite") \
    .save(SILVER_PATH)


print("Silver transactions transformation completed successfully.")
print(f"Rows written: {df_silver.count()}")
print(f"Output path: {SILVER_PATH}")

df_silver.printSchema()

spark.stop()