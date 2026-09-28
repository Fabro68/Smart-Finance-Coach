import sys

from pyspark.sql import SparkSession
from delta.tables import DeltaTable


SILVER_PATHS = {
    "users": "/opt/project/data/silver/users",
    "transactions": "/opt/project/data/silver/transactions",
    "loans": "/opt/project/data/silver/loans",
    "economic_data": "/opt/project/data/silver/economic_data",
}


if len(sys.argv) != 2:
    print(
        "Usage: spark-submit show_delta_history.py "
        "[users|transactions|loans|economic_data]"
    )
    sys.exit(1)


dataset = sys.argv[1].lower()

if dataset not in SILVER_PATHS:
    print(f"Invalid dataset: {dataset}")
    print("Valid options: users, transactions, loans, economic_data")
    sys.exit(1)


delta_path = SILVER_PATHS[dataset]

spark = (
    SparkSession.builder
    .appName(f"show_delta_history_{dataset}")
    .getOrCreate()
)

try:
    delta_table = DeltaTable.forPath(spark, delta_path)

    history_df = (
        delta_table
        .history()
        .select(
            "version",
            "timestamp",
            "operation",
            "operationParameters",
            "operationMetrics",
        )
        .orderBy("version", ascending=False)
    )

    print(f"Delta history for dataset: {dataset}")
    print(f"Path: {delta_path}")

    history_df.show(truncate=False)

finally:
    spark.stop()