from pyspark.sql import SparkSession
from pyspark.sql import functions as F


USERS_GOLD_PATH = "/opt/project/data/gold/user_financial_profile"
MONTHLY_GOLD_PATH = "/opt/project/data/gold/user_monthly_finance"
CATEGORY_GOLD_PATH = "/opt/project/data/gold/user_category_monthly"
MACRO_GOLD_PATH = "/opt/project/data/gold/monthly_macro_context"
LOANS_GOLD_PATH = "/opt/project/data/gold/loan_risk_training"

TRANSACTIONS_SILVER_PATH = "/opt/project/data/silver/transactions"


spark = (
    SparkSession.builder
    .appName("validate_gold_layer")
    .getOrCreate()
)


def print_check(name, passed, detail):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}: {detail}")
    return passed


try:
    profile_df = (
        spark.read.format("delta")
        .load(USERS_GOLD_PATH)
    )

    monthly_df = (
        spark.read.format("delta")
        .load(MONTHLY_GOLD_PATH)
    )

    category_df = (
        spark.read.format("delta")
        .load(CATEGORY_GOLD_PATH)
    )

    macro_df = (
        spark.read.format("delta")
        .load(MACRO_GOLD_PATH)
    )

    loans_df = (
        spark.read.format("delta")
        .load(LOANS_GOLD_PATH)
    )

    transactions_df = (
        spark.read.format("delta")
        .load(TRANSACTIONS_SILVER_PATH)
    )

    checks = []

    print("\n=== GOLD LAYER VALIDATION ===\n")

    # ========================================================
    # USER FINANCIAL PROFILE
    # ========================================================

    profile_rows = profile_df.count()

    profile_unique_users = (
        profile_df
        .select("user_id")
        .distinct()
        .count()
    )

    checks.append(
        print_check(
            "Profile row count",
            profile_rows == 100,
            f"{profile_rows} rows",
        )
    )

    checks.append(
        print_check(
            "Profile unique user_id",
            profile_rows == profile_unique_users,
            (
                f"{profile_unique_users} unique IDs "
                f"for {profile_rows} rows"
            ),
        )
    )

    # ========================================================
    # MONTHLY FINANCE
    # ========================================================

    monthly_rows = monthly_df.count()

    monthly_unique_keys = (
        monthly_df
        .select(
            "user_id",
            "year_month",
        )
        .distinct()
        .count()
    )

    monthly_users = (
        monthly_df
        .select("user_id")
        .distinct()
        .count()
    )

    monthly_period = (
        monthly_df
        .agg(
            F.min("year_month").alias("min_month"),
            F.max("year_month").alias("max_month"),
        )
        .first()
    )

    checks.append(
        print_check(
            "Monthly unique grain",
            monthly_rows == monthly_unique_keys,
            (
                f"{monthly_unique_keys} unique "
                f"(user_id, year_month) keys "
                f"for {monthly_rows} rows"
            ),
        )
    )

    checks.append(
        print_check(
            "Monthly distinct users",
            monthly_users == 3,
            f"{monthly_users} users",
        )
    )

    checks.append(
        print_check(
            "Monthly period",
            (
                monthly_period["min_month"] == "2018-01"
                and monthly_period["max_month"] == "2019-09"
            ),
            (
                f"{monthly_period['min_month']} "
                f"to {monthly_period['max_month']}"
            ),
        )
    )

    # ========================================================
    # MONTHLY FORMULAS
    # ========================================================

    balance_errors = (
        monthly_df
        .filter(
            F.abs(
                F.col("transactional_balance")
                - (
                    F.col("total_credits")
                    - F.col("total_debits")
                )
            ) > 0.0001
        )
        .count()
    )

    margin_errors = (
        monthly_df
        .filter(
            F.abs(
                F.col("estimated_margin")
                - (
                    F.col("salary_monthly")
                    - F.col("consumer_spending")
                )
            ) > 0.0001
        )
        .count()
    )

    savings_errors = (
        monthly_df
        .filter(
            F.abs(
                F.col("estimated_savings_capacity")
                - F.greatest(
                    (
                        F.col("salary_monthly")
                        - F.col("consumer_spending")
                    ),
                    F.lit(0.0),
                )
            ) > 0.0001
        )
        .count()
    )

    ratio_errors = (
        monthly_df
        .filter(
            (F.col("salary_monthly") > 0)
            & (
                F.abs(
                    F.col("spending_to_salary_ratio")
                    - (
                        F.col("consumer_spending")
                        / F.col("salary_monthly")
                    )
                ) > 0.0001
            )
        )
        .count()
    )

    checks.append(
        print_check(
            "Transactional balance formula",
            balance_errors == 0,
            f"{balance_errors} invalid rows",
        )
    )

    checks.append(
        print_check(
            "Estimated margin formula",
            margin_errors == 0,
            f"{margin_errors} invalid rows",
        )
    )

    checks.append(
        print_check(
            "Estimated savings capacity formula",
            savings_errors == 0,
            f"{savings_errors} invalid rows",
        )
    )

    checks.append(
        print_check(
            "Spending-to-salary ratio formula",
            ratio_errors == 0,
            f"{ratio_errors} invalid rows",
        )
    )

    # ========================================================
    # CATEGORY MONTHLY
    # ========================================================

    category_rows = category_df.count()

    category_unique_keys = (
        category_df
        .select(
            "user_id",
            "year_month",
            "categoria",
        )
        .distinct()
        .count()
    )

    checks.append(
        print_check(
            "Category unique grain",
            category_rows == category_unique_keys,
            (
                f"{category_unique_keys} unique "
                f"(user_id, year_month, categoria) keys "
                f"for {category_rows} rows"
            ),
        )
    )

    category_totals = (
        category_df
        .groupBy(
            "user_id",
            "year_month",
        )
        .agg(
            F.sum("total_amount")
            .alias("category_consumer_spending")
        )
    )

    category_vs_monthly = (
        monthly_df
        .select(
            "user_id",
            "year_month",
            "consumer_spending",
        )
        .join(
            category_totals,
            on=[
                "user_id",
                "year_month",
            ],
            how="left",
        )
    )

    category_amount_errors = (
        category_vs_monthly
        .filter(
            F.abs(
                F.coalesce(
                    F.col("consumer_spending"),
                    F.lit(0.0),
                )
                - F.coalesce(
                    F.col("category_consumer_spending"),
                    F.lit(0.0),
                )
            ) > 0.0001
        )
        .count()
    )

    checks.append(
        print_check(
            "Category totals vs consumer spending",
            category_amount_errors == 0,
            f"{category_amount_errors} mismatched user-months",
        )
    )

    category_share_errors = (
        category_df
        .groupBy(
            "user_id",
            "year_month",
        )
        .agg(
            F.sum(
                "percentage_of_monthly_spending"
            ).alias("share_sum")
        )
        .filter(
            F.abs(
                F.col("share_sum")
                - F.lit(1.0)
            ) > 0.0001
        )
        .count()
    )

    checks.append(
        print_check(
            "Category spending shares",
            category_share_errors == 0,
            (
                f"{category_share_errors} "
                f"user-months not summing to 1"
            ),
        )
    )

    # ========================================================
    # NULL CATEGORY CAVEAT
    # ========================================================

    linked_debit_null_category = (
        transactions_df
        .filter(
            F.col("user_id").isNotNull()
            & (F.col("tipo") == "debit")
            & F.col("categoria").isNull()
        )
        .count()
    )

    checks.append(
        print_check(
            "Linked debit null categories",
            linked_debit_null_category == 0,
            (
                f"{linked_debit_null_category} linked debit "
                f"transactions with null category"
            ),
        )
    )

    # ========================================================
    # MACRO CONTEXT
    # ========================================================

    macro_rows = macro_df.count()

    macro_unique_months = (
        macro_df
        .select("year_month")
        .distinct()
        .count()
    )

    checks.append(
        print_check(
            "Macro monthly grain",
            (
                macro_rows == 27
                and macro_unique_months == 27
            ),
            (
                f"{macro_rows} rows, "
                f"{macro_unique_months} unique months"
            ),
        )
    )

    # ========================================================
    # LOAN RISK TRAINING
    # ========================================================

    loan_rows = loans_df.count()

    loan_unique_ids = (
        loans_df
        .select("loan_id")
        .distinct()
        .count()
    )

    invalid_default_values = (
        loans_df
        .filter(
            ~F.col("default").isin(
                0,
                1,
            )
            | F.col("default").isNull()
        )
        .count()
    )

    checks.append(
        print_check(
            "Loan unique grain",
            loan_rows == loan_unique_ids,
            (
                f"{loan_unique_ids} unique loan IDs "
                f"for {loan_rows} rows"
            ),
        )
    )

    checks.append(
        print_check(
            "Loan default target validity",
            invalid_default_values == 0,
            (
                f"{invalid_default_values} invalid "
                f"default values"
            ),
        )
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    passed_checks = sum(checks)
    total_checks = len(checks)

    print("\n=== VALIDATION SUMMARY ===")

    print(
        f"Passed checks: "
        f"{passed_checks}/{total_checks}"
    )

    if passed_checks == total_checks:
        print(
            "GOLD LAYER VALIDATION: PASS"
        )
    else:
        print(
            "GOLD LAYER VALIDATION: FAIL"
        )


finally:
    spark.stop()