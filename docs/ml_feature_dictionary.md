# Smart Finance Coach
## Semana 17 — Diccionario de Variables para Machine Learning

### 1. Objetivo

Documentar el dataset `loan_ml_dataset`, preparado en la Semana 17 como base de entrenamiento del modelo de riesgo crediticio que se desarrollará en la Semana 18.

Para cada variable se documenta su rol, tipo, origen, justificación y riesgo de fuga de información (*data leakage*), de forma que las decisiones de Feature Engineering sean trazables y reproducibles.

---

### 2. Alcance y advertencias

- El dataset proviene de `Loan_default.csv`, una fuente pública **sin relación verificable** con los 100 usuarios del proyecto (no comparte `user_id`).
- El modelo que se entrene con este dataset será un **modelo general de riesgo crediticio**. No estima el riesgo individual de los usuarios mostrados en el dashboard.
- La probabilidad de impago que produzca el modelo **no debe confundirse** con `financial_risk_level` de `user_financial_kpis`, que es un indicador descriptivo basado en reglas.
- El proyecto es académico, utiliza datos públicos o simulados y **no constituye asesoría financiera**.

---

### 3. Linaje

```text
Loan_default.csv (Raw)
        │  src/ingestion/ingest_loans.py
        ▼
Bronze loans
        │  src/transformation/silver_loans.py
        ▼
Silver loans
        │  src/analytics/gold_loan_risk_training.py
        ▼
Gold loan_risk_training      (255,347 filas)
        │  src/analytics/gold_loan_ml_dataset.py
        ▼
Gold loan_ml_dataset         (255,347 filas)
```

**Ruta:** `data/gold/loan_ml_dataset` (Delta Lake).

**Orquestación:** tarea `gold_loan_ml_dataset` del DAG `smart_finance_end_to_end_pipeline`, que depende de `gold_loan_risk_training` y precede a `validate_gold_layer`.

**Principio aplicado:** `loan_risk_training` no se modifica; `loan_ml_dataset` se construye encima como una tabla nueva.

---

### 4. Diccionario de variables

**Roles:**

- **Llave:** identifica el registro; no se usa como variable de entrada.
- **Control:** columna técnica; no se usa como variable de entrada.
- **Objetivo:** variable a predecir.
- **Feature:** variable de entrada candidata para el modelo.

**Origen:**

- **Silver:** copiada sin cambios desde Silver `loans`.
- **Gold W14:** derivada en `gold_loan_risk_training`.
- **Gold W17:** transformada o derivada en `gold_loan_ml_dataset`.

**Correlación:** correlación de Pearson con `default` obtenida en el perfilado de la Semana 17 (`src/analytics/inspect_loan_risk_training.py`). Mide solo relación lineal.

#### 4.1. Llave, control y objetivo

| Variable | Rol | Tipo | Origen | Descripción |
|---|---|---|---|---|
| `loan_id` | Llave | Texto | Silver | Identificador único del préstamo. Único y sin nulos. |
| `split` | Control | Texto | Gold W17 | Partición asignada: `train`, `validation` o `test`. Ver sección 7. |
| `default` | Objetivo | Entero (0/1) | Silver | 1 = incumplimiento, 0 = sin incumplimiento. Tasa global: 11.6128%. |
| `gold_created_at` | Control | Timestamp | Gold W17 | Fecha de generación de la tabla. Se recalcula en cada ejecución. |

#### 4.2. Variables numéricas

| Variable | Tipo | Origen | Correlación | Justificación | Riesgo de fuga |
|---|---|---|---|---|---|
| `age` | Entero | Silver | -0.168 | Segunda variable con mayor relación lineal. Rango 18–69. | Bajo |
| `income` | Numérico | Silver | -0.099 | Capacidad de pago del solicitante (ingreso anual). | Bajo |
| `loan_amount` | Numérico | Silver | +0.087 | Tamaño de la obligación solicitada. | Bajo |
| `loan_to_income_ratio` | Numérico | Gold W14 | +0.179 | `loan_amount / income`. Mayor relación lineal del dataset. | Bajo |
| `estimated_monthly_payment` | Numérico | Gold W17 | No perfilada | Cuota mensual por amortización francesa (fórmula en sección 5.2). | **Moderado** (usa `interest_rate`) |
| `payment_to_income_ratio` | Numérico | Gold W17 | No perfilada | Cuota mensual estimada / ingreso mensual. | **Moderado** (usa `interest_rate`) |
| `credit_score` | Entero | Silver | -0.034 | Historial crediticio. Rango 300–849. | Bajo |
| `months_employed` | Entero | Silver | -0.097 | Estabilidad laboral. | Bajo |
| `num_credit_lines` | Entero | Silver | +0.028 | Exposición crediticia existente. | Bajo |
| `interest_rate` | Numérico | Silver | +0.131 | Costo del crédito, en porcentaje anual (2%–25%). | **Moderado** (ver sección 6) |
| `loan_term` | Entero | Silver | +0.0005 | Plazo en meses (12, 24, 36, 48 o 60). Sin relación lineal, se conserva para el cálculo de la cuota y para modelos no lineales. | Bajo |
| `dti_ratio` | Numérico | Silver | +0.019 | Relación deuda-ingreso reportada (0.10–0.90). | Bajo |

