from datetime import datetime, timezone
import sys

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp

sys.path.append("/opt/project/src/quality")

from audit_logger import create_run_id, write_audit_log


BRONZE_PATH = "/opt/project/data/bronze/loans"
SILVER_PATH = "/opt/project/data/silver/loans"


run_id = create_run_id()
start_time = datetime.now(timezone.utc)

spark = None
records_read = None
records_written = None

try:
    spark = (
        SparkSession.builder
        .appName("silver_loans")
        .getOrCreate()
    )

    df_bronze = spark.read.format("delta").load(BRONZE_PATH)

    records_read = df_bronze.count()

    df_silver = (
        df_bronze
        .select(
            col("LoanID").cast("string").alias("loan_id"),
            col("Age").cast("int").alias("age"),
            col("Income").cast("double").alias("income"),
            col("LoanAmount").cast("double").alias("loan_amount"),
            col("CreditScore").cast("int").alias("credit_score"),
            col("MonthsEmployed").cast("int").alias("months_employed"),
            col("NumCreditLines").cast("int").alias("num_credit_lines"),
            col("InterestRate").cast("double").alias("interest_rate"),
            col("LoanTerm").cast("int").alias("loan_term"),
            col("DTIRatio").cast("double").alias("dti_ratio"),
            col("Education").cast("string").alias("education"),
            col("EmploymentType").cast("string").alias("employment_type"),
            col("MaritalStatus").cast("string").alias("marital_status"),
            col("HasMortgage").cast("string").alias("has_mortgage"),
            col("HasDependents").cast("string").alias("has_dependents"),
            col("LoanPurpose").cast("string").alias("loan_purpose"),
            col("HasCoSigner").cast("string").alias("has_cosigner"),
            col("Default").cast("int").alias("default"),
            col("_ingestion_timestamp"),
            col("_source_file"),
            current_timestamp().alias("_silver_timestamp"),
        )
    )

    records_written = df_silver.count()

    df_silver.write \
        .format("delta") \
        .mode("overwrite") \
        .save(SILVER_PATH)

    end_time = datetime.now(timezone.utc)

    write_audit_log(
        pipeline_run_id=run_id,
        process_name="silver_loans",
        layer="silver",
        dataset="loans",
        status="SUCCESS",
        start_time=start_time,
        end_time=end_time,
        records_read=records_read,
        records_written=records_written,
        message="Silver loans transformation completed successfully.",
    )

    print("Silver loans transformation completed successfully.")
    print(f"Rows read: {records_read}")
    print(f"Rows written: {records_written}")
    print(f"Output path: {SILVER_PATH}")

    df_silver.printSchema()

except Exception as error:
    end_time = datetime.now(timezone.utc)

    write_audit_log(
        pipeline_run_id=run_id,
        process_name="silver_loans",
        layer="silver",
        dataset="loans",
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