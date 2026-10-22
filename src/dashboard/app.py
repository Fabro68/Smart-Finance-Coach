from pathlib import Path
import json

import pandas as pd
import streamlit as st

from deltalake import DeltaTable


st.set_page_config(
    page_title="Smart Finance Coach",
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


GOLD_KPIS_PATH = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "user_financial_kpis"
)

GOLD_PROFILE_PATH = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "user_financial_profile"
)

GOLD_MONTHLY_FINANCE_PATH = (
    PROJECT_ROOT
    / "data"
    / "gold"
    / "user_monthly_finance"
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

def load_spark_csv_folder(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    csv_files = list(
        path.glob("part-*.csv")
    )

    if not csv_files:
        return pd.DataFrame()

    return pd.concat(
        [
            pd.read_csv(file)
            for file in csv_files
        ],
        ignore_index=True,
    )

def load_delta_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    table = DeltaTable(str(path))

    return table.to_pyarrow_table().to_pandas()


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

users_df = load_delta_table(
    GOLD_PROFILE_PATH
)


kpis_df = load_delta_table(
    GOLD_KPIS_PATH
)

monthly_finance_df = load_delta_table(
    GOLD_MONTHLY_FINANCE_PATH
)

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


# ============================================================
# PREPARACIÓN DE DATOS PARA LA VISTA FINANCIERA
# ============================================================

if not users_df.empty:
    users_df["user_id"] = pd.to_numeric(
        users_df["user_id"],
        errors="coerce",
    )

    users_df["salario_mensual"] = pd.to_numeric(
        users_df["salario_mensual"],
        errors="coerce",
    )



if not kpis_df.empty:
    kpis_df["user_id"] = pd.to_numeric(
        kpis_df["user_id"],
        errors="coerce",
    )

    kpis_df["year_month"] = (
        kpis_df["year_month"]
        .astype(str)
    )

    numeric_kpi_columns = [
        "salary_monthly",
        "consumer_spending",
        "total_debits",
        "total_credits",
        "transactional_balance",
        "estimated_margin",
        "spending_to_salary_ratio",
        "estimated_savings_capacity",
        "estimated_savings_rate",
        "previous_month_spending",
        "spending_change_pct",
    ]

    for column in numeric_kpi_columns:
        kpis_df[column] = pd.to_numeric(
            kpis_df[column],
            errors="coerce",
        )

if not monthly_finance_df.empty:
    monthly_finance_df["user_id"] = pd.to_numeric(
        monthly_finance_df["user_id"],
        errors="coerce",
    )

    monthly_finance_df["year_month"] = (
        monthly_finance_df["year_month"]
        .astype(str)
    )

    numeric_monthly_columns = [
        "salary_monthly",
        "transaction_count",
        "debit_count",
        "credit_count",
        "total_debits",
        "total_credits",
        "transactional_balance",
        "consumer_spending",
        "credit_card_payments",
        "estimated_margin",
        "spending_to_salary_ratio",
        "estimated_savings_capacity",
        "estimated_savings_rate",
        "average_debit_amount",
        "average_credit_amount",
    ]

    for column in numeric_monthly_columns:
        monthly_finance_df[column] = pd.to_numeric(
            monthly_finance_df[column],
            errors="coerce",
        )

def fix_text(value):
    """
    Corrige problemas simples de codificación
    como QuerÃ©taro -> Querétaro.
    """

    if not isinstance(value, str):
        return value

    if "Ã" not in value and "Â" not in value:
        return value

    try:
        return value.encode(
            "latin1"
        ).decode(
            "utf-8"
        )

    except (
        UnicodeEncodeError,
        UnicodeDecodeError,
    ):
        return value


for column in [
    "ciudad",
    "estado_civil",
]:
    if (
        not users_df.empty
        and column in users_df.columns
    ):
        users_df[column] = (
            users_df[column]
            .map(fix_text)
        )




# ============================================================
# ENCABEZADO
# ============================================================

st.title(
    "💰 Smart Finance Coach"
)

st.caption(
    "Tu visión financiera personal en un solo lugar"
)


# ============================================================
# VALIDAR DATOS
# ============================================================

if users_df.empty:
    st.error(
        "No se encontraron datos de usuarios."
    )
    st.stop()


# Usuarios que realmente tienen transacciones asociadas
gold_user_ids = (
    kpis_df[
        "user_id"
    ]
    .dropna()
    .unique()
)

available_users = (
    users_df[
        users_df[
            "user_id"
        ].isin(
            gold_user_ids
        )
    ]
    .copy()
    .sort_values(
        "user_id"
    )
)


if available_users.empty:
    st.warning(
        "No hay usuarios con "
        "transacciones vinculadas."
    )
    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "Smart Finance Coach"
    )

    selected_user_id = (
        st.selectbox(
            "Selecciona un usuario",
            available_users[
                "user_id"
            ].astype(
                int
            ).tolist(),
            format_func=lambda x:
                f"Usuario {x}",
        )
    )

    page = st.radio(
        "Vista",
        [
            "Mis finanzas",
            "Mi perfil",
            "Monitoreo técnico",
        ],
    )

    st.divider()

    st.caption(
        "Financial Digital Twin"
    )


# ============================================================
# USUARIO SELECCIONADO
# ============================================================

user_row = (
    users_df[
        users_df["user_id"]
        == selected_user_id
    ]
    .iloc[0]
)


user_kpis = (
    kpis_df[
        kpis_df["user_id"]
        == selected_user_id
    ]
    .copy()
    .sort_values(
        "year_month"
    )
)

user_monthly_finance = (
    monthly_finance_df[
        monthly_finance_df["user_id"]
        == selected_user_id
    ]
    .copy()
    .sort_values(
        "year_month"
    )
)


# ============================================================
# MIS FINANZAS
# ============================================================

if page == "Mis finanzas":

    st.subheader(
        f"Hola, Usuario "
        f"{int(selected_user_id)} 👋"
    )

    st.write(
        "Aquí puedes consultar "
        "el comportamiento de tus "
        "finanzas y movimientos."
    )


    if user_monthly_finance.empty:

        st.info(
            "Este usuario no tiene "
            "información financiera disponible."
        )

        st.stop()

    # --------------------------------------------------------
    # PERIODO
    # --------------------------------------------------------

    periods = sorted(
        user_monthly_finance[
            "year_month"
        ]
        .dropna()
        .unique(),
        reverse=True,
    )


    selected_period = (
    st.selectbox(
        "Periodo",
        [
            *periods,
            "Todo el historial",
        ],
    )
)


    if (
        selected_period
        == "Todo el historial"
    ):

        period_df = (
            user_monthly_finance
            .copy()
        )

        period_name = (
            "todo el historial"
        )

    else:

        period_df = (
            user_monthly_finance[
                user_monthly_finance[
                    "year_month"
                ]
                == selected_period
            ]
            .copy()
        )

        period_name = (
            selected_period
        )


    # --------------------------------------------------------
    # DÉBITOS Y CRÉDITOS
    # --------------------------------------------------------

    if (
        selected_period
        == "Todo el historial"
    ):

        total_debits = (
            period_df[
                "total_debits"
            ].sum()
        )

        total_credits = (
            period_df[
                "total_credits"
            ].sum()
        )

        transaction_balance = (
            period_df[
                "transactional_balance"
            ].sum()
        )

    else:

        period_row = (
            period_df
            .iloc[0]
        )

        total_debits = float(
            period_row[
                "total_debits"
            ]
        )

        total_credits = float(
            period_row[
                "total_credits"
            ]
        )

        transaction_balance = float(
            period_row[
                "transactional_balance"
            ]
        )


    monthly_salary = float(
        user_row[
            "salario_mensual"
        ]
    )


    # --------------------------------------------------------
    # MÉTRICAS PRINCIPALES
    # --------------------------------------------------------

    c1, c2, c3, c4 = (
        st.columns(4)
    )


    c1.metric(
        "Salario mensual",
        f"${monthly_salary:,.2f}",
    )


    c2.metric(
        "Gastos del periodo",
        f"${total_debits:,.2f}",
    )

    c3.metric(
        "Movimientos recibidos",
        f"${total_credits:,.2f}",
    )

    c4.metric(
        "Balance de movimientos",
        f"${transaction_balance:,.2f}",
    )


    st.caption(
        "Los créditos representan "
        "movimientos clasificados como "
        "'credit' en la fuente de datos. "
        "No necesariamente representan "
        "ingresos salariales."
    )


    # --------------------------------------------------------
    # INDICADORES DEL MES
    # --------------------------------------------------------

    if (
        selected_period
        != "Todo el historial"
    ):

        estimated_margin = float(
            period_row[
                "estimated_margin"
            ]
        )

        spending_ratio = float(
            period_row[
                "spending_to_salary_ratio"
            ]
        ) * 100


        st.subheader(
            "Tu situación este mes"
        )


        m1, m2, m3 = (
            st.columns(3)
        )


        m1.metric(
            "Margen estimado",
            f"${estimated_margin:,.2f}",
        )


        m2.metric(
            "Gastos vs. salario",
            f"{spending_ratio:.1f}%",
        )


        m3.metric(
            "Movimientos",
            f"{int(period_row['transaction_count']):,}",
        )


        st.caption(
            "El margen estimado se calcula "
            "como salario mensual menos "
            "débitos registrados. "
            "No representa el saldo real "
            "de una cuenta bancaria."
        )


    st.divider()


    # --------------------------------------------------------
    # GRÁFICAS
    # --------------------------------------------------------

    graph1, graph2 = (
        st.columns(2)
    )


    with graph1:

        st.subheader(
            "Evolución de movimientos"
        )


        monthly = (
            user_monthly_finance[
                [
                    "year_month",
                    "total_debits",
                    "total_credits",
                ]
            ]
            .copy()
            .set_index(
                "year_month"
            )
            .rename(
                columns={
                    "total_debits":
                        "Débitos",
                    "total_credits":
                        "Créditos",
                }
            )
            .sort_index()
        )


        st.line_chart(
            monthly
        )


    with graph2:

        st.subheader(
            "¿En qué estás gastando?"
        )


        category_spend = (
            user_monthly_finance[
                [
                    "top_spending_category",
                    "consumer_spending",
                ]
            ]
            .dropna(
                subset=[
                    "top_spending_category",
                ]
            )
            .groupby(
                "top_spending_category"
            )[
                "consumer_spending"
            ]
            .sum()
            .sort_values(
                ascending=False
            )
            .head(10)
        )

        if category_spend.empty:

            st.info(
                "No hay información de gasto "
                "por categoría disponible."
            )

        else:

            st.bar_chart(
                category_spend
            )


    # --------------------------------------------------------
    # RESUMEN AUTOMÁTICO
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "Resumen de tus finanzas"
    )


    if not period_df.empty:

        if (
            selected_period
            == "Todo el historial"
        ):

            latest_kpi = (
                user_kpis
                .sort_values(
                    "year_month"
                )
                .iloc[-1]
            )

        else:

            latest_kpi = (
                user_kpis[
                    user_kpis[
                        "year_month"
                    ]
                    == selected_period
                ]
                .iloc[0]
            )

        risk_level = (
            latest_kpi[
                "financial_risk_level"
            ]
        )

        savings_health = (
            latest_kpi[
                "savings_health"
            ]
        )

        savings_rate = float(
            latest_kpi[
                "estimated_savings_rate"
            ]
        ) * 100

        top_category = (
            latest_kpi[
                "top_spending_category"
            ]
        )

        st.info(
            f"En {period_name}, "
            f"tu nivel de riesgo financiero es "
            f"**{risk_level}** y la salud de tu ahorro "
            f"se clasifica como **{savings_health}**. "
            f"Tu tasa estimada de ahorro es de "
            f"**{savings_rate:.1f}%** y la categoría "
            f"principal de gasto es **{top_category}**."
        )




