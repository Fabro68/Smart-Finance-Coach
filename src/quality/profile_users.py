import pandas as pd

file_path = "data/raw/users.csv"

df = pd.read_csv(file_path)

print("=== DIMENSIONES ===")
print(f"Filas: {df.shape[0]}")
print(f"Columnas: {df.shape[1]}")

print("\n=== TIPOS DE DATOS ===")
print(df.dtypes)

print("\n=== VALORES NULOS ===")
print(df.isnull().sum())

print("\n=== REGISTROS DUPLICADOS ===")
print(df.duplicated().sum())

print("\n=== USER_ID DUPLICADOS ===")
print(df["user_id"].duplicated().sum())

print("\n=== RANGO DE EDAD ===")
print(f"Mínima: {df['edad'].min()}")
print(f"Máxima: {df['edad'].max()}")

print("\n=== SALARIO MENSUAL ===")
print(df["salario_mensual"].describe())

print("\n=== RANGO DE DEPENDIENTES ===")
print(f"Mínimo: {df['dependientes'].min()}")
print(f"Máximo: {df['dependientes'].max()}")

print("\n=== CIUDADES ===")
print(df["ciudad"].value_counts())

print("\n=== ESTADOS CIVILES ===")
print(df["estado_civil"].value_counts())