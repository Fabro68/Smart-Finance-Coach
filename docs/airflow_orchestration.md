# Airflow Orchestration

## 1. Objetivo

La capa de orquestación del proyecto Smart Finance Coach utiliza Apache Airflow para coordinar y monitorear la ejecución de los pipelines de ingeniería de datos.

Durante la Semana 8 se implementó la orquestación del proceso de ingesta desde la capa Raw hacia la capa Bronze del Lakehouse.

El flujo implementado es:

Raw CSV → Airflow → Docker → Apache Spark / PySpark → Bronze Delta Lake

---

## 2. Arquitectura de orquestación

El entorno se ejecuta localmente mediante Docker Compose y está compuesto por los siguientes servicios principales:

- PostgreSQL: almacena los metadatos de Airflow.
- Airflow Webserver: proporciona la interfaz web de administración y monitoreo.
- Airflow Scheduler: administra y ejecuta las tareas programadas.
- Apache Spark: ejecuta los procesos de ingesta desarrollados con PySpark.

Airflow utiliza LocalExecutor para la ejecución de tareas.

El Airflow Scheduler tiene acceso al Docker Engine del host mediante el montaje de:

/var/run/docker.sock:/var/run/docker.sock

Esto permite que las tareas de Airflow ejecuten comandos dentro del contenedor de Spark.

---

## 3. DAG principal

El DAG principal se encuentra en:

dags/bronze_ingestion_dag.py

Su identificador es:

bronze_ingestion_pipeline

El DAG coordina la ingesta de las cuatro fuentes principales del proyecto.

### Tareas

1. ingest_users
2. ingest_transactions
3. ingest_loans
4. ingest_economic_data

Las tareas ejecutan los scripts PySpark correspondientes dentro del contenedor:

smart-finance-spark

---

## 4. Flujo de ejecución

Actualmente las tareas se ejecutan de manera secuencial:

ingest_users
    ↓
ingest_transactions
    ↓
ingest_loans
    ↓
ingest_economic_data

Aunque las fuentes son independientes, se decidió utilizar ejecución secuencial durante el desarrollo local para reducir el consumo simultáneo de recursos y facilitar el monitoreo y diagnóstico de errores.

Esta estrategia puede modificarse posteriormente para permitir procesamiento paralelo en una infraestructura con mayores recursos.

---

## 5. Integración Airflow y Spark

Cada tarea utiliza BashOperator para ejecutar un proceso Spark mediante Docker.

El patrón de ejecución es:

docker exec smart-finance-spark /opt/spark/bin/spark-submit <script>

Los scripts ejecutados son:

- src/ingestion/ingest_users.py
- src/ingestion/ingest_transactions.py
- src/ingestion/ingest_loans.py
- src/ingestion/ingest_economic_data.py

Spark procesa los archivos de la capa Raw y escribe los resultados en tablas Delta Lake dentro de:

data/bronze/

---

## 6. Validación del DAG

Se verificó que Airflow detectara correctamente el DAG mediante:

docker compose exec airflow-webserver airflow dags list

También se validaron posibles errores de importación mediante:

docker compose exec airflow-webserver airflow dags list-import-errors

El resultado obtenido fue:

No data found

Esto confirma que no existen errores de importación en los DAGs registrados.

---

## 7. Prueba end-to-end

El pipeline completo se validó mediante una ejecución de prueba desde el Airflow Scheduler.

Comando utilizado:

docker compose exec airflow-scheduler airflow dags test bronze_ingestion_pipeline 2026-09-07

La ejecución completó correctamente las cuatro tareas del pipeline.

El flujo validado fue:

Airflow Scheduler
    ↓
Docker Engine
    ↓
Spark Container
    ↓
PySpark
    ↓
Delta Lake Bronze

El DAG finalizó con estado:

success

Esto demuestra que Airflow puede orquestar correctamente los procesos Spark responsables de construir la capa Bronze.

---

## 8. Logging y observabilidad

Airflow genera logs de ejecución que se almacenan dentro del contenedor en:

/opt/airflow/logs

La carpeta se encuentra montada en el host mediante Docker Compose:

./logs:/opt/airflow/logs

Se verificó la creación de logs correspondientes al DAG principal, incluyendo:

logs/scheduler/2026-09-07/bronze_ingestion_dag.py.log

La carpeta logs/ se mantiene fuera del repositorio Git mediante .gitignore, ya que contiene información generada dinámicamente durante las ejecuciones.

Estos logs permiten consultar:

- inicio y finalización de ejecuciones;
- ejecución de tareas;
- salida de procesos Spark;
- errores;
- estado de las tareas;
- estado final de los DAGs.

---

## 9. Consideración de seguridad

El montaje de /var/run/docker.sock permite al Airflow Scheduler controlar el Docker Engine del host.

Esta configuración se utiliza exclusivamente para el entorno local y académico del proyecto Smart Finance Coach debido a su simplicidad para integrar Airflow y Spark mediante Docker Compose.

No se considera una configuración recomendada para producción, debido al nivel de acceso que proporciona sobre el Docker Engine.

En un entorno productivo se deberían evaluar mecanismos de ejecución aislados y con permisos restringidos.

---

## 10. Resultado de la Semana 8

Al finalizar esta etapa se cuenta con:

- Apache Airflow operativo mediante Docker Compose.
- PostgreSQL como base de metadatos.
- Airflow Webserver y Scheduler funcionales.
- LocalExecutor configurado.
- DAG principal para la ingesta Bronze.
- Integración Airflow → Docker → Spark.
- Ejecución secuencial de las cuatro fuentes.
- Escritura de resultados en Delta Lake.
- Pipeline end-to-end validado exitosamente.
- Persistencia local de logs de Airflow.
- Logs excluidos correctamente del repositorio Git.

Con esta implementación, la capa Bronze deja de depender de la ejecución manual individual de scripts y pasa a estar controlada por una capa formal de orquestación.