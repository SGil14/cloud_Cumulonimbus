"""Modelos de respuesta del historial de lluvia."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Periodo = Literal["6h", "24h", "7d", "30d"]
Paso = Literal["hora", "dia"]


class PuntoHistorial(BaseModel):
    inicio: datetime
    mm: float | None  # None = sin datos en ese intervalo (la app estaba apagada o la estación no reportó)
    lecturas: int


class SerieHistorial(BaseModel):
    etiqueta: str
    periodo: Periodo
    paso: Paso
    desde: datetime
    hasta: datetime
    puntos: list[PuntoHistorial]
    total_mm: float
    pico: PuntoHistorial | None
    estaciones: int
    datos_desde: datetime | None  # primera lectura guardada en toda la base
    cobertura_pct: int  # % de intervalos con al menos una lectura


class SerieEstacion(BaseModel):
    id_sensor: int
    nombre: str
    localidad: str
    distancia_km: float
    serie: SerieHistorial


class HistorialDestino(BaseModel):
    periodo: Periodo
    estaciones: list[SerieEstacion]
