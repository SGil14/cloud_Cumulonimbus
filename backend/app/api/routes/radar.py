"""Capa de radar para el mapa."""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import radar

router = APIRouter(prefix="/api", tags=["mapa"])


class RadarRespuesta(BaseModel):
    obtenido_en: datetime
    capturado_en: datetime | None
    norte: float
    sur: float
    este: float
    oeste: float
    imagen: str  # data URL del PNG transparente


@router.get("/radar", response_model=RadarRespuesta)
def radar_actual():
    """Imagen del radar del IDIGER y la zona que cubre. Donde hay color, está lloviendo."""
    try:
        return radar.obtener_radar()
    except radar.RadarError as e:
        raise HTTPException(502, "El radar no está disponible en este momento.") from e
