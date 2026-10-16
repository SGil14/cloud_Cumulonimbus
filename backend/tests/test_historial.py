from datetime import datetime, timedelta

from app.core.tiempo import BOGOTA_TZ
from app.services import historial_service as h

AHORA = datetime(2026, 10, 14, 12, 14, tzinfo=BOGOTA_TZ)


def local(hora, dia=14):
    """Como llega de PostgreSQL: hora local sin zona."""
    return datetime(2026, 10, dia, hora, 0)


def test_ventana_por_hora_incluye_la_hora_actual():
    v = h.ventana("6h", AHORA)
    assert v.paso == "hora" and len(v.intervalos) == 6
    assert v.intervalos[0].hour == 7 and v.intervalos[-1].hour == 12
    assert v.intervalos[0].utcoffset() == timedelta(hours=-5)


def test_ventana_por_dia_empieza_a_medianoche():
    v = h.ventana("7d", AHORA)
    assert v.paso == "dia" and len(v.intervalos) == 7
    assert v.intervalos[-1] == datetime(2026, 10, 14, 0, 0, tzinfo=BOGOTA_TZ)
    assert v.intervalos[0] == datetime(2026, 10, 8, 0, 0, tzinfo=BOGOTA_TZ)


def test_serie_promedia_estaciones_y_marca_sin_datos():
    v = h.ventana("6h", AHORA)
    filas = [
        (local(10), 1, "SUBA", 2.0, 5),
        (local(10), 2, "SUBA", 4.0, 5),   # promedio de la hora: 3.0
        (local(11), 1, "SUBA", 0.0, 4),
    ]
    s = h.agregar_serie(filas, v, "Suba", datos_desde=None)
    por_hora = {p.inicio.hour: p for p in s.puntos}
    assert por_hora[10].mm == 3.0 and por_hora[10].lecturas == 10
    assert por_hora[11].mm == 0.0
    assert por_hora[8].mm is None and por_hora[8].lecturas == 0   # sin datos ≠ seco
    assert s.total_mm == 3.0
    assert s.pico.inicio.hour == 10
    assert s.estaciones == 2
    assert s.cobertura_pct == 33  # 2 de 6 horas con datos


def test_serie_sin_lluvia_no_tiene_pico():
    v = h.ventana("6h", AHORA)
    s = h.agregar_serie([(local(11), 1, "SUBA", 0.0, 3)], v, "Suba", None)
    assert s.total_mm == 0 and s.pico is None


def test_serie_vacia_no_falla():
    s = h.agregar_serie([], h.ventana("24h", AHORA), "Toda Bogotá", None)
    assert s.total_mm == 0 and s.cobertura_pct == 0 and s.estaciones == 0


def test_ranking_promedia_el_total_de_cada_estacion_por_localidad():
    v = h.ventana("24h", AHORA)
    filas = [
        (local(9), 1, "SUBA", 1.0, 3), (local(10), 1, "SUBA", 2.0, 3),   # estación 1: 3.0
        (local(10), 2, "SUBA", 1.0, 3),                                   # estación 2: 1.0  → promedio 2.0
        (local(10), 3, "BOSA", 0.5, 3),
    ]
    r = h.agregar_ranking(filas, v, None)
    assert [i.localidad for i in r.items] == ["SUBA", "BOSA"]
    suba = r.items[0]
    assert (suba.total_mm, suba.max_estacion_mm, suba.estaciones) == (2.0, 3.0, 2)
