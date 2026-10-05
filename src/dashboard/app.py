from pathlib import Path
import json

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Smart Finance Coach",
    page_icon="💰",
    layout="wide",
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

AUDIT_PATH = (
    PROJECT_ROOT
    / "data"
    / "audit"
    / "pipeline_audit.jsonl"
)

QUALITY_PATH = (
    PROJECT_ROOT
    / "data"
    / "quality"
    / "quality_results.jsonl"
)


def load_jsonl(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    records = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))

            except json.JSONDecodeError:
                pass

    return pd.DataFrame(records)


def latest_success_counts(
    audit_df: pd.DataFrame,
) -> dict:

    counts = {
        "users": None,
        "transactions": None,
        "loans": None,
        "economic_data": None,
    }

    if audit_df.empty:
        return counts

    df = audit_df.copy()

    if "status" in df.columns:
        df = df[
            df["status"] == "SUCCESS"
        ]

    if "end_time" in df.columns:
        df["end_time"] = pd.to_datetime(
            df["end_time"],
            errors="coerce",
            utc=True,
        )

        df = df.sort_values(
            "end_time"
        )

    for dataset in counts:

        if "dataset" not in df.columns:
            continue

        dataset_df = df[
            df["dataset"] == dataset
        ]

        if not dataset_df.empty:

            row = dataset_df.iloc[-1]

            value = row.get(
                "records_written"
            )

            if pd.notna(value):
                counts[dataset] = int(value)

    return counts