#### 4.3. Variables binarias

Convertidas en la Semana 17 de `Yes`/`No` a `1`/`0`.

| Variable | Tipo | Origen | Observación del perfilado | Riesgo de fuga |
|---|---|---|---|---|
| `has_mortgage` | Entero (0/1) | Gold W17 | No perfilada por separado. | Bajo |
| `has_dependents` | Entero (0/1) | Gold W17 | Default: 10.50% con dependientes vs 12.72% sin dependientes. Asociación observada; no se interpreta como causal. | Bajo |
| `has_cosigner` | Entero (0/1) | Gold W17 | Default: 10.36% con aval vs 12.87% sin aval. | Bajo |

#### 4.4. Variables categóricas multivalor

Se conservan como texto. La codificación se realizará en la Semana 18 (ver sección 5.3).

| Variable | Tipo | Origen | Observación del perfilado | Riesgo de fuga |
|---|---|---|---|---|
| `education` | Texto | Silver | No perfilada por separado. | Bajo |
| `employment_type` | Texto | Silver | Default: Unemployed 13.55% vs Full-time 9.46%. Categorías: Full-time, Part-time, Self-employed, Unemployed. | Bajo |
| `marital_status` | Texto | Silver | No perfilada por separado. | Bajo |
| `loan_purpose` | Texto | Silver | No perfilada por separado. Categorías: Auto, Business, Education, Home, Other. | Bajo |

---

### 5. Transformaciones aplicadas

#### 5.1. Columnas excluidas

| Columna en `loan_risk_training` | Motivo de exclusión |
|---|---|
| `monthly_income` | Redundante: es `income / 12`. Aporta la misma información que `income`. |
| `employment_years` | Redundante: es `months_employed / 12`. |
| `gold_created_at` (original) | Columna técnica de la tabla origen. Se genera una nueva en `loan_ml_dataset`. |

#### 5.2. Variables derivadas

**Cuota mensual estimada** (amortización francesa):

```text
r = interest_rate / 1200        (tasa mensual; interest_rate está en % anual)
n = loan_term                   (número de pagos mensuales)

estimated_monthly_payment = loan_amount * r / (1 - (1 + r)^(-n))
```

Si `r = 0`, se usa `loan_amount / n`.

**Ratio cuota sobre ingreso:**

```text
payment_to_income_ratio = estimated_monthly_payment / (income / 12)
```

Si `income <= 0`, el valor queda en `NULL`. En los datos actuales no hay nulos.

#### 5.3. Codificación de categóricas

- **Binarias** (`has_mortgage`, `has_dependents`, `has_cosigner`): codificadas a 1/0 en Gold.
- **Multivalor** (`education`, `employment_type`, `marital_status`, `loan_purpose`): se mantienen como texto. El One-Hot Encoding se hará en la Semana 18 dentro del pipeline de entrenamiento, ajustado **solo con el split `train`**, para que las categorías y su tratamiento no dependan de los datos de validación o prueba.

---

### 6. Riesgo de fuga en `interest_rate`

En un proceso de crédito real, la tasa de interés suele fijarse **después** de que el banco evalúa el riesgo del solicitante. Si es así, `interest_rate` contiene en parte la propia evaluación de riesgo del banco, y un modelo que la use podría estar aprendiendo esa decisión en lugar del riesgo subyacente.

El dataset no documenta cómo se asignó la tasa, por lo que no puede confirmarse ni descartarse este efecto. Las variables derivadas `estimated_monthly_payment` y `payment_to_income_ratio` heredan el mismo riesgo.

