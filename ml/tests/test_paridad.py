"""Las variables que calcula la API deben ser las mismas que usó el entrenamiento (ml/datos.py)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import datos

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.models.schemas import Estacion  # noqa: E402
from app.services import prediccion_service as api  # noqa: E402

INICIO = pd.Timestamp("2026-10-14 06:00", tz="America/Bogota")
ESTACIONES = pd.DataFrame({
    "id_sensor": [1, 2, 3, 4, 5],
    "latitud": [4.60, 4.61, 4.64, 4.70, 4.52],
    "longitud": [-74.10, -74.09, -74.12, -74.04, -74.15],
})


def lecturas_con_lluvia(semilla=3, horas=8):
    """Cinco estaciones con lecturas cada 5 minutos y rachas de lluvia distintas en cada una."""
    rng = np.random.default_rng(semilla)
    tablas = []
    for id_sensor in ESTACIONES["id_sensor"]:
        total, acumulado = 0.0, []
        for i in range(horas * 12):
            if 40 < i < 70 and rng.random() < 0.6:
                total += round(rng.choice([0.1, 0.2, 0.3]), 1)
            acumulado.append(round(total, 1))
        tablas.append(pd.DataFrame({
            "id_sensor": id_sensor,
            "fecha_lectura": [INICIO + pd.Timedelta(minutes=5 * i) for i in range(len(acumulado))],
            "acumulado_dia": acumulado,
        }))
    return pd.concat(tablas, ignore_index=True)


def estacion_api(fila):
    return Estacion(
        id_sensor=int(fila.id_sensor), nombre="E", localidad="X", latitud=fila.latitud, longitud=fila.longitud,
        valor_5min=0, mm_hora=0, acumulado_dia=0, intensidad="sin_lluvia", nivel_acumulado="sin_lluvia",
        lloviendo=False, fecha_lectura=INICIO.to_pydatetime(), desactualizada=False,
    )


def test_la_api_y_el_entrenamiento_calculan_las_mismas_variables():
    lect = lecturas_con_lluvia()
    limpio = datos.limpiar_lecturas(lect)
    ejemplos = datos.construir_ejemplos(
        datos.a_pasos(datos.lluvia_por_lectura(limpio)), datos.estaciones_vecinas(ESTACIONES)
    )
    assert len(ejemplos) > 100

    estaciones_api = [estacion_api(f) for f in ESTACIONES.itertuples()]
    por_estacion = {
        int(i): [(f.to_pydatetime(), float(a)) for f, a in zip(g["fecha_lectura"], g["acumulado_dia"])]
        for i, g in lect.groupby("id_sensor")
    }
    comparados = 0
    for _, fila in ejemplos.iloc[::25].iterrows():
        est = next(e for e in estaciones_api if e.id_sensor == int(fila["id_sensor"]))
        vecinas = api.vecinas_de(est, estaciones_api)
        ahora = (fila["fin"] + pd.Timedelta(minutes=3)).tz_localize("America/Bogota").to_pydatetime()
        variables, _ = api.variables_de(
            por_estacion[est.id_sensor], [por_estacion[v.id_sensor] for v in vecinas], ahora
        )
        assert variables is not None, f"la API no pudo calcular las variables en {fila['fin']}"
        for nombre in datos.VARIABLES:
            assert variables[nombre] == pytest.approx(fila[nombre], abs=1e-9), (nombre, fila["fin"], est.id_sensor)
        comparados += 1
    assert comparados > 5


def test_las_variables_de_la_api_son_las_del_entrenamiento():
    assert api.VARIABLES == datos.VARIABLES
