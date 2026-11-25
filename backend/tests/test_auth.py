"""Autenticación, roles y favoritos.

Usan SQLite en memoria solo con las tablas de usuarios y favoritos: no necesitan PostgreSQL.
"""

import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://ci:ci@localhost:5432/ci")
os.environ["JWT_SECRET_KEY"] = "llave-solo-para-pruebas-0123456789"
os.environ["ADMIN_CORREO"] = "jefe@ejemplo.com"

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.core import seguridad  # noqa: E402
from app.db.models import Favorito, Usuario  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

CLAVE = "Clave1234"


@pytest.fixture()
def cliente():
    get_settings.cache_clear()
    motor = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Usuario.__table__.create(motor)
    Favorito.__table__.create(motor)
    Sesion = sessionmaker(bind=motor, expire_on_commit=False)

    def _db():
        with Sesion() as db:
            yield db

    app.dependency_overrides[get_db] = _db
    # Sin "with": no se ejecuta el lifespan, así que no arranca el recolector.
    yield TestClient(app)
    app.dependency_overrides.clear()
    motor.dispose()


def registrar(c, correo="ana@ejemplo.com", clave=CLAVE):
    return c.post("/api/auth/registro", json={"correo": correo, "clave": clave})


def entrar(c, correo="ana@ejemplo.com", clave=CLAVE):
    r = c.post("/api/auth/login", json={"correo": correo, "clave": clave})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def token_con(**cambios):
    ahora = datetime.now(timezone.utc)
    carga = {"sub": "1", "correo": "ana@ejemplo.com", "rol": "usuario", "iat": ahora, "exp": ahora + timedelta(minutes=5)}
    carga.update(cambios)
    return jwt.encode(carga, get_settings().jwt_secret_key, algorithm="HS256")


# ---------- contraseñas ----------
def test_la_clave_se_guarda_con_hash_y_se_verifica():
    h = seguridad.hashear_clave(CLAVE)
    assert CLAVE not in h and h.startswith("scrypt$")
    assert seguridad.verificar_clave(CLAVE, h)
    assert not seguridad.verificar_clave("otra", h)
    assert seguridad.hashear_clave(CLAVE) != h  # sal distinta cada vez
    assert not seguridad.verificar_clave(CLAVE, "basura")


# ---------- registro ----------
def test_registro_crea_usuario_sin_exponer_la_clave(cliente):
    r = registrar(cliente)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["correo"] == "ana@ejemplo.com" and cuerpo["rol"] == "usuario"
    assert "clave" not in cuerpo and "clave_hash" not in cuerpo


def test_registro_normaliza_el_correo_y_rechaza_repetidos(cliente):
    assert registrar(cliente, "Ana@Ejemplo.com").status_code == 201
    r = registrar(cliente, "ana@ejemplo.COM")
    assert r.status_code == 409


@pytest.mark.parametrize("clave", ["corta1", "sololetrasaqui", "123456789"])
def test_registro_rechaza_claves_debiles(cliente, clave):
    assert registrar(cliente, clave=clave).status_code == 422


def test_registro_rechaza_correo_invalido(cliente):
    assert registrar(cliente, correo="no-es-correo").status_code == 422


# ---------- inicio de sesión ----------
def test_login_devuelve_token_con_rol_y_expiracion(cliente):
    registrar(cliente)
    r = cliente.post("/api/auth/login", json={"correo": "ana@ejemplo.com", "clave": CLAVE})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["token_type"] == "bearer" and cuerpo["expira_en_segundos"] == 3600
    carga = jwt.decode(cuerpo["access_token"], get_settings().jwt_secret_key, algorithms=["HS256"])
    assert carga["rol"] == "usuario" and carga["correo"] == "ana@ejemplo.com" and "exp" in carga


def test_login_con_clave_o_correo_equivocados_responde_401_igual(cliente):
    registrar(cliente)
    mala = cliente.post("/api/auth/login", json={"correo": "ana@ejemplo.com", "clave": "Equivocada1"})
    inexistente = cliente.post("/api/auth/login", json={"correo": "nadie@ejemplo.com", "clave": CLAVE})
    assert mala.status_code == inexistente.status_code == 401
    assert mala.json() == inexistente.json()


def test_yo_devuelve_el_usuario_del_token(cliente):
    registrar(cliente)
    r = cliente.get("/api/auth/yo", headers=entrar(cliente))
    assert r.status_code == 200 and r.json()["correo"] == "ana@ejemplo.com"


# ---------- token ausente, inválido, vencido ----------
def test_sin_token_responde_401(cliente):
    assert cliente.get("/api/auth/yo").status_code == 401
    assert cliente.get("/api/favoritos").status_code == 401