**Decisión:** las tres variables se conservan en el dataset. En la Semana 18 se entrenará el modelo **con y sin** estas variables y se compararán los resultados antes de elegir la configuración final.

---

### 7. Estrategia de partición (split)

La columna `split` se asigna de forma **determinista y estratificada** por `default`:

1. Se calcula `xxhash64(loan_id)` como orden pseudoaleatorio estable.
2. Dentro de cada clase de `default`, se calcula `percent_rank()` sobre ese hash.
3. Se asigna `train` si el rango es menor que 0.70, `validation` si es menor que 0.85 y `test` en otro caso.

**Propiedades:**

- **Reproducible:** el mismo `loan_id` cae siempre en el mismo split, sin depender de una semilla ni del orden de lectura.
- **Estratificado:** cada split conserva la proporción de incumplimiento global.

**Resultado verificado:**

| Split | Filas | % filas | Tasa de default |
|---|---|---|---|
| train | 178,743 | 70% | 11.6128% |
| validation | 38,302 | 15% | 11.6130% |
| test | 38,302 | 15% | 11.6130% |

**Uso previsto en la Semana 18:**

- `train`: ajuste del modelo y del preprocesamiento.
- `validation`: selección de modelo e hiperparámetros.
- `test`: evaluación final, usado una sola vez.

`split` y `loan_id` **no** deben usarse como variables de entrada.

---

### 8. Validación

`src/analytics/validate_gold_layer.py` incluye 7 controles para `loan_ml_dataset`:

1. Número de filas igual al de `loan_risk_training`.
2. `loan_id` único.
3. Sin valores nulos en ninguna columna.
4. `split` solo contiene `train`, `validation` o `test`.
5. Existen los tres splits y la tasa de default de cada uno difiere menos de 0.001 de la tasa global.
6. Las variables binarias solo contienen 0 o 1.
7. `estimated_monthly_payment` y `payment_to_income_ratio` son mayores que cero.

**Resultado de la última ejecución:** 23/23 controles de la capa Gold aprobados (16 previos + 7 nuevos).

Si algún control falla, el script termina con código de salida 1. Airflow marca la tarea `validate_gold_layer` como fallida y no se ejecuta `save_raw_state`.

---

### 9. Limitaciones

1. **Dataset sintético.** Las variables numéricas tienen distribuciones casi uniformes, poco habituales en datos reales. Es probable que el desempeño alcanzable sea modesto.
2. **Relaciones lineales débiles.** La correlación más alta con `default` es +0.179 (`loan_to_income_ratio`). Modelos no lineales podrían capturar más señal, pero no se debe esperar una separación fuerte entre clases.
3. **Montos altos frente al ingreso.** La mediana de `payment_to_income_ratio` es 0.68 y el máximo cercano a 18. La fórmula es correcta; el valor refleja montos de préstamo muy altos respecto al ingreso, otra señal de datos sintéticos.
4. **Desbalance de clases.** Solo 11.61% de los préstamos incumplen. La accuracy no es una métrica adecuada (un modelo que siempre predice 0 obtendría 88.4%).
5. **Asociaciones no causales.** Diferencias como la menor tasa de default con dependientes son asociaciones observadas en este dataset y no deben interpretarse como relaciones causales.
6. **Sin relación con los usuarios del proyecto.** Las predicciones de este modelo no describen a los usuarios del dashboard.

---

### 10. Pendientes para la Semana 18

- Entrenar con y sin `interest_rate`, `estimated_monthly_payment` y `payment_to_income_ratio` (sección 6).
- Entrenar el modelo reducido (sección 11) y comparar su desempeño con el del modelo completo.
- Usar métricas adecuadas al desbalance, como PR-AUC, ROC-AUC, recall y precisión de la clase 1, en lugar de accuracy.
- Ajustar el One-Hot Encoding solo con el split `train`.
- Actualizar la sección de préstamos de `docs/data_dictionary.md`: los nombres de Silver en el código están en inglés (`age`, `income`, `loan_amount`…) y no en español, y `has_cosigner` llega a Gold como texto `Yes`/`No`, no como BOOLEAN.

---

### 11. Puente hacia los usuarios del proyecto

#### 11.1. Contexto

La propuesta del proyecto pide estimar una probabilidad de impago a partir del perfil del usuario. El dataset de préstamos no comparte llave con los usuarios, por lo que no es posible entrenar un modelo con datos reales de impago de esos usuarios.

