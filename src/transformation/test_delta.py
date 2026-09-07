from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("TestDeltaLake")
    .getOrCreate()
)

output_path = "/opt/project/data/delta_test"

data = [
    (1, "prueba"),
    (2, "delta"),
]

df = spark.createDataFrame(data, ["id", "valor"])

df.write.format("delta").mode("overwrite").save(output_path)

print("Delta write completed successfully.")
print(f"Rows written: {df.count()}")
print(f"Output path: {output_path}")

df_read = spark.read.format("delta").load(output_path)

print("Delta read completed successfully.")
df_read.show()

spark.stop()