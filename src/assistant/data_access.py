"""
Acceso de solo lectura a la capa Gold para el asistente de IA (Semana 20).

- Las tablas Gold (Delta Lake) se cargan una vez en memoria (Arrow).
- Cada usuario obtiene su propia conexion DuckDB en memoria que contiene
  SOLO sus filas: el asistente no puede consultar datos de otro usuario,
  sin importar el SQL que genere el modelo.
- La conexion no tiene acceso externo (no puede leer archivos ni red) y
  su configuracion queda bloqueada.
- validate_sql() usa el parser de DuckDB: una sola sentencia SELECT/WITH,
  solo tablas permitidas y sin funciones de tabla.
"""

import json
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
from deltalake import DeltaTable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLD_PATH = PROJECT_ROOT / "data" / "gold"

# Tablas Gold disponibles para el asistente y si se filtran por usuario.
USER_TABLES = (
    "user_financial_profile",
    "user_monthly_finance",
    "user_category_monthly",
    "user_financial_kpis",
    "ml_user_features",
)
SHARED_TABLES = ("monthly_macro_context",)

# Vistas amigables para las consultas libres: montos en pesos (convertidos
# con el tipo de cambio de cada mes) y categorías en español.
SQL_VIEWS = ("gastos_por_categoria", "resumen_mensual")

GOLD_TABLES = USER_TABLES + SHARED_TABLES
ALLOWED_TABLES = GOLD_TABLES + SQL_VIEWS

CATEGORY_ES = {
    "Alcohol & Bars": "Bares y alcohol",
    "Auto Insurance": "Seguro de auto",
    "Coffee Shops": "Cafeterías",
    "Electronics & Software": "Electrónica y software",
    "Entertainment": "Entretenimiento",
    "Fast Food": "Comida rápida",
    "Food & Dining": "Comida",
    "Gas & Fuel": "Gasolina",
    "Groceries": "Supermercado",
    "Haircut": "Corte de cabello",
    "Home Improvement": "Mejoras del hogar",
    "Internet": "Internet",
    "Mobile Phone": "Celular",
    "Mortgage & Rent": "Renta o hipoteca",
    "Movies & DVDs": "Películas",
    "Music": "Música",
    "Restaurants": "Restaurantes",
    "Shopping": "Compras",
    "Television": "Televisión",
    "Utilities": "Servicios (luz, agua, gas)",
}


def category_es(name: str | None) -> str | None:
    """Nombre de la categoría en español (o el original si no está en el catálogo)."""
    return CATEGORY_ES.get(name, name) if name else name

MAX_ROWS = 200

# Columnas tecnicas que no aportan al asistente.
_DROP_COLUMNS = {"gold_created_at"}


class SQLValidationError(ValueError):
    """El SQL generado no cumple las reglas de solo lectura."""


@lru_cache(maxsize=1)
def load_gold_tables() -> dict[str, pa.Table]:
    """Lee las tablas Gold permitidas (una sola vez por proceso)."""
    tables = {}
    for name in GOLD_TABLES:
        table = DeltaTable(str(GOLD_PATH / name)).to_pyarrow_table()
        keep = [c for c in table.column_names if c not in _DROP_COLUMNS]
        tables[name] = table.select(keep)
    return tables


def available_users() -> list[int]:
    """Usuarios con historial mensual (los que puede atender el asistente)."""
    monthly = load_gold_tables()["user_monthly_finance"]
    return sorted(int(u) for u in pc.unique(monthly["user_id"]).to_pylist())