La alternativa adoptada es aplicar a los usuarios un modelo entrenado con el dataset de préstamos, usando únicamente las variables que pueden obtenerse de forma justificada desde su perfil, y presentar el resultado como un escenario ilustrativo.

#### 11.2. Decisiones (Semana 17)

| # | Decisión | Justificación |
|---|---|---|
| 1 | **Dos modelos.** Un modelo completo, con todas las variables, para la evaluación del riesgo crediticio general (Semana 18). Un modelo reducido, solo con variables obtenibles del usuario y parámetros del escenario, para aplicarlo a los usuarios en el simulador (Semana 19). | El modelo completo usa toda la información disponible. El modelo reducido evita llenar con supuestos las variables que los usuarios no tienen. Comparar ambos cuantifica cuánto se pierde al usar menos variables. |
| 2 | **`Union libre` se trata como `Married`.** | El dataset de préstamos solo tiene `Single`, `Married` y `Divorced`. La unión libre es una convivencia en pareja con efectos económicos similares al matrimonio. Es un supuesto documentado. |
| 3 | **El salario se convierte de MXN a USD con el tipo de cambio de cada mes** (`monthly_macro_context.average_exchange_rate`). El perfil estático usa el último mes disponible. | Los ingresos de usuarios y de préstamos están en monedas distintas (ver 11.4). El tipo de cambio mensual refleja las condiciones de cada periodo. |

#### 11.3. Mapeo de variables

| Variable del modelo | Fuente para el usuario | Regla |
|---|---|---|
| `age` | Silver `users.edad` | Directa. |
| `income` | Silver `users.salario_mensual` | `salario_mensual × 12 / tipo de cambio del mes` (USD anual). |
| `marital_status` | Silver `users.estado_civil` | `Soltero` → `Single`; `Casado` → `Married`; `Divorciado` → `Divorced`; `Union libre` → `Married`. |
| `has_dependents` | Silver `users.dependientes` | `1` si `dependientes > 0`, `0` en otro caso. |
| `loan_amount` | Escenario del simulador | Parámetro capturado por el usuario. |
| `loan_term` | Escenario del simulador | Parámetro capturado por el usuario (12, 24, 36, 48 o 60 meses). |
| `interest_rate` | Escenario del simulador | Parámetro capturado por el usuario. |
| `loan_purpose` | Escenario del simulador | Parámetro capturado por el usuario. |
| `loan_to_income_ratio`, `estimated_monthly_payment`, `payment_to_income_ratio` | Derivadas | Se calculan con las mismas fórmulas de la sección 5.2 a partir de los valores anteriores. |
| `credit_score`, `months_employed`, `num_credit_lines`, `dti_ratio`, `education`, `employment_type`, `has_mortgage`, `has_cosigner` | Sin equivalente | No forman parte del modelo reducido. |

#### 11.4. Evidencia de la revisión de compatibilidad

Revisión de solo lectura sobre Silver `users` (100 usuarios) y Gold `loan_ml_dataset` (255,347 préstamos):

| Variable | Usuarios | Préstamos | Compatibilidad |
|---|---|---|---|
| Edad | 18–64 | 18–69 | Dentro del rango. |
| Estado civil | Casado 34, Divorciado 25, Soltero 21, Union libre 20 | Divorced, Married, Single | `Union libre` requiere mapeo (decisión 2). |
| Dependientes | 79% con dependientes | 50% con dependientes | Mapeo binario directo; proporciones distintas. |
| Ingreso anual | 102,644–995,825 (salario × 12, MXN) | 15,000–149,999 | Monedas distintas (decisión 3). |

**Cobertura del rango de ingreso de entrenamiento:**

| Escenario | Usuarios dentro del rango |
|---|---|
| Sin conversión de moneda | 9 de 100 (91 por encima del máximo) |
| Convertido con el tipo de cambio promedio del periodo (19.32 MXN/USD) | 76 de 100 (24 por debajo del mínimo de 15,000) |

Aun convertidos, los ingresos de los usuarios se concentran en la parte baja del rango: el máximo es 51,531 USD, frente a una mediana de 82,464 USD en préstamos.

**Usuarios con transacciones (los que se muestran en el dashboard):**

