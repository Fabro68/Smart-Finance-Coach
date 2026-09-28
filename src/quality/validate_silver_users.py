from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim

from quality_logger import (
    create_quality_run_id,
    write_quality_result,
)


SILVER_PATH = "/opt/project/data/silver/users"


spark = (
    SparkSession.builder
    .appName("validate_silver_users")
    .getOrCreate()
)

try:
    df = spark.read.format("delta").load(SILVER_PATH)

    total_rows = df.count()
    distinct_users = df.select("user_id").distinct().count()

    null_user_id = df.filter(col("user_id").isNull()).count()

    invalid_user_id = df.filter(
        col("user_id") <= 0
    ).count()

    invalid_age = df.filter(
        col("edad").isNull()
        | (col("edad") < 18)
        | (col("edad") > 100)
    ).count()

    invalid_salary = df.filter(
        col("salario_mensual").isNull()
        | (col("salario_mensual") <= 0)
    ).count()

    invalid_dependents = df.filter(
        col("dependientes").isNull()
        | (col("dependientes") < 0)
    ).count()

    invalid_city = df.filter(
        col("ciudad").isNull()
        | (trim(col("ciudad")) == "")
    ).count()

    invalid_marital_status = df.filter(
        col("estado_civil").isNull()
        | (trim(col("estado_civil")) == "")
    ).count()

    null_ingestion_timestamp = df.filter(
        col("_ingestion_timestamp").isNull()
    ).count()

    invalid_source_file = df.filter(
        col("_source_file").isNull()
        | (trim(col("_source_file")) == "")
    ).count()

    null_silver_timestamp = df.filter(
        col("_silver_timestamp").isNull()
    ).count()

    duplicate_user_ids = total_rows - distinct_users

    check_results = {
        "user_id_not_null": {
            "passed": null_user_id == 0,
            "observed": null_user_id,
            "expected": 0,
        },
        "user_id_positive": {
            "passed": invalid_user_id == 0,
            "observed": invalid_user_id,
            "expected": 0,
        },
        "user_id_unique": {
            "passed": duplicate_user_ids == 0,
            "observed": duplicate_user_ids,
            "expected": 0,
        },
        "edad_between_18_and_100": {
            "passed": invalid_age == 0,
            "observed": invalid_age,
            "expected": 0,
        },
        "salario_mensual_positive": {
            "passed": invalid_salary == 0,
            "observed": invalid_salary,
            "expected": 0,
        },
        "dependientes_non_negative": {
            "passed": invalid_dependents == 0,
            "observed": invalid_dependents,
            "expected": 0,
        },
        "ciudad_not_empty": {
            "passed": invalid_city == 0,
            "observed": invalid_city,
            "expected": 0,
        },
        "estado_civil_not_empty": {
            "passed": invalid_marital_status == 0,
            "observed": invalid_marital_status,
            "expected": 0,
        },
        "ingestion_timestamp_not_null": {
            "passed": null_ingestion_timestamp == 0,
            "observed": null_ingestion_timestamp,
            "expected": 0,
        },
        "source_file_not_empty": {
            "passed": invalid_source_file == 0,
            "observed": invalid_source_file,
            "expected": 0,
        },
        "silver_timestamp_not_null": {
            "passed": null_silver_timestamp == 0,
            "observed": null_silver_timestamp,
            "expected": 0,
        },
    }

    passed_checks = sum(
        result["passed"]
        for result in check_results.values()
    )

    total_checks = len(check_results)

    print("=== SILVER USERS DATA QUALITY REPORT ===")
    print(f"Total rows: {total_rows}")
    print(f"Distinct user_id: {distinct_users}")
    print(f"Duplicate user_id: {duplicate_user_ids}")
    print()

    quality_run_id = create_quality_run_id()

    for check_name, result in check_results.items():
        status = "PASS" if result["passed"] else "FAIL"

        print(f"{status}: {check_name}")

        write_quality_result(
            quality_run_id=quality_run_id,
            dataset="users",
            check_name=check_name,
            status=status,
            observed_value=result["observed"],
            expected_value=result["expected"],
        )

    print()
    print(f"Checks passed: {passed_checks}/{total_checks}")
    print(f"quality_run_id: {quality_run_id}")

    if passed_checks == total_checks:
        print("Overall result: PASS")
    else:
        print("Overall result: FAIL")

finally:
    spark.stop()