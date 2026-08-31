from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("SmartFinanceCoachTest") \
    .getOrCreate()

data = [
    ("U001", "Alimentación", 450.50),
    ("U001", "Transporte", 200.00),
    ("U002", "Alimentación", 300.00),
    ("U002", "Entretenimiento", 150.00),
]

columns = ["user_id", "categoria", "monto"]

df = spark.createDataFrame(data, columns)

df.show()

spark.stop()