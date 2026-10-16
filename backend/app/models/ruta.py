"""Modelos de la consulta de lluvia a lo largo de una ruta."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.schemas import Intensidad, UbicacionDestino

Modo = Literal["auto", "bus", "bicicleta", "a_pie"]
EstadoTramo = Literal["lluvia", "seco", "sin_datos"]


class TramoRuta(BaseModel):
    desde_km: float
    hasta_km: float
    estado: EstadoTramo
    estacion: str | None  # estación más representativa del tramo
    intensidad: Intensidad | None
    mm_hora: float
    coordenadas: list[list[float]]  # [[lon, lat], ...] para dibujar el tramo en el mapa


class RutaRespuesta(BaseModel):
    encontrado: bool
    mensaje: str
    modo: Modo
    origen: UbicacionDestino | None = None
    destino: UbicacionDestino | None = None
    distancia_km: float = 0
    duracion_min: int = 0
    hay_lluvia: bool = False
    porcentaje_sin_datos: int = 0
    resumen: str = ""
    nota: str = ""
    tramos: list[TramoRuta] = []
    datos_obtenidos_en: datetime | None = None
