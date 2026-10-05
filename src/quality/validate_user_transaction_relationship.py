import sys

from pyspark.sql import SparkSession
from pyspark.sql.functions import col

sys.path.append("/opt/project/src/quality")

from quality_logger import (
    create_quality_run_id,
    write_quality_result,
)


USERS_PATH = "/opt/project/data/silver/users"
TRANSACTIONS_PATH = "/opt/project/data/silver/transactions"


spark = (
    SparkSession.builder
    .appName("validate_user_transaction_relationship")
    .getOrCreate()
)


quality_run_id = create_quality_run_id()


try:
    users_df = (
        spark.read
        .format("delta")
        .load(USERS_PATH)
    )

    transactions_df = (
        spark.read
        .format("delta")
        .load(TRANSACTIONS_PATH)
    )

    total_users = users_df.count()
    total_transactions = transactions_df.count()

    linked_transactions = (
        transactions_df
        .filter(
            col("user_id").isNotNull()
        )
        .count()
    )

    unlinked_transactions = (
        transactions_df
        .filter(
            col("user_id").isNull()
        )
        .count()
    )

    valid_linked_transactions = (
        transactions_df
        .filter(
            col("user_id").isNotNull()
        )
        .join(
            users_df.select("user_id"),
            on="user_id",
            how="inner",
        )
        .count()
    )

    orphan_transactions = (
        transactions_df
        .filter(
            col("user_id").isNotNull()
        )
        .join(
            users_df.select("user_id"),
            on="user_id",
            how="left_anti",
        )
        .count()
    )

    users_with_transactions = (
        users_df
        .join(
            transactions_df
            .filter(
                col("user_id").isNotNull()
            )
            .select("user_id")
            .distinct(),
            on="user_id",
            how="inner",
        )
        .count()
    )

    users_without_transactions = (
        users_df
        .join(
            transactions_df
            .filter(
                col("user_id").isNotNull()
            )
            .select("user_id")
            .distinct(),
            on="user_id",
            how="left_anti",
        )
        .count()
    )

    linkage_percentage = (
        (
            linked_transactions
            / total_transactions
        )
        * 100
        if total_transactions > 0
        else 0
    )

    valid_linkage_percentage = (
        (
            valid_linked_transactions
            / linked_transactions
        )
        * 100
        if linked_transactions > 0
        else 0
    )

    orphan_status = (
        "PASS"
        if orphan_transactions == 0
        else "FAIL"
    )

    write_quality_result(
        quality_run_id=quality_run_id,
        dataset="users_transactions",
        check_name="transaction_user_referential_integrity",
        status=orphan_status,
        observed_value=orphan_transactions,
        expected_value=0,
        message=(
            "Number of linked transactions "
            "whose user_id does not exist "
            "in Silver users."
        ),
    )

    write_quality_result(
        quality_run_id=quality_run_id,
        dataset="users_transactions",
        check_name="transaction_user_linkage_percentage",
        status="INFO",
        observed_value=round(
            linkage_percentage,
            2,
        ),
        expected_value="informational",
        message=(
            f"{linked_transactions} linked "
            f"transactions and "
            f"{unlinked_transactions} "
            f"unlinked transactions."
        ),
    )

    write_quality_result(
        quality_run_id=quality_run_id,
        dataset="users_transactions",
        check_name="valid_linked_transactions_percentage",
        status="INFO",
        observed_value=round(
            valid_linkage_percentage,
            2,
        ),
        expected_value="informational",
        message=(
            f"{valid_linked_transactions} "
            "linked transactions reference "
            "an existing user."
        ),
    )

    write_quality_result(
        quality_run_id=quality_run_id,
        dataset="users_transactions",
        check_name="users_with_transactions",
        status="INFO",
        observed_value=users_with_transactions,
        expected_value="informational",
        message=(
            f"{users_with_transactions} of "
            f"{total_users} users have at "
            "least one linked transaction."
        ),
    )

    write_quality_result(
        quality_run_id=quality_run_id,
        dataset="users_transactions",
        check_name="users_without_transactions",
        status="INFO",
        observed_value=users_without_transactions,
        expected_value="informational",
        message=(
            f"{users_without_transactions} "
            "users do not have linked "
            "transactions."
        ),
    )

    print(
        "=== USER / TRANSACTION RELATIONSHIP ==="
    )

    print(
        f"quality_run_id: {quality_run_id}"
    )

    print(
        f"Users: {total_users}"
    )

    print(
        f"Transactions: {total_transactions}"
    )

    print(
        f"Linked transactions: "
        f"{linked_transactions}"
    )

    print(
        f"Unlinked transactions: "
        f"{unlinked_transactions}"
    )

    print(
        f"Valid linked transactions: "
        f"{valid_linked_transactions}"
    )

    print(
        f"Orphan transactions: "
        f"{orphan_transactions}"
    )

    print(
        f"Users with transactions: "
        f"{users_with_transactions}"
    )

    print(
        f"Users without transactions: "
        f"{users_without_transactions}"
    )

    print(
        f"Linkage percentage: "
        f"{linkage_percentage:.2f}%"
    )

    print(
        f"Valid linkage percentage: "
        f"{valid_linkage_percentage:.2f}%"
    )

finally:
    spark.stop()