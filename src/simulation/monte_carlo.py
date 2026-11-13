"""
Motor de simulacion financiera Monte Carlo (Semana 19).

Proyecta el cambio acumulado en el flujo de efectivo de un usuario a 12,
24 o 36 meses bajo escenarios basados en reglas, y estima la P(impago)
de un credito con el modelo reducido (Semana 18).

Diseno:
- Metodo: bootstrap de meses historicos. Cada mes simulado toma al azar
  un mes real del propio usuario (par creditos/debitos). Conserva la
  asimetria y los picos sin suponer una distribucion. Se justifica por
  la autocorrelacion casi nula del flujo neto mensual.
- Moneda: todo en MXN. Los creditos/debitos historicos (unidad inferida:
  USD) se convierten con el tipo de cambio de su mes. Los montos de los
  escenarios se capturan en MXN. Para el modelo de riesgo, el monto del
  credito se convierte a USD con el tipo de cambio del ultimo mes del
  usuario.
- Linea base y escenario usan los mismos meses sorteados (numeros
  aleatorios comunes): la diferencia refleja solo el escenario.
- No se conoce el saldo real de la cuenta: se simula el cambio acumulado
  desde 0, no un saldo bancario.

Este modulo no depende de Streamlit; lo usan el dashboard y, en la
Semana 20, el asistente de IA.

Alcance: escenarios ilustrativos con datos simulados. No es asesoria
financiera.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from deltalake import DeltaTable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ML_USER_FEATURES_PATH = PROJECT_ROOT / "data" / "gold" / "ml_user_features"
LOAN_ML_PATH = PROJECT_ROOT / "data" / "gold" / "loan_ml_dataset"
REDUCED_MODEL_PATH = PROJECT_ROOT / "models" / "loan_risk_reduced.joblib"

ALLOWED_HORIZONS = (12, 24, 36)
DEFAULT_N_SIMULATIONS = 5000
DEFAULT_SEED = 42
LOAN_PURPOSES = ("Auto", "Business", "Education", "Home", "Other")

# Reglas de credito responsable (ajustables).
# Capacidad de pago: la cuota no debe superar el 30% del ingreso
# (recomendacion habitual en Mexico, p. ej. CONDUSEF).
DEFAULT_MAX_PAYMENT_SHARE = 0.30
# Estres Monte Carlo: probabilidad maxima de terminar el plazo con flujo
# acumulado negativo.
DEFAULT_MAX_PROB_NEGATIVE = 0.10
# Monto minimo para que una oferta tenga sentido (MXN).
MIN_OFFER_MXN = 10_000

# Valores de referencia aproximados (ajustables en el simulador).
DEFAULT_PERSONAL_LOAN_RATE = 15.0
DEFAULT_MORTGAGE_RATE = 10.5
DEFAULT_MORTGAGE_TERM_YEARS = 20
DEFAULT_CLOSING_COSTS_PCT = 6.0

# Plazo maximo visto por el modelo de riesgo (meses).
MODEL_MAX_TERM_MONTHS = 60


# ============================================================
# SCENARIO DEFINITIONS (amounts in MXN)
# ============================================================

@dataclass
class LoanScenario:
    """Contratar un credito."""
    amount_mxn: float
    term_months: int
    annual_rate_pct: float
    purpose: str = "Other"


@dataclass
class IncomeChange:
    """Cambio de empleo o de ingreso."""
    pct_change: float = 0.0          # ej. -20 = ingresos 20% menores
    months_without_income: int = 0   # meses iniciales sin ingresos


@dataclass
class ExpenseIncrease:
    """Aumento de gastos."""
    pct: float = 0.0                 # ej. 15 = gastos 15% mayores


@dataclass
class CarPurchase:
    """Comprar un auto nuevo: enganche + credito Auto + gasto mensual."""
    price_mxn: float
    down_payment_pct: float
    term_months: int
    annual_rate_pct: float
    monthly_car_cost_mxn: float = 0.0  # seguro, mantenimiento, gasolina


@dataclass
class HousingChange:
    """Cambiarse de vivienda (renta)."""
    current_rent_mxn: float
    new_rent_mxn: float
    one_time_costs_mxn: float = 0.0    # mudanza, deposito


@dataclass
class MortgageFromRent:
    """
    Comprar vivienda pagando de hipoteca lo mismo que hoy paga de renta.
    Supuesto: la renta actual ya esta incluida en los gastos historicos,
    por lo que el flujo mensual no cambia; solo hay una salida unica en
    el mes 1 (enganche + gastos de escrituracion).
    """
    current_rent_mxn: float
    down_payment_mxn: float = 0.0
    annual_rate_pct: float = DEFAULT_MORTGAGE_RATE
    term_years: int = DEFAULT_MORTGAGE_TERM_YEARS
    closing_costs_pct: float = DEFAULT_CLOSING_COSTS_PCT


@dataclass
class Scenario:
    """Combinacion de componentes. Sin componentes = linea base."""
    name: str = "Linea base"
    loan: LoanScenario | None = None
    income: IncomeChange | None = None
    expenses: ExpenseIncrease | None = None
    car: CarPurchase | None = None
    housing: HousingChange | None = None
    mortgage: MortgageFromRent | None = None


# ============================================================
# DATA
# ============================================================

@dataclass
class UserHistory:
    user_id: int
    months: list[str]
    credits_mxn: np.ndarray
    debits_mxn: np.ndarray
    last_month: str
    last_exchange_rate: float
    age: int
    marital_status_model: str
    has_dependents: int
    annual_income_usd: float
    salary_monthly_mxn: float

    @property
    def net_flow_mxn(self) -> np.ndarray:
        return self.credits_mxn - self.debits_mxn


def available_users(path: Path = ML_USER_FEATURES_PATH) -> list[int]:
    """Usuarios con historial en el feature store."""
    df = DeltaTable(str(path)).to_pandas(columns=["user_id"])
    return sorted(int(u) for u in df["user_id"].unique())


def load_user_history(user_id: int, path: Path = ML_USER_FEATURES_PATH) -> UserHistory:
    """Historial mensual del usuario convertido a MXN con el tipo de cambio de cada mes."""
    columns = [
        "user_id", "year_month", "total_credits", "total_debits",
        "average_exchange_rate", "age", "marital_status_model",
        "has_dependents", "annual_income_usd", "salary_monthly",
    ]
    df = DeltaTable(str(path)).to_pandas(columns=columns)
    df = df[df["user_id"] == user_id].sort_values("year_month")

    if df.empty:
        raise ValueError(f"User {user_id} has no history in ml_user_features")
    if df["average_exchange_rate"].isna().any():
        raise ValueError(f"User {user_id} has months without exchange rate")

    last = df.iloc[-1]

    return UserHistory(
        user_id=int(user_id),
        months=df["year_month"].tolist(),
        credits_mxn=(df["total_credits"] * df["average_exchange_rate"]).to_numpy(float),
        debits_mxn=(df["total_debits"] * df["average_exchange_rate"]).to_numpy(float),
        last_month=str(last["year_month"]),
        last_exchange_rate=float(last["average_exchange_rate"]),
        age=int(last["age"]),
        marital_status_model=str(last["marital_status_model"]),
        has_dependents=int(last["has_dependents"]),
        annual_income_usd=float(last["annual_income_usd"]),
        salary_monthly_mxn=float(last["salary_monthly"]),
    )


@lru_cache(maxsize=1)
def training_ranges(path: Path = LOAN_ML_PATH) -> dict:
    """Rangos del split train de loan_ml_dataset (lo que el modelo vio)."""
    df = DeltaTable(str(path)).to_pandas(
        columns=["split", "income", "loan_amount", "loan_term", "interest_rate"]
    )
    train = df[df["split"] == "train"]
    return {
        "income": (float(train["income"].min()), float(train["income"].max())),
        "loan_amount": (float(train["loan_amount"].min()), float(train["loan_amount"].max())),
        "loan_term": sorted(int(t) for t in train["loan_term"].unique()),
        "interest_rate": (float(train["interest_rate"].min()), float(train["interest_rate"].max())),
    }


@lru_cache(maxsize=1)
def _load_reduced_model(path: Path = REDUCED_MODEL_PATH):
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run src/ml/train_loan_model.py and "
            "src/ml/evaluate_loan_model.py first."
        )
    return joblib.load(path)


# ============================================================
# CREDIT CALCULATIONS
# ============================================================

def monthly_payment(amount: float, annual_rate_pct: float, term_months: int) -> float:
    """Cuota fija (amortizacion francesa); misma formula que Gold loan_ml_dataset."""
    if amount <= 0:
        return 0.0
    r = annual_rate_pct / 1200.0
    if r == 0:
        return amount / term_months
    return amount * r / (1.0 - (1.0 + r) ** (-term_months))


def max_principal(payment: float, annual_rate_pct: float, term_months: int) -> float:
    """Monto maximo financiable con una cuota dada (amortizacion invertida)."""
    if payment <= 0:
        return 0.0
    r = annual_rate_pct / 1200.0
    if r == 0:
        return payment * term_months
    return payment * (1.0 - (1.0 + r) ** (-term_months)) / r


def remaining_balance(principal: float, annual_rate_pct: float, term_months: int, months_paid: int) -> float:
    """Saldo insoluto despues de months_paid cuotas."""
    if principal <= 0:
        return 0.0
    k = min(max(months_paid, 0), term_months)
    r = annual_rate_pct / 1200.0
    if r == 0:
        return principal * (1 - k / term_months)
    payment = monthly_payment(principal, annual_rate_pct, term_months)
    return principal * (1 + r) ** k - payment * ((1 + r) ** k - 1) / r


def estimate_default_probability(
    history: UserHistory,
    amount_mxn: float,
    term_months: int,
    annual_rate_pct: float,
    purpose: str,
) -> dict:
    """
    P(impago) con el modelo reducido. Escenario ilustrativo: el modelo se
    entreno con prestamos sin relacion con los usuarios del proyecto.
    """
    if purpose not in LOAN_PURPOSES:
        raise ValueError(f"purpose must be one of {LOAN_PURPOSES}")

    fx = history.last_exchange_rate

    # Plazos mayores a los vistos en entrenamiento (p. ej. hipotecas):
    # no se calcula una probabilidad poco confiable.
    if term_months > MODEL_MAX_TERM_MONTHS:
        return {
            "probability_of_default": None,
            "amount_usd": amount_mxn / fx,
            "exchange_rate_used": fx,
            "exchange_rate_month": history.last_month,
            "annual_income_usd": history.annual_income_usd,
            "outside_training_range": ["loan_term"],
            "reliable": False,
            "note": (
                f"Plazo de {term_months} meses fuera del rango del modelo "
                f"(máximo {MODEL_MAX_TERM_MONTHS}). P(impago) no disponible."
            ),
        }
    amount_usd = amount_mxn / fx
    income_usd = history.annual_income_usd
    payment_usd = monthly_payment(amount_usd, annual_rate_pct, term_months)

    features = pd.DataFrame([{
        "age": history.age,
        "income": income_usd,
        "has_dependents": history.has_dependents,
        "loan_amount": amount_usd,
        "loan_term": term_months,
        "interest_rate": annual_rate_pct,
        "loan_to_income_ratio": amount_usd / income_usd,
        "estimated_monthly_payment": payment_usd,
        "payment_to_income_ratio": payment_usd / (income_usd / 12.0),
        "marital_status": history.marital_status_model,
        "loan_purpose": purpose,
    }])

    model = _load_reduced_model()
    probability = float(model.predict_proba(features)[:, 1][0])

    ranges = training_ranges()
    outside = []
    if not ranges["income"][0] <= income_usd <= ranges["income"][1]:
        outside.append("income")
    if not ranges["loan_amount"][0] <= amount_usd <= ranges["loan_amount"][1]:
        outside.append("loan_amount")
    if term_months not in ranges["loan_term"]:
        outside.append("loan_term")
    if not ranges["interest_rate"][0] <= annual_rate_pct <= ranges["interest_rate"][1]:
        outside.append("interest_rate")

    return {
        "probability_of_default": probability,
        "amount_usd": amount_usd,
        "exchange_rate_used": fx,
        "exchange_rate_month": history.last_month,
        "annual_income_usd": income_usd,
        "outside_training_range": outside,
        "reliable": not outside,
    }


# ============================================================
# SIMULATION
# ============================================================

@dataclass
class SimulationResult:
    scenario_name: str
    horizon: int
    monthly_net: np.ndarray        # (n_simulations, horizon), MXN
    cumulative: np.ndarray         # (n_simulations, horizon), MXN
    loans: list[dict] = field(default_factory=list)
    mortgage: dict | None = None
    warnings: list[str] = field(default_factory=list)

    def percentiles(self, q=(5, 50, 95)) -> pd.DataFrame:
        """Bandas de confianza del cambio acumulado por mes."""
        values = np.percentile(self.cumulative, q, axis=0)
        frame = pd.DataFrame(values.T, columns=[f"p{p}" for p in q])
        frame.insert(0, "month", np.arange(1, self.horizon + 1))
        return frame

    def summary(self) -> dict:
        final = self.cumulative[:, -1]
        return {
            "scenario": self.scenario_name,
            "horizon_months": self.horizon,
            "final_p5": float(np.percentile(final, 5)),
            "final_p50": float(np.percentile(final, 50)),
            "final_p95": float(np.percentile(final, 95)),
            "prob_final_negative": float(np.mean(final < 0)),
            "prob_any_month_negative": float(np.mean((self.cumulative < 0).any(axis=1))),
            "expected_monthly_net": float(self.monthly_net.mean()),
        }


def _validate(horizon: int, n_simulations: int) -> None:
    if horizon not in ALLOWED_HORIZONS:
        raise ValueError(f"horizon must be one of {ALLOWED_HORIZONS}")
    if n_simulations <= 0:
        raise ValueError("n_simulations must be positive")


def _loan_component(history, amount, term, rate, purpose, horizon, label) -> tuple[np.ndarray, dict]:
    """Cuota mensual durante el plazo (dentro del horizonte) y su P(impago)."""
    payment = monthly_payment(amount, rate, term)
    schedule = np.zeros(horizon)
    schedule[: min(term, horizon)] = payment

    risk = estimate_default_probability(history, amount, term, rate, purpose)
    median_net = float(np.median(history.net_flow_mxn))

    info = {
        "label": label,
        "amount_mxn": amount,
        "term_months": term,
        "annual_rate_pct": rate,
        "purpose": purpose,
        "monthly_payment_mxn": payment,
        "payment_to_median_net_flow": (payment / median_net) if median_net > 0 else None,
        **risk,
    }
    return schedule, info


def _rent_warning(history: UserHistory, rent_mxn: float) -> str | None:
    """
    Los escenarios de vivienda suponen que la renta actual ya esta incluida
    en los gastos historicos. Si la renta supera los debitos mensuales
    tipicos, ese supuesto no se cumple.
    """
    typical_debits = float(np.median(history.debits_mxn))
    if rent_mxn > typical_debits:
        return (
            f"La renta indicada ({rent_mxn:,.0f} MXN) es mayor que tus gastos "
            f"mensuales típicos registrados ({typical_debits:,.0f} MXN); "
            "la simulación podría subestimar el impacto."
        )
    return None


def _sample_months(history: UserHistory, horizon: int, n_simulations: int, seed: int):
    """Bootstrap: indices de meses historicos sorteados con reemplazo."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(history.months), size=(n_simulations, horizon))
    return history.credits_mxn[idx].copy(), history.debits_mxn[idx].copy()


