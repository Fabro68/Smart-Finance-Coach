"""
Herramientas del asistente de IA (Semana 20).

Cada herramienta calcula los hechos con datos de Gold o con el motor del
simulador (Semana 19) y devuelve un ToolResult con:
- summary: la respuesta para una persona sin conocimientos técnicos, en
  lenguaje sencillo, en pesos y en segunda persona. Se genera con
  plantillas en código, así que las cifras son exactas por construcción.
- warnings: la primera es una nota breve y amable para mostrar junto a la
  respuesta; las demás son detalles para quien quiera revisar.
- data, sources, sql: el detalle técnico, que la interfaz esconde en un
  desplegable "¿De dónde sale esto?".
- metrics: cifras en formato numérico para otros módulos (sugerencias).

Solo la consulta libre (SQL) deja la redacción al modelo, con verificación.
El usuario siempre viene de la interfaz, nunca de la pregunta.
Montos en pesos: las transacciones (USD inferido) se convierten con el
tipo de cambio de su mes, igual que en el simulador.
"""

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from assistant.data_access import (
    CATEGORY_ES,
    SQLValidationError,
    category_es,
    run_readonly_query,
    user_connection,
)
from simulation.monte_carlo import (
    ALLOWED_HORIZONS,
    DEFAULT_PERSONAL_LOAN_RATE,
    ExpenseIncrease,
    IncomeChange,
    Scenario,
    compare,
    credit_offer,
    load_user_history,
    simulate,
)


LOAN_TERMS = (12, 24, 36, 48, 60)

RISK_LABELS = {"LOW": "bajo", "MEDIUM": "medio", "HIGH": "alto"}
MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
YEARS_ES = {12: "un año", 24: "dos años", 36: "tres años", 48: "cuatro años", 60: "cinco años"}


@dataclass
class ToolResult:
    tool: str
    title: str
    summary: str
    data: pd.DataFrame | None = None
    sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sql: str | None = None
    metrics: dict = field(default_factory=dict)
    # Textos que una respuesta redactada por el modelo debe conservar (SQL).
    key_facts: list[str] = field(default_factory=list)


# ============================================================
# PLAIN-LANGUAGE HELPERS
# ============================================================

def mxn(value: float) -> str:
    """Pesos sin decimales: $12,345 (o −$12,345)."""
    sign = "−" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def signed_mxn(value: float) -> str:
    return ("+" if value >= 0 else "−") + f"${abs(value):,.0f}"


def month_name(year_month: str) -> str:
    year, month = year_month.split("-")
    return f"{MONTHS_ES[int(month) - 1]} de {year}"


def plural(n: int, singular: str, plural_form: str) -> str:
    return f"{n} {singular if n == 1 else plural_form}"


def join_es(items: list[str]) -> str:
    """'a', 'a y b', 'a, b y c'."""
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " y " + items[-1]


def term_text(months: int) -> str:
    return f"{YEARS_ES[months]} ({months} meses)" if months in YEARS_ES else f"{months} meses"


def red_numbers_text(prob: float) -> str:
    """Probabilidad de terminar en números rojos, en palabras."""
    if prob < 0.05:
        return "es muy poco probable que termines en números rojos"
    if prob < 0.25:
        return f"hay una probabilidad baja ({prob:.0%}) de que termines en números rojos"
    if prob < 0.5:
        return f"hay una probabilidad considerable ({prob:.0%}) de que termines en números rojos"
    return f"es probable ({prob:.0%}) que termines en números rojos"


def _fx_by_month(con) -> dict[str, float]:
    rows = con.execute(
        "SELECT year_month, average_exchange_rate FROM monthly_macro_context"
    ).fetchall()
    return {ym: float(fx) for ym, fx in rows}


# ============================================================
# 1. PERFIL Y RIESGO
# ============================================================

