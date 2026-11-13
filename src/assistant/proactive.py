"""
Sugerencias proactivas del asistente (Semana 20).

Al abrir el asistente, revisa el historial del usuario y muestra lo que le
aplica, sin que tenga que preguntarlo:
- Crédito preaprobado ilustrativo: solo si cumple las dos reglas de crédito
  responsable (cuota <= 30% del ingreso y riesgo de terminar en negativo
  <= 10%) Y no muestra señales de dificultad financiera.
- Alerta de gasto: si el gasto del último mes subió más de 30%.
- Ritmo de ahorro: cuánto podría juntar en 12 meses si su flujo es positivo.
- Renta o compra: invitación a calcularlo.

Criterio de banca responsable: no se ofrece crédito de forma proactiva a
quien muestra señales de dificultad (3 o más meses con balance negativo en
los últimos 6, o una anomalía de gasto en los últimos 3 meses), aunque sea
elegible. En su lugar se muestra la sugerencia de ahorro.

Todo es ilustrativo y se calcula con las mismas herramientas del asistente.
"""

from dataclasses import dataclass, field

from assistant import tools
from assistant.data_access import user_connection
from assistant.tools import mxn, month_name, term_text
from simulation.monte_carlo import Scenario, load_user_history, simulate


SPENDING_ALERT_PCT = 30.0
DISTRESS_NEGATIVE_MONTHS = 3
DISTRESS_ANOMALY_WINDOW = 3


@dataclass
class Insight:
    kind: str            # credito | alerta_gasto | ahorro | vivienda
    title: str
    text: str
    follow_up: str       # pregunta sugerida para profundizar


@dataclass
class Welcome:
    greeting: str
    insights: list[Insight] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    credit_withheld_reason: str | None = None


def distress_signals(user_id: int) -> list[str]:
    """Señales de dificultad financiera reciente en el historial del usuario."""
    con = user_connection(user_id)
    recent = con.execute(
        "SELECT negative_balance_months_6m, is_spend_anomaly FROM ml_user_features "
        "ORDER BY year_month DESC LIMIT ?", [DISTRESS_ANOMALY_WINDOW]
    ).df()

    signals = []
    negative = int(recent.iloc[0]["negative_balance_months_6m"])
    if negative >= DISTRESS_NEGATIVE_MONTHS:
        signals.append(f"{negative} meses con balance negativo en los últimos 6")
    if (recent["is_spend_anomaly"].fillna(0) == 1).any():
        signals.append(f"una anomalía de gasto en los últimos {DISTRESS_ANOMALY_WINDOW} meses")
    return signals


def build_welcome(user_id: int) -> Welcome:
    history = load_user_history(user_id)
    insights: list[Insight] = []
    withheld = None

    # 1. Crédito preaprobado (solo crédito responsable y sin señales de dificultad)
    signals = distress_signals(user_id)
    offer = tools.oferta_credito(user_id, "36 meses")
    if offer.metrics["eligible"] and not signals:
        insights.append(Insight(
            kind="credito",
            title="Tienes un crédito preaprobado",
            text=(
                f"Te podríamos prestar hasta {mxn(offer.metrics['amount_mxn'])} a "
                f"{term_text(offer.metrics['term'])}, pagando {mxn(offer.metrics['monthly_payment_mxn'])} al mes."
            ),
            follow_up="¿Cuánto me pueden prestar a 2 años?",
        ))
    elif signals:
        withheld = "señales de dificultad: " + "; ".join(signals)
    else:
        withheld = "no cumple las reglas de crédito responsable"

    # 2. Alerta de gasto
    change = tools.cambio_ahorro(user_id)
    pct = change.metrics["spending_change_pct"]
    if pct > SPENDING_ALERT_PCT:
        category = change.metrics["top_increase_category"]
        insights.append(Insight(
            kind="alerta_gasto",
            title="Tu gasto subió",
            text=(
                f"Ojo: en {month_name(change.metrics['target'])} gastaste {pct:.0f}% más que el mes anterior"
                + (f", sobre todo en {category}." if category else ".")
            ),
            follow_up="¿Por qué bajó mi ahorro el mes pasado?",
        ))

    # 3. Ritmo de ahorro
    baseline = simulate(history, Scenario(), 12).summary()
    if baseline["expected_monthly_net"] > 0:
        insights.append(Insight(
            kind="ahorro",
            title="Tu ahorro",
            text=f"Si sigues como vas, en un año podrías juntar unos {mxn(baseline['final_p50'])}.",
            follow_up="¿Cuándo podría juntar 100 mil pesos?",
        ))

    # 4. Renta o compra (invitación)
    insights.append(Insight(
        kind="vivienda",
        title="¿Pagas renta?",
        text=(
            "En el Simulador, pestaña «Renta o compra», te digo qué casa podrías comprar "
            "pagando lo mismo que hoy pagas de renta."
        ),
        follow_up="¿Qué pasaría si mis gastos suben 20%?",
    ))

    greeting = (
        f"¡Hola! Revisé tus movimientos hasta {month_name(history.last_month)} "
        "y esto es lo que te puede interesar:"
    )
    suggestions = []
    for item in [i.follow_up for i in insights] + ["¿Cómo están mis finanzas?", "¿Cuánto gasté en restaurantes en 2019?"]:
        if item not in suggestions:
            suggestions.append(item)

    return Welcome(greeting, insights, suggestions[:5], withheld)
