from datetime import datetime, timezone
import sys

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp

sys.path.append("/opt/project/src/quality")

from audit_logger import create_run_id, write_audit_log


BRONZE_PATH = "/opt/project/data/bronze/users"
SILVER_PATH = "/opt/project/data/silver/users"


run_id = create_run_id()
start_time = datetime.now(timezone.utc)

spark = None

try:
    spark = (
        SparkSession.builder
        .appName("silver_users")
        .getOrCreate()
    )

    df_bronze = spark.read.format("delta").load(BRONZE_PATH)

    records_read = df_bronze.count()

    df_silver = (
        df_bronze
        .select(
            col("user_id").cast("int").alias("user_id"),
            col("edad").cast("int").alias("edad"),
            col("salario_mensual").cast("double").alias("salario_mensual"),
            col("ciudad").cast("string").alias("ciudad"),
            col("estado_civil").cast("string").alias("estado_civil"),
            col("dependientes").cast("int").alias("dependientes"),
            col("_ingestion_timestamp"),
            col("_source_file"),
            current_timestamp().alias("_silver_timestamp"),
        )
    )

    df_silver = df_silver.dropDuplicates(["user_id"])

    records_written = df_silver.count()

    (
        df_silver.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .save(SILVER_PATH)
    )

    end_time = datetime.now(timezone.utc)

    write_audit_log(
        pipeline_run_id=run_id,
        process_name="silver_users",
        layer="silver",
        dataset="users",
        status="SUCCESS",
        start_time=start_time,
        end_time=end_time,
        records_read=records_read,
        records_written=records_written,
        message="Silver users transformation completed successfully.",
    )

    print("Silver users transformation completed successfully.")
    print(f"Rows read: {records_read}")
    print(f"Rows written: {records_written}")
    print(f"Output path: {SILVER_PATH}")

    df_silver.printSchema()

except Exception as error:
    end_time = datetime.now(timezone.utc)

    write_audit_log(
        pipeline_run_id=run_id,
        process_name="silver_users",
        layer="silver",
        dataset="users",
        status="FAILED",
        start_time=start_time,
        end_time=end_time,
        records_read=None,
        records_written=None,
        message=str(error),
    )

    raise

finally:
    if spark is not None:
        spark.stop()