"""
Vista "Simulador" del dashboard (Semana 19).

Interfaz en Streamlit sobre el motor src/simulation/monte_carlo.py.
No contiene logica financiera propia: solo captura parametros, llama al
motor y muestra resultados.

Secciones:
1. Simula un escenario (combinable).
2. Cuanto credito te podemos ofrecer.
3. Renta o compra (hipoteca con la misma cuota que la renta).
"""

import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from simulation.monte_carlo import (  # noqa: E402
    ALLOWED_HORIZONS,
    DEFAULT_CLOSING_COSTS_PCT,
    DEFAULT_MAX_PAYMENT_SHARE,
    DEFAULT_MAX_PROB_NEGATIVE,
    DEFAULT_MORTGAGE_RATE,
    DEFAULT_MORTGAGE_TERM_YEARS,
    DEFAULT_PERSONAL_LOAN_RATE,
    LOAN_PURPOSES,
    CarPurchase,
    ExpenseIncrease,
    HousingChange,
    IncomeChange,
    LoanScenario,
    MortgageFromRent,
    Scenario,
    compare,
    credit_offer,
    load_user_history,
)


LOAN_TERMS = (12, 24, 36, 48, 60)
PURPOSE_LABELS = {
    "Auto": "Auto",
    "Business": "Negocio",
    "Education": "Educación",
    "Home": "Vivienda",
    "Other": "Otro",
}


# ============================================================
# HELPERS
# ============================================================

def mxn(value: float) -> str:
    return f"${value:,.0f} MXN"


@st.cache_data(show_spinner=False)
def _history(user_id: int):
    return load_user_history(user_id)


def band_chart(results, title: str):
    """Bandas P5–P95 y mediana del cambio acumulado, por escenario."""
    frames = []
    for res in results:
        p = res.percentiles()
        p["escenario"] = res.scenario_name
        frames.append(p)
    data = pd.concat(frames, ignore_index=True)

    base = alt.Chart(data).encode(
        x=alt.X("month:Q", title="Mes", axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("escenario:N", title="Escenario"),
    )
    band = base.mark_area(opacity=0.18).encode(
        y=alt.Y("p5:Q", title="Cambio acumulado (MXN)"),
        y2="p95:Q",
        tooltip=[
            alt.Tooltip("escenario:N", title="Escenario"),
            alt.Tooltip("month:Q", title="Mes"),
            alt.Tooltip("p5:Q", title="P5", format=",.0f"),
            alt.Tooltip("p50:Q", title="Mediana", format=",.0f"),
            alt.Tooltip("p95:Q", title="P95", format=",.0f"),
        ],
    )
    median = base.mark_line(strokeWidth=2.5).encode(y="p50:Q")
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q")

    return (band + median + zero).properties(title=title, height=360)


def traffic_light(prob_negative: float) -> tuple[str, str]:
    """Semáforo de '¿Me alcanza?' según la probabilidad de terminar en negativo."""
    if prob_negative <= 0.10:
        return "🟢", "Sí te alcanza en la mayoría de los escenarios simulados."
    if prob_negative <= 0.30:
        return "🟡", "Te alcanza con riesgo: en varios escenarios terminas en negativo."
    return "🔴", "No te alcanza: en muchos escenarios terminas en negativo."


def show_summary_metrics(baseline, scenario):
    b, s = baseline.summary(), scenario.summary()
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Mediana al final",
        mxn(s["final_p50"]),
        delta=f"{s['final_p50'] - b['final_p50']:,.0f} vs. línea base",
        border=True,
    )
    c2.metric(
        "Prob. de terminar en negativo",
        f"{s['prob_final_negative']:.0%}",
        delta=f"{(s['prob_final_negative'] - b['prob_final_negative']) * 100:+.0f} pp",
        delta_color="inverse",
        border=True,
    )
    c3.metric(
        "Flujo mensual esperado",
        mxn(s["expected_monthly_net"]),
        delta=f"{s['expected_monthly_net'] - b['expected_monthly_net']:,.0f} vs. línea base",
        border=True,
    )


