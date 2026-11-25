"""Contraseñas y tokens JWT.

- Las contraseñas se guardan con scrypt (biblioteca estándar) y una sal aleatoria por usuario.
- Los tokens son JWT firmados con HS256. La llave sale de la variable de entorno JWT_SECRET_KEY.
"""

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings

ALGORITMO = "HS256"
# Parámetros de scrypt (OWASP: N=2^15 es lo recomendado; 2^14 es el valor por omisión de hashlib).
_N, _R, _P = 2**14, 8, 1


class TokenInvalido(Exception):
    """El token no existe, está mal firmado o venció."""


class LlaveNoConfigurada(Exception):
    """Falta JWT_SECRET_KEY: sin llave no se pueden firmar ni verificar tokens."""


# ---------- contraseñas ----------
def hashear_clave(clave: str) -> str:
    sal = os.urandom(16)
    h = hashlib.scrypt(clave.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(
        _N, _R, _P, base64.b64encode(sal).decode(), base64.b64encode(h).decode()
    )


def verificar_clave(clave: str, guardado: str) -> bool:
    try:
        _, n, r, p, sal, esperado = guardado.split("$")
        h = hashlib.scrypt(
            clave.encode(), salt=base64.b64decode(sal), n=int(n), r=int(r), p=int(p), dklen=32
        )
        return hmac.compare_digest(h, base64.b64decode(esperado))
    except (ValueError, TypeError):
        return False


# ---------- tokens ----------
def _llave() -> str:
    llave = get_settings().jwt_secret_key
    if len(llave) < 16:
        raise LlaveNoConfigurada("JWT_SECRET_KEY no está configurada (mínimo 16 caracteres).")
    return llave


def crear_token(id_usuario: int, correo: str, rol: str) -> tuple[str, int]:
    """Devuelve el token y los segundos que dura."""
    minutos = get_settings().jwt_expira_minutos
    ahora = datetime.now(timezone.utc)
    carga = {
        "sub": str(id_usuario),
        "correo": correo,
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=minutos),
    }
    return jwt.encode(carga, _llave(), algorithm=ALGORITMO), minutos * 60


def leer_token(token: str) -> dict:
    try:
        return jwt.decode(token, _llave(), algorithms=[ALGORITMO], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError as e:
        raise TokenInvalido(str(e)) from e
