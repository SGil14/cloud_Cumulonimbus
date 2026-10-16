"""Caché persistente de direcciones ya geocodificadas."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import GeoCache
from app.services.geocoding.base import Ubicacion


def buscar(db: Session, consulta_normalizada: str) -> Ubicacion | None:
    fila = db.scalar(select(GeoCache).where(GeoCache.consulta_normalizada == consulta_normalizada))
    if fila is None:
        return None
    fila.usos += 1
    fila.ultimo_uso = func.now()
    db.commit()
    return Ubicacion(
        latitud=fila.latitud,
        longitud=fila.longitud,
        direccion=fila.direccion,
        proveedor=fila.proveedor,
        barrio=fila.barrio,
        localidad=fila.localidad,
        aproximada=fila.aproximada,
    )


def guardar(db: Session, consulta_normalizada: str, consulta_original: str, u: Ubicacion) -> None:
    if db.scalar(select(GeoCache.id).where(GeoCache.consulta_normalizada == consulta_normalizada)):
        return
    db.add(GeoCache(
        consulta_normalizada=consulta_normalizada[:300],
        consulta_original=consulta_original[:300],
        latitud=u.latitud,
        longitud=u.longitud,
        direccion=(u.direccion or "")[:500] or None,
        barrio=u.barrio,
        localidad=u.localidad,
        proveedor=u.proveedor,
        aproximada=u.aproximada,
    ))
    db.commit()
