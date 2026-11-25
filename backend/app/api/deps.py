"""Dependencias de seguridad: quién hace la petición y qué rol tiene."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.seguridad import LlaveNoConfigurada, TokenInvalido, leer_token
from app.db.models import Usuario
from app.db.session import get_db

_esquema = HTTPBearer(auto_error=False, description="Token JWT obtenido en /api/auth/login")


def _no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detalle, headers={"WWW-Authenticate": "Bearer"})


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_esquema),
    db: Session = Depends(get_db),
) -> Usuario:
    """El usuario dueño del token. 401 si falta, es inválido o venció."""
    if credenciales is None:
        raise _no_autenticado("Falta el token. Inicia sesión.")
    try:
        carga = leer_token(credenciales.credentials)
    except TokenInvalido:
        raise _no_autenticado("El token no es válido o venció. Inicia sesión de nuevo.")
    except LlaveNoConfigurada:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "La autenticación no está configurada.")
    usuario = db.get(Usuario, int(carga["sub"])) if str(carga["sub"]).isdigit() else None
    if usuario is None:
        raise _no_autenticado("El usuario del token ya no existe.")
    return usuario


def requiere_rol(*roles: str):
    """403 si el usuario no tiene alguno de los roles. Úsese como dependencia."""

    def _verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tienes permisos para esta acción.")
        return usuario

    return _verificar


solo_administrador = requiere_rol("administrador")
