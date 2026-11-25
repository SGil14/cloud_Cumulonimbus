import json
import os
from datetime import datetime, timedelta

import pytest

from app.core.tiempo import BOGOTA_TZ
from app.models.schemas import Estacion
from app.services import prediccion_service as svc

AHORA = datetime(2026, 10, 14, 12, 14, tzinfo=BOGOTA_TZ)  # el instante de decisión es 12:10


def estacion(id_sensor, lat, lon, lloviendo=False, nombre=None):
    return Estacion(
        id_sensor=id_sensor, nombre=nombre or f"E{id_sensor}", localidad="Suba", latitud=lat, longitud=lon,
        valor_5min=0.1 if lloviendo else 0, mm_hora=1.2 if lloviendo else 0, acumulado_dia=0,
        intensidad="ligera" if lloviendo else "sin_lluvia", nivel_acumulado="sin_lluvia",
        lloviendo=lloviendo, fecha_lectura=AHORA, desactualizada=False,
    )


def lecturas(acumulados, cada_min=5, fin=datetime(2026, 10, 14, 12, 5, tzinfo=BOGOTA_TZ)):
    """Lecturas que terminan en `fin` (por defecto, dentro del último paso completo: 12:00-12:10), una cada `cada_min` min."""
    n = len(acumulados)
    return [(fin - timedelta(minutes=cada_min * (n - 1 - i)), a) for i, a in enumerate(acumulados)]


def modelo_de_prueba(umbral=0.5):
    return svc.Modelo(
        variables=svc.VARIABLES, media=[0.0] * 8, escala=[1.0] * 8,
        coeficientes=[2.0, 0, 0, 0, 3.0, 0, 0, 0], intercepto=-3.0, umbral=umbral,
    )


ESTACIONES = [estacion(1, 4.60, -74.10), estacion(2, 4.61, -74.10), estacion(3, 4.62, -74.09), estacion(4, 4.63, -74.08)]


def historial_seco(ids):
    return {i: lecturas([0.0] * 20) for i in ids}  # 20 lecturas de 5 min = 100 min sin lluvia


# ---------- Variables ----------

def test_la_lluvia_es_la_diferencia_del_acumulado_y_se_reinicia_a_medianoche():
    mm, acumulado = svc.lluvia_por_paso(lecturas([0.0, 0.5, 0.5, 2.0, 0.3], cada_min=2))
    assert round(sum(mm.values()), 2) == 0.5 + 1.5 + 0.3  # 2.0 -> 0.3 es un reinicio: vale lo que marca
    assert acumulado[max(acumulado)] == 0.3  # el acumulado de un paso es el de su última lectura


def test_un_historial_seco_da_variables_en_cero():
    variables, mm_60 = svc.variables_de(lecturas([0.0] * 20), [lecturas([0.0] * 20)], AHORA)
    assert mm_60 == 0
    assert variables["mm_10"] == variables["mm_60"] == variables["vecinas_mm_60"] == 0
    assert abs(variables["hora_sin"] ** 2 + variables["hora_cos"] ** 2 - 1) < 1e-9


def test_la_lluvia_reciente_se_ve_en_las_ventanas():
    # 0.1 mm cada 5 minutos durante la última hora: 12 lecturas nuevas en 6 pasos
    acumulado = [0.0] * 8 + [round(0.1 * k, 1) for k in range(1, 13)]
    variables, mm_60 = svc.variables_de(lecturas(acumulado), [lecturas([0.0] * 20)], AHORA)
    assert mm_60 == pytest.approx(1.2)
    assert variables["mm_10"] == pytest.approx(0.2) and variables["mm_30"] == pytest.approx(0.6)
    assert variables["acumulado_dia"] == pytest.approx(1.2)
    assert variables["vecinas_mm_60"] == 0


def test_un_hueco_en_la_ultima_hora_invalida_las_variables():
    corto = lecturas([0.0] * 6)  # solo 30 minutos de lecturas
    assert svc.variables_de(corto, [lecturas([0.0] * 20)], AHORA) == (None, None)


def test_sin_vecinas_con_historial_no_hay_variables():
    assert svc.variables_de(lecturas([0.0] * 20), [lecturas([0.0] * 3)], AHORA) == (None, None)


def test_las_vecinas_son_las_mas_cercanas_y_no_incluyen_a_la_propia():
    v = svc.vecinas_de(ESTACIONES[0], ESTACIONES, 2)
    assert [e.id_sensor for e in v] == [2, 3]


# ---------- Modelo ----------

def test_el_modelo_publicado_es_valido_y_coincide_con_las_variables():
    modelo = svc.cargar_modelo()
    assert modelo is not None and modelo.variables == svc.VARIABLES
    assert len(modelo.media) == len(modelo.escala) == len(modelo.coeficientes) == len(svc.VARIABLES)
    assert 0 < modelo.umbral < 1
    assert 0 <= modelo.probabilidad(dict.fromkeys(svc.VARIABLES, 0.0)) <= 1