def show_model_risk(loans: list[dict]):
    """'Riesgo según el modelo', separado de '¿Me alcanza?'."""
    st.markdown("##### Riesgo según el modelo")
    st.caption(
        "Probabilidad de impago estimada con el modelo de riesgo crediticio "
        "(Semana 18). Es un **escenario ilustrativo**: el modelo se entrenó con "
        "préstamos que no corresponden a los usuarios del proyecto y **no ve tu "
        "flujo de efectivo**, solo edad, ingreso, estado civil, dependientes y "
        "las condiciones del crédito."
    )
    for loan in loans:
        p = loan.get("probability_of_default")
        label = f"{loan['label']} ({mxn(loan['amount_mxn'])}, {loan['term_months']} meses)"
        if p is None:
            st.info(f"{label}: P(impago) no disponible. {loan.get('note', '')}")
            continue
        st.write(f"**{label}:** P(impago) = **{p:.1%}**")
        if loan["outside_training_range"]:
            fields = ", ".join(loan["outside_training_range"])
            st.warning(
                f"Estimación poco confiable: valores fuera del rango de entrenamiento ({fields})."
            )


def assumptions_note():
    st.caption(
        "Montos en MXN. Los créditos y débitos históricos se convirtieron con el "
        "tipo de cambio de cada mes, suponiendo que las transacciones están en USD "
        "(unidad inferida). La simulación muestra el **cambio acumulado desde hoy, "
        "partiendo de 0**, no un saldo bancario. Bootstrap de meses históricos, "
        "5,000 trayectorias. Proyecto académico con datos simulados: no es una "
        "oferta real ni asesoría financiera."
    )


# ============================================================
# SECTION 1: SCENARIOS
# ============================================================

