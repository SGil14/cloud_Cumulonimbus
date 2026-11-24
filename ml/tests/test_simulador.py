import pandas as pd

import datos
import simulador

ESTACIONES = pd.DataFrame({
    "id_sensor": [1, 2, 3, 4],
    "latitud": [4.60, 4.62, 4.65, 4.70],
    "longitud": [-74.10, -74.08, -74.06, -74.04],
})


def test_mismas_semillas_dan_los_mismos_datos():
    a = simulador.simular(ESTACIONES, 5, semilla=3)
    b = simulador.simular(ESTACIONES, 5, semilla=3)
    assert a.equals(b)
    assert not a.equals(simulador.simular(ESTACIONES, 5, semilla=4))


def test_el_formato_es_el_del_sab_y_el_acumulado_se_reinicia_a_medianoche():
    lect = simulador.simular(ESTACIONES, 6, semilla=1)
    assert list(lect.columns) == ["id_sensor", "fecha_lectura", "valor_5min", "acumulado_dia"]
    assert (lect["valor_5min"] >= 0).all()
    e = lect[lect["id_sensor"] == 1].reset_index(drop=True)
    por_dia = e.groupby(e["fecha_lectura"].dt.date)
    for _, dia in por_dia:
        assert dia["acumulado_dia"].is_monotonic_increasing          # solo sube dentro del día
        assert abs(dia["acumulado_dia"].iloc[-1] - dia["valor_5min"].sum()) < 0.2  # y suma lo llovido
    assert e["fecha_lectura"].dt.tz is not None


def test_llueve_en_algunas_lecturas_y_en_otras_no():
    lect = simulador.simular(ESTACIONES, 20, semilla=7)
    fraccion = (lect["valor_5min"] > 0).mean()
    assert 0 < fraccion < 0.2


def test_el_pipeline_acepta_los_datos_simulados():
    lect = simulador.simular(ESTACIONES, 10, semilla=7)
    entrenamiento, prueba = datos.preparar(lect, ESTACIONES)
    assert not entrenamiento.empty and not prueba.empty
