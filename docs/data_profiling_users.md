# Perfilado de Datos - Usuarios

## Dataset
users.csv

## Descripción
Dataset sintético de usuarios generado para el proyecto Smart Finance Coach.

Su propósito es proporcionar información demográfica y financiera básica para construir el perfil 360° de cada usuario y relacionarlo posteriormente con transacciones, créditos e indicadores financieros.

Los datos fueron generados de forma reproducible utilizando una semilla fija (`random.seed(42)`).

## Dimensiones
- Registros: 100
- Columnas: 6

## Estructura

| Campo | Tipo detectado | Descripción |
|---|---|---|
| user_id | int64 | Identificador único del usuario |
| edad | int64 | Edad del usuario |
| salario_mensual | float64 | Ingreso mensual estimado |
| ciudad | string | Ciudad de residencia |
| estado_civil | string | Estado civil |
| dependientes | int64 | Número de dependientes económicos |

## Calidad de datos

### Valores nulos
No se detectaron valores nulos.

### Duplicados
No se detectaron registros completamente duplicados.

### Identificadores
- Total de usuarios: 100
- user_id duplicados: 0

Por lo tanto, `user_id` puede utilizarse como clave primaria lógica del dataset.

### Edad
- Mínima: 18 años
- Máxima: 64 años

Todos los registros se encuentran dentro del rango definido para el MVP.

### Salario mensual
- Mínimo: $8,553.69
- Promedio: $44,879.91
- Mediana: $44,986.83
- Máximo: $82,985.45

No se detectaron salarios negativos o iguales a cero.

### Dependientes
- Mínimo: 0
- Máximo: 4

### Ciudades
- Querétaro: 27
- Ciudad de México: 24
- Guadalajara: 20
- Puebla: 16
- Monterrey: 13

### Estados civiles
- Casado: 34
- Divorciado: 25
- Soltero: 21
- Unión libre: 20

## Reglas preliminares para Silver

- `user_id` no debe ser nulo.
- `user_id` debe ser único.
- `edad` debe encontrarse dentro del rango permitido.
- `salario_mensual` debe ser mayor que cero.
- `ciudad` no debe ser nula.
- `estado_civil` debe pertenecer al catálogo permitido.
- `dependientes` debe ser un número entero mayor o igual a cero.
- Los tipos de datos deberán estandarizarse antes de llegar a Silver.

## Relación con otras fuentes

`user_id` será utilizado como clave para relacionar los usuarios con sus transacciones y posteriormente con información de créditos.

Los identificadores 1, 2 y 3 son compatibles con los usuarios identificados actualmente en la fuente de transacciones.

## Estrategia de capas

**Raw:** conservará `users.csv` generado originalmente.

**Bronze:** realizará la ingestión de los registros preservando los datos de origen.

**Silver:** aplicará validaciones, tipificación y reglas de calidad.

**Gold:** combinará usuarios con transacciones, créditos e indicadores para construir el perfil financiero 360°.