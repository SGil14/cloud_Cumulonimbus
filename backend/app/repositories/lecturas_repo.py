"""Guardado de estaciones y lecturas del SAB."""

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Estacion, Lectura
from app.models.schemas import EstacionSAB


def guardar_estaciones(db: Session, estaciones: list[EstacionSAB]) -> None:
    """Inserta estaciones nuevas y actualiza las existentes."""
    if not estaciones:
        return
    filas = [
        {
            "id_sensor": e.id_sensor,
            "id_estacion": e.id_estacion,
            "nombre": e.nombre,
            "id_localidad": e.id_localidad,
            "localidad": e.localidad.title(),
            "latitud": e.latitud,
            "longitud": e.longitud,
            "tecnologia": e.tecnologia,
        }
        for e in estaciones
    ]
    stmt = insert(Estacion).values(filas)
    columnas = {c: stmt.excluded[c] for c in filas[0] if c != "id_sensor"}
    db.execute(stmt.on_conflict_do_update(
        index_elements=["id_sensor"],
        set_={**columnas, "actualizado_en": func.now()},
    ))


def guardar_lecturas(db: Session, estaciones: list[EstacionSAB]) -> int:
    """Guarda las lecturas ignorando las que ya existían. Devuelve cuántas son nuevas."""
    filas = [
        {
            "id_sensor": e.id_sensor,
            "fecha_lectura": e.fecha_lectura,
            "valor_5min": e.valor_5min,
            "acumulado_dia": e.acumulado_dia,
        }
        for e in estaciones
        if e.fecha_lectura is not None
    ]
    if not filas:
        return 0
    stmt = (
        insert(Lectura)
        .values(filas)
        .on_conflict_do_nothing(constraint="uq_lectura_sensor_fecha")
        .returning(Lectura.id)
    )
    return len(db.execute(stmt).all())


def guardar_snapshot(db: Session, estaciones: list[EstacionSAB]) -> int:
    guardar_estaciones(db, estaciones)
    nuevas = guardar_lecturas(db, estaciones)
    db.commit()
    return nuevas
