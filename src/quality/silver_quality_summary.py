import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

QUALITY_PATH = (
    PROJECT_ROOT
    / "data"
    / "quality"
    / "quality_results.jsonl"
)


def load_quality_results(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    records = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            try:
                records.append(
                    json.loads(line)
                )
            except json.JSONDecodeError:
                pass

    return pd.DataFrame(records)


def get_latest_runs(
    quality_df: pd.DataFrame,
) -> pd.DataFrame:

    if quality_df.empty:
        return quality_df

    df = quality_df.copy()

    df["checked_at"] = pd.to_datetime(
        df["checked_at"],
        errors="coerce",
        utc=True,
    )

    latest_runs = (
        df
        .sort_values("checked_at")
        .groupby(
            "dataset",
            as_index=False,
        )
        .tail(1)[
            [
                "dataset",
                "quality_run_id",
            ]
        ]
    )

    latest_df = df.merge(
        latest_runs,
        on=[
            "dataset",
            "quality_run_id",
        ],
        how="inner",
    )

    return latest_df


def build_summary(
    latest_df: pd.DataFrame,
) -> pd.DataFrame:

    if latest_df.empty:
        return pd.DataFrame()

    rows = []

    for dataset, group in latest_df.groupby(
        "dataset"
    ):

        statuses = (
            group["status"]
            .astype(str)
            .str.upper()
        )

        pass_count = int(
            (statuses == "PASS").sum()
        )

        fail_count = int(
            (statuses == "FAIL").sum()
        )

        info_count = int(
            (statuses == "INFO").sum()
        )

        structural_checks = (
            pass_count
            + fail_count
        )

        pass_rate = (
            (
                pass_count
                / structural_checks
            )
            * 100
            if structural_checks > 0
            else 0
        )

        overall_status = (
            "PASS"
            if fail_count == 0
            else "FAIL"
        )

        latest_checked_at = (
            group["checked_at"]
            .max()
        )

        rows.append(
            {
                "dataset": dataset,
                "quality_run_id": (
                    group[
                        "quality_run_id"
                    ]
                    .iloc[0]
                ),
                "total_checks": len(group),
                "pass_checks": pass_count,
                "fail_checks": fail_count,
                "info_checks": info_count,
                "structural_pass_rate": round(
                    pass_rate,
                    2,
                ),
                "overall_status": (
                    overall_status
                ),
                "checked_at": (
                    latest_checked_at
                ),
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values("dataset")
    )


quality_df = load_quality_results(
    QUALITY_PATH
)

if not quality_df.empty and "dataset" in quality_df.columns:
    quality_df = quality_df[
        quality_df["dataset"] != "test_dataset"
    ]

if quality_df.empty:
    print(
        "No quality results found."
    )

else:
    latest_df = get_latest_runs(
        quality_df
    )

    summary_df = build_summary(
        latest_df
    )

    print(
        "=== SILVER QUALITY SUMMARY ==="
    )

    print()

    print(
        summary_df.to_string(
            index=False
        )
    )

    print()

    total_pass = int(
        summary_df[
            "pass_checks"
        ].sum()
    )

    total_fail = int(
        summary_df[
            "fail_checks"
        ].sum()
    )

    total_info = int(
        summary_df[
            "info_checks"
        ].sum()
    )

    structural_checks = (
        total_pass
        + total_fail
    )

    overall_pass_rate = (
        (
            total_pass
            / structural_checks
        )
        * 100
        if structural_checks > 0
        else 0
    )

    print(
        "=== GLOBAL QUALITY ==="
    )

    print(
        f"PASS checks: "
        f"{total_pass}"
    )

    print(
        f"FAIL checks: "
        f"{total_fail}"
    )

    print(
        f"INFO checks: "
        f"{total_info}"
    )

    print(
        f"Structural pass rate: "
        f"{overall_pass_rate:.2f}%"
    )