def perfil_riesgo(user_id: int, question: str = "") -> ToolResult:
    con = user_connection(user_id)

    kpi = con.execute(
        "SELECT * FROM user_financial_kpis ORDER BY year_month DESC LIMIT 1"
    ).df().iloc[0]
    feat = con.execute(
        "SELECT * FROM ml_user_features ORDER BY year_month DESC LIMIT 1"
    ).df().iloc[0]

    level = str(kpi["financial_risk_level"])
    risk = RISK_LABELS.get(level, level.lower())
    month = str(kpi["year_month"])
    negative = int(feat["negative_balance_months_6m"])
    anomalies = int(feat["anomaly_count_6m"])
    savings_rate = feat["savings_rate_3m"]
    debt_ratio = feat["debt_payment_ratio_3m"]

    opening = {
        "LOW": "Tus finanzas se ven sanas",
        "MEDIUM": "Tus finanzas están bien, aunque con algunas señales de cuidado",
        "HIGH": "Tus finanzas necesitan atención",
    }.get(level, "Este es el panorama de tus finanzas")

    summary = f"{opening}: tu nivel de riesgo es **{risk}** (con datos hasta {month_name(month)}). "
    if pd.notna(savings_rate):
        if savings_rate > 0:
            summary += f"En los últimos 3 meses lograste guardar {savings_rate * 100:.0f} de cada 100 pesos que te entraron. "
        else:
            summary += "En los últimos 3 meses gastaste más de lo que te entró. "
    if negative > 0:
        summary += f"En el último medio año hubo {plural(negative, 'mes', 'meses')} en los que gastaste más de lo que te entró"
        summary += f", y {plural(anomalies, 'mes', 'meses')} con un gasto mucho mayor de lo normal. " if anomalies else ". "
    elif anomalies:
        summary += f"En el último medio año hubo {plural(anomalies, 'mes', 'meses')} con un gasto mucho mayor de lo normal. "
    if pd.notna(debt_ratio) and debt_ratio > 0:
        summary += f"Lo que pagas de tarjeta equivale al {debt_ratio:.0%} de lo que te entra."

    data = pd.DataFrame([
        ("Datos hasta", month),
        ("Nivel de riesgo (clasificación por reglas)", risk),
        ("Meses en que gastaste más de lo que entró (últimos 6)", str(negative)),
        ("Meses con gasto fuera de lo normal (últimos 6)", str(anomalies)),
        ("Ahorro de los últimos 3 meses", f"{savings_rate:.0%}" if pd.notna(savings_rate) else "n/d"),
        ("Pagos de tarjeta / ingresos (3 meses)", f"{debt_ratio:.0%}" if pd.notna(debt_ratio) else "n/d"),
    ], columns=["Indicador", "Valor"])

    warnings = ["El nivel de riesgo es una clasificación general de tus finanzas, no una calificación de crédito."]
    if int(feat["income_outside_training_range"]) == 1:
        warnings.append(
            "Detalle técnico: el ingreso queda fuera del rango con el que se entrenó el modelo de riesgo; "
            "una probabilidad de impago sería poco confiable."
        )

    return ToolResult(
        tool="perfil_riesgo",
        title="Tu nivel de riesgo",
        summary=summary.strip(),
        data=data,
        sources=["Gold user_financial_kpis", "Gold ml_user_features"],
        warnings=warnings,
        metrics={
            "month": month,
            "risk": risk,
            "negative_months_6m": negative,
            "anomalies_6m": anomalies,
            "income_outside_training_range": int(feat["income_outside_training_range"]),
        },
    )


# ============================================================
# 2. CAMBIO EN LA CAPACIDAD DE AHORRO
# ============================================================

