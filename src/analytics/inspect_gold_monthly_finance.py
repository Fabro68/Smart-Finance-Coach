from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("Inspect Gold Monthly Finance")
    .getOrCreate()
)

path = "/opt/project/data/gold/user_monthly_finance"

df = spark.read.format("delta").load(path)

print("\n=== GOLD USER MONTHLY FINANCE SCHEMA ===")
df.printSchema()

print("\n=== SAMPLE ROWS ===")
df.orderBy("user_id", "year_month").show(10, truncate=False)

print("\n=== SUMMARY ===")
print(f"Rows: {df.count()}")
print(f"Users: {df.select('user_id').distinct().count()}")

spark.stop()