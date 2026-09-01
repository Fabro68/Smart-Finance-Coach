import pandas as pd

file_path = "data/raw/Loan_default.csv"

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

print("\n=== LOAN ID DUPLICADOS ===")
print(df["LoanID"].duplicated().sum())

print("\n=== EDAD ===")
print(df["Age"].describe())

print("\n=== INGRESOS ===")
print(df["Income"].describe())

print("\n=== MONTO DEL PRESTAMO ===")
print(df["LoanAmount"].describe())

print("\n=== CREDIT SCORE ===")
print(df["CreditScore"].describe())

print("\n=== TASA DE INTERES ===")
print(df["InterestRate"].describe())

print("\n=== PLAZO DEL CREDITO ===")
print(df["LoanTerm"].value_counts().sort_index())

print("\n=== DTI RATIO ===")
print(df["DTIRatio"].describe())

print("\n=== PROPOSITO DEL CREDITO ===")
print(df["LoanPurpose"].value_counts(dropna=False))

print("\n=== TIPO DE EMPLEO ===")
print(df["EmploymentType"].value_counts(dropna=False))

print("\n=== DEFAULT ===")
print(df["Default"].value_counts(dropna=False))

print("\n=== DISTRIBUCION DEFAULT (%) ===")
print(
    df["Default"]
    .value_counts(normalize=True, dropna=False)
    .mul(100)
    .round(2)
)