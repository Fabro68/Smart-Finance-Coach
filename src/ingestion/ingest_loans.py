from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, input_file_name


spark = (
    SparkSession.builder
    .appName("IngestLoansToBronze")
    .getOrCreate()
)

input_path = "/opt/project/data/raw/Loan_default.csv"
output_path = "/opt/project/data/bronze/loans"

df = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "false")
    .csv(input_path)
)

df_bronze = (
    df
    .withColumn("_ingestion_timestamp", current_timestamp())
    .withColumn("_source_file", input_file_name())
)

df_bronze.write.format("delta").mode("overwrite").save(output_path)

print("Ingestion completed successfully.")
print(f"Rows ingested: {df_bronze.count()}")
print(f"Output path: {output_path}")

df_bronze.printSchema()
df_bronze.show(5, truncate=False)

spark.stop()