| user_id | Ingreso anual estimado (USD, tipo de cambio promedio) | Dentro del rango |
|---|---|---|
| 1 | 10,291 | No (por debajo) |
| 2 | 40,181 | Sí |
| 3 | 6,487 | No (por debajo) |

Los modelos basados en árboles (XGBoost, LightGBM) no extrapolan: un ingreso por debajo de 15,000 se trata igual que el valor mínimo visto en entrenamiento. Por eso la predicción para esos usuarios puede subestimar su riesgo sin ninguna advertencia del modelo.

#### 11.5. Supuestos

- **El salario de los usuarios está en pesos mexicanos.** Es una inferencia: los usuarios son sintéticos, están ubicados en ciudades de México y el generador (`src/ingestion/generate_users.py`) no documenta la moneda.
- **El ingreso del dataset de préstamos está en dólares estadounidenses.** Tampoco está documentado en la fuente; se infiere por el origen del dataset.
- **`Union libre` equivale a `Married`** para efectos del modelo.

#### 11.6. Reglas de uso del resultado

- La probabilidad calculada para un usuario se presenta como **escenario ilustrativo**, nunca como su riesgo crediticio real.
- Cada resultado lleva la bandera `income_outside_training_range` cuando el ingreso convertido queda fuera del rango 15,000–149,999. En ese caso, el simulador y el asistente deben indicar que la estimación es poco confiable.
- Esta probabilidad se mantiene separada de `financial_risk_level`, que es un indicador descriptivo basado en reglas.

---

### 12. Feature store por usuario (`ml_user_features`)

#### 12.1. Objetivo y alcance

`ml_user_features` es el feature store simulado del proyecto: variables de comportamiento financiero consolidadas por usuario y mes, con agregaciones temporales, contexto macroeconómico y las variables del puente hacia el modelo reducido (sección 11).

**Alcance:** demostrativo. Solo 3 de los 100 usuarios tienen transacciones vinculadas, por lo que la tabla tiene 63 filas (21 meses por usuario). **No es una base de entrenamiento** y sus resultados no deben generalizarse al resto de los usuarios.

#### 12.2. Linaje

```text
Gold user_monthly_finance ──┐
Gold monthly_macro_context ─┤  (broadcast join por year_month)
Gold user_financial_profile ┼──► src/analytics/gold_ml_user_features.py ──► Gold ml_user_features
Gold loan_ml_dataset ───────┘  (solo el rango de income del split train)
```

**Ruta:** `data/gold/ml_user_features` (Delta Lake).

**Grano:** una fila por `user_id` y `year_month`.

**Orquestación:** tarea `gold_ml_user_features` del DAG, que depende de `gold_user_monthly_finance`, `gold_monthly_macro_context`, `gold_user_financial_profile` y `gold_loan_ml_dataset`, y precede a `validate_gold_layer`.

#### 12.3. Reglas contra la fuga de información

- Todas las ventanas incluyen **solo el mes actual y meses anteriores**; nunca meses futuros.
- Las ventanas usan `rangeBetween` sobre un índice numérico de mes (`año × 12 + mes`), por lo que una ventana de 3 meses abarca 3 meses calendario aunque falte alguno.
- El z-score de anomalías compara el gasto del mes **solo contra meses previos**; el mes evaluado no forma parte de su propia referencia.
- En los primeros meses las ventanas son parciales (usan los meses disponibles). La columna `history_months` indica cuántos meses de historial existen.

#### 12.4. Diccionario de variables

**Llave y control**

| Variable | Tipo | Descripción |
|---|---|---|
| `user_id` | Entero | Usuario. |
| `year_month` | Texto | Mes (`yyyy-MM`). |
| `history_months` | Entero | Meses de historial hasta el mes actual, inclusive. |
| `gold_created_at` | Timestamp | Fecha de generación de la tabla. |

**Base mensual (trazabilidad, copiadas de `user_monthly_finance`)**

| Variable | Descripción |
|---|---|
| `consumer_spending` | Gasto de consumo del mes (débitos sin pagos de tarjeta). |
| `total_credits` | Créditos (entradas) del mes. |
| `total_debits` | Débitos (salidas) del mes. |
| `credit_card_payments` | Pagos de tarjeta de crédito del mes. |
| `transactional_balance` | `total_credits − total_debits`. |

**Comportamiento**

