import sys

from pyspark.sql import SparkSession


SILVER_PATHS = {
    "users": "/opt/project/data/silver/users",
    "transactions": "/opt/project/data/silver/transactions",
    "loans": "/opt/project/data/silver/loans",
    "economic_data": "/opt/project/data/silver/economic_data",
}


if len(sys.argv) != 3:
    print(
        "Usage: spark-submit show_delta_version.py "
        "[users|transactions|loans|economic_data] [version]"
    )
    sys.exit(1)


dataset = sys.argv[1].lower()

try:
    version = int(sys.argv[2])
except ValueError:
    print("Version must be an integer.")
    sys.exit(1)


if dataset not in SILVER_PATHS:
    print(f"Invalid dataset: {dataset}")
    print(
        "Valid options: users, transactions, "
        "loans, economic_data"
    )
    sys.exit(1)


delta_path = SILVER_PATHS[dataset]


spark = (
    SparkSession.builder
    .appName(f"show_delta_version_{dataset}_{version}")
    .getOrCreate()
)


try:
    df = (
        spark.read
        .format("delta")
        .option("versionAsOf", version)
        .load(delta_path)
    )

    row_count = df.count()

    print("=== DELTA TIME TRAVEL ===")
    print(f"Dataset: {dataset}")
    print(f"Version: {version}")
    print(f"Path: {delta_path}")
    print(f"Rows in version: {row_count}")
    print()

    df.show(10, truncate=False)

finally:
    spark.stop()