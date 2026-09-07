from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, input_file_name


spark = (
    SparkSession.builder
    .appName("IngestEconomicDataToBronze")
    .getOrCreate()
)

sources = [
    {
        "input": "/opt/project/data/raw/MEXCPALTT01IXNBM.csv",
        "output": "/opt/project/data/bronze/economic/cpi",
    },
    {
        "input": "/opt/project/data/raw/IRSTCI01MXM156N.csv",
        "output": "/opt/project/data/bronze/economic/interest_rate",
    },
    {
        "input": "/opt/project/data/raw/DEXMXUS.csv",
        "output": "/opt/project/data/bronze/economic/exchange_rate",
    },
]

for source in sources:
    df = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "false")
        .csv(source["input"])
    )

    df_bronze = (
        df
        .withColumn("_ingestion_timestamp", current_timestamp())
        .withColumn("_source_file", input_file_name())
    )

    df_bronze.write.format("delta").mode("overwrite").save(source["output"])

    print("Ingestion completed successfully.")
    print(f"Source: {source['input']}")
    print(f"Rows ingested: {df_bronze.count()}")
    print(f"Output path: {source['output']}")
    df_bronze.printSchema()
    df_bronze.show(5, truncate=False)

spark.stop()