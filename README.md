# Smart Finance Coach

## Descripción

Smart Finance Coach es un proyecto de Data Engineering orientado al desarrollo de un Gemelo Digital Financiero Personal.

El sistema busca integrar información financiera proveniente de diferentes fuentes para construir una vista 360° del usuario, permitiendo analizar su situación financiera, calcular indicadores clave, evaluar riesgos y simular diferentes escenarios financieros.

El proyecto utiliza una arquitectura Lakehouse basada en el modelo Medallion, organizando los datos en las capas Bronze, Silver y Gold.

## Problema

La información financiera de una persona puede encontrarse distribuida entre diferentes fuentes, dificultando obtener una visión integral y confiable de su situación financiera.

Además, disponer de los datos no necesariamente permite tomar mejores decisiones si no existen mecanismos para analizarlos, calcular indicadores, identificar riesgos y simular escenarios futuros.

Smart Finance Coach busca resolver estos problemas mediante una plataforma de datos que centralice, procese y transforme la información financiera en conocimiento útil para la toma de decisiones.

## Objetivo general

Diseñar e implementar una plataforma moderna de Data Engineering que permita integrar, procesar y analizar información financiera para construir un perfil financiero 360° y generar indicadores, predicciones y simulaciones que apoyen la toma de decisiones financieras.

## Arquitectura

El proyecto utilizará una arquitectura Medallion:

- **Bronze:** almacenamiento de los datos en su formato original.
- **Silver:** limpieza, validación, estandarización e integración.
- **Gold:** generación de información preparada para análisis, KPIs, modelos predictivos y simulaciones.

Flujo general:

Fuentes de datos → Ingesta → Bronze → Silver → Gold → Analytics / ML / Simulaciones → Dashboard / Asistente IA

## Fuentes de datos

Inicialmente se contemplan cuatro dominios principales:

- Usuarios
- Transacciones financieras
- Créditos
- Indicadores económicos

Para el MVP se utilizarán datos públicos, anonimizados y/o sintéticos.

## Tecnologías

- Python
- SQL
- PySpark / Apache Spark
- Apache Airflow
- Delta Lake
- PostgreSQL
- Docker
- Git / GitHub
- Great Expectations
- Scikit-Learn / XGBoost
- Streamlit / Power BI
- LangChain / Ollama

## Estructura del proyecto

```text
smart-finance-coach/
├── config/
├── dags/
├── data/
│   ├── raw/
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── docker/
├── docs/
├── notebooks/
├── src/
│   ├── analytics/
│   ├── ingestion/
│   ├── ml/
│   ├── quality/
│   └── transformation/
├── tests/
├── .gitignore
├── docker-compose.yml
├── README.md
└── requirements.txt