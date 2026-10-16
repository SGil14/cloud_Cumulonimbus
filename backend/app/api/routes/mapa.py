"""Datos geográficos para dibujar el mapa."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.services import barrios

router = APIRouter(prefix="/api", tags=["mapa"])


@router.get("/localidades")
def localidades():
    """Contorno de las localidades de Bogotá (GeoJSON), con su nombre y código."""
    try:
        geojson = barrios.limites_localidades()
    except barrios.LimitesError as e:
        raise HTTPException(502, "No se pudieron cargar los límites de las localidades.") from e
    return JSONResponse(geojson, headers={"Cache-Control": "public, max-age=86400"})