def quality_summary(
    quality_df: pd.DataFrame,
) -> pd.DataFrame:

    if quality_df.empty:

        return pd.DataFrame(
            columns=[
                "dataset",
                "checks",
                "pass",
                "fail",
                "info",
                "pass_rate",
            ]
        )

    df = quality_df.copy()

    if "checked_at" in df.columns:

        df["checked_at"] = pd.to_datetime(
            df["checked_at"],
            errors="coerce",
            utc=True,
        )

    if (
        "quality_run_id" in df.columns
        and "dataset" in df.columns
    ):

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

        df = df.merge(
            latest_runs,
            on=[
                "dataset",
                "quality_run_id",
            ],
            how="inner",
        )

    rows = []

    for dataset, group in df.groupby(
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

        rows.append(
            {
                "dataset": dataset,
                "checks": len(group),
                "pass": pass_count,
                "fail": fail_count,
                "info": info_count,
                "pass_rate": round(
                    pass_rate,
                    2,
                ),
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values("dataset")
    )


audit_df = load_jsonl(
    AUDIT_PATH
)

if not audit_df.empty and "process_name" in audit_df.columns:
    audit_df = audit_df[
        audit_df["process_name"] != "test_audit_logger"
    ]

quality_df = load_jsonl(
    QUALITY_PATH
)

if not quality_df.empty and "dataset" in quality_df.columns:
    quality_df = quality_df[
        quality_df["dataset"] != "test_dataset"
    ]

counts = latest_success_counts(
    audit_df
)

quality_df_summary = quality_summary(
    quality_df
)

relationship_metrics = {}

if (
    not quality_df.empty
    and "dataset" in quality_df.columns
    and "check_name" in quality_df.columns
):

    relationship_df = quality_df[
        quality_df["dataset"]
        == "users_transactions"
    ].copy()

    if not relationship_df.empty:

        if "checked_at" in relationship_df.columns:
            relationship_df["checked_at"] = pd.to_datetime(
                relationship_df["checked_at"],
                errors="coerce",
                utc=True,
            )

            relationship_df = relationship_df.sort_values(
                "checked_at"
            )

        latest_run_id = (
            relationship_df[
                "quality_run_id"
            ].iloc[-1]
        )

        relationship_df = relationship_df[
            relationship_df[
                "quality_run_id"
            ] == latest_run_id
        ]

        for _, row in relationship_df.iterrows():
            relationship_metrics[
                row["check_name"]
            ] = row["observed_value"]


st.title(
    "💰 Smart Finance Coach"
)

st.caption(
    "Dashboard preliminar de Ingeniería de Datos · "
    "Medallion Architecture · Calidad · Auditoría"
)


with st.sidebar:

    st.header(
        "Smart Finance Coach"
    )

    st.write(
        "Avance técnico del proyecto"
    )

    page = st.radio(
        "Vista",
        [
            "Resumen",
            "Pipeline",
            "Calidad",
            "Auditoría",
        ],
    )

    st.divider()

    st.caption(
        "Raw → Bronze → Silver → Gold"
    )

    st.caption(
        "Estado actual: "
        "Silver + Calidad + Auditoría"
    )


if page == "Resumen":

    st.subheader(
        "Resumen del proyecto"
    )

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    col1.metric(
        "Usuarios",
        (
            f"{counts['users']:,}"
            if counts["users"]
            is not None
            else "N/D"
        ),
    )

    col2.metric(
        "Transacciones",
        (
            f"{counts['transactions']:,}"
            if counts["transactions"]
            is not None
            else "N/D"
        ),
    )

    col3.metric(
        "Préstamos",
        (
            f"{counts['loans']:,}"
            if counts["loans"]
            is not None
            else "N/D"
        ),
    )

    col4.metric(
        "Registros económicos",
        (
            f"{counts['economic_data']:,}"
            if counts["economic_data"]
            is not None
            else "N/D"
        ),
    )

        

    st.divider()

    st.subheader(
        "Estado de la arquitectura"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.success(
        "✅ RAW\n\n"
        "Datos fuente disponibles"
    )

    c2.success(
        "✅ BRONZE\n\n"
        "Delta Lake implementado"
    )

    c3.success(
        "✅ SILVER\n\n"
        "Transformación y limpieza"
    )

    c4.info(
        "⏳ GOLD\n\n"
        "Pendiente"
    )

    st.subheader(
        "Observabilidad"
    )

    c1, c2, c3 = st.columns(3)

    c1.success(
        "✅ Auditoría de pipelines"
    )

    c2.success(
        "✅ Validaciones de calidad"
    )

    c3.success(
        "✅ Delta History / Time Travel"
    )

    if not quality_df_summary.empty:

        st.subheader(
            "Calidad de datos actual"
        )

        chart_df = (
            quality_df_summary
        .set_index("dataset")[
         ["pass", "fail", "info"]
        ]
        )   

        st.bar_chart(
        chart_df,
        y_label="Número de checks",
        )


        display_quality = (
            quality_df_summary
            .rename(
                columns={
                    "dataset": "Dataset",
                    "checks": "Checks",
                    "pass": "PASS",
                    "fail": "FAIL",
                    "info": "INFO",
                    "pass_rate": "PASS %",
                }
            )
        )

        st.dataframe(
            display_quality,
            use_container_width=True,
            hide_index=True,
        )


elif page == "Pipeline":

    st.subheader(
        "Pipeline Medallion"
    )

    st.markdown(
        """
### Flujo actual

**Fuentes / Raw**

↓

**Bronze — Delta Lake**

↓

**Silver — Limpieza, tipificación y trazabilidad**

↓

**Validaciones de calidad**

↓

**Gold — Métricas de negocio (siguiente etapa)**
"""
    )

    st.divider()

    st.subheader(
        "Últimas ejecuciones"
    )

    if audit_df.empty:

        st.warning(
            "No se encontró historial "
            "de auditoría."
        )

    else:

        pipeline_df = (
            audit_df.copy()
        )

    if (
        "start_time" in pipeline_df.columns
        and "end_time" in pipeline_df.columns
    ):

        pipeline_df["start_time"] = pd.to_datetime(
            pipeline_df["start_time"],
            errors="coerce",
            utc=True,
        )

        pipeline_df["end_time"] = pd.to_datetime(
            pipeline_df["end_time"],
            errors="coerce",
            utc=True,
        )

        pipeline_df["duration_seconds"] = (
            pipeline_df["end_time"]
            - pipeline_df["start_time"]
        ).dt.total_seconds()

        pipeline_df = pipeline_df.sort_values(
            "end_time",
            ascending=False,
        )

        latest_update = None

        if (
            "end_time" in pipeline_df.columns
            and not pipeline_df["end_time"].dropna().empty
        ):
            latest_update = (
                pipeline_df["end_time"]
                .dropna()
                .max()
            )

        columns = [
            column
            for column in [
                "pipeline_run_id",
                "process_name",
                "dataset",
                "status",
                "records_read",
                "records_written",
                "duration_seconds",
                "start_time",
                "end_time",
            ]
            if column
            in pipeline_df.columns
        ]

        if "duration_seconds" in pipeline_df.columns:
            valid_durations = pipeline_df[
                "duration_seconds"
            ].dropna()

            average_duration = (
                valid_durations.mean()
                if not valid_durations.empty
                else 0
            )

            max_duration = (
                valid_durations.max()
                if not valid_durations.empty
                else 0
            )

            success_count = (
                pipeline_df["status"]
                .eq("SUCCESS")
                .sum()
                if "status" in pipeline_df.columns
                else 0
            )

            failed_count = (
                pipeline_df["status"]
                .eq("FAILED")
                .sum()
                if "status" in pipeline_df.columns
                else 0
            )

            total_runs = (
                success_count
                + failed_count
            )

            success_rate = (
                (success_count / total_runs) * 100
                if total_runs > 0
                else 0
            )

            failure_rate = (
                (failed_count / total_runs) * 100
                if total_runs > 0
                else 0
            )

            c1, c2, c3, c4, c5, c6 = st.columns(6)

            c1.metric(
                "Duración promedio",
                f"{average_duration:.1f} s",
            )

            c2.metric(
                "Duración máxima",
                f"{max_duration:.1f} s",
            )

            c3.metric(
                "Ejecuciones exitosas",
                int(success_count),
            )

            c4.metric(
                "Tasa de éxito",
                f"{success_rate:.1f}%",
            )

            c5.metric(
                "Tasa de error",
                f"{failure_rate:.1f}%",
            )

            c6.metric(
                "Última actualización",
                (
                    latest_update.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    if latest_update is not None
                    else "N/D"
                ),
            )

        st.subheader(
            "Volumen procesado por dataset"
        )

        volume_data = {
            "users": counts["users"] or 0,
            "transactions": counts["transactions"] or 0,
            "loans": counts["loans"] or 0,
            "economic_data": counts["economic_data"] or 0,
        }

        volume_df = pd.DataFrame(
            list(volume_data.items()),
            columns=[
                "dataset",
                "records",
            ],
        )

        volume_df = (
            volume_df
            .set_index("dataset")
        )

        st.bar_chart(
            volume_df,
            y_label="Registros",
        )

        st.dataframe(
            volume_df.reset_index(),
            use_container_width=True,
            hide_index=True,
        )

        st.dataframe(
            pipeline_df[
                columns
            ].head(20),
            use_container_width=True,
            hide_index=True,
        )


elif page == "Calidad":

    st.subheader(
        "Calidad de datos"
    )

    if quality_df_summary.empty:

        st.warning(
            "No se encontraron "
            "resultados de calidad."
        )

    else:

        total_pass = int(
            quality_df_summary[
                "pass"
            ].sum()
        )

        total_fail = int(
            quality_df_summary[
                "fail"
            ].sum()
        )

        structural = (
            total_pass
            + total_fail
        )

        overall_rate = (
            total_pass
            / structural
            * 100
            if structural > 0
            else 0
        )

        c1, c2, c3 = (
            st.columns(3)
        )

        c1.metric(
            "Checks PASS",
            total_pass,
        )

        c2.metric(
            "Checks FAIL",
            total_fail,
        )

        c3.metric(
            "Calidad estructural",
            f"{overall_rate:.1f}%",
        )

        st.subheader(
            "Calidad relacional users ↔ transactions"
        )

        r1, r2, r3, r4 = st.columns(4)

        r1.metric(
            "Transacciones vinculadas",
            f"{relationship_metrics.get(
                'transaction_user_linkage_percentage',
                0
            ):.2f}%",
        )

        r2.metric(
            "Integridad referencial",
            f"{relationship_metrics.get(
                'valid_linked_transactions_percentage',
                0
            ):.2f}%",
        )

        r3.metric(
            "Usuarios con transacciones",
            int(
                relationship_metrics.get(
                    "users_with_transactions",
                    0
                )
            ),
        )

        r4.metric(
            "Usuarios sin transacciones",
            int(
                relationship_metrics.get(
                    "users_without_transactions",
                    0
                )
            ),
        )

        st.dataframe(
            quality_df_summary,
            use_container_width=True,
            hide_index=True,
        )

        if (
            "dataset"
            in quality_df.columns
        ):

            datasets = sorted(
                quality_df[
                    "dataset"
                ]
                .dropna()
                .unique()
            )

        else:

            datasets = []

        selected_dataset = (
            st.selectbox(
                "Dataset",
                datasets,
            )
        )

        if selected_dataset:

            detail = (
                quality_df[
                    quality_df[
                        "dataset"
                    ]
                    == selected_dataset
                ]
                .copy()
            )

            if (
                "checked_at"
                in detail.columns
            ):

                detail[
                    "checked_at"
                ] = pd.to_datetime(
                    detail[
                        "checked_at"
                    ],
                    errors="coerce",
                    utc=True,
                )

                detail = (
                    detail
                    .sort_values(
                        "checked_at",
                        ascending=False,
                    )
                )

            st.subheader(
                f"Últimos checks: "
                f"{selected_dataset}"
            )

            st.dataframe(
                detail.head(30),
                use_container_width=True,
                hide_index=True,
            )


