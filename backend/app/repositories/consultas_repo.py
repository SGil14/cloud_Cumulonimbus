"""Registro de las búsquedas de destino."""

from sqlalchemy.orm import Session

from app.db.models import Consulta


def registrar_consulta(
    db: Session,
    *,
    texto: str,
    tipo: str,
    encontrado: bool,
    latitud: float | None = None,
    longitud: float | None = None,
    barrio: str | None = None,
    localidad: str | None = None,
    proveedor: str | None = None,
    lloviendo_cerca: bool | None = None,
) -> None:
    db.add(Consulta(
        texto=texto[:300],
        tipo=tipo,
        encontrado=encontrado,
        latitud=latitud,
        longitud=longitud,
        barrio=barrio,
        localidad=localidad,
        proveedor=proveedor,
        lloviendo_cerca=lloviendo_cerca,
    ))
    db.commit()
