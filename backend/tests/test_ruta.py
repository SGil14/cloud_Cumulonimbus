from datetime import datetime

import pytest

from app.core.tiempo import BOGOTA_TZ
from app.models.schemas import Estacion, Intensidad, NivelAcumulado
from app.services import ruta_service as r


def codificar(puntos, precision=6):
    """Codificador de polilíneas (para probar el decodificador de ida y vuelta)."""
    factor = 10 ** precision
    salida, lat0, lon0 = [], 0, 0
    for lon, lat in puntos:
        lat_i, lon_i = round(lat * factor), round(lon * factor)
        for delta in (lat_i - lat0, lon_i - lon0):
            v = ~(delta << 1) if delta < 0 else delta << 1
            while v >= 0x20:
                salida.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            salida.append(chr(v + 63))
        lat0, lon0 = lat_i, lon_i
    return "".join(salida)


def estacion(nombre, lon, lat, lloviendo=False, desactualizada=False, mm_hora=0.0):
    return Estacion(
        id_sensor=1, nombre=nombre, localidad="Suba", latitud=lat, longitud=lon, valor_5min=mm_hora / 12,
        mm_hora=mm_hora, acumulado_dia=0, intensidad=Intensidad.moderada if lloviendo else Intensidad.sin_lluvia,
        nivel_acumulado=NivelAcumulado.sin_lluvia, lloviendo=lloviendo,
        fecha_lectura=datetime(2026, 10, 14, 12, 0, tzinfo=BOGOTA_TZ), desactualizada=desactualizada,
    )


# Ruta recta de oeste a este (~11 km) por la latitud 4.65
RUTA = [(-74.10 + i * 0.01, 4.65) for i in range(11)]


def test_polilinea_ida_y_vuelta():
    puntos = [(-74.0578, 4.6563), (-74.0602, 4.6590), (-74.1100, 4.7097)]
    decodificados = r.decodificar_polilinea(codificar(puntos))
    for (lon, lat), (lon2, lat2) in zip(puntos, decodificados):
        assert lon == pytest.approx(lon2, abs=1e-6) and lat == pytest.approx(lat2, abs=1e-6)


def test_muestreo_cada_400_m_incluye_inicio_y_final():
    muestras = r.muestrear(RUTA)
    assert muestras[0].km == 0
    assert muestras[-1].km == pytest.approx(11.07, abs=0.2)
    pasos = [b.km - a.km for a, b in zip(muestras, muestras[1:-1])]
    assert all(p == pytest.approx(0.4, abs=0.01) for p in pasos)


def test_la_lluvia_en_el_centro_parte_la_ruta_en_tres_tramos():
    estaciones = [
        estacion("Oeste", -74.10, 4.65),
        estacion("Centro", -74.05, 4.65, lloviendo=True, mm_hora=12),
        estacion("Este", -74.00, 4.65),
    ]
    tramos = r.analizar(RUTA, estaciones)
    assert [t.estado for t in tramos] == ["seco", "lluvia", "seco"]
    lluvia = tramos[1]
    assert lluvia.estacion == "Centro" and lluvia.mm_hora == 12
    # los tramos están pegados: el fin de uno es el comienzo del siguiente
    assert tramos[0].coordenadas[-1] == tramos[1].coordenadas[0]
    assert tramos[1].coordenadas[-1] == tramos[2].coordenadas[0]
    assert tramos[0].desde_km == 0 and tramos[-1].hasta_km == pytest.approx(11.07, abs=0.2)


def test_lejos_de_toda_estacion_es_sin_datos_no_seco():
    tramos = r.analizar(RUTA, [estacion("Lejana", -74.50, 4.20)])
    assert [t.estado for t in tramos] == ["sin_datos"]


def test_estacion_desactualizada_no_cuenta_como_seco():
    tramos = r.analizar(RUTA, [estacion("Vieja", -74.05, 4.65, desactualizada=True)])
    assert {t.estado for t in tramos} == {"sin_datos"}


def test_resumen_con_lluvia_indica_donde():
    estaciones = [estacion("Centro", -74.05, 4.65, lloviendo=True, mm_hora=5), estacion("Borde", -74.10, 4.65)]
    tramos = r.analizar(RUTA, estaciones)
    hay, pct, texto = r.resumir(tramos, 11.07)
    assert hay and "Puede mojarte" in texto and "Centro" in texto


def test_resumen_seco_y_sin_datos():
    seco = r.analizar(RUTA, [estacion("A", -74.05, 4.65)])
    assert r.resumir(seco, 11.07)[2] == "Sin lluvia en todo el trayecto."
    hay, pct, texto = r.resumir(r.analizar(RUTA, [estacion("Lejana", -74.50, 4.20)]), 11.07)
    assert not hay and pct == 100 and "no se puede asegurar" in texto
