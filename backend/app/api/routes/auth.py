"""Registro e inicio de sesión."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.config import get_settings
from app.core.seguridad import LlaveNoConfigurada, crear_token, hashear_clave, verificar_clave
from app.db.models import Usuario
from app.db.session import get_db
from app.models.auth import Credenciales, Registro, TokenOut, UsuarioOut

router = APIRouter(prefix="/api/auth", tags=["autenticación"])

# Se compara contra este hash cuando el correo no existe, para que tardar igual no delate qué correos están registrados.
_HASH_FALSO = hashear_clave("no-existe")


def _entregar_token(usuario: Usuario) -> TokenOut:
    try:
        token, segundos = crear_token(usuario.id, usuario.correo, usuario.rol)
    except LlaveNoConfigurada:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "La autenticación no está configurada.")
    return TokenOut(access_token=token, expira_en_segundos=segundos, usuario=UsuarioOut.model_validate(usuario))


@router.post("/registro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def registrar(datos: Registro, db: Session = Depends(get_db)):
    """Crea una cuenta. Quien se registre con el correo ADMIN_CORREO queda como administrador."""
    if db.scalar(select(Usuario.id).where(Usuario.correo == datos.correo)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo.")
    admin = get_settings().admin_correo.strip().lower()
    usuario = Usuario(
        correo=datos.correo,
        clave_hash=hashear_clave(datos.clave),
        rol="administrador" if admin and datos.correo == admin else "usuario",
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:  # dos registros simultáneos con el mismo correo
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo.")
    return usuario


@router.post("/login", response_model=TokenOut)
def iniciar_sesion(datos: Credenciales, db: Session = Depends(get_db)):
    """Valida las credenciales y entrega un token JWT que dura JWT_EXPIRA_MINUTOS."""
    usuario = db.scalar(select(Usuario).where(Usuario.correo == datos.correo))
    valido = verificar_clave(datos.clave, usuario.clave_hash if usuario else _HASH_FALSO)
    if not usuario or not valido:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos.", headers={"WWW-Authenticate": "Bearer"}
        )
    return _entregar_token(usuario)


@router.get("/yo", response_model=UsuarioOut)
def quien_soy(usuario: Usuario = Depends(usuario_actual)):
    """El usuario al que pertenece el token."""
    return usuario
