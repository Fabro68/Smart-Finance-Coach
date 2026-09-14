from pyspark.sql import SparkSession


SILVER_PATH = "/opt/project/data/silver/users"


spark = (
    SparkSession.builder
    .appName("validate_silver_users")
    .getOrCreate()
)


df = spark.read.format("delta").load(SILVER_PATH)


print("=== SILVER USERS VALIDATION ===")
print(f"Total rows: {df.count()}")
print(f"Total columns: {len(df.columns)}")

df.printSchema()

print("Sample records:")
df.show(5, truncate=False)


spark.stop()