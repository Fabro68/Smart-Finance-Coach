from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="bronze_ingestion_pipeline",
    description="Orquestación de ingestas Raw hacia Bronze Delta Lake",
    start_date=datetime(2026, 9, 1),
    schedule=None,
    catchup=False,
    tags=["smart-finance-coach", "bronze", "ingestion"],
) as dag:

    ingest_users = BashOperator(
        task_id="ingest_users",
        bash_command=(
            "docker exec smart-finance-spark "
            "/opt/spark/bin/spark-submit "
            "/opt/project/src/ingestion/ingest_users.py"
        ),
    )

    ingest_transactions = BashOperator(
        task_id="ingest_transactions",
        bash_command=(
            "docker exec smart-finance-spark "
            "/opt/spark/bin/spark-submit "
            "/opt/project/src/ingestion/ingest_transactions.py"
        ),
    )

    ingest_loans = BashOperator(
        task_id="ingest_loans",
        bash_command=(
            "docker exec smart-finance-spark "
            "/opt/spark/bin/spark-submit "
            "/opt/project/src/ingestion/ingest_loans.py"
        ),
    )

    ingest_economic_data = BashOperator(
        task_id="ingest_economic_data",
        bash_command=(
            "docker exec smart-finance-spark "
            "/opt/spark/bin/spark-submit "
            "/opt/project/src/ingestion/ingest_economic_data.py"
        ),
    )

    ingest_users >> ingest_transactions >> ingest_loans >> ingest_economic_data