"""
Vista "Asistente" del dashboard (Semana 20).

Chat pensado para una persona sin conocimientos técnicos:
- Al abrir, el asistente saluda y muestra lo que le puede interesar según
  su historial (crédito preaprobado, alerta de gasto, ahorro, vivienda).
- Botones con preguntas sugeridas para empezar con un clic.
- Respuestas en lenguaje sencillo y en pesos.
- El detalle técnico (tabla, SQL, fuentes) queda escondido en un
  desplegable "¿De dónde sale esto?".

La lógica vive en src/assistant/; esta vista solo la presenta.
"""

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from assistant.assistant import ask, ollama_available  # noqa: E402
from assistant.proactive import build_welcome  # noqa: E402


INSIGHT_ICONS = {
    "credito": "💳",
    "alerta_gasto": "⚠️",
    "ahorro": "🐷",
    "vivienda": "🏠",
}


@st.cache_data(show_spinner=False)
def _welcome(user_id: int):
    return build_welcome(user_id)


@st.cache_data(show_spinner=False, ttl=60)
def _llm_ready() -> bool:
    return ollama_available()


def _reset_if_user_changed(user_id: int):
    if st.session_state.get("assistant_user") != user_id:
        st.session_state.assistant_user = user_id
        st.session_state.assistant_messages = []
        st.session_state.assistant_pending = None


def _show_details(response):
    """Detalle técnico, escondido por defecto."""
    result = response.result
    if result is None:
        return

    if result.warnings:
        st.caption(result.warnings[0])

    with st.expander("¿De dónde sale esto?", expanded=False):
        if result.data is not None and not result.data.empty:
            st.dataframe(result.data, hide_index=True, width="stretch")

        if response.answer_source == "modelo":
            st.caption("Respuesta redactada por la IA a partir de tus datos y revisada automáticamente.")
        else:
            st.caption("Respuesta calculada directamente con tus datos.")

        if result.sources:
            st.caption("Fuente: " + " · ".join(result.sources))
        for note in result.warnings[1:]:
            st.caption(note)
        if result.sql:
            st.code(result.sql, language="sql")


def _answer(question: str, user_id: int, use_llm: bool):
    st.session_state.assistant_messages.append({"role": "user", "text": question})
    with st.spinner("Revisando tus datos…"):
        response = ask(question, user_id, use_llm=use_llm)
    st.session_state.assistant_messages.append(
        {"role": "assistant", "text": response.answer, "response": response}
    )


def render_assistant(user_id: int):
    user_id = int(user_id)
    _reset_if_user_changed(user_id)

    st.subheader("💬 Tu asistente financiero")
    st.caption("Pregúntame sobre tu dinero. Respondo con tus propios datos.")

    use_llm = _llm_ready()
    if not use_llm:
        st.info(
            "Ahora mismo no puedo responder preguntas libres (por ejemplo, cuánto gastaste en algo), "
            "pero sí todo lo demás: cómo están tus finanzas, tu ahorro, metas, simulaciones y créditos."
        )

    # ---------------- Bienvenida proactiva ----------------
    try:
        welcome = _welcome(user_id)
    except Exception as error:  # noqa: BLE001 - datos o modelos no disponibles
        st.error(f"No pude revisar tu historial: {error}")
        return

    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(welcome.greeting)
        for insight in welcome.insights:
            with st.container(border=True):
                st.markdown(f"**{INSIGHT_ICONS.get(insight.kind, '•')} {insight.title}**")
                st.markdown(insight.text)
        st.caption("Propuestas ilustrativas con datos simulados; no son ofertas reales ni asesoría financiera.")

    st.markdown("**Puedes empezar por aquí:**")
    columns = st.columns(len(welcome.suggestions))
    for index, (column, suggestion) in enumerate(zip(columns, welcome.suggestions)):
        if column.button(suggestion, key=f"suggestion_{user_id}_{index}", width="stretch"):
            st.session_state.assistant_pending = suggestion

    # ---------------- Conversación ----------------
    for message in st.session_state.assistant_messages:
        avatar = "🤖" if message["role"] == "assistant" else "🙂"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["text"])
            if message["role"] == "assistant":
                _show_details(message["response"])

    typed = st.chat_input("Escribe tu pregunta…")
    question = typed or st.session_state.assistant_pending
    st.session_state.assistant_pending = None

    if question:
        _answer(question, user_id, use_llm)
        st.rerun()
