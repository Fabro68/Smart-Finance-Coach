# Smart Finance Coach
## Semana 19 — Simulador Financiero (Monte Carlo)

### 1. Objetivo

Construir un simulador que proyecte la situación financiera de un usuario bajo distintos escenarios de vida y que responda tres preguntas:

1. **¿Qué pasaría si...?** Comparar la línea base del usuario con escenarios basados en reglas: contratar un crédito, cambiar de empleo, aumentar gastos, comprar un auto o cambiarse de vivienda.
2. **¿Cuánto crédito se le puede ofrecer de forma responsable?** Calcular una propuesta de crédito con base en sus finanzas registradas.
3. **¿Le conviene rentar o comprar?** Calcular qué vivienda podría adquirir si pagara de hipoteca lo mismo que hoy paga de renta, y cuánto patrimonio acumularía.

El simulador cubre la capacidad "Simular escenarios" de la propuesta del proyecto y el valor agregado de un motor Monte Carlo con bandas de confianza.

---

### 2. Alcance y advertencias

- Solo 3 usuarios tienen historial de transacciones (21 meses cada uno); el simulador trabaja con ellos.
- Los resultados son **escenarios ilustrativos** construidos con datos simulados. Las propuestas de crédito **no son ofertas reales** y el simulador **no constituye asesoría financiera**.
- La probabilidad de impago proviene de un modelo entrenado con préstamos sin relación verificable con los usuarios (ver `docs/ml_model_report.md`).

---

### 3. Arquitectura

```text
Gold ml_user_features ──┐
Gold loan_ml_dataset ───┼──► src/simulation/monte_carlo.py ──► src/dashboard/simulator_page.py ──► Vista "Simulador"
models/loan_risk_reduced.joblib ┘        (motor, sin Streamlit)        (interfaz Streamlit)
```

| Componente | Responsabilidad |
|---|---|
| `src/simulation/monte_carlo.py` | Motor: carga del historial, conversión a MXN, escenarios, simulación Monte Carlo, oferta de crédito, hipoteca y P(impago). No depende de Streamlit, por lo que podrá reutilizarlo el asistente de IA (Semana 20). |
| `src/dashboard/simulator_page.py` | Interfaz: captura parámetros, llama al motor y muestra gráficas y resultados. No contiene lógica financiera propia. |
| `src/dashboard/app.py` | Agrega la vista "Simulador" al menú lateral. |

---

### 4. Datos y moneda

#### 4.1. Fuentes

- **Historial mensual del usuario:** `total_credits` y `total_debits` de Gold `ml_user_features`, junto con el tipo de cambio del mes y las variables del puente hacia el modelo (edad, estado civil, dependientes, ingreso anual en USD).
- **Rangos de entrenamiento del modelo:** split `train` de Gold `loan_ml_dataset` (ingreso, monto, plazo y tasa).
- **Modelo de riesgo:** `models/loan_risk_reduced.joblib` (Semana 18).

#### 4.2. Todo se presenta en MXN

| Dato | Tratamiento |
|---|---|
| Créditos y débitos históricos | Se suponen en USD (unidad inferida de las transacciones) y se convierten a MXN con el **tipo de cambio de su mes** (`monthly_macro_context.average_exchange_rate`). |
| Montos de los escenarios | Se capturan en MXN (monto del crédito, precio del auto, renta, enganche). |
| Entrada al modelo de riesgo | El monto del crédito se convierte a USD con el **tipo de cambio del último mes del usuario** (2019-09: 19.55 MXN/USD). El ingreso usa `annual_income_usd` del feature store. |
| Salario | No se suma a los flujos. Se usa solo como ingreso de entrada al modelo, porque no está en la misma escala que las transacciones (ver `docs/ml_feature_dictionary.md`, sección 12.8). |

---

### 5. Método Monte Carlo

#### 5.1. Bootstrap de meses históricos

