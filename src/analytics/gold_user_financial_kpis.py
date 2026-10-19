from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark = (
    SparkSession.builder
    .appName("Gold User Financial KPIs")
    .getOrCreate()
)

input_path = "/opt/project/data/gold/user_monthly_finance"
output_path = "/opt/project/data/gold/user_financial_kpis"

df = spark.read.format("delta").load(input_path)

user_window = Window.partitionBy("user_id").orderBy("year_month")

kpis = (
    df
    .withColumn(
        "previous_month_spending",
        F.lag("consumer_spending").over(user_window)
    )
    .withColumn(
        "spending_change_pct",
        F.when(
            F.col("previous_month_spending") > 0,
            ((F.col("consumer_spending") - F.col("previous_month_spending"))
             / F.col("previous_month_spending")) * 100
        )
    )
    .withColumn(
        "financial_risk_level",
        F.when(F.col("spending_to_salary_ratio") <= 0.50, F.lit("LOW"))
         .when(F.col("spending_to_salary_ratio") <= 0.80, F.lit("MEDIUM"))
         .otherwise(F.lit("HIGH"))
    )
    .withColumn(
        "savings_health",
        F.when(F.col("estimated_savings_rate") >= 0.20, F.lit("HEALTHY"))
         .when(F.col("estimated_savings_rate") >= 0.10, F.lit("MODERATE"))
         .otherwise(F.lit("LOW"))
    )
    .withColumn(
        "negative_transactional_balance_flag",
        F.col("transactional_balance") < 0
    )
    .withColumn(
        "gold_created_at",
        F.current_timestamp()
    )
    .select(
        "user_id",
        "year_month",
        "salary_monthly",
        "consumer_spending",
        "total_debits",
        "total_credits",
        "transactional_balance",
        "estimated_margin",
        "spending_to_salary_ratio",
        "estimated_savings_capacity",
        "estimated_savings_rate",
        "top_spending_category",
        "previous_month_spending",
        "spending_change_pct",
        "financial_risk_level",
        "savings_health",
        "negative_transactional_balance_flag",
        "gold_created_at"
    )
)

(
    kpis.write
    .format("delta")
    .mode("overwrite")
    .save(output_path)
)

print("\n=== GOLD USER FINANCIAL KPIs ===")
kpis.orderBy("user_id", "year_month").show(20, truncate=False)

print(f"Rows: {kpis.count()}")
print(f"Users: {kpis.select('user_id').distinct().count()}")

spark.stop()