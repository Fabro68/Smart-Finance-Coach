import pandas as pd

CPI_FILE = "data/raw/MEXCPALTT01IXNBM.csv"
RATE_FILE = "data/raw/IRSTCI01MXM156N.csv"
FX_FILE = "data/raw/DEXMXUS.csv"

cpi = pd.read_csv(CPI_FILE)
rate = pd.read_csv(RATE_FILE)
fx = pd.read_csv(FX_FILE)

datasets = {
    "CPI": cpi,
    "INTEREST_RATE": rate,
    "EXCHANGE_RATE": fx
}

for name, df in datasets.items():
    print(f"\n=== {name} ===")

    print("\nDIMENSIONES")
    print(f"Filas: {df.shape[0]}")
    print(f"Columnas: {df.shape[1]}")

    print("\nCOLUMNAS")
    print(df.columns.tolist())

    print("\nTIPOS DE DATOS")
    print(df.dtypes)

    print("\nVALORES NULOS")
    print(df.isnull().sum())

    print("\nREGISTROS DUPLICADOS")
    print(df.duplicated().sum())

    df["observation_date"] = pd.to_datetime(
        df["observation_date"],
        errors="coerce"
    )

    print("\nRANGO DE FECHAS")
    print(f"Fecha mínima: {df['observation_date'].min()}")
    print(f"Fecha máxima: {df['observation_date'].max()}")
    print(
        f"Fechas inválidas: "
        f"{df['observation_date'].isnull().sum()}"
    )

    period = df[
        (df["observation_date"] >= "2018-01-01") &
        (df["observation_date"] <= "2020-03-31")
    ]

    print("\nPERIODO DEL PROYECTO 2018-01 A 2020-03")
    print(f"Registros encontrados: {len(period)}")

    value_column = [
        col for col in df.columns
        if col != "observation_date"
    ][0]

    print("\nESTADISTICAS DEL VALOR")
    print(period[value_column].describe())