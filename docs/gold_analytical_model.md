# Smart Finance Coach
## Semana 13 — Diseño Analítico de la Capa Gold

### 1. Objetivo

Diseñar el modelo analítico de la Capa Gold del proyecto Smart Finance Coach, definiendo las estructuras de datos y métricas financieras que permitirán construir una visión 360 del usuario, analizar su comportamiento financiero y preparar información para consumo de negocio, dashboards y futuros modelos de Machine Learning.

La Capa Gold tendrá como propósito transformar los datos confiables de Silver en información analítica lista para consulta, agregación y explotación.

De acuerdo con la propuesta BBVA - Tecmilenio, la Capa Gold deberá concentrar KPIs financieros, métricas de riesgo, variables analíticas y datasets preparados para consumo de negocio e Inteligencia Artificial.

---

### 2. Alcance de la Semana 13

Durante esta semana no se construirán todavía las tablas Gold físicas.

El objetivo es definir:

- el modelo analítico;
- la granularidad de cada tabla;
- las fuentes Silver utilizadas;
- las llaves principales;
- las métricas financieras;
- las reglas de negocio;
- las limitaciones de integración entre datasets;
- las variables que posteriormente podrán utilizarse en Machine Learning.

La construcción física de las tablas Gold se realizará en la Semana 14.

---

### 3. Principios de diseño

El modelo analítico seguirá los siguientes principios:

#### 3.1. No inventar relaciones entre datasets

Solo se realizarán relaciones cuando exista una llave válida y verificable entre datasets.

El dataset de préstamos no comparte actualmente una llave de usuario con el dataset principal de usuarios. Por esta razón, no se asociarán préstamos de forma artificial con clientes específicos.

El dataset de préstamos se utilizará como fuente independiente para construir posteriormente un dataset de entrenamiento de riesgo crediticio.

#### 3.2. Diferenciar ausencia de datos de valores en cero

Un usuario sin transacciones vinculadas no debe interpretarse automáticamente como un usuario sin gastos o sin actividad financiera.

La ausencia de información se representará mediante indicadores de cobertura de datos.

#### 3.3. Evitar doble conteo financiero

Los movimientos categorizados como pagos de tarjeta de crédito no deben considerarse automáticamente como consumo adicional, ya que pueden representar el pago de gastos previamente registrados.

Estas operaciones se conservarán como movimientos financieros, pero podrán excluirse de determinadas métricas de gasto de consumo.

#### 3.4. Mantener trazabilidad hacia Silver

Cada tabla Gold deberá poder relacionarse con sus datasets Silver de origen y conservar una lógica reproducible mediante jobs de PySpark.

#### 3.5. Diseñar Gold para consumo futuro

Las estructuras deberán servir posteriormente para:

- dashboard financiero;
- KPIs ejecutivos;
- análisis de comportamiento;
- modelos predictivos;
- simulación financiera;
- asistente de IA.

---

## 4. Modelo analítico propuesto

La Capa Gold estará compuesta por varias estructuras con objetivos diferentes. Se prioriza una arquitectura simple, clara y adecuada para un MVP académico.

### 4.1. gold_user_financial_profile

**Propósito:**  
Construir una visión 360 resumida del usuario.

**Granularidad:**  
Una fila por usuario.

**Fuente principal:**  
- Silver `users`
- Silver `transactions`

**Llave principal:**  
- `user_id`

**Campos propuestos:**

- `user_id`
- `edad`
- `ciudad`
- `estado_civil`
- `dependientes`
- `salario_mensual`
- `has_transaction_data`
- `linked_transaction_count`
- `first_transaction_date`
- `last_transaction_date`
- `total_debits`
- `total_credits`
- `transactional_balance`
- `average_transaction_amount`
- `active_months`
- `primary_account`
- `top_spending_category`
- `data_coverage_status`
- `gold_created_at`

**Regla importante:**  
Los usuarios sin transacciones vinculadas no deberán interpretarse como usuarios con gasto igual a cero.

En esos casos:

- `has_transaction_data = false`
- métricas transaccionales podrán permanecer en `NULL`
- `data_coverage_status = "NO_LINKED_TRANSACTIONS"`

---

### 4.2. gold_user_monthly_finance

**Propósito:**  
Analizar la evolución financiera mensual de cada usuario.

**Granularidad:**  
Una fila por `user_id` y mes.

**Fuente principal:**  
- Silver `transactions`
- Silver `users`

**Llave compuesta:**

- `user_id`
- `year_month`

**Campos propuestos:**

- `user_id`
- `year_month`
- `salary_monthly`
- `transaction_count`
- `debit_count`
- `credit_count`
- `total_debits`
- `total_credits`
- `transactional_balance`
- `consumer_spending`
- `credit_card_payments`
- `estimated_margin`
- `spending_to_salary_ratio`
- `average_debit_amount`
- `average_credit_amount`
- `top_spending_category`
- `has_transaction_data`
- `gold_created_at`