def user_connection(user_id: int) -> duckdb.DuckDBPyConnection:
    """Conexion DuckDB en memoria con SOLO los datos del usuario."""
    con = duckdb.connect(config={"enable_external_access": False})

    for name, table in load_gold_tables().items():
        if name in USER_TABLES:
            table = table.filter(pc.equal(table["user_id"], int(user_id)))
        con.register(name, table)

    con.register("catalogo_categorias", pa.table({
        "en": list(CATEGORY_ES.keys()),
        "es": list(CATEGORY_ES.values()),
    }))

    con.execute("""
        CREATE VIEW gastos_por_categoria AS
        SELECT c.year_month AS mes,
               COALESCE(k.es, c.categoria) AS categoria,
               ROUND(c.total_amount * x.average_exchange_rate, 2) AS monto_pesos,
               c.transaction_count AS num_compras
        FROM user_category_monthly c
        JOIN monthly_macro_context x USING (year_month)
        LEFT JOIN catalogo_categorias k ON k.en = c.categoria
    """)
    con.execute("""
        CREATE VIEW resumen_mensual AS
        SELECT m.year_month AS mes,
               ROUND(m.total_credits * x.average_exchange_rate, 2) AS ingresos_pesos,
               ROUND(m.consumer_spending * x.average_exchange_rate, 2) AS gasto_consumo_pesos,
               ROUND(m.credit_card_payments * x.average_exchange_rate, 2) AS pagos_tarjeta_pesos,
               ROUND(m.total_debits * x.average_exchange_rate, 2) AS gastos_totales_pesos,
               m.transaction_count AS num_movimientos,
               COALESCE(k.es, m.top_spending_category) AS categoria_principal
        FROM user_monthly_finance m
        JOIN monthly_macro_context x USING (year_month)
        LEFT JOIN catalogo_categorias k ON k.en = m.top_spending_category
    """)

    con.execute("SET lock_configuration = true")
    return con


def table_schemas() -> dict[str, list[str]]:
    """Nombre de columnas por tabla, para describirlas al modelo."""
    return {name: table.column_names for name, table in load_gold_tables().items()}


def _walk(node, on_dict):
    if isinstance(node, dict):
        on_dict(node)
        for value in node.values():
            _walk(value, on_dict)
    elif isinstance(node, list):
        for value in node:
            _walk(value, on_dict)


def validate_sql(con: duckdb.DuckDBPyConnection, sql: str) -> str:
    """
    Valida el SQL con el parser de DuckDB. Devuelve el SQL limpio o lanza
    SQLValidationError. Reglas: una sentencia SELECT/WITH, solo tablas
    permitidas (o nombres de CTE definidos en la consulta), sin funciones
    de tabla (read_csv, etc.).
    """
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise SQLValidationError("La consulta está vacía.")
    if ";" in cleaned:
        raise SQLValidationError("Solo se permite una sentencia.")

    raw = con.execute("SELECT json_serialize_sql(?)", [cleaned]).fetchone()[0]
    parsed = json.loads(raw)
    if parsed.get("error"):
        raise SQLValidationError(
            "Solo se permiten consultas SELECT válidas: "
            + str(parsed.get("error_message", ""))[:200]
        )
    if len(parsed.get("statements", [])) != 1:
        raise SQLValidationError("Solo se permite una sentencia.")

    tables, ctes, functions = set(), set(), []

    def on_dict(node):
        node_type = node.get("type")
        if node_type == "BASE_TABLE" and node.get("table_name"):
            tables.add(str(node["table_name"]).lower())
        elif node_type == "TABLE_FUNCTION":
            functions.append(node)
        cte_map = node.get("cte_map")
        if isinstance(cte_map, dict):
            for entry in cte_map.get("map", []):
                if isinstance(entry, dict) and entry.get("key"):
                    ctes.add(str(entry["key"]).lower())

    _walk(parsed, on_dict)

    if functions:
        raise SQLValidationError("No se permiten funciones de tabla (por ejemplo, read_csv).")
    if not tables:
        raise SQLValidationError("La consulta debe usar al menos una tabla permitida.")

    not_allowed = sorted(t for t in tables if t not in ALLOWED_TABLES and t not in ctes)
    if not_allowed:
        raise SQLValidationError(f"Tablas no permitidas: {', '.join(not_allowed)}.")

    return cleaned


def run_readonly_query(con: duckdb.DuckDBPyConnection, sql: str, max_rows: int = MAX_ROWS) -> pd.DataFrame:
    """Valida y ejecuta la consulta, limitada a max_rows filas."""
    cleaned = validate_sql(con, sql)
    return con.execute(f"SELECT * FROM ({cleaned}) AS q LIMIT {int(max_rows)}").df()
