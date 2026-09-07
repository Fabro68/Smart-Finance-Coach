# Pipeline de Ingestión — Raw a Bronze

## 1. Objetivo

La etapa de ingestión del proyecto Smart Finance Coach tiene como objetivo trasladar los datos desde la capa Raw hacia la capa Bronze del Lakehouse.

La capa Raw conserva los archivos originales, mientras que Bronze almacena una representación estructurada mediante Delta Lake, manteniendo los datos de origen sin aplicar reglas de negocio, limpieza o transformaciones analíticas. La implementación inicial de la Semana 6 utilizó Parquet y posteriormente fue migrada a Delta Lake durante la Semana 7.

Las transformaciones de tipos, reglas de calidad, homologación e integración de fuentes se realizarán posteriormente en la capa Silver.

---

## 2. Arquitectura de ingestión

```text
Fuentes de datos
      |
      v
   RAW (CSV)
      |
      | PySpark
      v
 BRONZE (Delta Lake)
      |
      v
 SILVER
```

La ingestión es implementada mediante jobs de PySpark ejecutados dentro del servicio Spark desplegado con Docker Compose.

---

## 3. Metadatos técnicos

Durante la ingestión se agregan dos columnas técnicas a todos los datasets:

| Campo | Tipo | Descripción |
|---|---|---|
| `_ingestion_timestamp` | timestamp | Fecha y hora en la que Spark procesó el registro |
| `_source_file` | string | Archivo Raw del cual proviene el registro |

Estas columnas permiten mantener trazabilidad sobre el origen y momento de ingestión de los datos.

---

## 4. Pipelines implementados

### 4.1 Users

**Fuente Raw**

`data/raw/users.csv`

**Job**

`src/ingestion/ingest_users.py`

**Destino Bronze**

`data/bronze/users/`

**Registros ingeridos**

100

---

### 4.2 Transactions

**Fuente Raw**

`data/raw/aug_personal_transactions_with_UserId.csv`

**Job**

`src/ingestion/ingest_transactions.py`

**Destino Bronze**

`data/bronze/transactions/`

**Registros ingeridos**

10,806

En Bronze se conserva el campo `User ID` tal como se encuentra en la fuente, incluyendo valores faltantes. La estrategia de tratamiento de dichos registros será aplicada posteriormente en Silver.

---

### 4.3 Loans

**Fuente Raw**

`data/raw/Loan_default.csv`

**Job**

`src/ingestion/ingest_loans.py`

**Destino Bronze**

`data/bronze/loans/`

**Registros ingeridos**

255,347

Las columnas numéricas se conservan inicialmente como cadenas de texto para evitar alterar los datos originales durante la ingestión. La conversión de tipos y validación se realizará en Silver.

Este dataset se utilizará principalmente para el desarrollo posterior del modelo de riesgo de incumplimiento.

---

### 4.4 Economic Data

La información económica está formada por tres series independientes.

#### Consumer Price Index (CPI)

Fuente:

`data/raw/MEXCPALTT01IXNBM.csv`

Destino:

`data/bronze/economic/cpi/`

Registros:

660

#### Interest Rate

Fuente:

`data/raw/IRSTCI01MXM156N.csv`

Destino:

`data/bronze/economic/interest_rate/`

Registros:

611

#### Exchange Rate

Fuente:

`data/raw/DEXMXUS.csv`

Destino:

`data/bronze/economic/exchange_rate/`

Registros:

586

Las tres series se conservan de manera independiente en Bronze. La integración temporal, cálculo de inflación y agregación mensual del tipo de cambio se realizarán posteriormente en Silver.

---

## 5. Estructura resultante

```text
data/
├── raw/
│   ├── users.csv
│   ├── aug_personal_transactions_with_UserId.csv
│   ├── Loan_default.csv
│   ├── MEXCPALTT01IXNBM.csv
│   ├── IRSTCI01MXM156N.csv
│   └── DEXMXUS.csv
│
└── bronze/
    ├── users/
    ├── transactions/
    ├── loans/
    └── economic/
        ├── cpi/
        ├── interest_rate/
        └── exchange_rate/
```

---

## 6. Ejecución de los pipelines

Los pipelines pueden ejecutarse desde la raíz del proyecto mediante Docker Compose.

### Users

```bash
docker compose exec spark /opt/spark/bin/spark-submit /opt/project/src/ingestion/ingest_users.py
```

### Transactions

```bash
docker compose exec spark /opt/spark/bin/spark-submit /opt/project/src/ingestion/ingest_transactions.py
```

### Loans

```bash
docker compose exec spark /opt/spark/bin/spark-submit /opt/project/src/ingestion/ingest_loans.py
```

### Economic Data

```bash
docker compose exec spark /opt/spark/bin/spark-submit /opt/project/src/ingestion/ingest_economic_data.py
```

---

## 7. Validación

Durante la Semana 6, la implementación inicial en Parquet fue validada mediante los archivos _SUCCESS generados por Spark. Posteriormente, en la Semana 7, los datasets Bronze fueron migrados a Delta Lake y se validó la existencia del directorio _delta_log en cada una de las seis tablas.

Se generaron correctamente seis destinos Bronze:

- users
- transactions
- loans
- economic/cpi
- economic/interest_rate
- economic/exchange_rate

La ejecución de los pipelines finalizó correctamente sin errores de Spark.

---

## 8. Decisiones de diseño

La capa Bronze sigue el principio de preservar la información de origen con el menor nivel posible de transformación.

Por esta razón:

- No se eliminan registros por problemas de calidad.
- No se imputan valores faltantes.
- No se aplican reglas de negocio.
- No se integran todavía las diferentes fuentes.
- Se conservan inicialmente los tipos provenientes del CSV como cadenas.
- Se agregan únicamente metadatos técnicos de trazabilidad.

La limpieza, tipificación, estandarización, validación de calidad e integración serán responsabilidad de la capa Silver.

---

## 9. Resultado de la Semana 6

Al finalizar esta etapa se dispone de un pipeline reproducible de ingestión Raw → Bronze utilizando PySpark y Docker.

Las cuatro fuentes principales del proyecto se encuentran disponibles en la capa Bronze y preparadas para iniciar los procesos de transformación y calidad correspondientes a Silver.

## 10. Resultado de la semana 7

En la Semana 6, la capa Bronze se implementó inicialmente utilizando archivos Parquet. Durante la Semana 7, esta capa fue migrada a Delta Lake 3.2.0, manteniendo Parquet como formato físico de almacenamiento y agregando el transaction log (_delta_log) proporcionado por Delta Lake.