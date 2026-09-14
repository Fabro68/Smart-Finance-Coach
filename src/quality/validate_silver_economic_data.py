from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, min, max, when


SILVER_PATH = "/opt/project/data/silver/economic_data"


spark = (
    SparkSession.builder
    .appName("validate_silver_economic_data")
    .getOrCreate()
)


df = spark.read.format("delta").load(SILVER_PATH)


print("=== SILVER ECONOMIC DATA VALIDATION ===")
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


print("\nDate range:")
df.select(
    min("fecha").alias("min_fecha"),
    max("fecha").alias("max_fecha"),
).show()


print("\nSample records:")
df.orderBy("fecha").show(10, truncate=False)


spark.stop()