| Variable | Fórmula | Ventana |
|---|---|---|
| `avg_spend_3m` | Promedio de `consumer_spending` | 3 meses |
| `avg_spend_6m` | Promedio de `consumer_spending` | 6 meses |
| `spend_std_3m` | Desviación estándar muestral de `consumer_spending`; NULL con menos de 2 meses | 3 meses |
| `avg_income_3m` | Promedio de `total_credits` | 3 meses |
| `income_std_3m` | Desviación estándar muestral de `total_credits` (variabilidad del ingreso); NULL con menos de 2 meses | 3 meses |
| `spend_mom_pct` | `(gasto actual − gasto del mes anterior) / gasto del mes anterior`; NULL si el mes anterior no existe o su gasto es 0 | Mes anterior |
| `savings_rate_3m` | `(Σ créditos − Σ débitos) / Σ créditos` | 3 meses |
| `debt_payment_ratio_3m` | `Σ pagos de tarjeta / Σ créditos` (ratio de endeudamiento) | 3 meses |
| `negative_balance_months_6m` | Número de meses con `transactional_balance < 0` | 6 meses |

**Anomalías de gasto**

| Variable | Descripción |
|---|---|
| `spend_zscore` | Z-score del gasto del mes contra los meses previos del propio usuario, con piso de desviación (sección 12.5). NULL si hay menos de 3 meses previos. |
| `is_spend_anomaly` | `1` si `spend_zscore ≥ 2.0` (gasto inusualmente alto), `0` si no, `NULL` si no hay historial suficiente para evaluar. |
| `anomaly_count_6m` | Número de anomalías en los últimos 6 meses (los NULL cuentan como 0). |

**Contexto macroeconómico (de `monthly_macro_context`)**

| Variable | Descripción |
|---|---|
| `cpi_index` | Índice de precios al consumidor. |
| `annual_inflation_pct` | Inflación anual (%). |
| `macro_interest_rate` | Tasa de interés macroeconómica. Se renombra desde `interest_rate` para no confundirla con la tasa del préstamo. |
| `average_exchange_rate` | Tipo de cambio promedio del mes (MXN por USD). |

**Puente hacia el modelo reducido (sección 11)**

| Variable | Descripción |
|---|---|
| `age` | Edad del usuario (`edad`). |
| `marital_status_model` | Estado civil mapeado a las categorías del dataset de préstamos (`Union libre` → `Married`). |
| `has_dependents` | `1` si `dependientes > 0`, `0` en otro caso. |
| `salary_monthly` | Salario mensual registrado (MXN, inferido). |
| `annual_income_usd` | `salary_monthly × 12 / average_exchange_rate` del mes. |
| `income_outside_training_range` | `1` si `annual_income_usd` queda fuera del rango de `income` del split `train` de `loan_ml_dataset` (15,000–149,999). |

#### 12.5. Detección de anomalías

**Regla:**

```text
desviación efectiva = max(desviación previa, 0.20 × promedio previo)
spend_zscore        = (gasto del mes − promedio previo) / desviación efectiva
is_spend_anomaly    = 1 si spend_zscore ≥ 2.0
```

Se evalúa solo cuando hay al menos 3 meses previos. Con umbral 2.0 y piso de 20%, un mes debe superar en **al menos 40%** su promedio histórico para marcarse como anomalía. Solo se detecta gasto inusualmente alto, que es el caso relevante como alerta financiera.

**Justificación del piso de desviación:** con solo 3 meses previos y un gasto muy estable, la desviación estándar puede ser mínima y producir z-scores sin sentido. Sin piso, los 3 usuarios aparecían con anomalía en 2018-04, su primer mes evaluable. Se compararon alternativas (anomalía si z ≥ 2):

| Mes | Gasto vs promedio previo | Sin piso | Mínimo 6 meses previos | Piso 10% | **Piso 20% (elegido)** |
|---|---|---|---|---|---|
| U1 2018-04 | 1,612 vs 1,559 (+3%) | 4.20 | NULL | 0.34 | 0.17 |
| U1 2018-05 | 9,634 vs 1,572 (6×) | 285.24 | NULL | 51.27 | 25.63 |
| U1 2019-06 | 10,640 vs 2,022 (5×) | 4.39 | 4.39 | 4.39 | 4.39 |
| U2 2018-04 | 904 vs 296 (3×) | 11.37 | NULL | 11.37 | 10.25 |
| U3 2018-04 | 347 vs 256 (+35%) | 6.44 | NULL | 3.55 | 1.77 |
| U3 2018-12 | 514 vs 213 (2.4×) | 2.79 | 2.79 | 2.79 | 2.79 |
| **Total de anomalías** | | 6 | 2 | 5 | **4** |

