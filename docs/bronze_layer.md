# Bronze Layer - Delta Lake

## 1. Objetivo

La capa Bronze representa la primera capa persistente del Lakehouse del proyecto Smart Finance Coach.

Su propósito es almacenar los datos provenientes de las fuentes Raw de forma íntegra, trazable y reproducible, aplicando únicamente metadatos técnicos de ingestión y evitando transformaciones de negocio en esta etapa.

La arquitectura actual es:

Raw CSV → PySpark → Bronze Delta Lake → Silver

---

## 2. Tecnología utilizada

La capa Bronze utiliza:

- Apache Spark 3.5.5
- PySpark
- Delta Lake 3.2.0
- Docker Compose

Delta Lake se configuró sobre Spark mediante el archivo:

`config/spark-defaults.conf`

con las siguientes propiedades principales:

- `spark.jars.packages`
- `spark.jars.ivy`
- `spark.sql.extensions`
- `spark.sql.catalog.spark_catalog`

Esto permite utilizar Delta Lake directamente desde los procesos ejecutados con `spark-submit`.

---

## 3. Estructura de la capa Bronze

La estructura actual es:

```text
data/bronze/
├── users/
├── transactions/
├── loans/
└── economic/
    ├── cpi/
    ├── interest_rate/
    └── exchange_rate/