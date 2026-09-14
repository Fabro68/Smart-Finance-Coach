from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, when


SILVER_PATH = "/opt/project/data/silver/loans"


spark = (
    SparkSession.builder
    .appName("validate_silver_loans")
    .getOrCreate()
)


df = spark.read.format("delta").load(SILVER_PATH)


print("=== SILVER LOANS VALIDATION ===")
print(f"Total rows: {df.count()}")
print(f"Total columns: {len(df.columns)}")

df.printSchema()


print("\nNull values:")
df.select(
    [
        count(when(col(c).isNull(), c)).alias(c)
        for c in df.columns
    ]
).show(truncate=False)


print("\nDuplicate loan_id validation:")
total_rows = df.count()
distinct_loan_ids = df.select("loan_id").distinct().count()

print(f"Distinct loan_id: {distinct_loan_ids}")
print(f"Duplicate loan_id: {total_rows - distinct_loan_ids}")


print("\nDefault distribution:")
df.groupBy("default").count().orderBy("default").show()


print("\nSample records:")
df.select(
    "loan_id",
    "age",
    "income",
    "loan_amount",
    "credit_score",
    "interest_rate",
    "default",
).show(5, truncate=False)


spark.stop()