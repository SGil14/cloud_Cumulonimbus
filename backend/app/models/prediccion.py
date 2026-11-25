"""Modelos de respuesta de la predicción de lluvia en la próxima hora."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class EstacionPrediccion(BaseModel):
    id_sensor: int
    nombre: str
    localidad: str
    distancia_km: float
    lloviendo: bool
    mm_60: float | None  # lluvia de la última hora según el histórico; None si no hay histórico completo


class EvaluacionModelo(BaseModel):
    """Cómo le fue al modelo con datos que no vio, frente a la línea base «si llueve ahora, lloverá»."""

    f1_modelo: float
    f1_persistencia: float
    supera_persistencia: bool
    nota: str


class PrediccionRespuesta(BaseModel):
    datos_obtenidos_en: datetime
    latitud: float
    longitud: float
    horizonte_minutos: int
    metodo: Literal["modelo", "persistencia"]
    probabilidad: float | None  # solo con metodo = "modelo"
    llovera_probable: bool
    llueve_ahora: bool
    mensaje: str
    motivo_respaldo: str | None  # por qué se usó la persistencia en vez del modelo
    estaciones: list[EstacionPrediccion]
    evaluacion: EvaluacionModelo | None
    aviso: str
