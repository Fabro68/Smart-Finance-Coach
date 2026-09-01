# Perfilado de Datos - Datos Económicos

## Descripción
Conjunto de series económicas utilizadas para proporcionar contexto macroeconómico al proyecto Smart Finance Coach.

Las series fueron obtenidas de FRED y cubren variables relevantes para el análisis financiero:

- Índice de Precios al Consumidor de México.
- Tasa de interés interbancaria.
- Tipo de cambio MXN/USD.

El periodo de análisis del proyecto es enero de 2018 a marzo de 2020.

## Serie CPI / INPC

### Archivo
MEXCPALTT01IXNBM.csv

### Dimensiones
- Registros totales: 660
- Columnas: 2

### Rango temporal
- Fecha mínima: 1969-01-01
- Fecha máxima: 2023-12-01
- Fechas inválidas: 0

### Calidad
- Valores nulos: 0
- Registros duplicados: 0
- Registros dentro del periodo del proyecto: 27

### Estadísticas del periodo
- Mínimo: 98.795
- Promedio: 102.594
- Máximo: 106.889

La serie representa un índice de precios y no directamente una tasa porcentual de inflación.

## Serie de tasa de interés

### Archivo
IRSTCI01MXM156N.csv

### Dimensiones
- Registros totales: 611
- Columnas: 2

### Rango temporal
- Fecha mínima: 1975-08-01
- Fecha máxima: 2026-06-01
- Fechas inválidas: 0

### Calidad
- Valores nulos: 0
- Registros duplicados: 0
- Registros dentro del periodo del proyecto: 27

### Estadísticas del periodo
- Mínimo: 4.69
- Promedio: 5.60
- Máximo: 6.58

La serie corresponde a una tasa interbancaria y será utilizada como indicador del entorno de tasas de interés.

## Serie de tipo de cambio

### Archivo
DEXMXUS.csv

### Dimensiones
- Registros: 586
- Columnas: 2

### Rango temporal
- Fecha mínima: 2018-01-02
- Fecha máxima: 2020-03-31
- Fechas inválidas: 0

### Calidad
- Valores nulos en DEXMXUS: 26
- Registros duplicados: 0

### Estadísticas
- Valores válidos: 560
- Mínimo: 17.9705
- Promedio: 19.3268
- Máximo: 25.1320

La serie representa pesos mexicanos por dólar estadounidense y tiene frecuencia diaria.

## Problemas y consideraciones identificadas

1. Las tres series tienen frecuencias diferentes.
2. CPI y tasa de interés tienen frecuencia mensual.
3. El tipo de cambio tiene frecuencia diaria.
4. El tipo de cambio contiene 26 observaciones sin valor.
5. Las series utilizan nombres técnicos que deberán homologarse.
6. El CPI deberá transformarse posteriormente si se requiere calcular inflación porcentual.

## Reglas preliminares para Silver

- `observation_date` debe convertirse a fecha.
- No deben existir fechas inválidas.
- Las series deben limitarse al periodo requerido por el proyecto.
- El tipo de cambio deberá agregarse a frecuencia mensual.
- Los valores nulos del tipo de cambio no deberán utilizarse en el cálculo del promedio mensual.
- Las tres series deberán homologarse a una misma granularidad mensual.
- Los nombres de columnas deberán estandarizarse.

## Modelo objetivo

La información económica preparada tendrá una estructura similar a:

| Campo | Descripción |
|---|---|
| fecha | Mes de referencia |
| indice_precios | Índice de precios al consumidor |
| tasa_interes | Tasa interbancaria |
| tipo_cambio | Promedio mensual MXN/USD |

Posteriormente podrá añadirse una variable de inflación calculada a partir del índice de precios.

## Estrategia de capas

**Raw:** conservará las tres series originales sin modificaciones.

**Bronze:** ingerirá y almacenará las series preservando la información de origen.

**Silver:** filtrará el periodo, homologará fechas, agregará el tipo de cambio a frecuencia mensual y aplicará reglas de calidad.

**Gold:** utilizará estas variables como contexto macroeconómico para indicadores, simulaciones y análisis financieros.