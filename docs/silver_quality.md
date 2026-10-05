# Silver Data Quality

## Objetivo

La capa Silver de Smart Finance Coach tiene como objetivo transformar los datos provenientes de Bronze en datasets tipificados, consistentes, trazables y aptos para análisis posteriores.

Durante las semanas 10 y 11 se implementaron validaciones de calidad estructural, trazabilidad, auditoría e integridad relacional entre datasets.

---

## Datasets validados

Actualmente se validan los siguientes datasets de la capa Silver:

- users
- transactions
- loans
- economic_data

Además, se realiza una validación relacional entre:

- users
- transactions

---

## Resultados consolidados de calidad

Última ejecución disponible por dataset:

| Dataset | PASS | FAIL | INFO | Calidad estructural |
|---|---:|---:|---:|---:|
| economic_data | 13 | 0 | 0 | 100% |
| loans | 19 | 0 | 0 | 100% |
| transactions | 12 | 0 | 1 | 100% |
| users | 11 | 0 | 0 | 100% |
| users_transactions | 1 | 0 | 4 | 100% |

Resultado global:

- PASS checks: 56
- FAIL checks: 0
- INFO checks: 5
- Structural pass rate: 100%

---

## Validación de users

El dataset `users` valida aspectos como:

- `user_id` no nulo
- `user_id` positivo
- unicidad de `user_id`
- edad entre 18 y 100 años
- salario mensual positivo
- dependientes no negativos
- ciudad no vacía
- estado civil no vacío
- `_ingestion_timestamp` no nulo
- `_source_file` no vacío
- `_silver_timestamp` no nulo

La capa Silver conserva información de trazabilidad proveniente de Bronze.

---

## Validación de transactions

El dataset `transactions` valida aspectos estructurales como:

- identificador de transacción no nulo
- unicidad de transacciones
- fecha válida
- monto válido
- tipo de transacción
- categoría
- cuenta
- descripción
- trazabilidad de origen
- timestamp de transformación Silver
- consistencia del indicador `is_user_linked`

También se registra como información adicional el porcentaje de transacciones vinculadas a usuarios.

---

## Validación de loans

El dataset `loans` incluye validaciones relacionadas con:

- identificador único del préstamo
- edad
- ingresos
- monto del préstamo
- credit score
- meses de empleo
- líneas de crédito
- tasa de interés
- plazo
- DTI ratio
- variable Default
- educación
- tipo de empleo
- estado civil
- propósito del préstamo
- trazabilidad de origen
- timestamp Silver

---

## Validación de economic_data

El dataset económico valida:

- existencia de los 27 meses esperados
- fechas no nulas y únicas
- índice de precios válido
- inflación anual válida
- tasa de interés válida
- tipo de cambio válido
- periodo temporal esperado
- timestamp Silver

---

## Integridad relacional users - transactions

Durante la Semana 11 se agregó una validación específica para analizar la relación entre usuarios y transacciones.

Resultados:

- Usuarios: 100
- Transacciones: 10,806
- Transacciones vinculadas a usuario: 806
- Transacciones sin `user_id`: 10,000
- Transacciones vinculadas válidas: 806
- Transacciones huérfanas: 0
- Usuarios con transacciones: 3
- Usuarios sin transacciones: 97
- Porcentaje de vinculación: 7.46%
- Integridad referencial de las transacciones vinculadas: 100%

---

## Interpretación de la cobertura de identidad

El porcentaje de 7.46% de vinculación entre transacciones y usuarios no se considera un error estructural del pipeline.

El dataset de transacciones contiene una gran cantidad de registros sin `user_id`, por lo que la principal limitación es la cobertura de identidad disponible en la fuente.

Las 806 transacciones que sí cuentan con `user_id` mantienen una relación válida con usuarios existentes en Silver.

Por esta razón:

- La baja cobertura se registra como `INFO`.
- La existencia de transacciones con un `user_id` inexistente se considera un error de integridad referencial.
- Actualmente existen 0 transacciones huérfanas.

---

## Trazabilidad

La capa Silver mantiene distintos niveles de trazabilidad:

- `_ingestion_timestamp`: fecha y hora de ingreso desde Bronze.
- `_source_file`: archivo de origen.
- `_silver_timestamp`: fecha y hora de transformación a Silver.
- `pipeline_run_id`: identificador de ejecución de pipeline.
- `quality_run_id`: identificador de ejecución de validaciones de calidad.

Los resultados de calidad se almacenan en:

`data/quality/quality_results.jsonl`

Los resultados de auditoría se almacenan en:

`data/audit/pipeline_audit.jsonl`

---

## Historial con Delta Lake

Las tablas Silver utilizan Delta Lake.

Esto permite consultar:

- versiones históricas
- timestamp de cada versión
- tipo de operación
- métricas de escritura
- estado histórico de los datos

Los scripts utilizados son:

`src/quality/show_delta_history.py`

`src/quality/show_delta_version.py`

Esto permite utilizar Delta Time Travel para consultar versiones anteriores de los datasets.

---

## Limitaciones actuales

Actualmente existen las siguientes limitaciones conocidas:

1. La mayoría de las transacciones no cuenta con un `user_id`.
2. Solo 3 de los 100 usuarios tienen transacciones vinculadas.
3. El dataset de préstamos no cuenta con una relación directa con los usuarios del dataset principal.
4. Los logs de auditoría y calidad se almacenan actualmente en archivos JSON Lines locales.
5. La automatización completa del flujo de entrada hasta Gold todavía se encuentra pendiente.

Estas limitaciones se documentan explícitamente para evitar alterar o imputar relaciones que no están respaldadas por los datos originales.

---

## Próximos pasos

Los siguientes pasos del proyecto incluyen:

- automatización completa del pipeline
- preparación de datasets Gold
- generación de métricas financieras
- desarrollo del Financial Digital Twin
- simulaciones financieras
- integración de analítica predictiva
- explicación de resultados mediante GenAI
- evolución del dashboard técnico y de negocio