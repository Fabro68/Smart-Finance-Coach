"""
Asistente financiero de IA (Semana 20): LangChain + Ollama (llama3.2:3b).

Flujo controlado, no un agente autónomo:
1. Enrutar la pregunta a una herramienta: primero reglas por palabras
   clave (casos inequívocos), después el modelo con ejemplos.
2. Ejecutar la herramienta (datos exactos de Gold o del simulador). Sus
   respuestas se generan con plantillas en código: son exactas.
3. Solo para consultas SQL, el modelo genera la consulta y redacta la
   respuesta; un verificador la descarta si omite hechos o inventa
   cifras, y en ese caso se muestra el resultado de la consulta.

Decisión de diseño: en pruebas, llama3.2:3b tergiversaba cifras al
redactar (combinaba bien los números con un significado equivocado), así
que se separó la comprensión (LLM) del cálculo y la redacción numérica
(código).

Todo corre en local: no se envían datos a servicios externos.
Proyecto académico con datos simulados: no es asesoría financiera.
"""

import json
import os
import re
import time
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from typing import Literal

from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from assistant import tools
from assistant.tools import ToolResult


OLLAMA_MODEL = os.environ.get("SFC_OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_URL = os.environ.get("SFC_OLLAMA_URL", "http://localhost:11434")

ToolName = Literal[
    "perfil_riesgo", "cambio_ahorro", "simular_escenario", "meta_ahorro",
    "oferta_credito", "consulta_sql", "fuera_de_alcance",
]

OUT_OF_SCOPE_ANSWER = (
    "Eso se sale de lo que puedo hacer 🙂. Te puedo ayudar con tu dinero: cómo están tus "
    "finanzas, por qué cambió tu ahorro, qué pasaría si cambian tus gastos o ingresos, "
    "cuándo juntarías una meta, cuánto te podríamos prestar o cuánto gastaste en algo."
)

EXAMPLE_QUESTIONS = [
    "¿Cómo están mis finanzas?",
    "¿Por qué bajó mi ahorro el mes pasado?",
    "¿Qué pasaría si mis gastos suben 20%?",
    "¿Cuándo podría juntar 100 mil pesos?",
    "¿Cuánto me pueden prestar?",
    "¿Cuánto gasté en restaurantes en 2019?",
]


# ============================================================
# ROUTING
# ============================================================

def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


# Reglas para casos inequívocos (texto sin acentos, en minúsculas).
_RULES: list[tuple[str, str]] = [
    ("cambio_ahorro", r"(por ?que|porque).*(baj|disminu|subi|aument|cambi|cay|cae).*(ahorr|gast)"),
    ("cambio_ahorro", r"(por ?que|porque).*(ahorr|gast).*(baj|disminu|subi|aument|cambi|cay|cae)"),
    ("meta_ahorro", r"\bmeta\b|alcanz\w*.*\d|junt\w*.*\d|ahorr\w*.*\d.*(mil|pesos|\$)"),
    ("oferta_credito", r"(me|te) (pueden|puedes|podrian|podrias|podemos) prestar|cuanto (me|te) prest|cuanto (credito|prestamo|dinero)|(prestar|ofrecer|otorgar|pedir).*(credito|prestamo)|(credito|prestamo).*(prestar|ofrecer|otorgar|pedir)"),
    ("simular_escenario", r"que (pasaria|ocurriria|sucederia)|^y si |\bsi (aumento|reduzco|bajo|subo|pierdo|gano|recorto|gasto)"),
    ("perfil_riesgo", r"nivel de riesgo|mi riesgo|que tan riesgos|salud financiera|como estoy|mi perfil|como (estan|van|esta|va) (mis|mi) (finanzas|dinero|economia)"),
]


class Route(BaseModel):
    tool: ToolName
    reason: str = Field(description="justificación breve")


_ROUTER_PROMPT = """Clasifica la pregunta del usuario en UNA herramienta:
- perfil_riesgo: nivel de riesgo, perfil o salud financiera. Ej.: "¿Qué tan riesgoso es mi perfil?"
- cambio_ahorro: por qué cambió el ahorro o el gasto entre meses. Ej.: "¿Por qué bajó mi ahorro?"
- simular_escenario: qué pasaría si cambian gastos o ingresos, o si pierde el empleo. Ej.: "¿Y si gano 10% menos?"
- meta_ahorro: cuándo alcanzaría una meta o cantidad de ahorro. Ej.: "¿En cuánto tiempo junto 50 mil pesos?"
- oferta_credito: cuánto crédito o préstamo se le puede ofrecer. Ej.: "¿Me pueden prestar dinero?"
- consulta_sql: datos históricos concretos: montos, categorías, meses, conteos. Ej.: "¿Cuánto gasté en comida en 2018?", "¿Cuál fue mi mes con más gasto?"
- fuera_de_alcance: temas que no son sus finanzas en esta plataforma (deportes, clima, consejos de inversión en acciones, etc.)."""


def route_question(question: str, llm: ChatOllama | None) -> tuple[str, str]:
    """Devuelve (herramienta, método): método = 'reglas' o 'modelo'."""
    normalized = _normalize(question)
    for tool_name, pattern in _RULES:
        if re.search(pattern, normalized):
            return tool_name, "reglas"

    if llm is None:
        return "consulta_sql", "sin modelo"

    route = llm.with_structured_output(Route).invoke(
        [("system", _ROUTER_PROMPT), ("human", question)]
    )
    return route.tool, "modelo"


# ============================================================
# ANSWER
# ============================================================

_ANSWER_PROMPT = """Eres el asistente financiero de Smart Finance Coach.
Responde en español, en 2 o 3 frases claras, con tono amable y sin tecnicismos.
Habla directamente al usuario en segunda persona (tú): «gastaste», «tu gasto»; nunca en primera persona.
Los montos están en pesos: escríbelos con signo de pesos y sin decimales cuando sean grandes (por ejemplo, $9,103).
Responde directamente: sin frases introductorias ni descargos al inicio.
Usa ÚNICAMENTE los hechos de DATOS. Copia meses y cifras exactamente como aparecen;
no calcules, no redondees de otra forma y no inventes información.
Si DATOS incluye un "Supuesto", menciónalo.
No des consejos, recomendaciones ni juicios de valor (nada de "deberías", "es importante",
"te recomiendo"), ni asesoría financiera o de inversión.
Si hay una ADVERTENCIA, termina con "Nota:" y esa advertencia en tus palabras; no inventes otras."""


@dataclass
class AssistantResponse:
    question: str
    answer: str
    tool: str
    route_method: str
    result: ToolResult | None = None
    seconds: dict = field(default_factory=dict)
    llm_error: str | None = None
    # "modelo": redactada por el LLM y verificada; "datos": resumen exacto de la herramienta.
    answer_source: str = "datos"
    rejected_reason: str | None = None


_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in _NUMBER.findall(text or "")}


