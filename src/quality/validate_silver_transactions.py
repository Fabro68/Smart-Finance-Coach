from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim

from quality_logger import (
    create_quality_run_id,
    write_quality_result,
)


SILVER_PATH = "/opt/project/data/silver/transactions"


spark = (
    SparkSession.builder
    .appName("validate_silver_transactions")
    .getOrCreate()
)

try:
    df = spark.read.format("delta").load(SILVER_PATH)

    total_rows = df.count()

    distinct_transaction_ids = (
        df.select("transaction_id")
        .distinct()
        .count()
    )

    null_transaction_id = df.filter(
        col("transaction_id").isNull()
        | (trim(col("transaction_id")) == "")
    ).count()

    duplicate_transaction_ids = (
        total_rows - distinct_transaction_ids
    )

    invalid_fecha = df.filter(
        col("fecha").isNull()
    ).count()

    invalid_descripcion = df.filter(
        col("descripcion").isNull()
        | (trim(col("descripcion")) == "")
    ).count()

    invalid_monto = df.filter(
        col("monto").isNull()
        | (col("monto") <= 0)
    ).count()

    invalid_tipo = df.filter(
        col("tipo").isNull()
        | (~col("tipo").isin("debit", "credit"))
    ).count()

    invalid_categoria = df.filter(
        col("categoria").isNull()
        | (trim(col("categoria")) == "")
    ).count()

    invalid_cuenta = df.filter(
        col("cuenta").isNull()
        | (trim(col("cuenta")) == "")
    ).count()

    null_ingestion_timestamp = df.filter(
        col("_ingestion_timestamp").isNull()
    ).count()

    null_source_file = df.filter(
        col("_source_file").isNull()
        | (trim(col("_source_file")) == "")
    ).count()

    null_silver_timestamp = df.filter(
        col("_silver_timestamp").isNull()
    ).count()

    inconsistent_linkage = df.filter(
        col("is_user_linked").isNull()
    |
    (
        (col("is_user_linked") == True)
        & col("user_id").isNull()
    )
    |
    (
        (col("is_user_linked") == False)
        & col("user_id").isNotNull()
    )
    ).count()

    linked_rows = df.filter(
        col("is_user_linked") == True
    ).count()

    unlinked_rows = df.filter(
        col("is_user_linked") == False
    ).count()

    linked_percentage = (
        (linked_rows / total_rows) * 100
        if total_rows > 0
        else 0
    )

    check_results = {
        "transaction_id_not_null": {
            "passed": null_transaction_id == 0,
            "observed": null_transaction_id,
            "expected": 0,
        },
        "transaction_id_unique": {
            "passed": duplicate_transaction_ids == 0,
            "observed": duplicate_transaction_ids,
            "expected": 0,
        },
        "fecha_not_null": {
            "passed": invalid_fecha == 0,
            "observed": invalid_fecha,
            "expected": 0,
        },
        "descripcion_not_empty": {
            "passed": invalid_descripcion == 0,
            "observed": invalid_descripcion,
            "expected": 0,
        },
        "monto_positive": {
            "passed": invalid_monto == 0,
            "observed": invalid_monto,
            "expected": 0,
        },
        "tipo_valid": {
            "passed": invalid_tipo == 0,
            "observed": invalid_tipo,
            "expected": 0,
        },
        "categoria_not_empty": {
            "passed": invalid_categoria == 0,
            "observed": invalid_categoria,
            "expected": 0,
        },
        "cuenta_not_empty": {
            "passed": invalid_cuenta == 0,
            "observed": invalid_cuenta,
            "expected": 0,
        },
        "ingestion_timestamp_not_null": {
            "passed": null_ingestion_timestamp == 0,
            "observed": null_ingestion_timestamp,
            "expected": 0,
        },
        "source_file_not_empty": {
            "passed": null_source_file == 0,
            "observed": null_source_file,
            "expected": 0,
        },
        "silver_timestamp_not_null": {
            "passed": null_silver_timestamp == 0,
            "observed": null_silver_timestamp,
            "expected": 0,
        },
        "user_linkage_consistent": {
            "passed": inconsistent_linkage == 0,
            "observed": inconsistent_linkage,
            "expected": 0,
        },
    }

    passed_checks = sum(
        result["passed"]
        for result in check_results.values()
    )

    total_checks = len(check_results)

    print("=== SILVER TRANSACTIONS DATA QUALITY REPORT ===")
    print(f"Total rows: {total_rows}")
    print(
        f"Distinct transaction_id: "
        f"{distinct_transaction_ids}"
    )
    print(
        f"Duplicate transaction_id: "
        f"{duplicate_transaction_ids}"
    )
    print()

    quality_run_id = create_quality_run_id()

    for check_name, result in check_results.items():
        status = "PASS" if result["passed"] else "FAIL"

        print(f"{status}: {check_name}")

        write_quality_result(
            quality_run_id=quality_run_id,
            dataset="transactions",
            check_name=check_name,
            status=status,
            observed_value=result["observed"],
            expected_value=result["expected"],
        )

    print()
    print(f"Checks passed: {passed_checks}/{total_checks}")
    print(f"quality_run_id: {quality_run_id}")

    if passed_checks == total_checks:
        print("Overall structural result: PASS")
    else:
        print("Overall structural result: FAIL")

    print()
    print("=== USER IDENTITY LINKAGE METRIC ===")
    print(f"Linked transactions: {linked_rows}")
    print(f"Unlinked transactions: {unlinked_rows}")
    print(
        f"Linked percentage: "
        f"{linked_percentage:.2f}%"
    )

    write_quality_result(
        quality_run_id=quality_run_id,
        dataset="transactions",
        check_name="user_identity_linkage_percentage",
        status="INFO",
        observed_value=round(linked_percentage, 2),
        expected_value="informational",
        message=(
            f"{linked_rows} linked transactions and "
            f"{unlinked_rows} unlinked transactions."
        ),
    )

finally:
    spark.stop()