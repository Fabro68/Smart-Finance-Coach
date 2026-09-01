# Perfilado de Datos - Transacciones

## Dataset
aug_personal_transactions_with_UserId.csv

## Descripción
Dataset utilizado como fuente inicial de transacciones financieras para el proyecto Smart Finance Coach.

## Dimensiones
- Registros: 10,806
- Columnas: 7

## Estructura

| Campo | Tipo detectado | Descripción |
|---|---|---|
| User ID | float64 | Identificador del usuario |
| Date | string | Fecha de la transacción |
| Description | string | Descripción de la transacción |
| Amount | float64 | Monto de la transacción |
| Transaction Type | string | Tipo de movimiento (debit/credit) |
| Category | string | Categoría financiera |
| Account Name | string | Cuenta asociada a la transacción |

## Calidad de datos

### Valores nulos
- User ID: 10,000
- Resto de campos: 0

El 92.54% de las transacciones no cuenta con un identificador de usuario.

### Duplicados
No se detectaron registros completamente duplicados.

### Usuarios identificados
- Usuario 1: 264 transacciones
- Usuario 2: 366 transacciones
- Usuario 3: 176 transacciones
- Sin usuario: 10,000 transacciones

### Tipos de transacción
- debit: 5,679
- credit: 5,127

### Montos
- Mínimo: 1.00
- Promedio: 113.10
- Mediana: 96.865
- Máximo: 9,200.00

### Categorías
Se identificaron 22 categorías financieras, entre ellas:
- Groceries
- Restaurants
- Shopping
- Utilities
- Gas & Fuel
- Paycheck
- Mortgage & Rent
- Credit Card Payment
- Entertainment

## Problemas identificados

1. Alta cantidad de valores nulos en User ID.
2. User ID fue interpretado como float64 debido a la presencia de valores nulos.
3. Date fue interpretado inicialmente como texto y deberá convertirse a un tipo fecha.
4. Los nombres de columnas deberán estandarizarse para las capas posteriores.
5. Las categorías deberán analizarse y posiblemente homologarse para el modelo financiero del proyecto.

## Reglas preliminares para Silver

- user_id debe ser válido para análisis financiero individual.
- fecha debe convertirse a formato de fecha estándar.
- monto debe ser numérico y mayor que cero.
- tipo debe pertenecer al catálogo permitido.
- categoria no debe ser nula.
- los nombres de columnas deberán estandarizarse.
- se deberán controlar registros duplicados.

## Estrategia preliminar

La capa Raw conservará el dataset original sin modificaciones.

Bronze realizará la ingestión preservando la información de origen.

Silver aplicará limpieza, tipificación, estandarización y reglas de calidad.

Gold utilizará únicamente información preparada para la generación de indicadores y perfiles financieros.

### Rango temporal
- Fecha mínima: 2018-01-01
- Fecha máxima: 2020-03-10
- Fechas inválidas: 0

El dataset contiene más de dos años de historial transaccional y no se detectaron fechas inválidas, lo que permite realizar análisis temporales de ingresos, gastos y comportamiento financiero.
