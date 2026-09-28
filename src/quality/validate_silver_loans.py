from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim

from quality_logger import (
    create_quality_run_id,
    write_quality_result,
)


SILVER_PATH = "/opt/project/data/silver/loans"


spark = (
    SparkSession.builder
    .appName("validate_silver_loans")
    .getOrCreate()
)

try:
    df = spark.read.format("delta").load(SILVER_PATH)

    total_rows = df.count()

    distinct_loan_ids = (
        df.select("loan_id")
        .distinct()
        .count()
    )

    null_loan_id = df.filter(
        col("loan_id").isNull()
        | (trim(col("loan_id")) == "")
    ).count()

    duplicate_loan_ids = (
        total_rows - distinct_loan_ids
    )

    invalid_age = df.filter(
        col("age").isNull()
        | (col("age") < 18)
        | (col("age") > 100)
    ).count()

    invalid_income = df.filter(
        col("income").isNull()
        | (col("income") <= 0)
    ).count()

    invalid_loan_amount = df.filter(
        col("loan_amount").isNull()
        | (col("loan_amount") <= 0)
    ).count()

    invalid_credit_score = df.filter(
        col("credit_score").isNull()
        | (col("credit_score") < 300)
        | (col("credit_score") > 850)
    ).count()

    invalid_months_employed = df.filter(
        col("months_employed").isNull()
        | (col("months_employed") < 0)
    ).count()

    invalid_num_credit_lines = df.filter(
        col("num_credit_lines").isNull()
        | (col("num_credit_lines") < 0)
    ).count()

    invalid_interest_rate = df.filter(
        col("interest_rate").isNull()
        | (col("interest_rate") <= 0)
    ).count()

    invalid_loan_term = df.filter(
        col("loan_term").isNull()
        | (col("loan_term") <= 0)
    ).count()

    invalid_dti_ratio = df.filter(
        col("dti_ratio").isNull()
        | (col("dti_ratio") < 0)
        | (col("dti_ratio") > 1)
    ).count()

    invalid_default = df.filter(
        col("default").isNull()
        | (~col("default").isin(0, 1))
    ).count()

    invalid_education = df.filter(
        col("education").isNull()
        | (trim(col("education")) == "")
    ).count()

    invalid_employment_type = df.filter(
        col("employment_type").isNull()
        | (trim(col("employment_type")) == "")
    ).count()

    invalid_marital_status = df.filter(
        col("marital_status").isNull()
        | (trim(col("marital_status")) == "")
    ).count()

    invalid_loan_purpose = df.filter(
        col("loan_purpose").isNull()
        | (trim(col("loan_purpose")) == "")
    ).count()

    null_ingestion_timestamp = df.filter(
        col("_ingestion_timestamp").isNull()
    ).count()

    null_source_file = df.filter(
        col("_source_file").isNull()
        | (trim(col("_source_file")) == "")
    ).count()

    null_silver_timestamp = df.filter(
        col("_silver_timestamp").isNull()
    ).count()

    check_results = {
        "loan_id_not_null": {
            "passed": null_loan_id == 0,
            "observed": null_loan_id,
            "expected": 0,
        },
        "loan_id_unique": {
            "passed": duplicate_loan_ids == 0,
            "observed": duplicate_loan_ids,
            "expected": 0,
        },
        "age_between_18_and_100": {
            "passed": invalid_age == 0,
            "observed": invalid_age,
            "expected": 0,
        },
        "income_positive": {
            "passed": invalid_income == 0,
            "observed": invalid_income,
            "expected": 0,
        },
        "loan_amount_positive": {
            "passed": invalid_loan_amount == 0,
            "observed": invalid_loan_amount,
            "expected": 0,
        },
        "credit_score_between_300_and_850": {
            "passed": invalid_credit_score == 0,
            "observed": invalid_credit_score,
            "expected": 0,
        },
        "months_employed_non_negative": {
            "passed": invalid_months_employed == 0,
            "observed": invalid_months_employed,
            "expected": 0,
        },
        "num_credit_lines_non_negative": {
            "passed": invalid_num_credit_lines == 0,
            "observed": invalid_num_credit_lines,
            "expected": 0,
        },
        "interest_rate_positive": {
            "passed": invalid_interest_rate == 0,
            "observed": invalid_interest_rate,
            "expected": 0,
        },
        "loan_term_positive": {
            "passed": invalid_loan_term == 0,
            "observed": invalid_loan_term,
            "expected": 0,
        },
        "dti_ratio_between_0_and_1": {
            "passed": invalid_dti_ratio == 0,
            "observed": invalid_dti_ratio,
            "expected": 0,
        },
        "default_binary": {
            "passed": invalid_default == 0,
            "observed": invalid_default,
            "expected": 0,
        },
        "education_not_empty": {
            "passed": invalid_education == 0,
            "observed": invalid_education,
            "expected": 0,
        },
        "employment_type_not_empty": {
            "passed": invalid_employment_type == 0,
            "observed": invalid_employment_type,
            "expected": 0,
        },
        "marital_status_not_empty": {
            "passed": invalid_marital_status == 0,
            "observed": invalid_marital_status,
            "expected": 0,
        },
        "loan_purpose_not_empty": {
            "passed": invalid_loan_purpose == 0,
            "observed": invalid_loan_purpose,
            "expected": 0,
        },
        "ingestion_timestamp_not_null": {
            "passed": null_ingestion_timestamp == 0,
            "observed": null_ingestion_timestamp,
            "expected": 0,
        },
        "source_file_not_empty": {
            "passed": null_source_file == 0,
            "observed": null_source_file,
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

    print("=== SILVER LOANS DATA QUALITY REPORT ===")
    print(f"Total rows: {total_rows}")
    print(f"Distinct loan_id: {distinct_loan_ids}")
    print(f"Duplicate loan_id: {duplicate_loan_ids}")
    print()

    quality_run_id = create_quality_run_id()

    for check_name, result in check_results.items():
        status = "PASS" if result["passed"] else "FAIL"

        print(f"{status}: {check_name}")

        write_quality_result(
            quality_run_id=quality_run_id,
            dataset="loans",
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