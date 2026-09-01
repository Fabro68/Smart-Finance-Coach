# Perfilado de Datos - Créditos

## Dataset
Loan_default.csv

## Descripción
Dataset público utilizado como fuente de información crediticia y como base potencial para el desarrollo del modelo predictivo de riesgo de incumplimiento del proyecto Smart Finance Coach.

## Dimensiones
- Registros: 255,347
- Columnas: 18

## Calidad de datos

### Valores nulos
No se detectaron valores nulos en ninguna de las 18 columnas.

### Registros duplicados
No se detectaron registros completamente duplicados.

### Identificador del crédito
- LoanID duplicados: 0
- LoanID puede utilizarse como identificador único del crédito.

## Variables principales

### Edad
- Mínima: 18
- Promedio: 43.50
- Máxima: 69

### Ingreso
- Mínimo: 15,000
- Promedio: 82,499.30
- Mediana: 82,466
- Máximo: 149,999

### Monto del préstamo
- Mínimo: 5,000
- Promedio: 127,578.87
- Mediana: 127,556
- Máximo: 249,999

### Credit Score
- Mínimo: 300
- Promedio: 574.26
- Máximo: 849

### Tasa de interés
- Mínima: 2%
- Promedio: 13.49%
- Máxima: 25%

### Plazo
Se identificaron los siguientes plazos:
- 12 meses
- 24 meses
- 36 meses
- 48 meses
- 60 meses

### DTI Ratio
- Mínimo: 0.10
- Promedio: 0.50
- Máximo: 0.90

## Propósito del crédito

Se identificaron cinco categorías:
- Business
- Home
- Education
- Other
- Auto

## Tipo de empleo

Se identificaron cuatro categorías:
- Part-time
- Unemployed
- Self-employed
- Full-time

## Variable objetivo: Default

- Sin incumplimiento (0): 225,694 registros — 88.39%
- Con incumplimiento (1): 29,653 registros — 11.61%

Se observa un desbalance en la variable objetivo. Esta característica deberá considerarse durante el desarrollo y evaluación del modelo predictivo de riesgo.

## Problemas y consideraciones identificadas

1. El dataset no contiene el `user_id` utilizado por las demás fuentes del proyecto.
2. La variable objetivo `Default` presenta desbalance de clases.
3. Los nombres de columnas deberán homologarse al estándar definido para Silver.
4. Las variables categóricas deberán estandarizarse antes de utilizarlas en análisis o Machine Learning.
5. La integración con los usuarios del Gemelo Digital requerirá una estrategia independiente y documentada.

## Reglas preliminares para Silver

- `LoanID` no debe ser nulo y debe ser único.
- `Age` debe encontrarse dentro de un rango válido.
- `Income` debe ser mayor que cero.
- `LoanAmount` debe ser mayor que cero.
- `CreditScore` debe encontrarse dentro del rango esperado.
- `InterestRate` debe ser mayor o igual a cero.
- `LoanTerm` debe pertenecer al catálogo de plazos permitido.
- `DTIRatio` debe encontrarse entre 0 y 1.
- `Default` únicamente puede contener 0 o 1.
- Las variables categóricas deberán pertenecer a sus catálogos definidos.

## Uso dentro del proyecto

El dataset tendrá dos usos principales:

1. Servir como fuente para el entrenamiento y evaluación del modelo predictivo de riesgo de incumplimiento.
2. Servir como referencia crediticia para construir posteriormente la información de créditos asociada a los usuarios sintéticos del Gemelo Digital.

## Estrategia de capas

**Raw:** conservará el archivo original sin modificaciones.

**Bronze:** realizará la ingestión preservando la estructura y los valores de origen.

**Silver:** aplicará tipificación, estandarización y controles de calidad.

**Gold:** utilizará las variables necesarias para indicadores financieros, características de Machine Learning y análisis de riesgo.