def section_scenarios(history):
    horizon = st.selectbox("Horizonte", ALLOWED_HORIZONS, index=1, format_func=lambda h: f"{h} meses", key="sc_horizon")

    st.markdown("**Elige uno o varios escenarios:**")
    cols = st.columns(5)
    use_loan = cols[0].checkbox("Contratar crédito")
    use_income = cols[1].checkbox("Cambio de empleo / ingreso")
    use_expenses = cols[2].checkbox("Aumento de gastos")
    use_car = cols[3].checkbox("Comprar auto nuevo")
    use_housing = cols[4].checkbox("Cambiarse de vivienda (renta)")

    scenario = Scenario(name="Escenario")
    names = []

    if use_loan:
        with st.expander("Contratar crédito", expanded=True):
            c = st.columns(4)
            scenario.loan = LoanScenario(
                amount_mxn=c[0].number_input("Monto (MXN)", 1_000.0, 10_000_000.0, 100_000.0, 5_000.0, key="ln_amt"),
                term_months=c[1].selectbox("Plazo (meses)", LOAN_TERMS, index=2, key="ln_term"),
                annual_rate_pct=c[2].number_input("Tasa anual (%)", 0.0, 80.0, DEFAULT_PERSONAL_LOAN_RATE, 0.5, key="ln_rate"),
                purpose=c[3].selectbox("Propósito", LOAN_PURPOSES, index=LOAN_PURPOSES.index("Other"), format_func=PURPOSE_LABELS.get, key="ln_purpose"),
            )
        names.append("crédito")

    if use_income:
        with st.expander("Cambio de empleo / ingreso", expanded=True):
            c = st.columns(2)
            scenario.income = IncomeChange(
                pct_change=c[0].number_input("Cambio en ingresos (%)", -100.0, 200.0, -20.0, 5.0, key="inc_pct"),
                months_without_income=c[1].number_input("Meses sin ingreso al inicio", 0, 36, 0, 1, key="inc_gap"),
            )
        names.append("ingreso")

    if use_expenses:
        with st.expander("Aumento de gastos", expanded=True):
            scenario.expenses = ExpenseIncrease(
                pct=st.number_input("Aumento en gastos (%)", -50.0, 200.0, 15.0, 5.0, key="exp_pct"),
            )
        names.append("gastos")

    if use_car:
        with st.expander("Comprar auto nuevo", expanded=True):
            c = st.columns(5)
            scenario.car = CarPurchase(
                price_mxn=c[0].number_input("Precio (MXN)", 50_000.0, 5_000_000.0, 350_000.0, 10_000.0, key="car_price"),
                down_payment_pct=c[1].number_input("Enganche (%)", 0.0, 100.0, 20.0, 5.0, key="car_dp"),
                term_months=c[2].selectbox("Plazo (meses)", LOAN_TERMS, index=3, key="car_term"),
                annual_rate_pct=c[3].number_input("Tasa anual (%)", 0.0, 80.0, 13.0, 0.5, key="car_rate"),
                monthly_car_cost_mxn=c[4].number_input("Gasto mensual del auto (MXN)", 0.0, 100_000.0, 2_500.0, 500.0, key="car_cost"),
            )
        names.append("auto")

    if use_housing:
        with st.expander("Cambiarse de vivienda (renta)", expanded=True):
            c = st.columns(3)
            scenario.housing = HousingChange(
                current_rent_mxn=c[0].number_input("Renta actual (MXN)", 0.0, 500_000.0, 6_000.0, 500.0, key="h_cur"),
                new_rent_mxn=c[1].number_input("Renta nueva (MXN)", 0.0, 500_000.0, 8_000.0, 500.0, key="h_new"),
                one_time_costs_mxn=c[2].number_input("Mudanza y depósito (MXN)", 0.0, 1_000_000.0, 15_000.0, 1_000.0, key="h_once"),
            )
        names.append("vivienda")

    if not names:
        st.info("Selecciona al menos un escenario para compararlo con tu línea base.")
        baseline, _ = compare(history, Scenario(), horizon)
        st.altair_chart(band_chart([baseline], "Línea base: cambio acumulado proyectado"), width="stretch")
        return

    scenario.name = "Escenario: " + " + ".join(names)
    baseline, result = compare(history, scenario, horizon)

    st.altair_chart(
        band_chart([baseline, result], "Cambio acumulado proyectado (bandas P5–P95, línea = mediana)"),
        width="stretch",
    )
    show_summary_metrics(baseline, result)

    for warning in result.warnings:
        st.warning(warning)

    left, right = st.columns(2)
    with left:
        st.markdown("##### ¿Me alcanza?")
        icon, text = traffic_light(result.summary()["prob_final_negative"])
        st.markdown(f"### {icon}")
        st.write(text)
        for loan in result.loans:
            ratio = loan.get("payment_to_median_net_flow")
            ratio_txt = f"{ratio:.0%} de tu flujo neto mensual típico" if ratio is not None else "tu flujo neto típico no es positivo"
            st.write(f"- {loan['label']}: cuota de **{mxn(loan['monthly_payment_mxn'])}** = {ratio_txt}.")
        st.caption("Basado en tu flujo de efectivo real, simulado con 5,000 trayectorias.")
    with right:
        if result.loans:
            show_model_risk(result.loans)
        else:
            st.markdown("##### Riesgo según el modelo")
            st.caption("Aplica solo a escenarios con crédito (crédito o auto).")


# ============================================================
# SECTION 2: CREDIT OFFER
# ============================================================