def cambio_ahorro(user_id: int, question: str = "") -> ToolResult:
    con = user_connection(user_id)
    fx = _fx_by_month(con)

    months = [r[0] for r in con.execute(
        "SELECT year_month FROM user_financial_kpis ORDER BY year_month"
    ).fetchall()]

    requested = re.search(r"(20\d{2})-(\d{2})", question or "")
    target = f"{requested.group(1)}-{requested.group(2)}" if requested else months[-1]
    if target not in months or months.index(target) == 0:
        target = months[-1]
    previous = months[months.index(target) - 1]

    kpis = con.execute(
        "SELECT year_month, consumer_spending, total_credits FROM user_financial_kpis "
        "WHERE year_month IN (?, ?)", [previous, target]
    ).df().set_index("year_month")

    spend_prev = kpis.loc[previous, "consumer_spending"] * fx[previous]
    spend_curr = kpis.loc[target, "consumer_spending"] * fx[target]
    cred_prev = kpis.loc[previous, "total_credits"] * fx[previous]
    cred_curr = kpis.loc[target, "total_credits"] * fx[target]
    delta = spend_curr - spend_prev
    pct = (delta / spend_prev * 100) if spend_prev else 0.0

    cats = con.execute(
        "SELECT year_month, categoria, total_amount FROM user_category_monthly "
        "WHERE year_month IN (?, ?)", [previous, target]
    ).df()
    cats["categoria"] = cats["categoria"].map(category_es)
    cats["mxn"] = cats["total_amount"] * cats["year_month"].map(fx)
    table = (
        cats.pivot_table(index="categoria", columns="year_month", values="mxn", aggfunc="sum")
        .reindex(columns=[previous, target])
        .fillna(0.0)
    )
    table["cambio"] = table[target] - table[previous]
    table = table.sort_values("cambio", ascending=False).reset_index()

    ups = table[table["cambio"] > 0].head(3)
    downs = table[table["cambio"] < 0].sort_values("cambio").head(3)
    up_text = join_es([f"{r.categoria} ({signed_mxn(r.cambio)})" for r in ups.itertuples()])
    down_text = join_es([f"{r.categoria} ({signed_mxn(r.cambio)})" for r in downs.itertuples()])

    prev_name, curr_name = month_name(previous), month_name(target)
    asked_drop = bool(re.search(r"baj|disminu|cay|cae|redujo", (question or "").lower()))

    if delta > 0:
        summary = (
            f"En {curr_name} gastaste {mxn(delta)} más que en {prev_name} ({pct:.0f}% más), "
            f"así que te quedó menos para ahorrar. "
        )
        if up_text:
            summary += f"Donde más subió tu gasto: {up_text}. "
        if down_text:
            summary += f"En cambio, gastaste menos en {down_text}. "
    elif delta < 0:
        opening = "Buenas noticias: en realidad tu capacidad de ahorro subió. " if asked_drop else ""
        summary = (
            f"{opening}En {curr_name} gastaste {mxn(abs(delta))} menos que en {prev_name} "
            f"({abs(pct):.0f}% menos), así que te quedó más para ahorrar. "
        )
        if down_text:
            summary += f"Donde más bajó tu gasto: {down_text}. "
        if up_text:
            summary += f"Gastaste un poco más en {up_text}. "
    else:
        summary = f"Tu gasto fue el mismo en {prev_name} y en {curr_name}, así que tu capacidad de ahorro no cambió. "

    summary += f"Lo que te entró ese mes fue {mxn(cred_curr)} (en {MONTHS_ES[int(previous[5:]) - 1]}, {mxn(cred_prev)})."

    data = table.rename(columns={
        "categoria": "Categoría",
        previous: f"{prev_name} (pesos)",
        target: f"{curr_name} (pesos)",
        "cambio": "Cambio (pesos)",
    }).round(0)

    return ToolResult(
        tool="cambio_ahorro",
        title=f"Tu ahorro: {prev_name} → {curr_name}",
        summary=summary,
        data=data,
        sources=["Gold user_financial_kpis", "Gold user_category_monthly", "Gold monthly_macro_context"],
        warnings=[
            "Tu capacidad de ahorro es tu salario menos lo que gastas; como tu salario no cambia, "
            "sube o baja según tu gasto.",
            "Detalle técnico: salario (MXN) y transacciones (USD inferido) vienen de fuentes con escalas "
            "distintas; por eso el cambio se explica a partir del gasto, convertido a pesos.",
        ],
        metrics={
            "previous": previous,
            "target": target,
            "spending_change_mxn": float(delta),
            "spending_change_pct": float(pct),
            "top_increase_category": str(ups.iloc[0]["categoria"]) if not ups.empty else None,
        },
    )


