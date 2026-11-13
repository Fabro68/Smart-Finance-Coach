# Smart Finance Coach
## Semana 20 — Asistente Financiero de IA

### 1. Objetivo

Habilitar la consulta de la información financiera del usuario en lenguaje natural, de modo que una persona sin conocimientos técnicos pueda preguntar sobre su dinero y recibir respuestas claras basadas en sus propios datos.

El asistente cubre las preguntas de ejemplo de la propuesta del proyecto:

| Pregunta de la propuesta | Cómo la responde el asistente |
|---|---|
| ¿Cuál es mi nivel de riesgo? | Herramienta `perfil_riesgo` (KPIs y feature store de Gold) |
| ¿Qué ocurriría si aumento mis gastos? | Herramienta `simular_escenario` (simulador Monte Carlo de la Semana 19) |
| ¿Cuándo podría alcanzar una meta financiera? | Herramienta `meta_ahorro` (simulador Monte Carlo) |
| ¿Por qué disminuyó mi capacidad de ahorro? | Herramienta `cambio_ahorro` (KPIs y gasto por categoría) |

Además responde cuánto crédito se le podría ofrecer, consultas libres sobre sus gastos (Text-to-SQL) y muestra **sugerencias proactivas** sin que el usuario las pida.

---

### 2. Alcance y advertencias

- Solo los 3 usuarios con historial de transacciones pueden usar el asistente.
- Las respuestas son **estimaciones ilustrativas** con datos simulados de 2018 a 2019. Las propuestas de crédito **no son ofertas reales** y el asistente **no da asesoría financiera**.
- Todo corre **en local**: el modelo de lenguaje se ejecuta con Ollama en el equipo y no se envían datos a servicios externos.

---

### 3. Tecnología

| Componente | Herramienta | Versión |
|---|---|---|
| Modelo de lenguaje | Llama 3.2 (3B) en Ollama | `llama3.2:3b`, Ollama 0.40.16 |
| Orquestación | LangChain (`langchain-core`, `langchain-ollama`) | 1.8.0 / 1.1.0 |
| Consultas SQL | DuckDB en memoria sobre tablas Gold (Delta Lake) | 2.0.0 |
| Interfaz | Streamlit (vista "Asistente" del dashboard) | 1.66.1 |

**Elección del modelo.** El equipo de desarrollo no tiene GPU dedicada, por lo que el modelo corre en CPU. Se midió `llama3.2:3b` en el equipo: unos **20 tokens por segundo** y 2.6 GB de memoria. Un modelo de 8B habría sido unas 2.5 veces más lento y habría competido por memoria con los contenedores de Spark y Airflow.

Se usa `langchain-core` y no el paquete completo `langchain` porque el flujo es controlado (no un agente autónomo) y no requiere `langgraph`: son 21 dependencias en lugar de 27.

---

### 4. Arquitectura

```text
Pregunta del usuario (el usuario viene del dashboard, nunca de la pregunta)
        │
        ▼
1. Enrutamiento ──── reglas por palabras clave (casos claros, instantáneo)
        │            └─ si no aplican: LLM con ejemplos (salida estructurada)
        ▼
2. Herramienta ───── perfil_riesgo · cambio_ahorro · simular_escenario
        │            meta_ahorro · oferta_credito  → plantillas en código
        │            consulta_sql → el LLM genera SQL, se valida y se ejecuta
        ▼
3. Respuesta ─────── herramientas: texto de la plantilla (exacto)
                     consulta_sql: el LLM redacta + verificador
```

| Módulo | Responsabilidad |
|---|---|
| `src/assistant/data_access.py` | Carga de Gold en DuckDB, aislamiento por usuario, vistas en pesos y validación de SQL |
| `src/assistant/tools.py` | Las 6 herramientas y sus respuestas en lenguaje sencillo |
| `src/assistant/assistant.py` | Enrutamiento, ejecución, redacción de consultas SQL y verificación |
| `src/assistant/proactive.py` | Sugerencias proactivas de la bienvenida |
| `src/dashboard/assistant_page.py` | Interfaz de chat |

---

### 5. Decisión de diseño: separar comprensión y cálculo

La primera versión dejaba que el modelo redactara todas las respuestas a partir de los datos calculados. Las pruebas mostraron que **llama3.2:3b tergiversa cifras al redactar**, aun con los hechos explícitos en el prompt:

| Pregunta | Datos entregados al modelo | Redacción del modelo |
|---|---|---|
| Nivel de riesgo | Riesgo bajo, ahorro saludable | "No se pueden determinar niveles de riesgo basados en un solo mes" |
| Meta de 100 mil (usuario 1) | La mitad de las simulaciones la alcanza en el mes 5; 76% de probabilidad a 12 meses | "En el mes 5 o antes en 76% de los casos" |
| Caída del ahorro | De agosto a septiembre | "Disminuyó en agosto" |

Se agregó un verificador (hechos clave obligatorios y ninguna cifra ajena a los datos). Descartó 7 de 12 redacciones, pero 2 de las aceptadas seguían siendo incorrectas: tenían las cifras correctas con un significado equivocado.