def test_token_basura_o_con_otra_llave_responde_401(cliente):
    registrar(cliente)
    assert cliente.get("/api/auth/yo", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401
    falso = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, "otra-llave-distinta-123456", algorithm="HS256")
    assert cliente.get("/api/auth/yo", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_token_vencido_responde_401(cliente):
    registrar(cliente)
    vencido = token_con(exp=datetime.now(timezone.utc) - timedelta(minutes=1))
    r = cliente.get("/api/auth/yo", headers={"Authorization": f"Bearer {vencido}"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_token_de_un_usuario_que_ya_no_existe_responde_401(cliente):
    r = cliente.get("/api/auth/yo", headers={"Authorization": f"Bearer {token_con(sub='999')}"})
    assert r.status_code == 401


def test_sin_llave_configurada_la_autenticacion_responde_503(cliente, monkeypatch):
    registrar(cliente)
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    get_settings.cache_clear()
    r = cliente.post("/api/auth/login", json={"correo": "ana@ejemplo.com", "clave": CLAVE})
    assert r.status_code == 503


# ---------- roles ----------
def test_usuario_normal_recibe_403_en_la_zona_de_administracion(cliente):
    registrar(cliente)
    r = cliente.get("/api/admin/usuarios", headers=entrar(cliente))
    assert r.status_code == 403


def test_sin_token_la_administracion_responde_401(cliente):
    assert cliente.get("/api/admin/usuarios").status_code == 401


def test_el_correo_de_administrador_obtiene_ese_rol_y_lo_lleva_en_el_token(cliente):
    assert registrar(cliente, "jefe@ejemplo.com").json()["rol"] == "administrador"
    cab = entrar(cliente, "jefe@ejemplo.com")
    carga = jwt.decode(cab["Authorization"][7:], get_settings().jwt_secret_key, algorithms=["HS256"])
    assert carga["rol"] == "administrador"
    r = cliente.get("/api/admin/usuarios", headers=cab)
    assert r.status_code == 200 and len(r.json()) == 1


def test_el_administrador_puede_cambiar_roles_y_no_quedarse_sin_admin(cliente):
    registrar(cliente, "jefe@ejemplo.com")
    ana = registrar(cliente).json()
    jefe = entrar(cliente, "jefe@ejemplo.com")
    assert cliente.put(f"/api/admin/usuarios/{ana['id']}/rol", json={"rol": "administrador"}, headers=jefe).json()["rol"] == "administrador"
    assert cliente.put("/api/admin/usuarios/999/rol", json={"rol": "usuario"}, headers=jefe).status_code == 404
    assert cliente.put(f"/api/admin/usuarios/{ana['id']}/rol", json={"rol": "supremo"}, headers=jefe).status_code == 422
    # ya hay dos administradores: jefe puede quitarse el rol; luego ana (la única) no puede
    assert cliente.put("/api/admin/usuarios/1/rol", json={"rol": "usuario"}, headers=jefe).status_code == 200
    ana_h = entrar(cliente)
    assert cliente.put(f"/api/admin/usuarios/{ana['id']}/rol", json={"rol": "usuario"}, headers=ana_h).status_code == 409


# ---------- favoritos ----------
def test_favoritos_exigen_token_para_crear_editar_y_borrar(cliente):
    assert cliente.post("/api/favoritos", json={"nombre": "Casa", "texto": "Portal 80"}).status_code == 401
    assert cliente.put("/api/favoritos/1", json={"nombre": "Casa", "texto": "Portal 80"}).status_code == 401
    assert cliente.delete("/api/favoritos/1").status_code == 401


def test_crud_de_favoritos(cliente):
    registrar(cliente)
    h = entrar(cliente)
    creado = cliente.post("/api/favoritos", json={"nombre": " Casa ", "texto": "Calle 72 con Carrera 10"}, headers=h)
    assert creado.status_code == 201 and creado.json()["nombre"] == "Casa"
    fid = creado.json()["id"]
    assert cliente.post("/api/favoritos", json={"nombre": "Casa", "texto": "otro"}, headers=h).status_code == 409
    assert [f["nombre"] for f in cliente.get("/api/favoritos", headers=h).json()] == ["Casa"]
    editado = cliente.put(f"/api/favoritos/{fid}", json={"nombre": "Oficina", "texto": "Portal 80"}, headers=h)
    assert editado.status_code == 200 and editado.json()["nombre"] == "Oficina"
    assert cliente.delete(f"/api/favoritos/{fid}", headers=h).status_code == 204
    assert cliente.get("/api/favoritos", headers=h).json() == []
    assert cliente.delete(f"/api/favoritos/{fid}", headers=h).status_code == 404


def test_cada_usuario_solo_ve_y_modifica_sus_favoritos(cliente):
    registrar(cliente)
    registrar(cliente, "beto@ejemplo.com")
    ana, beto = entrar(cliente), entrar(cliente, "beto@ejemplo.com")
    fid = cliente.post("/api/favoritos", json={"nombre": "Casa", "texto": "Portal 80"}, headers=ana).json()["id"]
    assert cliente.get("/api/favoritos", headers=beto).json() == []
    assert cliente.put(f"/api/favoritos/{fid}", json={"nombre": "Mía", "texto": "robada"}, headers=beto).status_code == 404
    assert cliente.delete(f"/api/favoritos/{fid}", headers=beto).status_code == 404
    assert cliente.get("/api/favoritos", headers=ana).json()[0]["nombre"] == "Casa"


def test_favorito_invalido_responde_422(cliente):
    registrar(cliente)
    h = entrar(cliente)
    assert cliente.post("/api/favoritos", json={"nombre": "   ", "texto": "Portal 80"}, headers=h).status_code == 422


# ---------- lo público sigue público ----------
def test_los_endpoints_de_lluvia_y_salud_no_piden_token(cliente):
    assert cliente.get("/api/health/live").status_code == 200
    rutas_publicas = {"/api/resumen", "/api/estaciones", "/api/destino", "/api/radar", "/api/historial/serie"}
    for ruta in app.routes:
        if getattr(ruta, "path", None) in rutas_publicas:
            seguridad_dep = [d for d in ruta.dependant.dependencies if d.call.__name__ in ("usuario_actual", "_verificar")]
            assert not seguridad_dep, f"{ruta.path} no debería pedir token"