Cada mes simulado toma al azar, con reemplazo, un mes real del propio usuario, **conservando juntos sus créditos y débitos**. Se generan **5,000 trayectorias** con horizonte de **12, 24 o 36 meses** y semilla fija (42) para que los resultados sean reproducibles.

**Justificación.** El flujo neto mensual (créditos − débitos) de los usuarios tiene distribuciones muy asimétricas y autocorrelación casi nula:

| Usuario | Media (USD) | Desviación (USD) | Asimetría | Autocorrelación mes a mes |
|---|---|---|---|---|
| 1 | 536 | 2,891 | −1.87 | 0.06 |
| 2 | 578 | 608 | +1.88 | −0.13 |
| 3 | 228 | 317 | +1.87 | 0.03 |

- La asimetría y los picos (por ejemplo, los meses de gasto extraordinario del usuario 1) se representarían mal con una distribución normal; el bootstrap los conserva sin suponer una distribución.
- La autocorrelación casi nula indica que un mes no predice el siguiente, lo que justifica sortear los meses de forma independiente.

#### 5.2. Números aleatorios comunes

La línea base y el escenario usan **exactamente los mismos meses sorteados**. Así, la diferencia entre ambos refleja solo el efecto del escenario y no el azar.

Verificación: en el escenario de compra de auto (sección 6), la mediana final de los tres usuarios baja exactamente el costo determinista del escenario (310,288 MXN).

#### 5.3. Cambio acumulado desde 0

No se conoce el saldo real de las cuentas del usuario. La simulación muestra el **cambio acumulado del flujo de efectivo desde hoy, partiendo de 0**, no un saldo bancario.

---

### 6. Escenarios basados en reglas

Los escenarios de la primera sección se pueden **combinar**.

| Escenario | Parámetros (valores por defecto) | Efecto en la simulación |
|---|---|---|
| **Línea base** | — | Flujo histórico sin cambios. |
| **Contratar crédito** | Monto (100,000 MXN), plazo (36 meses), tasa (15%), propósito | La cuota mensual se suma a los débitos durante el plazo. Calcula la P(impago). |
| **Cambio de empleo / ingreso** | Cambio en ingresos (−20%), meses sin ingreso al inicio (0) | Modifica los créditos desde el mes 1; los meses sin ingreso tienen créditos en 0. |
| **Aumento de gastos** | Aumento en gastos (+15%) | Multiplica los débitos. |
| **Comprar auto nuevo** | Precio (350,000 MXN), enganche (20%), plazo (48 meses), tasa (13%), gasto mensual del auto (2,500 MXN) | Enganche como salida única en el mes 1; crédito por el resto con propósito `Auto` (cuota mensual y P(impago)); gasto mensual del auto durante todo el horizonte. |
| **Cambiarse de vivienda (renta)** | Renta actual (6,000 MXN), renta nueva (8,000 MXN), mudanza y depósito (15,000 MXN) | Diferencia de renta sumada a los débitos cada mes; mudanza y depósito como salida única en el mes 1. |

La cuota se calcula con la misma fórmula de amortización francesa usada en Gold `loan_ml_dataset`.

**Ejemplo: comprar un auto de 350,000 MXN, horizonte de 24 meses.**

| Usuario | Mediana final: línea base | Mediana final: con auto | Prob. de terminar en negativo | Cuota / flujo neto típico | P(impago) del modelo |
|---|---|---|---|---|---|
| 1 | 265,418 | −44,863 | 17% → 57% | 28% | 3.6% (ingreso fuera de rango) |
| 2 | 265,269 | −45,012 | 0% → 77% | 81% | 11.1% |
| 3 | 103,772 | −206,509 | 0% → 100% | 400% | 6.8% (ingreso fuera de rango) |

---

### 7. "¿Me alcanza?" frente a "Riesgo según el modelo"

El simulador muestra dos evaluaciones **por separado**:

