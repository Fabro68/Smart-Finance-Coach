from pyspark.sql import SparkSession


GOLD_PATH = "/opt/project/data/gold/user_financial_profile"


spark = (
    SparkSession.builder
    .appName("inspect_gold_user_financial_profile")
    .getOrCreate()
)


try:
    df = (
        spark.read
        .format("delta")
        .load(GOLD_PATH)
    )

    print("\n=== GOLD SCHEMA ===")
    df.printSchema()

    print("\n=== SAMPLE USERS WITH TRANSACTIONS ===")
    (
        df
        .filter("has_transaction_data = true")
        .orderBy("user_id")
        .show(
            10,
            truncate=False,
        )
    )

    print("\n=== SAMPLE USERS WITHOUT TRANSACTIONS ===")
    (
        df
        .filter("has_transaction_data = false")
        .orderBy("user_id")
        .show(
            5,
            truncate=False,
        )
    )

    print("\n=== COVERAGE SUMMARY ===")
    (
        df
        .groupBy("data_coverage_status")
        .count()
        .orderBy("data_coverage_status")
        .show(
            truncate=False,
        )
    )

finally:
    spark.stop()