def test_un_modelo_con_otras_variables_se_rechaza(tmp_path):
    (tmp_path / "modelo.json").write_text(json.dumps({"tipo": "regresion_logistica", "variables": ["otra"]}))
    assert svc.cargar_modelo(tmp_path) is None


def test_sin_archivo_de_modelo_no_falla(tmp_path):
    assert svc.cargar_modelo(tmp_path) is None
    assert svc.cargar_evaluacion(tmp_path) is None


def test_la_evaluacion_publicada_dice_la_verdad_sobre_la_linea_base():
    evaluacion = svc.cargar_evaluacion()
    assert evaluacion is not None
    assert evaluacion.supera_persistencia == (evaluacion.f1_modelo > evaluacion.f1_persistencia)


# ---------- Predicción y respaldos ----------

def predecir(estaciones=ESTACIONES, historial=historial_seco, modelo=None, lat=4.60, lon=-74.10):
    return svc.predecir(lat, lon, estaciones, AHORA, AHORA, historial, modelo)


def test_con_historial_usa_el_modelo_y_da_una_probabilidad():
    r = predecir(modelo=modelo_de_prueba())
    assert r.metodo == "modelo" and r.motivo_respaldo is None
    assert 0 <= r.probabilidad <= 1 and r.llovera_probable == (r.probabilidad >= 0.5)
    assert r.horizonte_minutos == 60 and r.aviso
    assert r.estaciones[0].id_sensor == 1 and r.estaciones[0].mm_60 == 0  # la elegida trae su lluvia de la hora


def test_la_lluvia_cercana_sube_la_probabilidad():
    def con_lluvia(ids):
        return {i: lecturas([0.0] * 8 + [round(0.1 * k, 1) for k in range(1, 13)]) for i in ids}

    seca = predecir(modelo=modelo_de_prueba()).probabilidad
    lloviendo = predecir(historial=con_lluvia, modelo=modelo_de_prueba()).probabilidad
    assert lloviendo > seca


def test_sin_modelo_responde_con_la_persistencia():
    r = predecir(modelo=None)
    assert r.metodo == "persistencia" and r.probabilidad is None
    assert "modelo" in r.motivo_respaldo.lower()
    assert r.llovera_probable is False


def test_la_persistencia_sigue_a_lo_que_pasa_ahora():
    lloviendo = [estacion(1, 4.60, -74.10, lloviendo=True)] + ESTACIONES[1:]
    r = predecir(estaciones=lloviendo, modelo=None)
    assert r.llovera_probable is True and r.llueve_ahora is True
    assert "siga lloviendo" in r.mensaje


def test_sin_historial_suficiente_cae_a_la_persistencia_y_lo_explica():
    r = predecir(historial=lambda ids: {}, modelo=modelo_de_prueba())
    assert r.metodo == "persistencia"
    assert "lecturas continuas" in r.motivo_respaldo


def test_si_falla_la_base_de_datos_no_falla_la_prediccion():
    def roto(ids):
        raise RuntimeError("base de datos caída")

    r = predecir(historial=roto, modelo=modelo_de_prueba())
    assert r.metodo == "persistencia" and "histórico" in r.motivo_respaldo


def test_prueba_la_siguiente_estacion_si_la_mas_cercana_no_tiene_historial():
    def historial(ids):
        return {i: lecturas([0.0] * 20) for i in ids if i != 1}  # la estación 1 no tiene lecturas

    r = predecir(historial=historial, modelo=modelo_de_prueba())
    assert r.metodo == "modelo"
    elegida = [e for e in r.estaciones if e.mm_60 is not None]
    assert [e.id_sensor for e in elegida] == [2]


# ---------- Endpoint ----------

@pytest.fixture
def cliente(monkeypatch):
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://x:x@localhost/x")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routes import prediccion
    from app.db.session import get_db
    from app.repositories import lecturas_repo
    from app.services import estaciones_service

    app = FastAPI()
    app.include_router(prediccion.router)
    app.dependency_overrides[get_db] = lambda: None
    monkeypatch.setattr(estaciones_service, "obtener_estaciones", lambda: (AHORA, ESTACIONES))
    monkeypatch.setattr(lecturas_repo, "lecturas_recientes", lambda db, ids, desde: {})
    return TestClient(app)


def test_el_endpoint_responde_y_valida_las_coordenadas(cliente):
    r = cliente.get("/api/prediccion", params={"lat": 4.6, "lon": -74.1})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["metodo"] in ("modelo", "persistencia") and cuerpo["horizonte_minutos"] == 60
    assert cliente.get("/api/prediccion", params={"lat": 99, "lon": -74.1}).status_code == 422
    assert cliente.get("/api/prediccion").status_code == 422


def test_el_endpoint_cuenta_la_prediccion_en_las_metricas(cliente):
    from app.core import metricas

    antes = metricas.IA_PREDICCIONES.labels("persistencia")._value.get()
    cliente.get("/api/prediccion", params={"lat": 4.6, "lon": -74.1})  # sin histórico: persistencia
    assert metricas.IA_PREDICCIONES.labels("persistencia")._value.get() == antes + 1
