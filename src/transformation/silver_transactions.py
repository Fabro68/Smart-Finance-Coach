from datetime import datetime, timezone
import sys

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    current_timestamp,
    to_date,
    sha2,
    concat_ws,
    when,
)

sys.path.append("/opt/project/src/quality")

from audit_logger import create_run_id, write_audit_log


BRONZE_PATH = "/opt/project/data/bronze/transactions"
SILVER_PATH = "/opt/project/data/silver/transactions"


run_id = create_run_id()
start_time = datetime.now(timezone.utc)

spark = None
records_read = None
records_written = None

try:
    spark = (
        SparkSession.builder
        .appName("silver_transactions")
        .getOrCreate()
    )

    df_bronze = spark.read.format("delta").load(BRONZE_PATH)

    records_read = df_bronze.count()

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

    records_written = df_silver.count()

    df_silver.write \
        .format("delta") \
        .mode("overwrite") \
        .save(SILVER_PATH)

    end_time = datetime.now(timezone.utc)

    write_audit_log(
        pipeline_run_id=run_id,
        process_name="silver_transactions",
        layer="silver",
        dataset="transactions",
        status="SUCCESS",
        start_time=start_time,
        end_time=end_time,
        records_read=records_read,
        records_written=records_written,
        message="Silver transactions transformation completed successfully.",
    )

    print("Silver transactions transformation completed successfully.")
    print(f"Rows read: {records_read}")
    print(f"Rows written: {records_written}")
    print(f"Output path: {SILVER_PATH}")

    df_silver.printSchema()

except Exception as error:
    end_time = datetime.now(timezone.utc)

    write_audit_log(
        pipeline_run_id=run_id,
        process_name="silver_transactions",
        layer="silver",
        dataset="transactions",
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