# ============================================================
# 3. SIMULACION DE ESCENARIOS
# ============================================================

_INCOME_WORDS = r"ingres|sueldo|salari|ganar|gano|empleo|trabajo"
_DOWN_WORDS = r"reduc|baj|disminu|recort|pierd|perd|menos|caer|cae"
_JOB_LOSS = r"(pierd|perd)\w*\s+(mi\s+|el\s+)?(empleo|trabajo)"


def _parse_scenario(question: str) -> tuple[Scenario, str, str | None, int]:
    """Devuelve (escenario, frase para 'Si ...', supuesto o None, horizonte)."""
    q = (question or "").lower()

    horizon_match = re.search(r"\b(12|24|36)\s*mes", q)
    years_match = re.search(r"\b(1|2|3|un|dos|tres)\s*años?", q)
    horizon = 12
    if horizon_match:
        horizon = int(horizon_match.group(1))
    elif years_match:
        horizon = {"1": 12, "un": 12, "2": 24, "dos": 24, "3": 36, "tres": 36}[years_match.group(1)]

    if re.search(_JOB_LOSS, q):
        months_match = re.search(r"(\d+)\s*mes(?:es)?\s*(sin|de)", q)
        months = int(months_match.group(1)) if months_match else 3
        assumption = None if months_match else "No me dijiste cuánto tiempo, así que supuse 3 meses sin ingresos."
        return (
            Scenario(name=f"Sin ingresos {months} meses", income=IncomeChange(months_without_income=months)),
            f"pierdes tu empleo y pasas {plural(months, 'mes', 'meses')} sin ingresos",
            assumption,
            horizon,
        )

    pct_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(%|por\s*ciento)", q)
    pct = float(pct_match.group(1).replace(",", ".")) if pct_match else 10.0
    down = bool(re.search(_DOWN_WORDS, q))
    signed = -pct if down else pct
    is_income = bool(re.search(_INCOME_WORDS, q))
    subject = "ingresos" if is_income else "gastos"
    verb = "bajan" if down else "suben"

    assumption = None if pct_match else f"No me dijiste cuánto, así que supuse que tus {subject} {verb} {pct:.0f}%."

    if is_income:
        scenario = Scenario(name=f"Ingresos {signed:+.0f}%", income=IncomeChange(pct_change=signed))
    else:
        scenario = Scenario(name=f"Gastos {signed:+.0f}%", expenses=ExpenseIncrease(pct=signed))

    return scenario, f"tus {subject} {verb} {pct:.0f}%", assumption, horizon