def section_offer(history):
    st.write(
        "Calculamos el crédito más alto que se te puede ofrecer de forma responsable, "
        "con base en tus finanzas registradas."
    )
    c = st.columns(5)
    term = c[0].selectbox("Plazo (meses)", LOAN_TERMS, index=2, key="of_term")
    rate = c[1].number_input("Tasa anual (%)", 0.0, 80.0, DEFAULT_PERSONAL_LOAN_RATE, 0.5, key="of_rate")
    purpose = c[2].selectbox("Propósito", LOAN_PURPOSES, index=LOAN_PURPOSES.index("Other"), format_func=PURPOSE_LABELS.get, key="of_purpose")
    share = c[3].slider("Cuota máx. (% del ingreso)", 10, 50, int(DEFAULT_MAX_PAYMENT_SHARE * 100), 5, key="of_share") / 100
    max_neg = c[4].slider("Prob. máx. de terminar en negativo (%)", 1, 30, int(DEFAULT_MAX_PROB_NEGATIVE * 100), 1, key="of_neg") / 100

    offer = credit_offer(history, term, rate, purpose, share, max_neg)

    st.markdown("##### Reglas aplicadas")
    r1, r2 = st.columns(2)
    r1.metric(
        f"1. Capacidad de pago ({share:.0%} del ingreso típico)",
        mxn(offer["payment_limit_by_income_mxn"]) + " /mes",
        help=f"Ingreso mensual típico (mediana de créditos): {mxn(offer['typical_monthly_income_mxn'])}",
        border=True,
    )
    r2.metric(
        f"2. Estrés Monte Carlo (≤ {max_neg:.0%} de terminar en negativo)",
        mxn(offer["payment_limit_by_stress_mxn"]) + " /mes",
        border=True,
    )

    if not offer["eligible"]:
        st.error("Por ahora no es posible ofrecerte un crédito con estas condiciones.")
        if offer["payment_limit_by_stress_mxn"] <= 0:
            st.write(
                f"Aun sin crédito, tu historial tiene una probabilidad mayor a {max_neg:.0%} "
                f"de terminar los {term} meses con flujo acumulado negativo "
                "(por ejemplo, por meses con gastos extraordinarios)."
            )
        elif offer.get("reason"):
            st.write(offer["reason"])
        return

    st.success(
        f"**Crédito ilustrativo:** {mxn(offer['amount_mxn'])} a {term} meses, "
        f"tasa {rate:.1f}% anual, cuota de **{mxn(offer['monthly_payment_mxn'])}** al mes."
    )
    st.caption(
        f"Regla que limita el monto: {offer['binding_rule']}. "
        f"Con esta cuota, la probabilidad de terminar el plazo en negativo es "
        f"{offer['prob_final_negative_with_offer']:.1%}."
    )

    horizon = term if term in ALLOWED_HORIZONS else 36
    offer_scenario = Scenario(
        name="Con el crédito ofrecido",
        loan=LoanScenario(offer["amount_mxn"], term, rate, purpose),
    )
    baseline, result = compare(history, offer_scenario, horizon)
    st.altair_chart(band_chart([baseline, result], f"Cambio acumulado a {horizon} meses"), width="stretch")
    show_model_risk(result.loans)


# ============================================================
# SECTION 3: RENT VS BUY
# ============================================================

