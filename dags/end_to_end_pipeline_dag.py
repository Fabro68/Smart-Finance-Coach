from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator, ShortCircuitOperator

from raw_file_state import (
    detect_changes,
    get_current_state,
    save_state,
)


DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


def spark_task(task_id: str, script_path: str) -> BashOperator:
    return BashOperator(
        task_id=task_id,
        bash_command=(
            "docker exec smart-finance-spark "
            "/opt/spark/bin/spark-submit "
            f"/opt/project/{script_path}"
        ),
    )


def check_raw_changes() -> bool:
    changed_files = detect_changes()

    if not changed_files:
        print("No RAW file changes detected.")
        return False

    print("RAW changes detected:")
    for file_name in changed_files:
        print(f" - {file_name}")

    return True


def update_raw_state() -> None:
    current_state = get_current_state()
    save_state(current_state)
    print("RAW file state updated successfully.")


with DAG(
    dag_id="smart_finance_end_to_end_pipeline",
    description=(
        "Automated Smart Finance Coach pipeline: "
        "Raw -> Bronze -> Silver -> Quality -> Gold"
    ),
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 10, 20),
    schedule="*/5 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=[
        "smart-finance-coach",
        "end-to-end",
        "automated",
        "bronze",
        "silver",
        "gold",
    ],
) as dag:

    # ============================================================
    # RAW CHANGE DETECTION
    # ============================================================

    check_raw = ShortCircuitOperator(
        task_id="check_raw_changes",
        python_callable=check_raw_changes,
    )

    # ============================================================
    # BRONZE
    # ============================================================

    bronze_users = spark_task(
        "bronze_users",
        "src/ingestion/ingest_users.py",
    )

    bronze_transactions = spark_task(
        "bronze_transactions",
        "src/ingestion/ingest_transactions.py",
    )

    bronze_loans = spark_task(
        "bronze_loans",
        "src/ingestion/ingest_loans.py",
    )

    bronze_economic = spark_task(
        "bronze_economic",
        "src/ingestion/ingest_economic_data.py",
    )

    # ============================================================
    # SILVER
    # ============================================================

    silver_users = spark_task(
        "silver_users",
        "src/transformation/silver_users.py",
    )

    silver_transactions = spark_task(
        "silver_transactions",
        "src/transformation/silver_transactions.py",
    )

    silver_loans = spark_task(
        "silver_loans",
        "src/transformation/silver_loans.py",
    )

    silver_economic = spark_task(
        "silver_economic",
        "src/transformation/silver_economic_data.py",
    )

    # ============================================================
    # SILVER QUALITY
    # ============================================================

    validate_users = spark_task(
        "validate_silver_users",
        "src/quality/validate_silver_users.py",
    )

    validate_transactions = spark_task(
        "validate_silver_transactions",
        "src/quality/validate_silver_transactions.py",
    )

    validate_loans = spark_task(
        "validate_silver_loans",
        "src/quality/validate_silver_loans.py",
    )

    validate_economic = spark_task(
        "validate_silver_economic",
        "src/quality/validate_silver_economic_data.py",
    )

    validate_relationship = spark_task(
        "validate_user_transaction_relationship",
        "src/quality/validate_user_transaction_relationship.py",
    )

    # ============================================================
    # GOLD
    # ============================================================

    gold_profile = spark_task(
        "gold_user_financial_profile",
        "src/analytics/gold_user_financial_profile.py",
    )

    gold_monthly_finance = spark_task(
        "gold_user_monthly_finance",
        "src/analytics/gold_user_monthly_finance.py",
    )

    gold_category_monthly = spark_task(
        "gold_user_category_monthly",
        "src/analytics/gold_user_category_monthly.py",
    )

    gold_macro = spark_task(
        "gold_monthly_macro_context",
        "src/analytics/gold_monthly_macro_context.py",
    )

    gold_loan_risk = spark_task(
        "gold_loan_risk_training",
        "src/analytics/gold_loan_risk_training.py",
    )

    gold_kpis = spark_task(
        "gold_user_financial_kpis",
        "src/analytics/gold_user_financial_kpis.py",
    )

    validate_gold = spark_task(
        "validate_gold_layer",
        "src/analytics/validate_gold_layer.py",
    )

    save_raw_state = PythonOperator(
        task_id="save_raw_state",
        python_callable=update_raw_state,
    )

    # ============================================================
    # DEPENDENCIES
    # ============================================================

    check_raw >> [
        bronze_users,
        bronze_transactions,
        bronze_loans,
        bronze_economic,
    ]

    bronze_users >> silver_users >> validate_users
    bronze_transactions >> silver_transactions >> validate_transactions
    bronze_loans >> silver_loans >> validate_loans
    bronze_economic >> silver_economic >> validate_economic

    [validate_users, validate_transactions] >> validate_relationship

    [
        validate_users,
        validate_transactions,
        validate_relationship,
    ] >> gold_profile

    [
        validate_users,
        validate_transactions,
        validate_relationship,
    ] >> gold_monthly_finance

    validate_transactions >> gold_category_monthly
    validate_economic >> gold_macro
    validate_loans >> gold_loan_risk

    gold_monthly_finance >> gold_kpis

    [
        gold_profile,
        gold_monthly_finance,
        gold_category_monthly,
        gold_macro,
        gold_loan_risk,
        gold_kpis,
    ] >> validate_gold

    validate_gold >> save_raw_state