def simular_escenario(user_id: int, question: str = "") -> ToolResult:
    scenario, description, assumption, horizon = _parse_scenario(question)
    history = load_user_history(user_id)
    baseline, result = compare(history, scenario, horizon)
    b, s = baseline.summary(), result.summary()
    diff = s["final_p50"] - b["final_p50"]
    period = YEARS_ES.get(horizon, f"{horizon} meses")

    summary = f"{assumption} " if assumption else ""
    if s["final_p50"] >= 0:
        summary += (
            f"Si {description}, en {period} podrías juntar unos {mxn(s['final_p50'])}, "
            f"en vez de {mxn(b['final_p50'])} si sigues igual: "
            f"unos {mxn(abs(diff))} {'menos' if diff < 0 else 'más'}. "
        )
    else:
        summary += (
            f"Si {description}, en {period} lo más probable es que te falten unos {mxn(abs(s['final_p50']))}, "
            f"cuando si sigues igual podrías juntar {mxn(b['final_p50'])}. "
        )

    if s["prob_final_negative"] - b["prob_final_negative"] >= 0.05:
        summary += (
            f"La probabilidad de terminar en números rojos subiría de {b['prob_final_negative']:.0%} "
            f"a {s['prob_final_negative']:.0%}. "
        )
    else:
        prefix = "Aun así, " if diff < 0 else ""
        text = red_numbers_text(s["prob_final_negative"])
        summary += f"{prefix}{text if prefix else text[0].upper() + text[1:]}. "

    summary += (
        f"Cada mes te quedarían, en promedio, unos {mxn(s['expected_monthly_net'])} "
        f"en lugar de {mxn(b['expected_monthly_net'])}."
    )

    data = pd.DataFrame([
        ("Lo más probable al final (mediana)", mxn(b["final_p50"]), mxn(s["final_p50"])),
        ("Si te va mal (percentil 5)", mxn(b["final_p5"]), mxn(s["final_p5"])),
        ("Si te va bien (percentil 95)", mxn(b["final_p95"]), mxn(s["final_p95"])),
        ("Probabilidad de números rojos", f"{b['prob_final_negative']:.0%}", f"{s['prob_final_negative']:.0%}"),
        ("Te queda al mes (promedio)", mxn(b["expected_monthly_net"]), mxn(s["expected_monthly_net"])),
    ], columns=["", "Si sigues igual", "Con el cambio"])

    return ToolResult(
        tool="simular_escenario",
        title=f"¿Qué pasaría si {description}?",
        summary=summary,
        data=data,
        sources=["Gold ml_user_features", "Simulador Monte Carlo (Semana 19), 5,000 simulaciones"],
        warnings=[
            "Es una estimación con base en tus movimientos de 2018 a 2019, no un pronóstico exacto.",
            "Detalle técnico: cambio acumulado desde 0 (no es un saldo bancario); transacciones "
            "convertidas a pesos (unidad USD inferida).",
        ],
        metrics={"baseline_final_p50": b["final_p50"], "scenario_final_p50": s["final_p50"]},
    )


# ============================================================
# 4. META DE AHORRO
# ============================================================

def _parse_amount(question: str) -> float | None:
    """Monto en pesos: '100 mil', '100,000', '100000', '1.5 millones'."""
    q = (question or "").lower()
    match = re.search(r"(\d+(?:[.,]\d+)*)\s*(mil\b|k\b|millon(?:es)?|millón)?", q)
    if not match:
        return None
    number, unit = match.group(1), match.group(2)

    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", number):
        value = float(re.sub(r"[.,]", "", number))      # 100,000 o 100.000
    else:
        value = float(number.replace(",", "."))          # 100 o 1.5 / 1,5

    if unit in ("mil", "k"):
        value *= 1_000
    elif unit:
        value *= 1_000_000
    return value


def meta_ahorro(user_id: int, question: str = "") -> ToolResult:
    target = _parse_amount(question)
    if not target or target <= 0:
        return ToolResult(
            tool="meta_ahorro",
            title="Tu meta de ahorro",
            summary="¿De cuánto es tu meta? Dime el monto, por ejemplo: «¿Cuándo junto 100 mil pesos?».",
        )

    horizon = max(ALLOWED_HORIZONS)
    history = load_user_history(user_id)
    baseline = simulate(history, Scenario(), horizon)
    cumulative = baseline.cumulative

    reached = cumulative >= target
    first_month = np.where(reached.any(axis=1), reached.argmax(axis=1) + 1, np.nan)
    probs = {h: float(np.mean(reached[:, :h].any(axis=1))) for h in ALLOWED_HORIZONS}
    median_month = int(np.nanmedian(first_month)) if probs[horizon] >= 0.5 else None
    expected_monthly = float(baseline.monthly_net.mean())

    if expected_monthly <= 0:
        summary = (
            f"Ahora mismo, en promedio, gastas más de lo que te entra, así que con tu ritmo actual "
            f"sería difícil juntar {mxn(target)}. "
        )
    elif median_month is not None:
        summary = (
            f"A tu ritmo actual (te quedan unos {mxn(expected_monthly)} al mes), lo más probable es que "
            f"juntes {mxn(target)} en unos {plural(median_month, 'mes', 'meses')}. "
        )
    else:
        summary = (
            f"A tu ritmo actual (te quedan unos {mxn(expected_monthly)} al mes), sería difícil juntar "
            f"{mxn(target)} en los próximos tres años. "
        )
    summary += (
        f"La probabilidad de lograrlo es de {probs[12]:.0%} en un año, "
        f"{probs[24]:.0%} en dos años y {probs[36]:.0%} en tres años."
    )

    data = pd.DataFrame(
        [(YEARS_ES[h], f"{probs[h]:.0%}") for h in ALLOWED_HORIZONS],
        columns=["Plazo", "Probabilidad de lograrlo"],
    )

    return ToolResult(
        tool="meta_ahorro",
        title=f"Tu meta de {mxn(target)}",
        summary=summary,
        data=data,
        sources=["Gold ml_user_features", "Simulador Monte Carlo (Semana 19), 5,000 simulaciones"],
        warnings=[
            "Supone que sigues ganando y gastando como en tu historial de 2018 a 2019.",
            "Detalle técnico: «lo más probable» es la mediana del primer mes en que se alcanza la meta.",
        ],
        metrics={"target": target, "median_month": median_month, "probabilities": probs},
    )