def _mortgage_component(history: UserHistory, mortgage: MortgageFromRent, horizon: int) -> dict:
    """Hipoteca con cuota igual a la renta: monto, precio y patrimonio mes a mes."""
    term_months = mortgage.term_years * 12
    payment = mortgage.current_rent_mxn
    principal = max_principal(payment, mortgage.annual_rate_pct, term_months)
    price = principal + mortgage.down_payment_mxn
    closing_costs = price * mortgage.closing_costs_pct / 100.0

    months = np.arange(1, horizon + 1)
    equity = np.array([
        mortgage.down_payment_mxn
        + principal
        - remaining_balance(principal, mortgage.annual_rate_pct, term_months, m)
        for m in months
    ])

    risk = estimate_default_probability(
        history, principal, term_months, mortgage.annual_rate_pct, "Home"
    )

    return {
        "monthly_payment_mxn": payment,
        "term_months": term_months,
        "annual_rate_pct": mortgage.annual_rate_pct,
        "loan_amount_mxn": principal,
        "home_price_mxn": price,
        "down_payment_mxn": mortgage.down_payment_mxn,
        "closing_costs_mxn": closing_costs,
        "upfront_cost_mxn": mortgage.down_payment_mxn + closing_costs,
        # Patrimonio en la vivienda (enganche + capital amortizado), por mes.
        "equity_by_month_mxn": equity.tolist(),
        # Rentando, el mismo pago no genera patrimonio.
        "rent_paid_by_month_mxn": (payment * months).tolist(),
        "total_interest_over_term_mxn": payment * term_months - principal,
        **{f"risk_{k}": v for k, v in risk.items()},
    }