def section_rent_vs_buy(history):
    st.write(
        "¿Y si pagaras de hipoteca lo mismo que hoy pagas de renta? "
        "Calculamos qué vivienda podrías adquirir y cuánto patrimonio acumularías."
    )
    c = st.columns(6)
    rent = c[0].number_input("Renta actual (MXN)", 1_000.0, 500_000.0, 8_000.0, 500.0, key="rb_rent")
    down = c[1].number_input("Enganche disponible (MXN)", 0.0, 20_000_000.0, 100_000.0, 10_000.0, key="rb_down")
    rate = c[2].number_input("Tasa hipotecaria (%)", 0.0, 40.0, DEFAULT_MORTGAGE_RATE, 0.25, key="rb_rate")
    years = c[3].selectbox("Plazo (años)", (10, 15, 20, 25, 30), index=(10, 15, 20, 25, 30).index(DEFAULT_MORTGAGE_TERM_YEARS), key="rb_years")
    closing = c[4].number_input("Escrituración (% del precio)", 0.0, 15.0, DEFAULT_CLOSING_COSTS_PCT, 0.5, key="rb_closing")
    horizon = c[5].selectbox("Horizonte", ALLOWED_HORIZONS, index=1, format_func=lambda h: f"{h} meses", key="rb_horizon")

    scenario = Scenario(
        name="Comprar con hipoteca",
        mortgage=MortgageFromRent(rent, down, rate, years, closing),
    )
    baseline, result = compare(history, scenario, horizon)
    m = result.mortgage

    k = st.columns(4)
    k[0].metric("Vivienda que podrías adquirir", mxn(m["home_price_mxn"]), border=True)
    k[1].metric("Crédito hipotecario", mxn(m["loan_amount_mxn"]), border=True)
    k[2].metric("Pago inicial (enganche + escrituración)", mxn(m["upfront_cost_mxn"]), border=True)
    k[3].metric(f"Patrimonio a {horizon} meses", mxn(m["equity_by_month_mxn"][-1]), border=True)

    st.caption(
        f"Cuota mensual = tu renta actual ({mxn(rent)}). Intereses totales en "
        f"{years} años: {mxn(m['total_interest_over_term_mxn'])}."
    )

    months = np.arange(1, horizon + 1)
    equity = pd.DataFrame({
        "month": np.concatenate([months, months]),
        "patrimonio": m["equity_by_month_mxn"] + [0.0] * horizon,
        "opción": ["Comprando"] * horizon + ["Rentando"] * horizon,
    })
    equity_chart = (
        alt.Chart(equity)
        .mark_line(strokeWidth=2.5)
        .encode(
            x=alt.X("month:Q", title="Mes"),
            y=alt.Y("patrimonio:Q", title="Patrimonio en vivienda (MXN)"),
            color=alt.Color("opción:N", title="Opción"),
            tooltip=[
                alt.Tooltip("opción:N"),
                alt.Tooltip("month:Q", title="Mes"),
                alt.Tooltip("patrimonio:Q", title="Patrimonio", format=",.0f"),
            ],
        )
        .properties(title="Patrimonio: comprar vs. rentar con el mismo pago mensual", height=320)
    )
    st.altair_chart(equity_chart, width="stretch")

    st.altair_chart(
        band_chart([baseline, result], "Tu flujo acumulado (el pago inicial sale en el mes 1)"),
        width="stretch",
    )

    for warning in result.warnings:
        st.warning(warning)

    icon, text = traffic_light(result.summary()["prob_final_negative"])
    st.markdown(f"##### ¿Puedes cubrir el pago inicial? {icon}")
    st.write(text)

    st.info(
        m.get("risk_note")
        or "P(impago) no disponible para este plazo: fuera del rango del modelo de riesgo."
    )


# ============================================================
# ENTRY POINT
# ============================================================

def render_simulator(user_id: int):
    st.subheader("🔮 Simulador financiero")

    try:
        history = _history(int(user_id))
    except (ValueError, FileNotFoundError) as error:
        st.error(f"No se pudo cargar el historial del usuario: {error}")
        return

    st.caption(
        f"Usuario {history.user_id} · {len(history.months)} meses de historial "
        f"({history.months[0]} a {history.last_month}) · tipo de cambio del último mes: "
        f"{history.last_exchange_rate:.2f} MXN/USD"
    )

    tab1, tab2, tab3 = st.tabs([
        "Simula un escenario",
        "¿Cuánto crédito te podemos ofrecer?",
        "Renta o compra",
    ])

    try:
        with tab1:
            section_scenarios(history)
        with tab2:
            section_offer(history)
        with tab3:
            section_rent_vs_buy(history)
    except FileNotFoundError as error:
        st.error(
            f"{error}\n\nEl modelo de riesgo no está disponible. Ejecuta primero "
            "`python src/ml/train_loan_model.py` y `python src/ml/evaluate_loan_model.py`."
        )

    st.divider()
    assumptions_note()