# ============================================================
# 5. OFERTA DE CREDITO
# ============================================================

def oferta_credito(user_id: int, question: str = "") -> ToolResult:
    q = (question or "").lower()
    notes = []

    term = 36
    months_match = re.search(r"(\d+)\s*mes", q)
    years_match = re.search(r"(\d+)\s*año", q)
    if months_match and int(months_match.group(1)) in LOAN_TERMS:
        term = int(months_match.group(1))
    elif years_match and int(years_match.group(1)) * 12 in LOAN_TERMS:
        term = int(years_match.group(1)) * 12
    elif months_match or years_match:
        notes.append("Ese plazo no está disponible (de 1 a 5 años), así que lo calculé a tres años.")

    rate_match = re.search(r"(\d+(?:[.,]\d+)?)\s*%", q)
    rate = float(rate_match.group(1).replace(",", ".")) if rate_match else DEFAULT_PERSONAL_LOAN_RATE

    history = load_user_history(user_id)
    offer = credit_offer(history, term, rate)
    details = []

    summary = " ".join(notes) + (" " if notes else "")
    if not offer["eligible"]:
        if offer["payment_limit_by_stress_mxn"] <= 0:
            summary += (
                "Por ahora no te podemos ofrecer un crédito: en tu historial hay meses en los que gastaste "
                "bastante más de lo que te entró, y una mensualidad extra podría ponerte en aprietos. "
                "Si tus gastos se estabilizan, vuelve a consultarlo."
            )
        else:
            summary += (
                "Por ahora la mensualidad que podrías pagar con tranquilidad es muy pequeña para un crédito."
            )
    else:
        reason = (
            f"para que la mensualidad no pase del {offer['max_payment_share']:.0%} de lo que normalmente te entra al mes"
            if offer["binding_rule"] == "capacidad de pago"
            else "para que, aun en meses difíciles, sea muy poco probable que te quedes sin dinero"
        )
        summary += (
            f"Según tu historial, te podríamos prestar hasta **{mxn(offer['amount_mxn'])}** a "
            f"{term_text(term)}, pagando **{mxn(offer['monthly_payment_mxn'])} al mes** "
            f"(tasa de {rate:.0f}% anual). Calculamos este monto {reason}."
        )
        risk = offer["risk"] or {}
        p_default = risk.get("probability_of_default")
        if p_default is not None:
            details.append(f"Detalle técnico: el modelo de riesgo estima una probabilidad de impago de {p_default:.1%} (ilustrativa).")
        if risk.get("outside_training_range"):
            details.append(
                "Detalle técnico: esa probabilidad es poco confiable porque los datos quedan fuera del rango "
                "con el que se entrenó el modelo (" + ", ".join(risk["outside_training_range"]) + ")."
            )

    data = pd.DataFrame([
        ("Lo que normalmente te entra al mes", mxn(offer["typical_monthly_income_mxn"])),
        (f"Mensualidad máxima ({offer['max_payment_share']:.0%} de tu ingreso)", mxn(offer["payment_limit_by_income_mxn"])),
        (f"Mensualidad máxima en meses difíciles (≤{offer['max_prob_negative']:.0%} de riesgo)", mxn(offer["payment_limit_by_stress_mxn"])),
        ("Monto que te podríamos prestar", mxn(offer["amount_mxn"]) if offer["eligible"] else "No disponible por ahora"),
    ], columns=["Concepto", "Valor"])

    return ToolResult(
        tool="oferta_credito",
        title=f"Crédito a {term_text(term)}",
        summary=summary.strip(),
        data=data,
        sources=["Gold ml_user_features", "Simulador Monte Carlo (Semana 19)", "Modelo de riesgo reducido (Semana 18)"],
        warnings=["Es una propuesta ilustrativa, no una oferta real ni asesoría financiera."] + details,
        metrics={
            "eligible": bool(offer["eligible"]),
            "amount_mxn": float(offer["amount_mxn"]),
            "monthly_payment_mxn": float(offer["monthly_payment_mxn"]),
            "term": term,
            "rate": rate,
        },
    )


