"""Simulador de lluvia SINTÉTICA, solo para pruebas y demostración. NO son datos reales.

Genera tormentas que cruzan la ciudad: cada una tiene un centro que se desplaza, un tamaño, una duración y una
intensidad máxima. Como la tormenta avanza, la lluvia de una estación vecina anticipa la de la siguiente, que es
justo lo que el modelo debe aprender. Eso hace que la demostración tenga señal, pero también significa que
**las métricas obtenidas con estos datos no dicen nada del modelo en la vida real**: solo prueban que el
procedimiento funciona de punta a punta.

Uso:
    python simulador.py --estaciones ../dataset/estaciones.csv --dias 20
Escribe `data/sintetico_lecturas.csv`, `data/sintetico_estaciones.csv` y `data/sintetico_LEEME.txt`.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
PASO_MIN = 5
AVISO = (
    "DATOS SINTÉTICOS generados por ml/simulador.py. No son mediciones del SAB ni de ningún pluviómetro.\n"
    "Úsalos solo para probar el pipeline y para demostraciones. Nunca para evaluar el modelo ni como evidencia.\n"
)


def simular(estaciones: pd.DataFrame, dias: int, semilla: int = 7, inicio: str = "2026-01-01") -> pd.DataFrame:
    """Lecturas con las columnas del SAB: id_sensor, fecha_lectura, valor_5min, acumulado_dia."""
    rng = np.random.default_rng(semilla)
    lat = estaciones["latitud"].to_numpy(float)
    lon = estaciones["longitud"].to_numpy(float)
    pasos_por_dia = 24 * 60 // PASO_MIN
    n = dias * pasos_por_dia
    km_por_grado = 111.0
    x = (lon - lon.mean()) * km_por_grado * np.cos(np.radians(lat.mean()))
    y = (lat - lat.mean()) * km_por_grado

    lluvia = np.zeros((n, len(estaciones)))
    n_tormentas = max(1, int(dias * 0.6))
    for _ in range(n_tormentas):
        duracion = int(rng.integers(6, 36))  # de 30 min a 3 h
        comienzo = int(rng.integers(0, max(1, n - duracion)))
        centro = rng.uniform([x.min(), y.min()], [x.max(), y.max()])
        rumbo = rng.uniform(0, 2 * np.pi)
        velocidad = rng.uniform(0.5, 3.0)  # km por paso de 5 min
        radio = rng.uniform(2.0, 6.0)  # km
        pico = rng.choice([0.2, 0.5, 1.5, 4.0], p=[0.4, 0.3, 0.2, 0.1])  # mm por 5 min
        for t in range(duracion):
            if comienzo + t >= n:
                break
            cx = centro[0] + velocidad * t * np.cos(rumbo)
            cy = centro[1] + velocidad * t * np.sin(rumbo)
            envolvente = np.sin(np.pi * (t + 0.5) / duracion)
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            lluvia[comienzo + t] += pico * envolvente * np.exp(-d2 / (2 * radio**2))

    lluvia = np.where(lluvia < 0.05, 0.0, np.round(lluvia, 1))  # el pluviómetro no mide menos de 0,1 mm
    hora = pd.date_range(inicio, periods=n, freq=f"{PASO_MIN}min", tz="America/Bogota")
    dia = np.repeat(np.arange(dias), pasos_por_dia)
    acumulado = np.vstack([
        np.cumsum(lluvia[dia == d], axis=0) for d in range(dias)
    ])
    filas = []
    for j, id_sensor in enumerate(estaciones["id_sensor"]):
        filas.append(pd.DataFrame({
            "id_sensor": id_sensor,
            "fecha_lectura": hora,
            "valor_5min": lluvia[:, j],
            "acumulado_dia": np.round(acumulado[:, j], 1),
        }))
    return pd.concat(filas, ignore_index=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--estaciones", type=Path, required=True, help="CSV con id_sensor, latitud, longitud")
    p.add_argument("--dias", type=int, default=20)
    p.add_argument("--semilla", type=int, default=7)
    p.add_argument("--salida", type=Path, default=AQUI / "data")
    a = p.parse_args()

    estaciones = pd.read_csv(a.estaciones)[["id_sensor", "latitud", "longitud"]].dropna()
    lecturas = simular(estaciones, a.dias, a.semilla)
    a.salida.mkdir(parents=True, exist_ok=True)
    lecturas.to_csv(a.salida / "sintetico_lecturas.csv", index=False)
    estaciones.to_csv(a.salida / "sintetico_estaciones.csv", index=False)
    (a.salida / "sintetico_LEEME.txt").write_text(AVISO, encoding="utf-8")
    con_lluvia = int((lecturas["valor_5min"] > 0).sum())
    print(f"{len(lecturas)} lecturas sintéticas ({a.dias} días, {len(estaciones)} estaciones), {con_lluvia} con lluvia.")
    print(AVISO)


if __name__ == "__main__":
    main()