| Evaluación | Base | Confiabilidad |
|---|---|---|
| **¿Me alcanza?** | Flujo de efectivo real del usuario, simulado con 5,000 trayectorias. | La más confiable disponible: usa los datos del propio usuario. |
| **Riesgo según el modelo** | P(impago) del modelo reducido. | Escenario ilustrativo; se marca como poco confiable cuando hay valores fuera del rango de entrenamiento. |

**Semáforo de "¿Me alcanza?"** (probabilidad de terminar el horizonte en negativo):

| Semáforo | Probabilidad | Mensaje |
|---|---|---|
| 🟢 | ≤ 10% | Te alcanza en la mayoría de los escenarios simulados. |
| 🟡 | 10%–30% | Te alcanza con riesgo. |
| 🔴 | > 30% | No te alcanza. |

**Por qué se separan.** Ambas evaluaciones pueden contradecirse. En el ejemplo del auto, el usuario 3 no puede pagarlo (la cuota es 4 veces su flujo neto típico y termina en negativo en el 100% de las trayectorias), pero el modelo le asigna solo 6.8% de P(impago). El modelo no ve el flujo de efectivo del usuario: solo conoce edad, ingreso declarado, estado civil, dependientes y las condiciones del crédito. Además, el ingreso del usuario 3 queda fuera del rango de entrenamiento. Mostrar solo la P(impago) daría una falsa sensación de seguridad.

---

### 8. Oferta de crédito responsable

Calcula el crédito más alto que se puede ofrecer al usuario para un plazo, tasa y propósito dados. Se aplican dos reglas y se toma la cuota más restrictiva:

| Regla | Criterio (valor por defecto, ajustable) |
|---|---|
| **1. Capacidad de pago** | La cuota no supera el **30% del ingreso mensual típico** (mediana mensual de créditos, en MXN). Es la recomendación habitual en México para el pago de deudas. |
| **2. Estrés Monte Carlo** | Con la cuota, la probabilidad de terminar el plazo con flujo acumulado negativo no supera el **10%**. Como la cuota es constante, la cuota máxima es el percentil 10 del flujo acumulado de la línea base al final del plazo, dividido entre el plazo. |

El monto ofrecido se obtiene invirtiendo la fórmula de amortización: dada la cuota máxima, el monto que se puede financiar. No se ofrece crédito si el monto calculado es menor a 10,000 MXN.

**Resultados (36 meses, 15% anual):**

| Usuario | Límite por capacidad | Límite por estrés | Oferta | Regla que limita | P(impago) |
|---|---|---|---|---|---|
| 1 | 23,127 /mes | 0 /mes | No elegible | Estrés | — |
| 2 | 5,094 /mes | 8,813 /mes | **146,935 MXN** (cuota 5,094) | Capacidad de pago | 11.9% |
| 3 | 1,758 /mes | 3,122 /mes | **50,705 MXN** (cuota 1,758) | Capacidad de pago | 5.3% (ingreso y monto fuera de rango) |

- **Usuario 1:** tiene el ingreso más alto, pero sus dos meses de gasto extraordinario hacen que, aun sin crédito, tenga 12.6% de probabilidad de terminar los 36 meses en negativo, por encima del límite de 10%. La regla de estrés lo deja sin oferta; el límite es ajustable en pantalla.
- **Usuario 3:** recibe una oferta acorde con su flujo real, en lugar de un crédito que no podría pagar.

---

### 9. Renta o compra

Calcula qué vivienda podría adquirir el usuario si pagara de hipoteca **lo mismo que hoy paga de renta**.

**Parámetros (valores por defecto):** renta actual (8,000 MXN), enganche disponible (100,000 MXN), tasa hipotecaria (10.5%), plazo (20 años), gastos de escrituración (6% del precio).

**Cálculo:**

