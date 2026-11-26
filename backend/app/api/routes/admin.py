"""Acciones reservadas a administradores: usuarios, roles y estado del sistema."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import solo_administrador
from app.config import get_settings
from app.db.models import Estacion, Favorito, Lectura, Usuario
from app.db.session import get_db
from app.models.auth import CambioRol, EstadoSistema, FavoritoOut, UsuarioAdminOut, UsuarioOut
from app.services.prediccion_service import cargar_evaluacion, cargar_modelo

router = APIRouter(prefix="/api/admin", tags=["administración"], dependencies=[Depends(solo_administrador)])


def _usuario_o_404(db: Session, id_usuario: int) -> Usuario:
    usuario = db.get(Usuario, id_usuario)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe ese usuario.")
    return usuario


@router.get("/usuarios", response_model=list[UsuarioAdminOut])
def listar_usuarios(db: Session = Depends(get_db)):
    filas = db.execute(
        select(Usuario, func.count(Favorito.id))
        .outerjoin(Favorito, Favorito.usuario_id == Usuario.id)
        .group_by(Usuario.id)
        .order_by(Usuario.id)
    ).all()
    return [UsuarioAdminOut.model_validate(u).model_copy(update={"favoritos": n}) for u, n in filas]


@router.get("/usuarios/{id_usuario}/favoritos", response_model=list[FavoritoOut])
def favoritos_de(id_usuario: int, db: Session = Depends(get_db)):
    _usuario_o_404(db, id_usuario)
    return db.scalars(select(Favorito).where(Favorito.usuario_id == id_usuario).order_by(Favorito.creado_en)).all()


@router.put("/usuarios/{id_usuario}/rol", response_model=UsuarioOut)
def cambiar_rol(
    id_usuario: int,
    cambio: CambioRol,
    admin: Usuario = Depends(solo_administrador),
    db: Session = Depends(get_db),
):
    usuario = _usuario_o_404(db, id_usuario)
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


@router.delete("/usuarios/{id_usuario}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(id_usuario: int, admin: Usuario = Depends(solo_administrador), db: Session = Depends(get_db)):
    """Borra la cuenta y sus favoritos. Un administrador no puede borrarse a sí mismo."""
    usuario = _usuario_o_404(db, id_usuario)
    if usuario.id == admin.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "No puedes eliminar tu propia cuenta.")
    # Se borran los favoritos a mano para no depender de que la base aplique el ON DELETE CASCADE.
    for favorito in db.scalars(select(Favorito).where(Favorito.usuario_id == usuario.id)).all():
        db.delete(favorito)
    db.delete(usuario)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/estado", response_model=EstadoSistema)
def estado_del_sistema(db: Session = Depends(get_db)):
    ajustes = get_settings()
    ahora = datetime.now(timezone.utc)

    def contar(tabla, *condiciones) -> int:
        return db.scalar(select(func.count()).select_from(tabla).where(*condiciones)) or 0

    ultima = db.scalar(select(func.max(Lectura.fecha_lectura)))
    if ultima is not None and ultima.tzinfo is None:
        ultima = ultima.replace(tzinfo=timezone.utc)
    evaluacion = cargar_evaluacion()
    return EstadoSistema(
        usuarios=contar(Usuario),
        administradores=contar(Usuario, Usuario.rol == "administrador"),
        favoritos=contar(Favorito),
        estaciones=contar(Estacion),
        lecturas=contar(Lectura),
        lecturas_24h=contar(Lectura, Lectura.fecha_lectura >= ahora - timedelta(hours=24)),
        ultima_lectura=ultima,
        minutos_desde_ultima_lectura=int((ahora - ultima).total_seconds() // 60) if ultima else None,
        recolector_activo_en_este_proceso=ajustes.recolector_activo,
        recolector_intervalo_minutos=ajustes.recolector_intervalo_minutos,
        ia_modelo_disponible=cargar_modelo() is not None,
        ia_f1_modelo=evaluacion.f1_modelo if evaluacion else None,
        ia_f1_persistencia=evaluacion.f1_persistencia if evaluacion else None,
        ia_supera_linea_base=evaluacion.supera_persistencia if evaluacion else None,
        grafana_url=ajustes.grafana_url,
    )