**Decisión (híbrida):**

- **El LLM entiende:** enruta las preguntas ambiguas, genera el SQL de las consultas libres y redacta su resultado, que es un hecho simple y se verifica.
- **El código calcula y redacta las cifras:** las herramientas responden con plantillas en lenguaje natural, exactas por construcción.

Así se cumple lo que pide la propuesta (lenguaje natural, LangChain, Ollama y Text-to-SQL) sin arriesgar la exactitud de las cifras.

---

### 6. Herramientas

| Herramienta | Qué calcula | Ejemplo de respuesta (usuario 2) |
|---|---|---|
| `perfil_riesgo` | Nivel de riesgo, ahorro de 3 meses, meses en negativo, gastos atípicos | "Tus finanzas se ven sanas: tu nivel de riesgo es **bajo**… lograste guardar 44 de cada 100 pesos que te entraron." |
| `cambio_ahorro` | Cambio del gasto entre dos meses y categorías que lo explican, en pesos | "En septiembre de 2019 gastaste $2,937 más que en agosto (48% más)… Donde más subió tu gasto: Bares y alcohol (+$1,427), Compras (+$1,411) y Restaurantes (+$1,256)." |
| `simular_escenario` | Monte Carlo con cambio de gastos, ingresos o pérdida de empleo; extrae porcentaje, meses y plazo de la pregunta | "Si tus gastos suben 20%, en un año podrías juntar unos $111,483, en vez de $131,237…" |
| `meta_ahorro` | Mes en que se alcanzaría la meta y probabilidad a 1, 2 y 3 años | "Lo más probable es que juntes $100,000 en unos 10 meses. La probabilidad de lograrlo es de 80% en un año…" |
| `oferta_credito` | Crédito responsable con las reglas de la Semana 19 | "Te podríamos prestar hasta **$146,935** a tres años, pagando **$5,094 al mes**…" |
| `consulta_sql` | Consulta libre sobre vistas en pesos (Text-to-SQL) | "Gastaste $9,145.84 en restaurantes en 2019." |

Si la pregunta parte de una premisa falsa, la herramienta responde con los datos. Ejemplo: al usuario 1, que preguntó por qué bajó su ahorro, le responde "Buenas noticias: en realidad tu capacidad de ahorro subió…".

Cuando la pregunta no indica un valor, se usa un supuesto y se dice: "No me dijiste cuánto, así que supuse que tus gastos suben 10%".

---

### 7. Enrutamiento

1. **Reglas por palabras clave** para los casos inequívocos ("por qué… bajó… ahorro", "cuánto me pueden prestar", "qué pasaría si", "meta", "cómo están mis finanzas"). Son instantáneas.
2. **LLM con ejemplos y salida estructurada** (modelo Pydantic con las herramientas posibles) para el resto, incluida la detección de preguntas fuera de tema.

En la prueba con las preguntas de la propuesta y variantes coloquiales, el enrutamiento acertó **en todos los casos** (8 de 8, y 9 de 9 en una prueba anterior), incluidas las preguntas fuera de tema.

---

### 8. Text-to-SQL seguro

| Control | Implementación |
|---|---|
| Aislamiento por usuario | Cada pregunta abre una conexión DuckDB en memoria que contiene **solo las filas del usuario**. Ni con un SQL malicioso se pueden ver datos de otros usuarios (`SELECT DISTINCT user_id` devuelve solo el usuario actual). |
| Solo lectura | El parser de DuckDB (`json_serialize_sql`) rechaza todo lo que no sea una sentencia `SELECT`/`WITH`: `DELETE`, `DROP` o varias sentencias quedan bloqueados. |
| Tablas permitidas | Solo las tablas y vistas autorizadas; se excluyen los nombres de CTE definidos en la consulta. |
| Sin acceso a archivos | Conexión con `enable_external_access = false` y configuración bloqueada; se rechazan las funciones de tabla (`read_csv` y similares). |
| Límite de resultados | Máximo 200 filas. |
| Corrección | Si el SQL falla, el error se devuelve al modelo para un segundo intento. |

**Vistas para el modelo.** El LLM no consulta las tablas Gold crudas, sino dos vistas pensadas para el usuario: `gastos_por_categoria` y `resumen_mensual`. Tienen los montos ya convertidos a **pesos** (con el tipo de cambio de cada mes) y las **categorías en español** ("Bares y alcohol", "Supermercado"). Esto simplifica el SQL que genera el modelo y hace que todas las respuestas usen la misma moneda.

---

### 9. Sugerencias proactivas

Al abrir el asistente, el sistema revisa el historial y muestra lo que le aplica al usuario, sin que lo pida:

