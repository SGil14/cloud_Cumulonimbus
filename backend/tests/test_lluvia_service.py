import json
from datetime import timedelta
from pathlib import Path

import pytest

from app.core.tiempo import BOGOTA_TZ
from app.models.schemas import EstacionSAB, Intensidad, NivelAcumulado
from app.services import lluvia_service as svc

FIXTURE = Path(__file__).parent / "fixtures" / "sab_sensores.json"


@pytest.fixture
def estaciones_sab() -> list[EstacionSAB]:
    crudos = json.loads(FIXTURE.read_text(encoding="utf-8"))["TipoSensores"]
    return [EstacionSAB.model_validate(c) for c in crudos]


def crear(valor=0.0, acumulado=0.0, fecha="2026-10-14 10:00:00.0", **extra) -> EstacionSAB:
    return EstacionSAB.model_validate({
        "IDSENSOR": extra.get("id", 1), "IDESTACION": 1, "ESTACION": extra.get("nombre", "X"),
        "LOCALIDAD": extra.get("localidad", "CHAPINERO"),
        "LATITUD": extra.get("lat", 4.65), "LONGITUD": extra.get("lon", -74.06),
        "VALORLECTURA": valor, "ACUMULADODIA": acumulado, "FECHALECTURA": fecha,
    })


@pytest.mark.parametrize("mm_5min,esperado", [
    (0, Intensidad.sin_lluvia),
    (0.1, Intensidad.ligera),       # 1.2 mm/h
    (0.3, Intensidad.moderada),     # 3.6 mm/h
    (1.0, Intensidad.fuerte),       # 12 mm/h
    (5.0, Intensidad.muy_fuerte),   # 60 mm/h
])
def test_clasificar_intensidad(mm_5min, esperado):
    assert svc.clasificar_intensidad(mm_5min) == esperado


@pytest.mark.parametrize("mm,esperado", [
    (0, NivelAcumulado.sin_lluvia),
    (10, NivelAcumulado.bajo),
    (10.1, NivelAcumulado.moderado),
    (30.1, NivelAcumulado.alto),
    (50.1, NivelAcumulado.muy_alto),
])
def test_clasificar_acumulado(mm, esperado):
    assert svc.clasificar_acumulado(mm) == esperado


def test_parseo_fixture_real(estaciones_sab):
    assert len(estaciones_sab) == 71
    est = estaciones_sab[0]
    assert est.fecha_lectura.tzinfo == BOGOTA_TZ
    assert est.localidad == "USAQUEN"


def test_lectura_vieja_no_cuenta_como_lluvia():
    est = crear(valor=0.5)
    ahora = est.fecha_lectura + timedelta(minutes=45)
    resultado = svc.a_estacion(est, ahora, minutos_vieja=30)
    assert resultado.desactualizada
    assert not resultado.lloviendo


def test_resumen_agrupa_por_localidad():
    ahora = crear().fecha_lectura
    estaciones = [
        svc.a_estacion(crear(id=1, valor=0.2, acumulado=12, localidad="SUBA"), ahora, 30),
        svc.a_estacion(crear(id=2, valor=0, acumulado=3, localidad="SUBA"), ahora, 30),
        svc.a_estacion(crear(id=3, valor=0, acumulado=1, localidad="BOSA"), ahora, 30),
    ]
    resumen = svc.construir_resumen(estaciones, ahora)
    assert resumen.estaciones_lloviendo == 1
    assert resumen.localidades_lloviendo == ["Suba"]
    suba = resumen.localidades[0]
    assert (suba.localidad, suba.acumulado_max, suba.nivel_acumulado) == ("Suba", 12, NivelAcumulado.moderado)
    assert resumen.estacion_max_acumulado.id_sensor == 1


def test_estaciones_cercanas_ordena_por_distancia():
    ahora = crear().fecha_lectura
    estaciones = [
        svc.a_estacion(crear(id=1, lat=4.70, lon=-74.05), ahora, 30),
        svc.a_estacion(crear(id=2, lat=4.60, lon=-74.08, valor=0.4), ahora, 30),
        svc.a_estacion(crear(id=3, lat=4.61, lon=-74.08), ahora, 30),
    ]
    cercania = svc.estaciones_cercanas(estaciones, 4.601, -74.08, 2, ahora)
    assert [e.id_sensor for e in cercania.estaciones] == [2, 3]
    assert cercania.lloviendo_cerca