**Reglas principales:**

`transactional_balance = total_credits - total_debits`

`estimated_margin = salary_monthly - consumer_spending`

`spending_to_salary_ratio = consumer_spending / salary_monthly`

El cálculo de gasto de consumo deberá excluir movimientos clasificados como `Credit Card Payment` para evitar considerar pagos de deuda como consumo nuevo.

---

### 4.3. gold_user_category_monthly

**Propósito:**  
Analizar el comportamiento de gasto por categoría.

**Granularidad:**  
Una fila por:

- `user_id`
- `year_month`
- `categoria`

**Fuente principal:**  
Silver `transactions`.

**Campos propuestos:**

- `user_id`
- `year_month`
- `categoria`
- `transaction_count`
- `total_amount`
- `average_amount`
- `percentage_of_monthly_spending`
- `gold_created_at`

Esta tabla permitirá identificar patrones de consumo, categorías dominantes y cambios de comportamiento.

---

### 4.4. gold_monthly_macro_context

**Propósito:**  
Proporcionar contexto macroeconómico para análisis financiero y futuros modelos predictivos.

**Granularidad:**  
Una fila por mes.

**Fuente principal:**  
Silver `economic_data`.

**Campos propuestos:**

- `year_month`
- `cpi_index`
- `interest_rate`
- `exchange_rate`
- `gold_created_at`

Esta tabla podrá relacionarse posteriormente con métricas financieras mensuales utilizando el periodo como llave temporal.

---

### 4.5. gold_loan_risk_training

**Propósito:**  
Preparar un dataset independiente para el entrenamiento del futuro modelo de riesgo crediticio.

**Granularidad:**  
Una fila por registro de préstamo.

**Fuente principal:**  
Silver `loans`.

**Consideración importante:**  
Esta tabla no se relacionará directamente con `gold_user_financial_profile`, debido a que el dataset de préstamos no contiene una llave común verificable con los usuarios del proyecto.

**Objetivo futuro:**  
Servir como dataset de entrenamiento para el modelo de Machine Learning de riesgo crediticio.

**Contenido esperado:**

- variables financieras del préstamo;
- variables demográficas;
- variables de comportamiento crediticio;
- variable objetivo de impago;
- features derivadas;
- `gold_created_at`

---

## 5. Relaciones del modelo

El modelo analítico propuesto tendrá las siguientes relaciones lógicas:

`gold_user_financial_profile`
1 ─── N
`gold_user_monthly_finance`

`gold_user_monthly_finance`
1 ─── N
`gold_user_category_monthly`

`gold_monthly_macro_context`
1 ─── N
`gold_user_monthly_finance`

mediante la relación:

`year_month`

Por otro lado:

`gold_loan_risk_training`

se mantendrá como un dominio analítico independiente orientado a Machine Learning.

---

## 6. KPIs financieros propuestos

Los KPIs definidos en esta sección serán diseñados durante la Semana 13, construidos físicamente sobre Gold en la Semana 14 y calculados formalmente durante la Semana 15.

### 6.1. Gasto mensual de consumo

**Objetivo:**  
Medir el monto total de consumo real del usuario durante un mes.

**Fórmula:**

`consumer_spending = SUM(monto de movimientos debit)`

excluyendo categorías que representan movimientos financieros y no consumo nuevo, como:

`Credit Card Payment`

**Interpretación:**  
Representa el monto aproximado destinado a consumo durante el periodo.

---

### 6.2. Movimientos de crédito registrados

**Objetivo:**  
Medir los movimientos clasificados como `credit` dentro del periodo.

**Fórmula:**

`total_credits = SUM(monto donde tipo = "credit")`

**Consideración:**  
Estos movimientos no deberán interpretarse automáticamente como ingresos salariales.

---

### 6.3. Balance transaccional

**Objetivo:**  
Medir la diferencia entre entradas y salidas registradas en las transacciones.

**Fórmula:**

`transactional_balance = total_credits - total_debits`

**Interpretación:**

- valor positivo: se registraron más créditos que débitos;
- valor negativo: se registraron más débitos que créditos.

**Limitación:**  
No representa necesariamente el saldo real de una cuenta bancaria.

---

### 6.4. Margen financiero estimado

**Objetivo:**  
Estimar cuánto del salario mensual permanecería disponible después del gasto de consumo observado.

**Fórmula:**

`estimated_margin = salary_monthly - consumer_spending`

**Interpretación:**

- valor positivo: el gasto observado se encuentra por debajo del salario mensual;
- valor negativo: el gasto de consumo observado supera el salario mensual registrado.

