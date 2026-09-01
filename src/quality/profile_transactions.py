import pandas as pd

file_path = "data/raw/aug_personal_transactions_with_UserId.csv"

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

print("\n=== VALORES UNICOS POR COLUMNA ===")
print(df.nunique())

print("\n=== ESTADISTICAS DE AMOUNT ===")
print(df["Amount"].describe())

print("\n=== TIPOS DE TRANSACCION ===")
print(df["Transaction Type"].value_counts(dropna=False))

print("\n=== CATEGORIAS ===")
print(df["Category"].value_counts(dropna=False))

print("\n=== USUARIOS ===")
print(df["User ID"].value_counts(dropna=False).sort_index())

print("\n=== RANGO DE FECHAS ===")

dates = pd.to_datetime(df["Date"], errors="coerce")

print(f"Fecha mínima: {dates.min()}")
print(f"Fecha máxima: {dates.max()}")
print(f"Fechas inválidas: {dates.isnull().sum()}")