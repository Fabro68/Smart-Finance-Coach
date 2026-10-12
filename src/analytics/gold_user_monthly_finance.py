from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F


USERS_PATH = "/opt/project/data/silver/users"
TRANSACTIONS_PATH = "/opt/project/data/silver/transactions"

GOLD_OUTPUT_PATH = (
    "/opt/project/data/gold/"
    "user_monthly_finance"
)


spark = (
    SparkSession.builder
    .appName("gold_user_monthly_finance")
    .getOrCreate()
)


try:
    # ========================================================
    # LOAD SILVER DATA
    # ========================================================

    users_df = (
        spark.read
        .format("delta")
        .load(USERS_PATH)
        .select(
            "user_id",
            "salario_mensual",
        )
    )


    transactions_df = (
        spark.read
        .format("delta")
        .load(TRANSACTIONS_PATH)
        .filter(
            F.col("user_id").isNotNull()
        )
        .select(
            "transaction_id",
            "user_id",
            "fecha",
            "monto",
            "tipo",
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
    # MONTHLY TRANSACTION METRICS
    # ========================================================

    monthly_metrics = (
        transactions_df
        .groupBy(
            "user_id",
            "year_month",
        )
        .agg(
            F.count(
                "transaction_id"
            ).alias(
                "transaction_count"
            ),

            F.sum(
                F.when(
                    F.lower(
                        F.col("tipo")
                    ) == "debit",
                    1,
                ).otherwise(0)
            ).alias(
                "debit_count"
            ),

            F.sum(
                F.when(
                    F.lower(
                        F.col("tipo")
                    ) == "credit",
                    1,
                ).otherwise(0)
            ).alias(
                "credit_count"
            ),

            F.sum(
                F.when(
                    F.lower(
                        F.col("tipo")
                    ) == "debit",
                    F.col("monto"),
                ).otherwise(0.0)
            ).alias(
                "total_debits"
            ),

            F.sum(
                F.when(
                    F.lower(
                        F.col("tipo")
                    ) == "credit",
                    F.col("monto"),
                ).otherwise(0.0)
            ).alias(
                "total_credits"
            ),

            F.sum(
                F.when(
                    (
                        F.lower(
                            F.col("tipo")
                        ) == "debit"
                    )
                    &
                    (
                        F.col("categoria")
                        != "Credit Card Payment"
                    ),
                    F.col("monto"),
                ).otherwise(0.0)
            ).alias(
                "consumer_spending"
            ),

            F.sum(
                F.when(
                    (
                        F.lower(
                            F.col("tipo")
                        ) == "debit"
                    )
                    &
                    (
                        F.col("categoria")
                        == "Credit Card Payment"
                    ),
                    F.col("monto"),
                ).otherwise(0.0)
            ).alias(
                "credit_card_payments"
            ),

            F.avg(
                F.when(
                    F.lower(
                        F.col("tipo")
                    ) == "debit",
                    F.col("monto"),
                )
            ).alias(
                "average_debit_amount"
            ),

            F.avg(
                F.when(
                    F.lower(
                        F.col("tipo")
                    ) == "credit",
                    F.col("monto"),
                )
            ).alias(
                "average_credit_amount"
            ),
        )
    )


    # ========================================================
    # TOP SPENDING CATEGORY PER USER-MONTH
    # ========================================================

    category_monthly = (
        transactions_df
        .filter(
            F.lower(
                F.col("tipo")
            ) == "debit"
        )
        .filter(
            F.col("categoria")
            != "Credit Card Payment"
        )
        .groupBy(
            "user_id",
            "year_month",
            "categoria",
        )
        .agg(
            F.sum(
                "monto"
            ).alias(
                "category_spending"
            )
        )
    )


    category_window = (
        Window
        .partitionBy(
            "user_id",
            "year_month",
        )
        .orderBy(
            F.desc(
                "category_spending"
            ),
            F.asc(
                "categoria"
            ),
        )
    )


    top_category = (
        category_monthly
        .withColumn(
            "category_rank",
            F.row_number().over(
                category_window
            ),
        )
        .filter(
            F.col(
                "category_rank"
            ) == 1
        )
        .select(
            "user_id",
            "year_month",
            F.col(
                "categoria"
            ).alias(
                "top_spending_category"
            ),
        )
    )


    # ========================================================
    # JOIN USER SALARY
    # ========================================================

    gold_df = (
        monthly_metrics
        .join(
            users_df,
            on="user_id",
            how="left",
        )
        .join(
            top_category,
            on=[
                "user_id",
                "year_month",
            ],
            how="left",
        )
    )


    # ========================================================
    # FINANCIAL KPIS
    # ========================================================

    gold_df = (
        gold_df
        .withColumn(
            "transactional_balance",
            F.col("total_credits")
            - F.col("total_debits"),
        )
        .withColumn(
            "estimated_margin",
            F.col("salario_mensual")
            - F.col("consumer_spending"),
        )
        .withColumn(
            "spending_to_salary_ratio",
            F.when(
                F.col("salario_mensual") > 0,
                F.col("consumer_spending")
                / F.col("salario_mensual"),
            ),
        )
        .withColumn(
            "estimated_savings_capacity",
            F.greatest(
                F.col("salario_mensual")
                - F.col("consumer_spending"),
                F.lit(0.0),
            ),
        )
        .withColumn(
            "estimated_savings_rate",
            F.when(
                F.col("salario_mensual") > 0,
                F.greatest(
                    F.col("salario_mensual")
                    - F.col("consumer_spending"),
                    F.lit(0.0),
                )
                / F.col("salario_mensual"),
            ),
        )
        .withColumn(
            "has_transaction_data",
            F.lit(True),
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
            F.col(
                "salario_mensual"
            ).alias(
                "salary_monthly"
            ),
            "transaction_count",
            "debit_count",
            "credit_count",
            "total_debits",
            "total_credits",
            "transactional_balance",
            "consumer_spending",
            "credit_card_payments",
            "estimated_margin",
            "spending_to_salary_ratio",
            "estimated_savings_capacity",
            "estimated_savings_rate",
            "average_debit_amount",
            "average_credit_amount",
            "top_spending_category",
            "has_transaction_data",
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


    first_month = (
        gold_df
        .agg(
            F.min(
                "year_month"
            )
        )
        .first()[0]
    )


    last_month = (
        gold_df
        .agg(
            F.max(
                "year_month"
            )
        )
        .first()[0]
    )


    print(
        "Gold user monthly finance "
        "completed successfully."
    )

    print(
        f"Total user-month rows: "
        f"{total_rows}"
    )

    print(
        f"Distinct users: "
        f"{distinct_users}"
    )

    print(
        f"Period: "
        f"{first_month} to {last_month}"
    )

    print(
        "Gold output: "
        f"{GOLD_OUTPUT_PATH}"
    )


finally:
    spark.stop()