elif page == "Auditoría":

    st.subheader(
        "Auditoría e historial "
        "de ejecuciones"
    )

    if audit_df.empty:

        st.warning(
            "No se encontraron "
            "logs de auditoría."
        )

    else:

        df = audit_df.copy()

        if "end_time" in df.columns:

            df["end_time"] = (
                pd.to_datetime(
                    df["end_time"],
                    errors="coerce",
                    utc=True,
                )
            )

            df = df.sort_values(
                "end_time",
                ascending=False,
            )

        status_counts = (
            df["status"].value_counts()
            if "status" in df.columns
            else pd.Series(
                dtype=int
            )
        )

        c1, c2, c3 = (
            st.columns(3)
        )

        c1.metric(
            "Ejecuciones",
            len(df),
        )

        c2.metric(
            "SUCCESS",
            int(
                status_counts.get(
                    "SUCCESS",
                    0,
                )
            ),
        )

        c3.metric(
            "FAILED",
            int(
                status_counts.get(
                    "FAILED",
                    0,
                )
            ),
        )

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

        st.info(
            "Delta Lake mantiene además "
            "el historial de versiones "
            "de cada tabla Silver. "
            "Los scripts "
            "show_delta_history.py y "
            "show_delta_version.py "
            "permiten consultar ese "
            "historial y realizar "
            "Time Travel."
        )