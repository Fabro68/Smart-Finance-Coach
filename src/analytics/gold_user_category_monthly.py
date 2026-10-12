from pyspark.sql import SparkSession
from pyspark.sql import functions as F


TRANSACTIONS_PATH = "/opt/project/data/silver/transactions"

GOLD_OUTPUT_PATH = (
    "/opt/project/data/gold/"
    "user_category_monthly"
)


spark = (
    SparkSession.builder
    .appName("gold_user_category_monthly")
    .getOrCreate()
)


try:
    # ========================================================
    # LOAD LINKED TRANSACTIONS
    # ========================================================

    transactions_df = (
        spark.read
        .format("delta")
        .load(TRANSACTIONS_PATH)
        .filter(
            F.col("user_id").isNotNull()
        )
        .filter(
            F.lower(
                F.col("tipo")
            ) == "debit"
        )
        .filter(
            F.col("categoria")
            != "Credit Card Payment"
        )
        .select(
            "transaction_id",
            "user_id",
            "fecha",
            "monto",
            "categoria",
        )
        .withColumn(
            "year_month",
            F.date_format(
                F.col("fecha"),
                "yyyy-MM",
            ),
        )
    )


    # ========================================================
    # MONTHLY CATEGORY AGGREGATION
    # ========================================================

    category_df = (
        transactions_df
        .groupBy(
            "user_id",
            "year_month",
            "categoria",
        )
        .agg(
            F.count(
                "transaction_id"
            ).alias(
                "transaction_count"
            ),

            F.sum(
                "monto"
            ).alias(
                "total_amount"
            ),

            F.avg(
                "monto"
            ).alias(
                "average_amount"
            ),
        )
    )


    # ========================================================
    # TOTAL CONSUMER SPENDING PER MONTH
    # ========================================================

    monthly_totals = (
        category_df
        .groupBy(
            "user_id",
            "year_month",
        )
        .agg(
            F.sum(
                "total_amount"
            ).alias(
                "monthly_consumer_spending"
            )
        )
    )


    # ========================================================
    # CATEGORY SHARE
    # ========================================================

    gold_df = (
        category_df
        .join(
            monthly_totals,
            on=[
                "user_id",
                "year_month",
            ],
            how="left",
        )
        .withColumn(
            "percentage_of_monthly_spending",
            F.when(
                F.col(
                    "monthly_consumer_spending"
                ) > 0,
                F.col("total_amount")
                / F.col(
                    "monthly_consumer_spending"
                ),
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
            "user_id",
            "year_month",
            "categoria",
            "transaction_count",
            "total_amount",
            "average_amount",
            "percentage_of_monthly_spending",
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


    distinct_users = (
        gold_df
        .select("user_id")
        .distinct()
        .count()
    )


    distinct_categories = (
        gold_df
        .select("categoria")
        .distinct()
        .count()
    )


    print(
        "Gold user category monthly "
        "completed successfully."
    )

    print(
        f"Total user-month-category rows: "
        f"{total_rows}"
    )

    print(
        f"Distinct users: "
        f"{distinct_users}"
    )

    print(
        f"Distinct categories: "
        f"{distinct_categories}"
    )

    print(
        "Gold output: "
        f"{GOLD_OUTPUT_PATH}"
    )


finally:
    spark.stop()