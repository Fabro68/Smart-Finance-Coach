import csv
import random
from pathlib import Path

random.seed(42)

OUTPUT_PATH = Path("data/raw/users.csv")

ciudades = [
    "Ciudad de México",
    "Monterrey",
    "Guadalajara",
    "Puebla",
    "Querétaro"
]

estados_civiles = [
    "Soltero",
    "Casado",
    "Divorciado",
    "Union libre"
]

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT_PATH, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)

    writer.writerow([
        "user_id",
        "edad",
        "salario_mensual",
        "ciudad",
        "estado_civil",
        "dependientes"
    ])

    for user_id in range(1, 101):
        edad = random.randint(18, 65)
        salario_mensual = round(random.uniform(8000, 85000), 2)
        ciudad = random.choice(ciudades)
        estado_civil = random.choice(estados_civiles)
        dependientes = random.randint(0, 4)

        writer.writerow([
            user_id,
            edad,
            salario_mensual,
            ciudad,
            estado_civil,
            dependientes
        ])

print(f"Archivo generado correctamente: {OUTPUT_PATH}")
print("Usuarios generados: 100")