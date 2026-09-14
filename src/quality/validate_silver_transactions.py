from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, when

SILVER_PATH = "/opt/project/data/silver/transactions"

spark = (
    SparkSession.builder
    .appName("validate_silver_transactions")
    .getOrCreate()
)

df = spark.read.format("delta").load(SILVER_PATH)

print("===== SILVER TRANSACTIONS VALIDATION =====")
print(f"Total rows: {df.count()}")
print(f"Total columns: {len(df.columns)}")

print("\nSchema:")
df.printSchema()

print("\nUser linkage summary:")
df.groupBy("is_user_linked").count().show()

print("\nNull values:")
df.select([
    count(when(col(c).isNull(), c)).alias(c)
    for c in df.columns
]).show(truncate=False)

print("\nSample records:")
df.select(
    "user_id",
    "fecha",
    "descripcion",
    "monto",
    "tipo",
    "categoria",
    "is_user_linked"
).show(5, truncate=False)

total_rows = df.count()
distinct_ids = df.select("transaction_id").distinct().count()

print("\nTransaction ID validation:")
print(f"Distinct transaction_id: {distinct_ids}")
print(f"Duplicate transaction_id: {total_rows - distinct_ids}")

spark.stop()