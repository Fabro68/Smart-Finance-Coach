# Silver Layer

## 1. Objetivo

La capa Silver del proyecto Smart Finance Coach transforma los datos almacenados en Bronze hacia estructuras limpias, tipadas y estandarizadas que puedan utilizarse posteriormente para análisis, construcción de KPIs, modelos de Machine Learning y generación de la capa Gold.

El flujo implementado durante la Semana 9 es:

Raw CSV → Bronze Delta Lake → PySpark Transformations → Silver Delta Lake

En Silver se aplican principalmente:

- Conversión de tipos de datos.
- Estandarización de nombres de columnas.
- Conversión y normalización de fechas.
- Generación de identificadores.
- Validación de registros.
- Integración de fuentes económicas.
- Conservación controlada de problemas de calidad conocidos.
- Escritura de las tablas mediante Delta Lake.

---

## 2. Silver Users

Ruta de origen:

`data/bronze/users`

Ruta de destino:

`data/silver/users`

Script de transformación:

`src/transformation/silver_users.py`

Script de validación:

`src/quality/validate_silver_users.py`

La transformación de usuarios convierte los atributos provenientes de Bronze a tipos apropiados para análisis.

Principales transformaciones:

- `user_id` → integer
- `edad` → integer
- `salario_mensual` → double
- `ciudad` → string
- `estado_civil` → string
- `dependientes` → integer
- Eliminación de duplicados mediante `user_id`.
- Incorporación de `_silver_timestamp`.

Resultado:

- 100 registros procesados.
- 100 usuarios únicos.
- Esquema estandarizado y tipado.
- Tabla almacenada en formato Delta Lake.

---

## 3. Silver Transactions

Ruta de origen:

`data/bronze/transactions`

Ruta de destino:

`data/silver/transactions`

Script de transformación:

`src/transformation/silver_transactions.py`

Script de validación:

`src/quality/validate_silver_transactions.py`

Las columnas originales del dataset fueron estandarizadas para facilitar su utilización en las siguientes capas.

Ejemplos:

- `User ID` → `user_id`
- `Date` → `fecha`
- `Description` → `descripcion`
- `Amount` → `monto`
- `Transaction Type` → `tipo`
- `Category` → `categoria`
- `Account Name` → `cuenta`

Durante la transformación se detectó que las fechas del dataset utilizaban el formato:

`M/d/yyyy`

El formato fue corregido durante la transformación a Silver, obteniendo fechas válidas para los 10,806 registros.

También se generó un identificador `transaction_id` mediante SHA-256 utilizando los atributos principales de cada transacción.

Adicionalmente se creó:

`is_user_linked`

Este indicador permite distinguir las transacciones que pueden relacionarse con un usuario.

Resultados de calidad:

- Total de transacciones: 10,806.
- `transaction_id` únicos: 10,806.
- Duplicados de `transaction_id`: 0.
- Fechas nulas: 0.
- Transacciones asociadas a usuario: 806.
- Transacciones sin `user_id`: 10,000.

Los registros sin usuario no fueron eliminados ni imputados artificialmente. Se conservan como un problema de calidad conocido para mantener la trazabilidad de la fuente original.

---

## 4. Silver Loans

Ruta de origen:

`data/bronze/loans`

Ruta de destino:

`data/silver/loans`

Script de transformación:

`src/transformation/silver_loans.py`

Script de validación:

`src/quality/validate_silver_loans.py`

El dataset de créditos fue estandarizado mediante PySpark para utilizar nombres consistentes y tipos adecuados.

Algunos atributos principales son:

- `loan_id`
- `age`
- `income`
- `loan_amount`
- `credit_score`
- `months_employed`
- `num_credit_lines`
- `interest_rate`
- `loan_term`
- `dti_ratio`
- `loan_purpose`
- `default`

También se conservaron los metadatos provenientes de Bronze:

- `_ingestion_timestamp`
- `_source_file`

y se agregó:

- `_silver_timestamp`

Resultados:

- Total de créditos: 255,347.
- `loan_id` únicos: 255,347.
- Duplicados de `loan_id`: 0.
- Transformación completada correctamente en Delta Lake.

Este dataset será utilizado principalmente para el desarrollo posterior del modelo de riesgo de incumplimiento.

No se establece una relación artificial entre estos créditos y los usuarios sintéticos del proyecto.

---

## 5. Silver Economic Data

La información económica proviene de tres tablas Bronze independientes:

- Índice de precios.
- Tasa de interés.
- Tipo de cambio.

Rutas Bronze:

`data/bronze/economic/cpi`

`data/bronze/economic/interest_rate`

`data/bronze/economic/exchange_rate`

Ruta Silver:

`data/silver/economic_data`

Script de transformación:

`src/transformation/silver_economic_data.py`

Script de validación:

`src/quality/validate_silver_economic_data.py`

### Índice de precios

La serie fue convertida a una estructura mensual con los campos:

- `fecha`
- `indice_precios`

También se calculó:

`inflacion_anual_pct`

La inflación anual se obtiene comparando cada valor del índice con el correspondiente a 12 meses anteriores.

El cálculo se realiza utilizando el histórico completo antes de filtrar el periodo de análisis, permitiendo conservar correctamente el rezago de 12 meses.

### Tasa de interés

La serie mensual fue estandarizada como:

`tasa_interes`

y posteriormente filtrada al periodo utilizado por el proyecto.

### Tipo de cambio

La fuente contiene observaciones diarias.

Los valores válidos fueron agrupados por mes utilizando el promedio mensual, generando:

`tipo_cambio_promedio`

Los registros sin valor de tipo de cambio no fueron imputados.

### Integración

Las tres fuentes fueron integradas utilizando `fecha` como llave temporal.

Resultado final:

- Total de registros: 27.
- Total de columnas: 6.
- Periodo: enero de 2018 a marzo de 2020.
- Valores nulos: 0.
- Granularidad: mensual.

Columnas finales:

- `fecha`
- `indice_precios`
- `inflacion_anual_pct`
- `tasa_interes`
- `tipo_cambio_promedio`
- `_silver_timestamp`

---

## 6. Tecnologías utilizadas

La construcción de Silver utiliza:

- Apache Spark 3.5.5
- PySpark
- Delta Lake 3.2.0
- Docker
- Python
- Git

Las transformaciones se ejecutan dentro del contenedor Spark del proyecto.

---

## 7. Resultado de la Semana 9

Al finalizar la Semana 9 se cuenta con cuatro dominios transformados y disponibles en Silver:

| Tabla Silver | Registros |
|---|---:|
| users | 100 |
| transactions | 10,806 |
| loans | 255,347 |
| economic_data | 27 |

La arquitectura alcanzada es:

Raw → Bronze Delta Lake → Silver Delta Lake

La capa Silver proporciona datos estandarizados y preparados para incorporar reglas de calidad más estrictas y posteriormente construir la capa Gold.

El principal problema de calidad identificado continúa siendo la ausencia de `user_id` en 10,000 de las 10,806 transacciones. Este problema se conserva de forma explícita y será considerado en el diseño analítico posterior.