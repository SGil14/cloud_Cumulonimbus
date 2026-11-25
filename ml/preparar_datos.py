"""Prepara los datos de la IA: de la tabla `lecturas` a los conjuntos de entrenamiento y prueba.

Desde la base de datos (usa DATABASE_URL del .env de la raíz o del entorno):
    python preparar_datos.py

Desde archivos CSV (por ejemplo, exportados de otra copia de la base):
    python preparar_datos.py --lecturas lecturas.csv --estaciones estaciones.csv

Escribe en `data/`: entrenamiento.csv, prueba.csv y resumen.json. Esa carpeta no se versiona.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

from datos import ETIQUETA, LINEA_BASE, PASO_MIN, PASOS_FUTURO, VARIABLES, preparar

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = Path(__file__).resolve().parent / "data"


def url_base_de_datos() -> str:
    url = os.environ.get("DATABASE_URL")
    env = RAIZ / ".env"
    if not url and env.is_file():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if linea.startswith("DATABASE_URL="):
                url = linea.split("=", 1)[1].strip()
    if not url:
        sys.exit("No se encontró DATABASE_URL. Defínela en el entorno o en el .env, o usa --lecturas y --estaciones.")
    return url


def leer_de_base_de_datos() -> tuple[pd.DataFrame, pd.DataFrame]:
    from sqlalchemy import create_engine

    engine = create_engine(url_base_de_datos())
    with engine.connect() as con:
        lecturas = pd.read_sql("SELECT id_sensor, fecha_lectura, acumulado_dia FROM lecturas", con)
        estaciones = pd.read_sql("SELECT id_sensor, latitud, longitud FROM estaciones", con)
    return lecturas, estaciones


def resumen(lecturas: pd.DataFrame, entrenamiento: pd.DataFrame, prueba: pd.DataFrame) -> dict:
    def describir(df: pd.DataFrame) -> dict:
        if df.empty:
            return {"filas": 0}
        return {
            "filas": int(len(df)),
            "estaciones": int(df["id_sensor"].nunique()),
            "desde": df["fin"].min().isoformat(),
            "hasta": df["fin"].max().isoformat(),
            "tasa_lluvia": round(float(df[ETIQUETA].mean()), 4),
        }

    return {
        "lecturas_crudas": int(len(lecturas)),
        "paso_minutos": PASO_MIN,
        "horizonte_minutos": PASO_MIN * PASOS_FUTURO,
        "variables": VARIABLES,
        "etiqueta": ETIQUETA,
        "linea_base": LINEA_BASE,
        "entrenamiento": describir(entrenamiento),
        "prueba": describir(prueba),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lecturas", type=Path, help="CSV con id_sensor, fecha_lectura, acumulado_dia")
    p.add_argument("--estaciones", type=Path, help="CSV con id_sensor, latitud, longitud")
    p.add_argument("--prueba", type=float, default=0.2, help="fracción más reciente que se reserva para la prueba")
    p.add_argument("--corte", help="fecha (AAAA-MM-DD, hora de Bogotá) desde la que empieza la prueba; reemplaza a --prueba")
    p.add_argument("--salida", type=Path, default=SALIDA)
    args = p.parse_args()

    if bool(args.lecturas) != bool(args.estaciones):
        p.error("--lecturas y --estaciones se usan juntos")
    if args.lecturas:
        lecturas, estaciones = pd.read_csv(args.lecturas), pd.read_csv(args.estaciones)
    else:
        lecturas, estaciones = leer_de_base_de_datos()

    sintetico = bool(args.lecturas) and args.lecturas.name.startswith("sintetico")
    entrenamiento, prueba = preparar(lecturas, estaciones, args.prueba, args.corte)
    if entrenamiento.empty or prueba.empty:
        sys.exit(
            "No hay suficientes datos continuos para armar los conjuntos. "
            "Se necesitan varias horas de lecturas seguidas (el recolector debe haber estado encendido)."
        )

    args.salida.mkdir(parents=True, exist_ok=True)
    entrenamiento.to_csv(args.salida / "entrenamiento.csv", index=False)
    prueba.to_csv(args.salida / "prueba.csv", index=False)
    datos = resumen(lecturas, entrenamiento, prueba)
    datos["sintetico"] = sintetico
    if sintetico:
        print("AVISO: datos sintéticos. Sirven para probar y demostrar, no para evaluar el modelo.", file=sys.stderr)
    (args.salida / "resumen.json").write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(datos, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
