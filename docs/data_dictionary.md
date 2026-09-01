# Diccionario de Datos - Smart Finance Coach

## Objetivo

Este documento describe las principales entidades, atributos y reglas de datos utilizadas en Smart Finance Coach.

El diccionario servirá como referencia para las capas Bronze, Silver y Gold y permitirá mantener consistencia en nombres, tipos de datos y reglas de calidad.

---

# 1. Users

Información demográfica y financiera básica de los usuarios del Gemelo Digital Financiero.

| Campo | Tipo objetivo | Nulo | Regla / Descripción |
|---|---|---|---|
| user_id | INTEGER | No | Identificador único del usuario |
| edad | INTEGER | No | Edad del usuario. Debe ser mayor o igual a 18 |
| salario_mensual | DECIMAL(12,2) | No | Ingreso mensual. Debe ser mayor que 0 |
| ciudad | STRING | No | Ciudad de residencia |
| estado_civil | STRING | No | Estado civil homologado |
| dependientes | INTEGER | No | Número de dependientes. Debe ser >= 0 |

### Clave primaria lógica

`user_id`

### Fuente

Dataset sintético generado mediante:

`src/ingestion/generate_users.py`

### Volumen actual

100 usuarios.

### Relación principal

`users.user_id` se utilizará para relacionar los usuarios con sus transacciones y posteriormente con información financiera adicional.

---

# 2. Transactions

Información histórica de los movimientos financieros utilizados para analizar ingresos, gastos y comportamiento financiero de los usuarios.

| Campo origen | Campo objetivo | Tipo objetivo | Nulo | Regla / Descripción |
|---|---|---|---|---|
| User ID | user_id | INTEGER | Condicional | Identificador del usuario. Los registros sin identificador no podrán utilizarse directamente para construir perfiles individuales |
| Date | fecha | DATE | No | Fecha en que ocurrió la transacción |
| Description | descripcion | STRING | No | Descripción original del movimiento |
| Amount | monto | DECIMAL(12,2) | No | Monto de la transacción. Debe ser mayor que 0 |
| Transaction Type | tipo | STRING | No | Tipo de movimiento: `debit` o `credit` |
| Category | categoria | STRING | No | Categoría financiera de la transacción |
| Account Name | cuenta | STRING | No | Cuenta asociada al movimiento |

### Clave primaria

El dataset de origen no contiene un identificador único explícito para cada transacción.

Durante las transformaciones posteriores se definirá una estrategia para generar un identificador técnico `transaction_id` sin modificar la información original almacenada en Raw.

### Fuente

`aug_personal_transactions_with_UserId.csv`

### Volumen actual

10,806 transacciones.

### Periodo

- Fecha inicial: 2018-01-01
- Fecha final: 2020-03-10
- Fechas inválidas: 0

### Calidad identificada

- Registros duplicados: 0
- User ID nulos: 10,000
- Registros con User ID válido: 806
- Usuarios identificados: 3
- Categorías identificadas: 22

El 92.54% de las transacciones no cuenta con un identificador de usuario.

Estos registros se conservarán en Raw y Bronze. Para análisis financieros individuales en Silver y Gold deberán aplicarse reglas específicas de calidad y elegibilidad.

### Relación

Cuando `user_id` sea válido:

`transactions.user_id → users.user_id`

### Reglas preliminares

- `fecha` debe ser una fecha válida.
- `monto` debe ser mayor que cero.
- `tipo` debe pertenecer al catálogo permitido.
- `categoria` no debe ser nula.
- `user_id` deberá existir en `users` cuando la transacción sea utilizada para análisis individual.
- Los registros sin `user_id` deberán identificarse mediante una regla de calidad y no mezclarse silenciosamente con los registros aptos para el Gemelo Digital.

---

# 3. Loans

Información crediticia utilizada para analizar características de los préstamos y desarrollar el modelo predictivo de riesgo de incumplimiento.

| Campo origen | Campo objetivo | Tipo objetivo | Nulo | Regla / Descripción |
|---|---|---|---|---|
| LoanID | loan_id | STRING | No | Identificador único del crédito |
| Age | edad | INTEGER | No | Edad del solicitante |
| Income | ingreso | DECIMAL(12,2) | No | Ingreso reportado. Debe ser mayor que 0 |
| LoanAmount | monto_credito | DECIMAL(12,2) | No | Monto del préstamo. Debe ser mayor que 0 |
| CreditScore | credit_score | INTEGER | No | Puntaje crediticio |
| MonthsEmployed | meses_empleado | INTEGER | No | Antigüedad laboral expresada en meses |
| NumCreditLines | numero_lineas_credito | INTEGER | No | Número de líneas de crédito |
| InterestRate | tasa_interes | DECIMAL(6,2) | No | Tasa de interés del crédito |
| LoanTerm | plazo_meses | INTEGER | No | Plazo del crédito en meses |
| DTIRatio | dti_ratio | DECIMAL(5,4) | No | Relación deuda-ingreso |
| Education | educacion | STRING | No | Nivel educativo |
| EmploymentType | tipo_empleo | STRING | No | Situación laboral |
| MaritalStatus | estado_civil | STRING | No | Estado civil |
| HasMortgage | tiene_hipoteca | BOOLEAN | No | Indica si posee hipoteca |
| HasDependents | tiene_dependientes | BOOLEAN | No | Indica si tiene dependientes |
| LoanPurpose | proposito_credito | STRING | No | Propósito del préstamo |
| HasCoSigner | tiene_aval | BOOLEAN | No | Indica si existe cofirmante o aval |
| Default | default | INTEGER | No | Variable objetivo: 0 = sin incumplimiento, 1 = incumplimiento |

