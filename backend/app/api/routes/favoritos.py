"""Destinos favoritos. Todo exige token y cada usuario solo toca los suyos."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.db.models import Favorito, Usuario
from app.db.session import get_db
from app.models.auth import FavoritoIn, FavoritoOut

router = APIRouter(prefix="/api/favoritos", tags=["favoritos"])

MAXIMO_POR_USUARIO = 50


def _suyo(db: Session, usuario: Usuario, id_favorito: int) -> Favorito:
    # Un favorito ajeno responde 404 (no 403) para no revelar que existe.
    fav = db.scalar(select(Favorito).where(Favorito.id == id_favorito, Favorito.usuario_id == usuario.id))
    if fav is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe ese favorito.")
    return fav


@router.get("", response_model=list[FavoritoOut])
def listar(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return db.scalars(select(Favorito).where(Favorito.usuario_id == usuario.id).order_by(Favorito.nombre)).all()


@router.post("", response_model=FavoritoOut, status_code=status.HTTP_201_CREATED)
def crear(datos: FavoritoIn, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Favorito).where(Favorito.usuario_id == usuario.id))
    if total >= MAXIMO_POR_USUARIO:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Máximo {MAXIMO_POR_USUARIO} favoritos.")
    fav = Favorito(usuario_id=usuario.id, nombre=datos.nombre, texto=datos.texto)
    db.add(fav)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya tienes un favorito con ese nombre.")
    return fav


@router.put("/{id_favorito}", response_model=FavoritoOut)
def actualizar(
    id_favorito: int, datos: FavoritoIn, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)
):
    fav = _suyo(db, usuario, id_favorito)
    fav.nombre, fav.texto = datos.nombre, datos.texto
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya tienes un favorito con ese nombre.")
    return fav


@router.delete("/{id_favorito}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(id_favorito: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    db.delete(_suyo(db, usuario, id_favorito))
    db.commit()