**Limitación:**  
No considera todas las posibles obligaciones financieras ni ingresos adicionales.

---

### 6.5. Ratio de gasto sobre salario

**Objetivo:**  
Medir qué proporción del salario mensual representa el gasto de consumo.

**Fórmula:**

`spending_to_salary_ratio = consumer_spending / salary_monthly`

**Presentación:**

`spending_to_salary_percentage = spending_to_salary_ratio * 100`

**Interpretación:**

Un valor de 0.40 equivale a que el gasto de consumo representa aproximadamente el 40% del salario mensual registrado.

---

### 6.6. Capacidad de ahorro estimada

**Objetivo:**  
Generar un indicador preliminar de la capacidad de ahorro del usuario.

**Fórmula propuesta:**

`estimated_savings_capacity = MAX(salary_monthly - consumer_spending, 0)`

**Ratio:**

`estimated_savings_rate = estimated_savings_capacity / salary_monthly`

**Interpretación:**  
Permite estimar qué porcentaje del salario podría permanecer disponible después de los gastos de consumo registrados.

**Limitación:**  
Es una aproximación y no debe interpretarse como ahorro bancario real.

---

### 6.7. Categoría principal de gasto

**Objetivo:**  
Identificar la categoría donde el usuario concentra la mayor cantidad de gasto de consumo.

**Cálculo:**

Agrupar por:

- `user_id`
- `year_month`
- `categoria`

y seleccionar la categoría con mayor `total_amount`.

**Métrica adicional:**

`top_category_spending_percentage`

representará qué porcentaje del gasto mensual corresponde a dicha categoría.

---

### 6.8. Promedio de gasto de los últimos 3 meses

**Objetivo:**  
Crear una variable temporal para analizar comportamiento y preparar futuros modelos predictivos.

**Fórmula:**

Promedio móvil del `consumer_spending` de los últimos tres meses disponibles.

**Nombre propuesto:**

`avg_consumer_spending_3m`

Esta métrica será especialmente útil durante la etapa de Feature Engineering.

---

### 6.9. Variación mensual del gasto

**Objetivo:**  
Detectar aumentos o disminuciones en el comportamiento financiero del usuario.

**Fórmula:**

`spending_change_pct = (current_month_spending - previous_month_spending) / previous_month_spending`

**Interpretación:**

- valor positivo: incremento del gasto;
- valor negativo: reducción del gasto.

---

### 6.10. Índice de cobertura de datos

**Objetivo:**  
Evitar interpretar ausencia de información como ausencia de actividad financiera.

**Campos propuestos:**

- `has_transaction_data`
- `linked_transaction_count`
- `active_months`
- `data_coverage_status`

**Estados propuestos:**

- `AVAILABLE`
- `PARTIAL`
- `NO_LINKED_TRANSACTIONS`

Este indicador acompañará las métricas financieras para mostrar la confiabilidad o disponibilidad de información de cada usuario.

---

## 7. KPI principal del MVP

El KPI principal seleccionado para el Smart Finance Coach será:

**Capacidad de ahorro estimada**

Este indicador fue elegido porque:

- puede calcularse a partir de los datos disponibles;
- es comprensible para un usuario final;
- puede visualizarse directamente en el dashboard;
- puede utilizarse posteriormente en simulaciones financieras;
- puede explicarse mediante IA Generativa;
- representa una métrica útil para el concepto de Gemelo Digital Financiero.

La capacidad de ahorro estimada se complementará con:

- gasto mensual de consumo;
- ratio de gasto sobre salario;
- balance transaccional;
- categoría principal de gasto;
- variación mensual del gasto.

---

## 8. Preparación para futuras etapas

El diseño realizado en la Semana 13 permitirá continuar con:

- **Semana 14:** construcción física de las tablas Gold;
- **Semana 15:** cálculo y validación de KPIs financieros;
- **Semana 16:** publicación del dashboard ejecutivo;
- **Semana 17:** generación de features para Machine Learning;
- **Semana 18:** modelo predictivo;
- **Semana 19:** simulador financiero;
- **Semana 20:** asistente financiero basado en IA.

---

## 9. Representación del modelo analítico

El modelo Gold propuesto se representa de forma lógica de la siguiente manera:

```text
                    SILVER
                      │
          ┌───────────┼───────────┐
          │           │           │
        users    transactions   economic_data
          │           │           │
          └──────┬────┘           │
                 │                │
                 ▼                ▼
     gold_user_financial_profile  gold_monthly_macro_context
                 │
                 │ 1:N
                 ▼
       gold_user_monthly_finance
                 │
                 │ 1:N
                 ▼
       gold_user_category_monthly


        loans
          │
          ▼
 gold_loan_risk_training
      (independiente)