def simulate(
    history: UserHistory,
    scenario: Scenario,
    horizon: int = 12,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
    seed: int = DEFAULT_SEED,
) -> SimulationResult:
    """Simula un escenario. Con la misma semilla, los meses sorteados son identicos."""
    _validate(horizon, n_simulations)

    credits, debits = _sample_months(history, horizon, n_simulations, seed)
    extra = np.zeros(horizon)  # salidas adicionales por mes (MXN)
    loans = []

    if scenario.income is not None:
        credits *= 1.0 + scenario.income.pct_change / 100.0
        gap = min(max(scenario.income.months_without_income, 0), horizon)
        credits[:, :gap] = 0.0

    if scenario.expenses is not None:
        debits *= 1.0 + scenario.expenses.pct / 100.0

    if scenario.loan is not None:
        loan = scenario.loan
        schedule, info = _loan_component(
            history, loan.amount_mxn, loan.term_months,
            loan.annual_rate_pct, loan.purpose, horizon, "Credito",
        )
        extra += schedule
        loans.append(info)

    if scenario.car is not None:
        car = scenario.car
        down_payment = car.price_mxn * car.down_payment_pct / 100.0
        financed = car.price_mxn - down_payment
        extra[0] += down_payment
        extra += car.monthly_car_cost_mxn
        if financed > 0:
            schedule, info = _loan_component(
                history, financed, car.term_months,
                car.annual_rate_pct, "Auto", horizon, "Credito auto",
            )
            extra += schedule
            info["down_payment_mxn"] = down_payment
            loans.append(info)

    warnings = []

    if scenario.housing is not None:
        housing = scenario.housing
        extra += housing.new_rent_mxn - housing.current_rent_mxn
        extra[0] += housing.one_time_costs_mxn
        warning = _rent_warning(history, housing.current_rent_mxn)
        if warning:
            warnings.append(warning)

    mortgage_info = None
    if scenario.mortgage is not None:
        # La cuota sustituye a la renta (flujo mensual igual);
        # solo cambia el mes 1 por enganche y escrituracion.
        mortgage_info = _mortgage_component(history, scenario.mortgage, horizon)
        extra[0] += mortgage_info["upfront_cost_mxn"]
        warning = _rent_warning(history, scenario.mortgage.current_rent_mxn)
        if warning:
            warnings.append(warning)

    monthly_net = credits - debits - extra
    cumulative = np.cumsum(monthly_net, axis=1)

    return SimulationResult(
        scenario_name=scenario.name,
        horizon=horizon,
        monthly_net=monthly_net,
        cumulative=cumulative,
        loans=loans,
        mortgage=mortgage_info,
        warnings=warnings,
    )


