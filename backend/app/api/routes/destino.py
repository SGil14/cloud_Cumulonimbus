"""Consulta de lluvia por destino: localidad, coordenadas, barrio, lugar, dirección o esquina."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.schemas import DestinoRespuesta
from app.repositories import consultas_repo
from app.services import destinos, estaciones_service, lluvia_service
from app.services.geocoding.base import GeocodingError

router = APIRouter(prefix="/api", tags=["destino"])


@router.get("/destino", response_model=DestinoRespuesta)
def consultar_destino(
    q: str = Query(..., min_length=2, max_length=200, description="Localidad, barrio, lugar, dirección o 'lat,lon'"),
    db: Session = Depends(get_db),
):
    """Ubica el destino y dice cómo está la lluvia en las estaciones más cercanas."""
    texto = q.strip()
    obtenido_en, estaciones = estaciones_service.obtener_estaciones()
    try:
        r = destinos.resolver(db, texto, estaciones)
    except GeocodingError:
        raise HTTPException(503, "El servicio de búsqueda no responde. Inténtalo de nuevo en unos minutos.")

    if not r.encontrado:
        consultas_repo.registrar_consulta(db, texto=texto, tipo=r.tipo.value, encontrado=False)
        return DestinoRespuesta(texto=texto, tipo=r.tipo, encontrado=False, mensaje=r.mensaje)

    u = r.ubicacion
    cercania = lluvia_service.estaciones_cercanas(r.estaciones, u.latitud, u.longitud, r.cantidad, obtenido_en)
    consultas_repo.registrar_consulta(
        db, texto=texto, tipo=r.tipo.value, encontrado=True,
        latitud=u.latitud, longitud=u.longitud, barrio=u.barrio, localidad=u.localidad,
        proveedor=u.proveedor, lloviendo_cerca=cercania.lloviendo_cerca,
    )
    return DestinoRespuesta(
        texto=texto, tipo=r.tipo, encontrado=True, mensaje=r.mensaje, ubicacion=u, cercania=cercania,
    )