### Clave primaria lógica

`loan_id`

### Fuente

`Loan_default.csv`

### Volumen actual

255,347 registros.

### Calidad identificada

- Valores nulos: 0
- Registros duplicados: 0
- LoanID duplicados: 0
- Default = 0: 225,694 registros (88.39%)
- Default = 1: 29,653 registros (11.61%)

### Reglas preliminares

- `loan_id` debe ser único y no nulo.
- `edad` debe encontrarse dentro de un rango válido.
- `ingreso` debe ser mayor que cero.
- `monto_credito` debe ser mayor que cero.
- `credit_score` debe encontrarse dentro del rango esperado.
- `tasa_interes` no debe ser negativa.
- `plazo_meses` debe pertenecer al catálogo de plazos permitido.
- `dti_ratio` debe encontrarse entre 0 y 1.
- `default` únicamente puede contener 0 o 1.
- Los valores categóricos deberán homologarse durante las transformaciones.

### Consideración de integración

El dataset original no contiene el `user_id` utilizado por Smart Finance Coach.

Por esta razón, no se realizará una relación artificial directa entre los 255,347 registros y los usuarios del Gemelo Digital.

El dataset tendrá principalmente dos propósitos:

1. Entrenar y evaluar el modelo predictivo de riesgo de incumplimiento.
2. Servir como referencia para las características crediticias utilizadas posteriormente en el Gemelo Digital.

La información crediticia específica asociada a los usuarios del MVP se construirá mediante una estrategia separada y documentada.

### Consideración para Machine Learning

La variable `default` presenta desbalance de clases:

- Clase 0: 88.39%
- Clase 1: 11.61%

Este desbalance deberá considerarse posteriormente durante el entrenamiento y evaluación del modelo.

---

# 4. Economic Data

Información macroeconómica utilizada para proporcionar contexto económico a los perfiles financieros, indicadores y simulaciones de Smart Finance Coach.

La entidad se construirá a partir de tres series económicas obtenidas de FRED.

| Campo origen | Campo objetivo | Tipo objetivo | Nulo | Regla / Descripción |
|---|---|---|---|---|
| observation_date | fecha | DATE | No | Mes de referencia del indicador económico |
| MEXCPALTT01IXNBM | indice_precios | DECIMAL(12,4) | No | Índice de precios al consumidor de México |
| IRSTCI01MXM156N | tasa_interes | DECIMAL(8,4) | No | Tasa interbancaria utilizada como indicador del entorno de tasas |
| DEXMXUS | tipo_cambio | DECIMAL(10,4) | Condicional | Pesos mexicanos por dólar estadounidense |

### Fuentes

- `MEXCPALTT01IXNBM.csv`
- `IRSTCI01MXM156N.csv`
- `DEXMXUS.csv`

### Granularidad objetivo

Mensual.

El periodo utilizado por el proyecto será:

- Fecha inicial: 2018-01
- Fecha final: 2020-03
- Meses esperados: 27

### CPI / Índice de precios

La serie contiene 27 observaciones dentro del periodo del proyecto y no presenta valores nulos en dicho análisis.

El valor corresponde a un índice de precios y no directamente a una tasa porcentual de inflación.

Posteriormente podrá calcularse la inflación interanual mediante:

inflacion = ((indice_actual / indice_12_meses_atras) - 1) * 100

### Tasa de interés

La serie contiene 27 observaciones mensuales dentro del periodo del proyecto.

No se detectaron valores nulos ni registros duplicados.

La variable representa una tasa interbancaria y será utilizada como indicador del entorno de tasas de interés.

### Tipo de cambio

La serie original tiene frecuencia diaria.

Para el periodo analizado:

- Registros: 586
- Valores válidos: 560
- Valores nulos: 26
- Mínimo: 17.9705 MXN/USD
- Promedio: 19.3268 MXN/USD
- Máximo: 25.1320 MXN/USD

En Silver se calculará el promedio mensual del tipo de cambio utilizando únicamente observaciones válidas.

### Reglas preliminares

- `fecha` debe ser una fecha válida.
- Las observaciones deberán limitarse al periodo requerido.
- La granularidad final deberá ser mensual.
- No deberán existir meses duplicados en la tabla preparada.
- `indice_precios` debe ser mayor que cero.
- `tasa_interes` no debe ser negativa.
- `tipo_cambio` debe ser mayor que cero.
- Los valores nulos diarios de tipo de cambio serán excluidos del cálculo del promedio mensual.
- Los nombres técnicos de las series deberán homologarse.

### Transformación esperada

Las tres fuentes Raw serán integradas posteriormente para producir una estructura mensual:

| fecha | indice_precios | tasa_interes | tipo_cambio |
|---|---:|---:|---:|
| 2018-01-01 | ... | ... | ... |
| 2018-02-01 | ... | ... | ... |
| ... | ... | ... | ... |
| 2020-03-01 | ... | ... | ... |

### Uso dentro del proyecto

La información económica podrá utilizarse para:

- Contextualizar el comportamiento financiero de los usuarios.
- Analizar cambios en el poder adquisitivo.
- Enriquecer indicadores financieros.
- Incorporar contexto económico en simulaciones.
- Proporcionar variables adicionales para análisis predictivos.

### Estrategia de capas

**Raw:** conservará los tres CSV originales.

**Bronze:** almacenará las series manteniendo trazabilidad con la fuente.

**Silver:** homologará nombres, tipos, periodos y granularidad e integrará las tres series.

**Gold:** utilizará los indicadores económicos preparados para análisis, simulaciones y perfiles financieros.