# ============================================================
# CREDIT OFFER
# ============================================================

def credit_offer(
    history: UserHistory,
    term_months: int = 36,
    annual_rate_pct: float = DEFAULT_PERSONAL_LOAN_RATE,
    purpose: str = "Other",
    max_payment_share: float = DEFAULT_MAX_PAYMENT_SHARE,
    max_prob_negative: float = DEFAULT_MAX_PROB_NEGATIVE,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
    seed: int = DEFAULT_SEED,
) -> dict:
    """
    Credito maximo que se puede ofrecer de forma responsable.

    Dos reglas; se toma la cuota mas restrictiva:
    1. Capacidad de pago: cuota <= max_payment_share x ingreso mensual
       tipico (mediana de creditos mensuales, MXN).
    2. Estres Monte Carlo: con la cuota, P(flujo acumulado al final del
       plazo < 0) <= max_prob_negative. Como la cuota es constante, la
       cuota maxima es el cuantil max_prob_negative del flujo acumulado
       de la linea base al final del plazo, dividido entre el plazo.
    """
    if not 1 <= term_months <= MODEL_MAX_TERM_MONTHS:
        raise ValueError(f"term_months must be between 1 and {MODEL_MAX_TERM_MONTHS}")

    typical_income = float(np.median(history.credits_mxn))
    payment_by_income = max_payment_share * typical_income

    credits, debits = _sample_months(history, term_months, n_simulations, seed)
    baseline_final = (credits - debits).sum(axis=1)
    stress_quantile = float(np.quantile(baseline_final, max_prob_negative))
    payment_by_stress = max(stress_quantile / term_months, 0.0)

    payment = min(payment_by_income, payment_by_stress)
    binding_rule = "capacidad de pago" if payment_by_income <= payment_by_stress else "estrés Monte Carlo"
    amount = max_principal(payment, annual_rate_pct, term_months)

    offer = {
        "eligible": amount >= MIN_OFFER_MXN,
        "amount_mxn": amount,
        "monthly_payment_mxn": payment,
        "term_months": term_months,
        "annual_rate_pct": annual_rate_pct,
        "purpose": purpose,
        "binding_rule": binding_rule,
        "typical_monthly_income_mxn": typical_income,
        "payment_limit_by_income_mxn": payment_by_income,
        "payment_limit_by_stress_mxn": payment_by_stress,
        "max_payment_share": max_payment_share,
        "max_prob_negative": max_prob_negative,
        "prob_final_negative_with_offer": float(np.mean(baseline_final - payment * term_months < 0)),
    }

    if offer["eligible"]:
        offer["risk"] = estimate_default_probability(
            history, amount, term_months, annual_rate_pct, purpose
        )
    else:
        offer["risk"] = None
        offer["reason"] = (
            f"El monto máximo calculado ({amount:,.0f} MXN) es menor al mínimo "
            f"de {MIN_OFFER_MXN:,.0f} MXN para una oferta."
        )

    return offer


