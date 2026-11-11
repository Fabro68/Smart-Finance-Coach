import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


USERS_GOLD_PATH = "/opt/project/data/gold/user_financial_profile"
MONTHLY_GOLD_PATH = "/opt/project/data/gold/user_monthly_finance"
CATEGORY_GOLD_PATH = "/opt/project/data/gold/user_category_monthly"
MACRO_GOLD_PATH = "/opt/project/data/gold/monthly_macro_context"
LOANS_GOLD_PATH = "/opt/project/data/gold/loan_risk_training"
LOAN_ML_GOLD_PATH = "/opt/project/data/gold/loan_ml_dataset"
ML_USER_FEATURES_GOLD_PATH = "/opt/project/data/gold/ml_user_features"

ANOMALY_MIN_PRIOR_MONTHS = 3

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


validation_passed = False

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

    loan_ml_df = (
        spark.read.format("delta")
        .load(LOAN_ML_GOLD_PATH)
    )

    ml_user_df = (
        spark.read.format("delta")
        .load(ML_USER_FEATURES_GOLD_PATH)
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
    # LOAN ML DATASET
    # ========================================================

    loan_ml_rows = loan_ml_df.count()

    checks.append(
        print_check(
            "Loan ML row count vs loan_risk_training",
            loan_ml_rows == loan_rows,
            (
                f"{loan_ml_rows} rows vs "
                f"{loan_rows} in loan_risk_training"
            ),
        )
    )

    loan_ml_unique_ids = (
        loan_ml_df
        .select("loan_id")
        .distinct()
        .count()
    )

    checks.append(
        print_check(
            "Loan ML unique loan_id",
            loan_ml_rows == loan_ml_unique_ids,
            (
                f"{loan_ml_unique_ids} unique loan IDs "
                f"for {loan_ml_rows} rows"
            ),
        )
    )

    loan_ml_null_counts = (
        loan_ml_df
        .select([
            F.sum(
                F.col(column).isNull().cast("int")
            ).alias(column)
            for column in loan_ml_df.columns
        ])
        .first()
        .asDict()
    )

    loan_ml_null_columns = {
        column: count
        for column, count in loan_ml_null_counts.items()
        if count
    }

    checks.append(
        print_check(
            "Loan ML no nulls",
            not loan_ml_null_columns,
            (
                f"columns with nulls: {loan_ml_null_columns}"
                if loan_ml_null_columns
                else "0 null values"
            ),
        )
    )

    invalid_split_values = (
        loan_ml_df
        .filter(
            ~F.col("split").isin(
                "train",
                "validation",
                "test",
            )
            | F.col("split").isNull()
        )
        .count()
    )

    checks.append(
        print_check(
            "Loan ML split values",
            invalid_split_values == 0,
            f"{invalid_split_values} invalid split values",
        )
    )

    global_default_rate = (
        loan_ml_df
        .agg(F.avg("default").alias("rate"))
        .first()["rate"]
    )

    split_default_rates = {
        row["split"]: row["rate"]
        for row in (
            loan_ml_df
            .groupBy("split")
            .agg(F.avg("default").alias("rate"))
            .collect()
        )
    }

    max_rate_gap = max(
        abs(rate - global_default_rate)
        for rate in split_default_rates.values()
    )

    checks.append(
        print_check(
            "Loan ML split stratification",
            (
                set(split_default_rates)
                == {"train", "validation", "test"}
                and max_rate_gap < 0.001
            ),
            (
                f"global rate {global_default_rate:.4%}, "
                f"max gap {max_rate_gap:.6f}, "
                + ", ".join(
                    f"{split} {rate:.4%}"
                    for split, rate in sorted(
                        split_default_rates.items()
                    )
                )
            ),
        )
    )

    binary_condition = None

    for column in [
        "has_mortgage",
        "has_dependents",
        "has_cosigner",
    ]:
        column_invalid = (
            ~F.col(column).isin(0, 1)
            | F.col(column).isNull()
        )
        binary_condition = (
            column_invalid
            if binary_condition is None
            else binary_condition | column_invalid
        )

    invalid_binary_rows = (
        loan_ml_df
        .filter(binary_condition)
        .count()
    )

    checks.append(
        print_check(
            "Loan ML binary columns",
            invalid_binary_rows == 0,
            (
                f"{invalid_binary_rows} rows with values "
                f"outside {{0, 1}}"
            ),
        )
    )

    non_positive_payment_rows = (
        loan_ml_df
        .filter(
            (F.col("estimated_monthly_payment") <= 0)
            | (F.col("payment_to_income_ratio") <= 0)
            | F.col("estimated_monthly_payment").isNull()
            | F.col("payment_to_income_ratio").isNull()
        )
        .count()
    )

    checks.append(
        print_check(
            "Loan ML payment features positive",
            non_positive_payment_rows == 0,
            (
                f"{non_positive_payment_rows} rows with "
                f"non-positive payment features"
            ),
        )
    )

    # ========================================================
    # ML USER FEATURES
    # ========================================================

    ml_user_rows = ml_user_df.count()

    checks.append(
        print_check(
            "ML user features row count vs monthly finance",
            ml_user_rows == monthly_rows,
            (
                f"{ml_user_rows} rows vs "
                f"{monthly_rows} in user_monthly_finance"
            ),
        )
    )

    ml_user_unique_keys = (
        ml_user_df
        .select(
            "user_id",
            "year_month",
        )
        .distinct()
        .count()
    )

    checks.append(
        print_check(
            "ML user features unique grain",
            ml_user_rows == ml_user_unique_keys,
            (
                f"{ml_user_unique_keys} unique "
                f"(user_id, year_month) keys "
                f"for {ml_user_rows} rows"
            ),
        )
    )

    missing_macro_rows = (
        ml_user_df
        .filter(
            F.col("cpi_index").isNull()
            | F.col("annual_inflation_pct").isNull()
            | F.col("macro_interest_rate").isNull()
            | F.col("average_exchange_rate").isNull()
        )
        .count()
    )

    checks.append(
        print_check(
            "ML user features macro coverage",
            missing_macro_rows == 0,
            f"{missing_macro_rows} user-months without macro data",
        )
    )

    invalid_flag_rows = (
        ml_user_df
        .filter(
            ~F.col("has_dependents").isin(0, 1)
            | F.col("has_dependents").isNull()
            | ~F.col("income_outside_training_range").isin(0, 1)
            | F.col("income_outside_training_range").isNull()
            | (
                F.col("is_spend_anomaly").isNotNull()
                & ~F.col("is_spend_anomaly").isin(0, 1)
            )
        )
        .count()
    )

    checks.append(
        print_check(
            "ML user features flag values",
            invalid_flag_rows == 0,
            f"{invalid_flag_rows} rows with invalid flag values",
        )
    )

    # is_spend_anomaly debe ser NULL si y solo si hay menos de
    # ANOMALY_MIN_PRIOR_MONTHS meses previos (history_months incluye
    # el mes actual).
    anomaly_rule_errors = (
        ml_user_df
        .filter(
            (
                F.col("is_spend_anomaly").isNull()
                & (F.col("history_months") > ANOMALY_MIN_PRIOR_MONTHS)
            )
            | (
                F.col("is_spend_anomaly").isNotNull()
                & (F.col("history_months") <= ANOMALY_MIN_PRIOR_MONTHS)
            )
        )
        .count()
    )

    checks.append(
        print_check(
            "ML user features anomaly history rule",
            anomaly_rule_errors == 0,
            (
                f"{anomaly_rule_errors} rows violating the "
                f"{ANOMALY_MIN_PRIOR_MONTHS}-prior-month rule"
            ),
        )
    )

    history_errors = (
        ml_user_df
        .groupBy("user_id")
        .agg(
            F.count("*").alias("months"),
            F.min("history_months").alias("min_history"),
            F.max("history_months").alias("max_history"),
        )
        .filter(
            (F.col("min_history") != 1)
            | (F.col("max_history") != F.col("months"))
        )
        .count()
    )

    checks.append(
        print_check(
            "ML user features history_months consistency",
            history_errors == 0,
            f"{history_errors} users with inconsistent history_months",
        )
    )

    # Sin fuga de datos: en el primer mes solo existe ese mes, por lo
    # que el promedio de 3 meses debe ser igual al gasto del mes y no
    # puede existir variacion contra un mes anterior.
    leakage_errors = (
        ml_user_df
        .filter(F.col("history_months") == 1)
        .filter(
            (
                F.abs(
                    F.col("avg_spend_3m")
                    - F.col("consumer_spending")
                ) > 0.0001
            )
            | F.col("spend_mom_pct").isNotNull()
        )
        .count()
    )

    checks.append(
        print_check(
            "ML user features no look-ahead in windows",
            leakage_errors == 0,
            (
                f"{leakage_errors} first-month rows using "
                f"data from other months"
            ),
        )
    )

    bridge_errors = (
        ml_user_df
        .filter(
            F.col("marital_status_model").isNull()
            | F.col("annual_income_usd").isNull()
            | (F.col("annual_income_usd") <= 0)
        )
        .count()
    )

    checks.append(
        print_check(
            "ML user features loan model bridge",
            bridge_errors == 0,
            (
                f"{bridge_errors} rows with unmapped marital status "
                f"or invalid annual_income_usd"
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

    validation_passed = passed_checks == total_checks

    if validation_passed:
        print(
            "GOLD LAYER VALIDATION: PASS"
        )
    else:
        print(
            "GOLD LAYER VALIDATION: FAIL"
        )


finally:
    spark.stop()


if not validation_passed:
    sys.exit(1)