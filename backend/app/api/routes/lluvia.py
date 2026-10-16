"""Endpoints de lluvia en tiempo real."""

from fastapi import APIRouter, Query

from app.config import get_settings
from app.models.schemas import Cercania, EstacionesRespuesta, Resumen
from app.services import estaciones_service, lluvia_service

router = APIRouter(prefix="/api", tags=["lluvia"])

ACTUALIZAR = Query(False, description="Ignora la caché y consulta el SAB en este momento")


@router.get("/estaciones", response_model=EstacionesRespuesta)
def listar_estaciones(actualizar: bool = ACTUALIZAR):
    """Todas las estaciones con su estado actual (para pintar el mapa)."""
    obtenido_en, estaciones = estaciones_service.obtener_estaciones(forzar=actualizar)
    return EstacionesRespuesta(datos_obtenidos_en=obtenido_en, estaciones=estaciones)


@router.get("/resumen", response_model=Resumen)
def resumen(actualizar: bool = ACTUALIZAR):
    """Dónde está lloviendo ahora y acumulado del día por localidad."""
    obtenido_en, estaciones = estaciones_service.obtener_estaciones(forzar=actualizar)
    return lluvia_service.construir_resumen(estaciones, obtenido_en)


@router.get("/cercanas", response_model=Cercania)
def cercanas(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    cantidad: int | None = Query(None, ge=1, le=10),
):
    """Estaciones más cercanas a un punto y si está lloviendo cerca."""
    obtenido_en, estaciones = estaciones_service.obtener_estaciones()
    cantidad = cantidad or get_settings().estaciones_cercanas
    return lluvia_service.estaciones_cercanas(estaciones, lat, lon, cantidad, obtenido_en)