- Sin piso se marcaba como anomalía un aumento de 3%.
- Exigir 6 meses previos perdía anomalías claras, entre ellas el pico de 2018-05.
- El piso de 20% conserva las 4 anomalías con gasto de 2.4 a 6 veces el promedio previo.

**Anomalías detectadas:**

| user_id | year_month | consumer_spending | spend_zscore |
|---|---|---|---|
| 1 | 2018-05 | 9,633.61 | 25.63 |
| 1 | 2019-06 | 10,640.00 | 4.39 |
| 2 | 2018-04 | 904.07 | 10.25 |
| 3 | 2018-12 | 514.26 | 2.79 |

Los parámetros (`ANOMALY_ZSCORE_THRESHOLD`, `ANOMALY_MIN_PRIOR_MONTHS`, `ANOMALY_STD_FLOOR_PCT`) están definidos como constantes al inicio del job.

#### 12.6. Decisiones de diseño

| Decisión | Justificación |
|---|---|
| Los ratios de ahorro y endeudamiento usan `total_credits` como denominador, no `salary_monthly`. | Salario y transacciones no están en la misma escala (sección 12.8). Comparar transacciones con transacciones mantiene la coherencia. |
| Sin forward-fill de variables macro. Si un mes no tiene datos macro, las columnas quedan en NULL y la validación hace fallar el pipeline. | Hoy los 21 meses tienen datos macro completos. Un check explícito es más simple y hace visible el problema en lugar de ocultarlo con una imputación. |
| El rango de ingreso para `income_outside_training_range` se lee del split `train` de `loan_ml_dataset`. | Se mantiene consistente con los datos que verá el modelo, sin valores fijos en el código. |
| `salary_monthly` no se usa como variable de comportamiento. | Es fijo por usuario (varianza 0). Para la variabilidad del ingreso se usa `total_credits`. |

#### 12.7. Validación

`src/analytics/validate_gold_layer.py` incluye 8 controles para `ml_user_features`:

1. Número de filas igual al de `user_monthly_finance`.
2. `(user_id, year_month)` único.
3. Sin nulos en las 4 columnas macro.
4. `has_dependents` e `income_outside_training_range` en {0, 1} sin nulos; `is_spend_anomaly` en {0, 1} o NULL.
5. `is_spend_anomaly` es NULL si y solo si hay menos de 3 meses previos.
6. `history_months` empieza en 1 y su máximo por usuario es igual a su número de meses.
7. **Sin fuga de datos:** en el primer mes de cada usuario, `avg_spend_3m` es igual a `consumer_spending` y `spend_mom_pct` es NULL.
8. `marital_status_model` sin nulos y `annual_income_usd` mayor que cero.

**Resultado de la última ejecución:** 31/31 controles de la capa Gold aprobados.

El control 5 supone meses consecutivos. Si en el futuro hubiera huecos en el historial, fallaría y obligaría a revisar la regla.

#### 12.8. Limitaciones

1. **Solo 3 usuarios.** Las variables y anomalías describen a esos 3 usuarios y no son representativas del resto.
2. **Salario y transacciones en escalas distintas.** El gasto mensual promedio representa el 14%, 0.7% y 2% del salario de los usuarios 1, 2 y 3. Un gasto de 428 frente a un salario de 64,708 (usuario 2) no es creíble. La explicación más probable es que el salario es sintético en MXN, mientras que las transacciones provienen de un dataset público, probablemente en USD, y no reflejan todo el gasto de la persona. Ninguna de las dos fuentes documenta su moneda.
   - **Impacto en KPIs existentes:** `spending_to_salary_ratio`, `estimated_margin`, `estimated_savings_capacity` y `estimated_savings_rate` de `user_monthly_finance` y `user_financial_kpis` comparan ambas fuentes y deben interpretarse con esta limitación. No se modifican porque son tablas ya validadas.
3. **Historial corto.** Con 21 meses por usuario, las desviaciones estándar y los z-scores de los primeros meses son poco estables; el piso de desviación mitiga, pero no elimina, este efecto.
4. **Ingreso fuera del rango de entrenamiento.** Los usuarios 1 y 3 quedan por debajo del rango de `income` del modelo en los 21 meses (sección 11.4).
