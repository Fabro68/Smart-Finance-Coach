from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp


BRONZE_PATH = "/opt/project/data/bronze/users"
SILVER_PATH = "/opt/project/data/silver/users"


spark = (
    SparkSession.builder
    .appName("silver_users")
    .getOrCreate()
)


df_bronze = spark.read.format("delta").load(BRONZE_PATH)


df_silver = (
    df_bronze
    .select(
        col("user_id").cast("int").alias("user_id"),
        col("edad").cast("int").alias("edad"),
        col("salario_mensual").cast("double").alias("salario_mensual"),
        col("ciudad").cast("string").alias("ciudad"),
        col("estado_civil").cast("string").alias("estado_civil"),
        col("dependientes").cast("int").alias("dependientes"),
        current_timestamp().alias("_silver_timestamp")
    )
)


df_silver = df_silver.dropDuplicates(["user_id"])


df_silver.write \
    .format("delta") \
    .mode("overwrite") \
    .save(SILVER_PATH)


print("Silver users transformation completed successfully.")
print(f"Rows written: {df_silver.count()}")
print(f"Output path: {SILVER_PATH}")

df_silver.printSchema()

spark.stop()