# ============================================================
# MI PERFIL
# ============================================================

elif page == "Mi perfil":

    st.subheader(
        "Mi perfil financiero"
    )


    p1, p2, p3 = (
        st.columns(3)
    )


    p1.metric(
        "Edad",
        f"{int(user_row['edad'])} años",
    )


    p2.metric(
        "Salario mensual",
        (
            f"${float(user_row['salario_mensual']):,.2f}"
        ),
    )


    p3.metric(
        "Dependientes",
        int(
            user_row[
                "dependientes"
            ]
        ),
    )


    st.divider()


    profile1, profile2 = (
        st.columns(2)
    )


    with profile1:

        st.markdown(
            "### Información personal"
        )

        st.write(
            "**Ciudad:** "
            f"{user_row['ciudad']}"
        )

        st.write(
            "**Estado civil:** "
            f"{user_row['estado_civil']}"
        )

        st.write(
            "**ID de usuario:** "
            f"{int(selected_user_id)}"
        )


    with profile2:

        st.markdown(
            "### Actividad financiera"
        )

        st.write(
            "**Movimientos registrados:** "
            f"{int(user_row['linked_transaction_count']):,}"
        )


        accounts = (
            [user_row["primary_account"]]
            if pd.notna(user_row["primary_account"])
            else []
        )


        st.write(
            "**Cuentas detectadas:** "
            f"{len(accounts)}"
        )


        if pd.notna(user_row["first_transaction_date"]):

            first_date = pd.to_datetime(
                user_row[
                    "first_transaction_date"
                ]
            )

            last_date = pd.to_datetime(
                user_row[
                    "last_transaction_date"
                ]
            )

            st.write(
                "**Primer movimiento:** "
                f"{first_date:%Y-%m-%d}"
            )

            st.write(
                "**Último movimiento:** "
                f"{last_date:%Y-%m-%d}"
            )