1. Cuota hipotecaria = renta actual.
2. Monto del crédito = monto financiable con esa cuota, tasa y plazo.
3. Precio de vivienda alcanzable = monto del crédito + enganche.
4. Pago inicial = enganche + escrituración, como salida única en el mes 1.
5. Patrimonio por mes = enganche + capital amortizado. Rentando, el mismo pago no genera patrimonio.

**Supuesto:** la renta actual ya está incluida en los gastos históricos, por lo que la cuota la sustituye y el flujo mensual no cambia.

**Resultado con los valores por defecto:**

| Concepto | Monto |
|---|---|
| Crédito hipotecario | 801,298 MXN |
| Vivienda alcanzable | 901,298 MXN |
| Pago inicial | 154,078 MXN |
| Patrimonio a 24 meses | 126,275 MXN (rentando: 0) |

Probabilidad de terminar los 24 meses en negativo por el pago inicial: 34% (usuario 1), 1% (usuario 2) y 95% (usuario 3).

**P(impago):** no disponible. El modelo se entrenó con plazos de 12 a 60 meses; una hipoteca a 20 años (240 meses) queda fuera de su alcance, por lo que no se muestra una probabilidad poco confiable.

---

### 10. Advertencias automáticas

| Situación | Advertencia |
|---|---|
| Ingreso, monto, plazo o tasa fuera del rango de entrenamiento del modelo | "Estimación poco confiable", indicando las variables fuera de rango. |
| Plazo mayor a 60 meses | P(impago) no disponible. |
| Renta capturada mayor que los débitos mensuales típicos del usuario | La renta no puede estar incluida en los gastos registrados; la simulación podría subestimar el impacto. Con una renta de 8,000 MXN se activa para los usuarios 2 (gastos típicos 7,872 MXN) y 3 (4,061 MXN). |

---

### 11. Verificación

| Verificación | Resultado |
|---|---|
| Amortización invertida | 100,000 MXN a 15% y 36 meses → cuota 3,466.53 → monto recalculado 100,000. |
| Saldo insoluto | 0 al terminar el plazo; igual al monto antes del primer pago. |
| Números aleatorios comunes | La mediana final baja exactamente el costo determinista del escenario (sección 5.2). |
| Interfaz (`streamlit.testing.AppTest`) | Vista "Simulador" con los 3 usuarios, los 5 escenarios combinables activos y las 3 pestañas: sin excepciones. |
| Revisión visual | Revisada en el navegador. |

---

### 12. Cómo ejecutar

Requiere los modelos de la Semana 18 en `models/`:

```powershell
python src/ml/train_loan_model.py
python src/ml/evaluate_loan_model.py
```

Dashboard:

```powershell
python -m streamlit run .\src\dashboard\app.py
```

En el menú lateral, elegir la vista **"Simulador"**.

Demo del motor en consola:

```powershell
python src/simulation/monte_carlo.py
```

---

### 13. Limitaciones

1. **Pocos datos.** Solo 3 usuarios y 21 meses de historial cada uno; el bootstrap solo puede repetir los meses observados y no genera situaciones nuevas.
2. **Moneda inferida.** La conversión a MXN supone que las transacciones están en USD; ninguna fuente lo documenta.
3. **Transacciones parciales.** Las transacciones no reflejan todo el gasto e ingreso del usuario: no cuadran con el salario registrado, incluso convertidas a MXN.
4. **Sin saldo real.** Se simula el cambio acumulado desde 0.
5. **Meses independientes.** El bootstrap no modela tendencias, estacionalidad ni inflación futura.
6. **Modelo de riesgo limitado.** No ve el flujo de efectivo, no cubre plazos mayores a 60 meses y es poco confiable fuera de su rango de entrenamiento.
7. **Supuesto de vivienda.** Los escenarios de vivienda suponen que la renta actual ya está incluida en los gastos registrados.
8. **Reglas de crédito simplificadas.** La oferta usa dos reglas transparentes; no incluye historial crediticio, buró de crédito ni otras deudas del usuario.