# ============================================================
# 6. CONSULTA LIBRE (TEXT-TO-SQL RESTRINGIDO)
# ============================================================

class SQLQuery(BaseModel):
    sql: str = Field(description="Una sola consulta SELECT de DuckDB")


def _sql_prompt(error: str | None = None) -> str:
    prompt = (
        "Genera UNA consulta SQL de DuckDB (solo SELECT) que responda la pregunta.\n"
        "Vistas disponibles (ya contienen solo los datos del usuario; montos en pesos):\n"
        "- gastos_por_categoria(mes, categoria, monto_pesos, num_compras)\n"
        "- resumen_mensual(mes, ingresos_pesos, gasto_consumo_pesos, pagos_tarjeta_pesos, "
        "gastos_totales_pesos, num_movimientos, categoria_principal)\n"
        "Reglas: mes es texto 'YYYY-MM' (para un año usa mes LIKE '2019-%'). "
        f"Las categorías (columna categoria) son: {', '.join(CATEGORY_ES.values())}. "
        "Usa el nombre exacto de una de esas categorías. Devuelve columnas con nombres claros."
    )
    if error:
        prompt += f"\nLa consulta anterior falló con este error, corrígela: {error}"
    return prompt


def consulta_sql(user_id: int, question: str, llm) -> ToolResult:
    con = user_connection(user_id)
    generator = llm.with_structured_output(SQLQuery)
    error, sql, df = None, None, None

    for _ in range(2):  # un intento y una corrección
        sql = generator.invoke([("system", _sql_prompt(error)), ("human", question)]).sql
        try:
            df = run_readonly_query(con, sql)
            break
        except (SQLValidationError, Exception) as exc:  # noqa: BLE001 - se reporta al modelo
            error = str(exc)[:300]
            df = None

    if df is None:
        return ToolResult(
            tool="consulta_sql",
            title="Consulta a tus datos",
            summary=(
                "No logré encontrar esa información. ¿Puedes decirlo de otra forma? "
                "Por ejemplo: «¿Cuánto gasté en supermercado en 2019?»."
            ),
            sources=["Gold (DuckDB, solo lectura)"],
            warnings=[f"Detalle técnico: {error}"],
            sql=sql,
        )

    preview = df.head(15).to_string(index=False) if not df.empty else "(sin resultados)"
    return ToolResult(
        tool="consulta_sql",
        title="Consulta a tus datos",
        summary=f"Resultado de la consulta ({len(df)} filas):\n{preview}",
        data=df,
        sources=["Gold, vistas en pesos (DuckDB, solo lectura)"],
        warnings=["Montos en pesos, convertidos con el tipo de cambio de cada mes."],
        sql=sql,
    )