# ============================================================
# MONITOREO TÉCNICO
# ============================================================

elif page == "Monitoreo técnico":

    st.subheader(
        "Monitoreo técnico"
    )

    st.caption(
        "Información secundaria para "
        "demostrar calidad, auditoría y "
        "observabilidad del pipeline."
    )


    tab1, tab2, tab3 = (
        st.tabs(
            [
                "Pipeline",
                "Calidad",
                "Auditoría",
            ]
        )
    )


    # --------------------------------------------------------
    # PIPELINE
    # --------------------------------------------------------

    with tab1:

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
                "start_time"
                in pipeline_df.columns
                and
                "end_time"
                in pipeline_df.columns
            ):

                pipeline_df[
                    "start_time"
                ] = pd.to_datetime(
                    pipeline_df[
                        "start_time"
                    ],
                    errors="coerce",
                    utc=True,
                )


                pipeline_df[
                    "end_time"
                ] = pd.to_datetime(
                    pipeline_df[
                        "end_time"
                    ],
                    errors="coerce",
                    utc=True,
                )


                pipeline_df[
                    "duration_seconds"
                ] = (
                    pipeline_df[
                        "end_time"
                    ]
                    - pipeline_df[
                        "start_time"
                    ]
                ).dt.total_seconds()


            success_count = int(
                (
                    pipeline_df[
                        "status"
                    ]
                    == "SUCCESS"
                ).sum()
            )


            failed_count = int(
                (
                    pipeline_df[
                        "status"
                    ]
                    == "FAILED"
                ).sum()
            )


            total_runs = (
                success_count
                + failed_count
            )


            success_rate = (
                (
                    success_count
                    / total_runs
                )
                * 100
                if total_runs > 0
                else 0
            )


            t1, t2, t3 = (
                st.columns(3)
            )


            t1.metric(
                "Ejecuciones",
                total_runs,
            )


            t2.metric(
                "Exitosas",
                success_count,
            )


            t3.metric(
                "Tasa de éxito",
                f"{success_rate:.1f}%",
            )


            st.dataframe(
                pipeline_df,
                use_container_width=True,
                hide_index=True,
            )


    # --------------------------------------------------------
    # CALIDAD
    # --------------------------------------------------------

    with tab2:

        if quality_df_summary.empty:

            st.warning(
                "No existen resultados "
                "de calidad."
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
                (
                    total_pass
                    / structural
                )
                * 100
                if structural > 0
                else 0
            )


            q1, q2, q3 = (
                st.columns(3)
            )


            q1.metric(
                "Checks PASS",
                total_pass,
            )


            q2.metric(
                "Checks FAIL",
                total_fail,
            )


            q3.metric(
                "Calidad estructural",
                f"{overall_rate:.1f}%",
            )


            st.dataframe(
                quality_df_summary,
                use_container_width=True,
                hide_index=True,
            )


    # --------------------------------------------------------
    # AUDITORÍA
    # --------------------------------------------------------

    with tab3:

        if audit_df.empty:

            st.warning(
                "No se encontraron "
                "logs de auditoría."
            )

        else:

            st.dataframe(
                audit_df,
                use_container_width=True,
                hide_index=True,
            )


            st.info(
                "Delta Lake conserva "
                "el historial de versiones "
                "de las tablas Silver y "
                "permite realizar Time Travel."
            )