def verify_answer(answer: str, result: ToolResult, question: str) -> str | None:
    """
    Devuelve None si la redacción es fiel a los datos, o el motivo del rechazo:
    - falta un hecho clave de la herramienta, o
    - aparece una cifra que no está en los datos ni en la pregunta.
    """
    normalized = answer.replace(" ", " ").lower()
    missing = [fact for fact in result.key_facts if fact.lower() not in normalized]
    if missing:
        return f"omite hechos clave: {', '.join(missing)}"

    allowed = _numbers(result.summary) | _numbers(question)
    for warning in result.warnings:
        allowed |= _numbers(warning)
    invented = sorted(n for n in _numbers(answer) if n not in allowed)
    if invented:
        return f"incluye cifras que no están en los datos: {', '.join(invented)}"
    return None


def ollama_available(timeout: float = 2.0) -> bool:
    """True si el servidor de Ollama responde y tiene el modelo descargado."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=timeout) as response:
            models = json.loads(response.read()).get("models", [])
        return any(m.get("name", "").startswith(OLLAMA_MODEL) for m in models)
    except Exception:  # noqa: BLE001
        return False


def make_llm(temperature: float = 0.0, max_tokens: int | None = None) -> ChatOllama:
    return ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_URL,
        temperature=temperature,
        num_predict=max_tokens,
    )


def _write_answer(question: str, result: ToolResult, llm: ChatOllama) -> str:
    facts = f"DATOS:\n{result.summary}"
    if result.warnings:
        facts += f"\nADVERTENCIA: {result.warnings[0]}"
    message = llm.invoke([("system", _ANSWER_PROMPT), ("human", f"PREGUNTA: {question}\n\n{facts}")])
    return str(message.content).strip()


def ask(question: str, user_id: int, use_llm: bool = True) -> AssistantResponse:
    """Responde una pregunta del usuario indicado (el usuario viene de la interfaz)."""
    seconds = {}
    llm_router = make_llm(0.0) if use_llm else None
    llm_writer = make_llm(0.2, max_tokens=220) if use_llm else None

    start = time.time()
    try:
        tool_name, method = route_question(question, llm_router)
    except Exception as exc:  # noqa: BLE001 - p. ej. Ollama no responde durante el enrutamiento
        return AssistantResponse(question, f"No pude interpretar la pregunta: {exc}", "error", "error")
    seconds["enrutamiento"] = round(time.time() - start, 1)

    if tool_name == "fuera_de_alcance":
        return AssistantResponse(question, OUT_OF_SCOPE_ANSWER, tool_name, method, seconds=seconds)

    start = time.time()
    if tool_name == "consulta_sql":
        if llm_router is None:
            return AssistantResponse(
                question,
                "Las consultas libres a tus datos requieren el modelo de lenguaje (Ollama), que no está disponible.",
                tool_name, method, seconds=seconds,
            )
        result = tools.consulta_sql(user_id, question, llm_router)
    else:
        result = getattr(tools, tool_name)(user_id, question)
    seconds["herramienta"] = round(time.time() - start, 1)

    response = AssistantResponse(question, result.summary, tool_name, method, result, seconds)

    # Híbrido: las herramientas ya responden con plantillas exactas; el modelo
    # solo redacta el resultado de una consulta SQL, y se verifica.
    if tool_name == "consulta_sql" and result.data is not None and llm_writer is not None:
        start = time.time()
        try:
            draft = _write_answer(question, result, llm_writer)
            rejected = verify_answer(draft, result, question)
            if rejected:
                response.rejected_reason = rejected      # se queda el resumen exacto
            else:
                response.answer, response.answer_source = draft, "modelo"
        except Exception as exc:  # noqa: BLE001 - se muestra el resumen de la herramienta
            response.llm_error = str(exc)[:200]
        seconds["redacción"] = round(time.time() - start, 1)

    return response
