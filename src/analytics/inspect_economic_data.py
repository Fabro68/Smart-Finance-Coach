from pyspark.sql import SparkSession


ECONOMIC_PATH = "/opt/project/data/silver/economic_data"


spark = (
    SparkSession.builder
    .appName("inspect_economic_data")
    .getOrCreate()
)


try:
    df = (
        spark.read
        .format("delta")
        .load(ECONOMIC_PATH)
    )

    print("\n=== ECONOMIC DATA SCHEMA ===")
    df.printSchema()

    print("\n=== ECONOMIC DATA SAMPLE ===")
    (
        df
        .orderBy(df.columns[0])
        .show(
            10,
            truncate=False,
        )
    )

    print("\n=== ECONOMIC DATA ROW COUNT ===")
    print(df.count())

finally:
    spark.stop()