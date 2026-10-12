from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F


USERS_PATH = "/opt/project/data/silver/users"
TRANSACTIONS_PATH = "/opt/project/data/silver/transactions"

GOLD_OUTPUT_PATH = (
    "/opt/project/data/gold/"
    "user_financial_profile"
)


spark = (
    SparkSession.builder
    .appName("gold_user_financial_profile")
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
            "edad",
            "salario_mensual",
            "ciudad",
            "estado_civil",
            "dependientes",
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
            "descripcion",
            "monto",
            "tipo",
            "categoria",
            "cuenta",
        )
    )


    # ========================================================
    # BASIC TRANSACTION METRICS
    # ========================================================

    transaction_metrics = (
        transactions_df
        .groupBy("user_id")
        .agg(
            F.count(
                "transaction_id"
            ).alias(
                "linked_transaction_count"
            ),

            F.min(
                "fecha"
            ).alias(
                "first_transaction_date"
            ),

            F.max(
                "fecha"
            ).alias(
                "last_transaction_date"
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

            F.avg(
                "monto"
            ).alias(
                "average_transaction_amount"
            ),

            F.countDistinct(
                F.date_format(
                    F.col("fecha"),
                    "yyyy-MM",
                )
            ).alias(
                "active_months"
            ),
        )
    )


    transaction_metrics = (
        transaction_metrics
        .withColumn(
            "transactional_balance",
            F.col("total_credits")
            - F.col("total_debits"),
        )
    )


    # ========================================================
    # PRIMARY ACCOUNT
    # ========================================================

    account_usage = (
        transactions_df
        .filter(
            F.col("cuenta").isNotNull()
        )
        .groupBy(
            "user_id",
            "cuenta",
        )
        .agg(
            F.count(
                "*"
            ).alias(
                "account_transaction_count"
            )
        )
    )


    account_window = (
        Window
        .partitionBy(
            "user_id"
        )
        .orderBy(
            F.desc(
                "account_transaction_count"
            ),
            F.asc(
                "cuenta"
            ),
        )
    )


    primary_account = (
        account_usage
        .withColumn(
            "account_rank",
            F.row_number().over(
                account_window
            ),
        )
        .filter(
            F.col(
                "account_rank"
            ) == 1
        )
        .select(
            "user_id",
            F.col(
                "cuenta"
            ).alias(
                "primary_account"
            ),
        )
    )


    # ========================================================
    # TOP SPENDING CATEGORY
    # ========================================================

    consumer_transactions = (
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
    )


    category_spending = (
        consumer_transactions
        .groupBy(
            "user_id",
            "categoria",
        )
        .agg(
            F.sum(
                "monto"
            ).alias(
                "category_total_spending"
            )
        )
    )


    category_window = (
        Window
        .partitionBy(
            "user_id"
        )
        .orderBy(
            F.desc(
                "category_total_spending"
            ),
            F.asc(
                "categoria"
            ),
        )
    )


    top_spending_category = (
        category_spending
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
            F.col(
                "categoria"
            ).alias(
                "top_spending_category"
            ),
        )
    )


    # ========================================================
    # BUILD GOLD PROFILE
    # ========================================================

    gold_df = (
        users_df
        .join(
            transaction_metrics,
            on="user_id",
            how="left",
        )
        .join(
            primary_account,
            on="user_id",
            how="left",
        )
        .join(
            top_spending_category,
            on="user_id",
            how="left",
        )
    )


    gold_df = (
        gold_df
        .withColumn(
            "has_transaction_data",
            F.col(
                "linked_transaction_count"
            ).isNotNull(),
        )
        .withColumn(
            "data_coverage_status",
            F.when(
                F.col(
                    "linked_transaction_count"
                ).isNotNull(),
                F.lit(
                    "AVAILABLE"
                ),
            ).otherwise(
                F.lit(
                    "NO_LINKED_TRANSACTIONS"
                )
            ),
        )
        .withColumn(
            "gold_created_at",
            F.current_timestamp(),
        )
    )


    # ========================================================
    # COLUMN ORDER
    # ========================================================

    gold_df = (
        gold_df
        .select(
            "user_id",
            "edad",
            "ciudad",
            "estado_civil",
            "dependientes",
            "salario_mensual",
            "has_transaction_data",
            "linked_transaction_count",
            "first_transaction_date",
            "last_transaction_date",
            "total_debits",
            "total_credits",
            "transactional_balance",
            "average_transaction_amount",
            "active_months",
            "primary_account",
            "top_spending_category",
            "data_coverage_status",
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

    total_users = (
        gold_df.count()
    )


    users_with_transactions = (
        gold_df
        .filter(
            F.col(
                "has_transaction_data"
            )
        )
        .count()
    )


    users_without_transactions = (
        total_users
        - users_with_transactions
    )


    print(
        "Gold user financial profile "
        "completed successfully."
    )

    print(
        f"Total users: "
        f"{total_users}"
    )

    print(
        "Users with transactions: "
        f"{users_with_transactions}"
    )

    print(
        "Users without linked transactions: "
        f"{users_without_transactions}"
    )

    print(
        "Gold output: "
        f"{GOLD_OUTPUT_PATH}"
    )


finally:
    spark.stop()