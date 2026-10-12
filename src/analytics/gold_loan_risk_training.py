from pyspark.sql import SparkSession
from pyspark.sql import functions as F


LOANS_PATH = "/opt/project/data/silver/loans"

GOLD_OUTPUT_PATH = (
    "/opt/project/data/gold/"
    "loan_risk_training"
)


spark = (
    SparkSession.builder
    .appName("gold_loan_risk_training")
    .getOrCreate()
)


try:
    # ========================================================
    # LOAD SILVER LOANS
    # ========================================================

    loans_df = (
        spark.read
        .format("delta")
        .load(LOANS_PATH)
        .select(
            "loan_id",
            "age",
            "income",
            "loan_amount",
            "credit_score",
            "months_employed",
            "num_credit_lines",
            "interest_rate",
            "loan_term",
            "dti_ratio",
            "education",
            "employment_type",
            "marital_status",
            "has_mortgage",
            "has_dependents",
            "loan_purpose",
            "has_cosigner",
            "default",
        )
    )


    # ========================================================
    # ANALYTICAL FEATURES
    # ========================================================

    gold_df = (
        loans_df
        .withColumn(
            "loan_to_income_ratio",
            F.when(
                F.col("income") > 0,
                F.col("loan_amount")
                / F.col("income"),
            ),
        )
        .withColumn(
            "employment_years",
            F.col("months_employed")
            / F.lit(12.0),
        )
        .withColumn(
            "monthly_income",
            F.when(
                F.col("income") > 0,
                F.col("income")
                / F.lit(12.0),
            ),
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
            "loan_id",
            "age",
            "income",
            "monthly_income",
            "loan_amount",
            "loan_to_income_ratio",
            "credit_score",
            "months_employed",
            "employment_years",
            "num_credit_lines",
            "interest_rate",
            "loan_term",
            "dti_ratio",
            "education",
            "employment_type",
            "marital_status",
            "has_mortgage",
            "has_dependents",
            "loan_purpose",
            "has_cosigner",
            "default",
            "gold_created_at",
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

    distinct_loans = (
        gold_df
        .select("loan_id")
        .distinct()
        .count()
    )

    defaulted_loans = (
        gold_df
        .filter(
            F.col("default") == 1
        )
        .count()
    )

    default_rate = (
        defaulted_loans
        / total_rows
        if total_rows > 0
        else 0.0
    )


    print(
        "Gold loan risk training "
        "completed successfully."
    )

    print(
        f"Total rows: "
        f"{total_rows}"
    )

    print(
        f"Distinct loan IDs: "
        f"{distinct_loans}"
    )

    print(
        f"Defaulted loans: "
        f"{defaulted_loans}"
    )

    print(
        f"Default rate: "
        f"{default_rate:.4%}"
    )

    print(
        "Gold output: "
        f"{GOLD_OUTPUT_PATH}"
    )


finally:
    spark.stop()