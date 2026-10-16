import pytest

from app.services import geocoding
from app.services.geocoding.base import Geocodificador, GeocodingError, Ubicacion


class Falso(Geocodificador):
    def __init__(self, nombre, resultado=None, falla=False, activo=True):
        self.nombre, self._resultado, self._falla, self._activo = nombre, resultado, falla, activo
        self.llamadas = 0

    def disponible(self):
        return self._activo

    def buscar(self, texto):
        self.llamadas += 1
        if self._falla:
            raise GeocodingError("caído")
        return self._resultado


@pytest.fixture(autouse=True)
def sin_red_ni_base(monkeypatch):
    """Aísla la caché de BD y las capas de Catastro."""
    guardado = {}
    monkeypatch.setattr(geocoding.geocache_repo, "buscar", lambda db, k: guardado.get(k))
    monkeypatch.setattr(geocoding.geocache_repo, "guardar", lambda db, k, o, u: guardado.setdefault(k, u))
    monkeypatch.setattr(geocoding.barrios, "barrio_de", lambda lat, lon: "Chapinero Central")
    monkeypatch.setattr(geocoding.barrios, "localidad_de", lambda lat, lon: "Chapinero")
    return guardado


def ubic(proveedor, **extra):
    return Ubicacion(4.65, -74.06, "dir", proveedor, **extra)


def test_normalizar_quita_tildes_y_espacios():
    assert geocoding.normalizar("  Galerías   NORTE ") == "galerias norte"


def test_usa_el_primer_proveedor_que_encuentra(monkeypatch):
    a, b = Falso("a", ubic("a")), Falso("b", ubic("b"))
    monkeypatch.setattr(geocoding, "PROVEEDORES", [a, b])
    r = geocoding.geocodificar(None, "algo")
    assert r.proveedor == "a" and b.llamadas == 0
    assert (r.barrio, r.localidad) == ("Chapinero Central", "Chapinero")


def test_pasa_al_respaldo_si_el_principal_falla_o_no_esta_disponible(monkeypatch):
    caido, sin_clave, respaldo = Falso("x", falla=True), Falso("y", activo=False), Falso("z", ubic("z"))
    monkeypatch.setattr(geocoding, "PROVEEDORES", [caido, sin_clave, respaldo])
    assert geocoding.geocodificar(None, "algo").proveedor == "z"
    assert sin_clave.llamadas == 0


def test_cache_evita_volver_a_consultar(monkeypatch):
    a = Falso("a", ubic("a"))
    monkeypatch.setattr(geocoding, "PROVEEDORES", [a])
    geocoding.geocodificar(None, "Parque de la 93")
    geocoding.geocodificar(None, "parque de la 93 ")
    assert a.llamadas == 1


def test_sin_resultado_devuelve_none(monkeypatch):
    monkeypatch.setattr(geocoding, "PROVEEDORES", [Falso("a")])
    assert geocoding.geocodificar(None, "zzz") is None


def test_error_si_todos_fallan(monkeypatch):
    monkeypatch.setattr(geocoding, "PROVEEDORES", [Falso("a", falla=True), Falso("b", falla=True)])
    with pytest.raises(GeocodingError):
        geocoding.geocodificar(None, "algo")


def test_si_uno_falla_y_el_otro_no_encuentra_se_pide_reintentar(monkeypatch):
    monkeypatch.setattr(geocoding, "PROVEEDORES", [Falso("a", falla=True), Falso("b")])
    with pytest.raises(GeocodingError):
        geocoding.geocodificar(None, "algo")
