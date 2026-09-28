from pyspark.sql import SparkSession
from pyspark.sql.functions import col

from quality_logger import (
    create_quality_run_id,
    write_quality_result,
)


SILVER_PATH = "/opt/project/data/silver/economic_data"


spark = (
    SparkSession.builder
    .appName("validate_silver_economic_data")
    .getOrCreate()
)

try:
    df = spark.read.format("delta").load(SILVER_PATH)

    total_rows = df.count()

    distinct_dates = (
        df.select("fecha")
        .distinct()
        .count()
    )

    duplicate_dates = total_rows - distinct_dates

    null_fecha = df.filter(
        col("fecha").isNull()
    ).count()

    null_cpi = df.filter(
        col("indice_precios").isNull()
    ).count()

    null_inflation = df.filter(
        col("inflacion_anual_pct").isNull()
    ).count()

    null_interest_rate = df.filter(
        col("tasa_interes").isNull()
    ).count()

    null_exchange_rate = df.filter(
        col("tipo_cambio_promedio").isNull()
    ).count()

    null_silver_timestamp = df.filter(
        col("_silver_timestamp").isNull()
    ).count()

    invalid_cpi = df.filter(
        col("indice_precios") <= 0
    ).count()

    invalid_interest_rate = df.filter(
        (col("tasa_interes") < 0)
        | (col("tasa_interes") > 100)
    ).count()

    invalid_exchange_rate = df.filter(
        col("tipo_cambio_promedio") <= 0
    ).count()

    invalid_inflation = df.filter(
        (col("inflacion_anual_pct") < -50)
        | (col("inflacion_anual_pct") > 100)
    ).count()

    out_of_range_dates = df.filter(
        (col("fecha") < "2018-01-01")
        | (col("fecha") > "2020-03-31")
    ).count()

    check_results = {
        "expected_27_months": {
            "passed": total_rows == 27,
            "observed": total_rows,
            "expected": 27,
        },
        "fecha_not_null": {
            "passed": null_fecha == 0,
            "observed": null_fecha,
            "expected": 0,
        },
        "fecha_unique": {
            "passed": duplicate_dates == 0,
            "observed": duplicate_dates,
            "expected": 0,
        },
        "indice_precios_not_null": {
            "passed": null_cpi == 0,
            "observed": null_cpi,
            "expected": 0,
        },
        "indice_precios_positive": {
            "passed": invalid_cpi == 0,
            "observed": invalid_cpi,
            "expected": 0,
        },
        "inflacion_anual_not_null": {
            "passed": null_inflation == 0,
            "observed": null_inflation,
            "expected": 0,
        },
        "inflacion_anual_reasonable": {
            "passed": invalid_inflation == 0,
            "observed": invalid_inflation,
            "expected": 0,
        },
        "tasa_interes_not_null": {
            "passed": null_interest_rate == 0,
            "observed": null_interest_rate,
            "expected": 0,
        },
        "tasa_interes_reasonable": {
            "passed": invalid_interest_rate == 0,
            "observed": invalid_interest_rate,
            "expected": 0,
        },
        "tipo_cambio_not_null": {
            "passed": null_exchange_rate == 0,
            "observed": null_exchange_rate,
            "expected": 0,
        },
        "tipo_cambio_positive": {
            "passed": invalid_exchange_rate == 0,
            "observed": invalid_exchange_rate,
            "expected": 0,
        },
        "fecha_in_project_range": {
            "passed": out_of_range_dates == 0,
            "observed": out_of_range_dates,
            "expected": 0,
        },
        "silver_timestamp_not_null": {
            "passed": null_silver_timestamp == 0,
            "observed": null_silver_timestamp,
            "expected": 0,
        },
    }

    passed_checks = sum(
        result["passed"]
        for result in check_results.values()
    )

    total_checks = len(check_results)

    print("=== SILVER ECONOMIC DATA QUALITY REPORT ===")
    print(f"Total rows: {total_rows}")
    print(f"Distinct dates: {distinct_dates}")
    print(f"Duplicate dates: {duplicate_dates}")
    print()

    quality_run_id = create_quality_run_id()

    for check_name, result in check_results.items():
        status = "PASS" if result["passed"] else "FAIL"

        print(f"{status}: {check_name}")

        write_quality_result(
            quality_run_id=quality_run_id,
            dataset="economic_data",
            check_name=check_name,
            status=status,
            observed_value=result["observed"],
            expected_value=result["expected"],
        )

    print()
    print(f"Checks passed: {passed_checks}/{total_checks}")
    print(f"quality_run_id: {quality_run_id}")

    if passed_checks == total_checks:
        print("Overall result: PASS")
    else:
        print("Overall result: FAIL")

finally:
    spark.stop()