"""Panel de administración: usuarios con favoritos, eliminar cuentas y estado del sistema.

Usan SQLite en memoria: no necesitan PostgreSQL.
"""

import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://ci:ci@localhost:5432/ci")
os.environ["JWT_SECRET_KEY"] = "llave-solo-para-pruebas-0123456789"
os.environ["ADMIN_CORREO"] = "jefe@ejemplo.com"
os.environ["GRAFANA_URL"] = "http://grafana.prueba:3000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.models import Estacion, Favorito, Lectura, Usuario  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

CLAVE = "Clave1234"


@pytest.fixture()
def cliente():
    get_settings.cache_clear()
    motor = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    for tabla in (Usuario, Favorito, Estacion, Lectura):
        tabla.__table__.create(motor)
    Sesion = sessionmaker(bind=motor, expire_on_commit=False)

    def _db():
        with Sesion() as db:
            yield db

    app.dependency_overrides[get_db] = _db
    c = TestClient(app)
    c.sesion = Sesion  # para sembrar datos desde las pruebas
    yield c
    app.dependency_overrides.clear()
    motor.dispose()
    get_settings.cache_clear()


def registrar(c, correo):
    r = c.post("/api/auth/registro", json={"correo": correo, "clave": CLAVE})
    assert r.status_code == 201, r.text
    return r.json()


def entrar(c, correo):
    r = c.post("/api/auth/login", json={"correo": correo, "clave": CLAVE})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def con_admin_y_ana(c):
    registrar(c, "jefe@ejemplo.com")
    ana = registrar(c, "ana@ejemplo.com")
    return entrar(c, "jefe@ejemplo.com"), entrar(c, "ana@ejemplo.com"), ana


# ---------- listado con favoritos ----------
def test_la_lista_de_usuarios_trae_cuantos_favoritos_tiene_cada_uno(cliente):
    jefe, ana_h, ana = con_admin_y_ana(cliente)
    cliente.post("/api/favoritos", json={"nombre": "Casa", "texto": "Calle 1 # 2-3"}, headers=ana_h)
    cliente.post("/api/favoritos", json={"nombre": "Trabajo", "texto": "Carrera 7 # 4-5"}, headers=ana_h)
    filas = cliente.get("/api/admin/usuarios", headers=jefe).json()
    assert {f["correo"]: f["favoritos"] for f in filas} == {"jefe@ejemplo.com": 0, "ana@ejemplo.com": 2}
    assert "clave_hash" not in filas[0]


def test_favoritos_de_un_usuario_solo_para_administradores(cliente):
    jefe, ana_h, ana = con_admin_y_ana(cliente)
    cliente.post("/api/favoritos", json={"nombre": "Casa", "texto": "Calle 1 # 2-3"}, headers=ana_h)
    lista = cliente.get(f"/api/admin/usuarios/{ana['id']}/favoritos", headers=jefe)
    assert lista.status_code == 200 and [f["nombre"] for f in lista.json()] == ["Casa"]
    assert cliente.get(f"/api/admin/usuarios/{ana['id']}/favoritos", headers=ana_h).status_code == 403
    assert cliente.get(f"/api/admin/usuarios/{ana['id']}/favoritos").status_code == 401
    assert cliente.get("/api/admin/usuarios/999/favoritos", headers=jefe).status_code == 404


# ---------- eliminar ----------
def test_el_administrador_elimina_un_usuario_y_se_van_sus_favoritos(cliente):
    jefe, ana_h, ana = con_admin_y_ana(cliente)
    cliente.post("/api/favoritos", json={"nombre": "Casa", "texto": "Calle 1 # 2-3"}, headers=ana_h)
    assert cliente.delete(f"/api/admin/usuarios/{ana['id']}", headers=jefe).status_code == 204
    assert [u["correo"] for u in cliente.get("/api/admin/usuarios", headers=jefe).json()] == ["jefe@ejemplo.com"]
    with cliente.sesion() as db:
        assert db.query(Favorito).count() == 0
    # su token ya no sirve: el usuario no existe
    assert cliente.get("/api/auth/yo", headers=ana_h).status_code == 401
    assert cliente.delete(f"/api/admin/usuarios/{ana['id']}", headers=jefe).status_code == 404


def test_no_se_puede_eliminar_la_propia_cuenta_ni_sin_ser_administrador(cliente):
    jefe, ana_h, ana = con_admin_y_ana(cliente)
    yo = cliente.get("/api/auth/yo", headers=jefe).json()["id"]
    assert cliente.delete(f"/api/admin/usuarios/{yo}", headers=jefe).status_code == 409
    assert cliente.delete(f"/api/admin/usuarios/{yo}", headers=ana_h).status_code == 403
    assert cliente.delete(f"/api/admin/usuarios/{yo}").status_code == 401


# ---------- estado ----------
def test_el_estado_resume_usuarios_lecturas_e_ia(cliente):
    jefe, ana_h, _ = con_admin_y_ana(cliente)
    ahora = datetime.now(timezone.utc)
    with cliente.sesion() as db:
        db.add(Estacion(id_sensor=1, id_estacion=1, nombre="Prueba", localidad="Suba", latitud=4.7, longitud=-74.1))
        db.flush()
        db.add_all([
            Lectura(id=1, id_sensor=1, fecha_lectura=ahora - timedelta(minutes=12), valor_5min=0, acumulado_dia=0),
            Lectura(id=2, id_sensor=1, fecha_lectura=ahora - timedelta(days=3), valor_5min=0, acumulado_dia=0),
        ])
        db.commit()
    e = cliente.get("/api/admin/estado", headers=jefe).json()
    assert (e["usuarios"], e["administradores"], e["favoritos"]) == (2, 1, 0)
    assert (e["estaciones"], e["lecturas"], e["lecturas_24h"]) == (1, 2, 1)
    assert 11 <= e["minutos_desde_ultima_lectura"] <= 13
    assert e["ia_modelo_disponible"] is True
    assert e["ia_f1_modelo"] is not None and e["ia_f1_persistencia"] is not None
    assert e["grafana_url"] == "http://grafana.prueba:3000"


def test_el_estado_sin_lecturas_no_falla_y_exige_ser_administrador(cliente):
    jefe, ana_h, _ = con_admin_y_ana(cliente)
    e = cliente.get("/api/admin/estado", headers=jefe).json()
    assert e["lecturas"] == 0 and e["ultima_lectura"] is None and e["minutos_desde_ultima_lectura"] is None
    assert cliente.get("/api/admin/estado", headers=ana_h).status_code == 403
    assert cliente.get("/api/admin/estado").status_code == 401
