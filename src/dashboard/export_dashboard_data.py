from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import col


USERS_PATH = "/opt/project/data/silver/users"
TRANSACTIONS_PATH = "/opt/project/data/silver/transactions"

DASHBOARD_PATH = "/opt/project/data/dashboard"

USERS_OUTPUT = f"{DASHBOARD_PATH}/users"
TRANSACTIONS_OUTPUT = f"{DASHBOARD_PATH}/transactions"


spark = (
    SparkSession.builder
    .appName("export_dashboard_data")
    .getOrCreate()
)


try:
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
            col("user_id").isNotNull()
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

    (
        users_df
        .coalesce(1)
        .write
        .mode("overwrite")
        .option("header", True)
        .csv(USERS_OUTPUT)
    )

    (
        transactions_df
        .coalesce(1)
        .write
        .mode("overwrite")
        .option("header", True)
        .csv(TRANSACTIONS_OUTPUT)
    )

    print("Dashboard export completed successfully.")
    print(f"Users exported: {users_df.count()}")
    print(
        "Transactions exported: "
        f"{transactions_df.count()}"
    )
    print(f"Users output: {USERS_OUTPUT}")
    print(
        "Transactions output: "
        f"{TRANSACTIONS_OUTPUT}"
    )

finally:
    spark.stop()