| Sugerencia | Condición |
|---|---|
| 💳 **Crédito preaprobado** | Cumple las dos reglas de crédito responsable (cuota ≤ 30% del ingreso típico y riesgo de terminar en negativo ≤ 10%) **y** no muestra señales de dificultad |
| ⚠️ **Tu gasto subió** | El gasto del último mes subió más de 30% |
| 🐷 **Tu ahorro** | Su flujo mensual esperado es positivo |
| 🏠 **¿Pagas renta?** | Siempre, como invitación al simulador de renta o compra |

**Criterio de banca responsable.** No se ofrece crédito de forma proactiva a quien muestra señales de dificultad (3 o más meses con balance negativo en los últimos 6, o una anomalía de gasto en los últimos 3 meses), aunque sea elegible.

| Usuario | Crédito proactivo | Motivo |
|---|---|---|
| 1 | No | 3 meses con balance negativo en los últimos 6 (además, no es elegible) |
| 2 | Sí: hasta $146,935 a tres años | Cumple las reglas y no tiene señales de dificultad |
| 3 | Sí: hasta $50,705 a tres años | Cumple las reglas; el monto se ajusta a su flujo |

Debajo de la bienvenida aparecen botones con preguntas sugeridas.

---

### 10. Experiencia para el usuario

El asistente está pensado para una persona sin conocimientos técnicos:

- **Lenguaje sencillo, en segunda persona y en pesos:** "números rojos" en lugar de "probabilidad de saldo acumulado negativo"; "lo más probable" en lugar de "mediana"; plazos en años; porcentajes redondeados.
- **Una nota breve y amable** debajo de cada respuesta (por ejemplo, "Es una propuesta ilustrativa, no una oferta real ni asesoría financiera").
- **El detalle técnico, escondido:** la tabla usada, las fuentes, el SQL generado y si la respuesta la calculó el código o la redactó la IA quedan en un desplegable cerrado, "¿De dónde sale esto?".
- **Si Ollama no está disponible,** el asistente sigue respondiendo todo excepto las consultas libres, y lo explica con un mensaje sencillo.

---

### 11. Desempeño medido

| Tipo de pregunta | Tiempo |
|---|---|
| Herramientas con plantilla (riesgo, ahorro, simulación, meta, crédito) | 0.0–0.3 s |
| Pregunta fuera de tema (enrutada por el LLM) | 2–4 s |
| Consulta libre (enrutamiento + SQL + redacción con el LLM) | 12–20 s |
| Bienvenida proactiva | menos de 1 s (la primera oferta de crédito puede tardar unos segundos al cargar los rangos del modelo) |

---

### 12. Verificación

- **Seguridad del SQL:** se probaron consultas permitidas y maliciosas; `DELETE`, varias sentencias, `read_csv` y tablas no autorizadas quedaron bloqueadas, y el aislamiento por usuario se confirmó.
- **Herramientas:** probadas con los 3 usuarios, incluidos casos sin porcentaje, pérdida de empleo, plazos en meses y años, y usuarios no elegibles para crédito.
- **Asistente completo:** las preguntas de la propuesta y variantes coloquiales con enrutamiento correcto.
- **Interfaz:** prueba automática con `streamlit.testing.AppTest` para los 3 usuarios (bienvenida, botón sugerido, pregunta escrita y consulta libre) sin excepciones.

---

### 13. Cómo ejecutarlo

1. Instalar Ollama y descargar el modelo:

   ```powershell
   winget install Ollama.Ollama
   ollama pull llama3.2:3b
   ```

   Si la descarga falla con un error de conexión por IPv6 (`dial tcp [2606:…]`), la red no está enrutando IPv6. Se puede indicar a Windows que prefiera IPv4 (como administrador, reversible):

   ```powershell
   netsh interface ipv6 set prefixpolicy ::ffff:0:0/96 60 4
   ```

2. Instalar las dependencias del entorno local (`requirements.txt`).

3. Tener los modelos de la Semana 18 en `models/` (`python src/ml/train_loan_model.py` y `python src/ml/evaluate_loan_model.py`).

4. Abrir el dashboard y elegir la vista **"Asistente"**:

   ```powershell
   python -m streamlit run .\src\dashboard\app.py
   ```

El modelo y la URL de Ollama se pueden cambiar con las variables de entorno `SFC_OLLAMA_MODEL` y `SFC_OLLAMA_URL`.

---

### 14. Limitaciones

1. **Modelo pequeño.** Con 3B parámetros, el modelo no es confiable para redactar cifras; por eso solo redacta el resultado de las consultas libres, con verificación.
2. **Consultas libres lentas.** Unos 12 a 20 segundos en CPU.
3. **El enrutamiento por reglas es en español** y depende de frases comunes; las preguntas muy distintas dependen del LLM.
4. **Interpretación limitada de parámetros:** porcentajes, meses, años y montos se extraen con expresiones regulares; se usan supuestos explícitos cuando faltan.
5. **Sin memoria de conversación:** cada pregunta se responde por separado.
6. **Mismas limitaciones de datos del proyecto:** solo 3 usuarios, moneda inferida de las transacciones y escalas distintas entre salario y transacciones.
7. **Sin RAG sobre documentación:** el asistente responde con datos, no sobre la metodología del proyecto.