def compare(
    history: UserHistory,
    scenario: Scenario,
    horizon: int = 12,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
    seed: int = DEFAULT_SEED,
) -> tuple[SimulationResult, SimulationResult]:
    """Linea base y escenario con los mismos meses sorteados."""
    baseline = simulate(history, Scenario(), horizon, n_simulations, seed)
    result = simulate(history, scenario, horizon, n_simulations, seed)
    return baseline, result


# ============================================================
# DEMO
# ============================================================

if __name__ == "__main__":
    for uid in available_users():
        hist = load_user_history(uid)
        print(
            f"\n=== User {uid} | {len(hist.months)} months | "
            f"median monthly net flow = {np.median(hist.net_flow_mxn):,.0f} MXN | "
            f"FX {hist.last_month} = {hist.last_exchange_rate:.2f} ==="
        )

        car_scenario = Scenario(
            name="Comprar auto",
            car=CarPurchase(
                price_mxn=350_000, down_payment_pct=20, term_months=48,
                annual_rate_pct=13.0, monthly_car_cost_mxn=2_500,
            ),
        )

        base, scen = compare(hist, car_scenario, horizon=24)
        for res in (base, scen):
            s = res.summary()
            print(
                f"  {s['scenario']:<12} final P5={s['final_p5']:>12,.0f}  "
                f"P50={s['final_p50']:>12,.0f}  P95={s['final_p95']:>12,.0f}  "
                f"P(final<0)={s['prob_final_negative']:.1%}"
            )
        for loan_info in scen.loans:
            print(
                f"  {loan_info['label']}: payment={loan_info['monthly_payment_mxn']:,.0f} MXN/month, "
                f"P(default)={loan_info['probability_of_default']:.1%}, "
                f"outside training range={loan_info['outside_training_range'] or 'none'}"
            )

        offer = credit_offer(hist, term_months=36)
        print(
            f"  Offer 36m @15%: eligible={offer['eligible']}  "
            f"amount={offer['amount_mxn']:,.0f}  payment={offer['monthly_payment_mxn']:,.0f}  "
            f"[income limit={offer['payment_limit_by_income_mxn']:,.0f}, "
            f"stress limit={offer['payment_limit_by_stress_mxn']:,.0f}, "
            f"binding={offer['binding_rule']}]  "
            f"P(final<0)={offer['prob_final_negative_with_offer']:.1%}"
        )
        if offer["risk"]:
            p = offer["risk"]["probability_of_default"]
            print(
                f"    P(default)={p:.1%}  outside range={offer['risk']['outside_training_range'] or 'none'}"
            )

        home = Scenario(
            name="Comprar vivienda",
            mortgage=MortgageFromRent(current_rent_mxn=8_000, down_payment_mxn=100_000),
        )
        _, res_home = compare(hist, home, horizon=24)
        m = res_home.mortgage
        print(
            f"  Mortgage (rent 8,000, 20y @10.5%, down 100,000): loan={m['loan_amount_mxn']:,.0f}  "
            f"price={m['home_price_mxn']:,.0f}  upfront={m['upfront_cost_mxn']:,.0f}  "
            f"equity@24m={m['equity_by_month_mxn'][-1]:,.0f}  "
            f"P(default)={m['risk_probability_of_default']}  "
            f"P(final<0)={res_home.summary()['prob_final_negative']:.1%}"
        )
        for w in res_home.warnings:
            print(f"    WARNING: {w}")
