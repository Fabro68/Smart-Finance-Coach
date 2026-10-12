from pyspark.sql import SparkSession


LOANS_PATH = "/opt/project/data/silver/loans"


spark = (
    SparkSession.builder
    .appName("inspect_loans")
    .getOrCreate()
)


try:
    df = (
        spark.read
        .format("delta")
        .load(LOANS_PATH)
    )

    print("\n=== LOANS SCHEMA ===")
    df.printSchema()

    print("\n=== LOANS SAMPLE ===")
    (
        df
        .show(
            10,
            truncate=False,
        )
    )

    print("\n=== LOANS ROW COUNT ===")
    print(df.count())

finally:
    spark.stop()