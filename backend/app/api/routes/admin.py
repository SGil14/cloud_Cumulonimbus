"""Acciones reservadas a administradores."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import solo_administrador
from app.db.models import Usuario
from app.db.session import get_db
from app.models.auth import CambioRol, UsuarioOut

router = APIRouter(prefix="/api/admin", tags=["administración"], dependencies=[Depends(solo_administrador)])


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.scalars(select(Usuario).order_by(Usuario.id)).all()


@router.put("/usuarios/{id_usuario}/rol", response_model=UsuarioOut)
def cambiar_rol(
    id_usuario: int,
    cambio: CambioRol,
    admin: Usuario = Depends(solo_administrador),
    db: Session = Depends(get_db),
):
    usuario = db.get(Usuario, id_usuario)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe ese usuario.")
    if usuario.id == admin.id and cambio.rol != "administrador":
        # Evita quedarse sin administradores por accidente.
        otros = db.scalar(
            select(func.count()).select_from(Usuario).where(Usuario.rol == "administrador", Usuario.id != admin.id)
        )
        if not otros:
            raise HTTPException(status.HTTP_409_CONFLICT, "Eres el único administrador: no puedes quitarte el rol.")
    usuario.rol = cambio.rol
    db.commit()
    return usuario
