"""Modelos de datos: lo que llega del SAB y lo que responde la API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.tiempo import BOGOTA_TZ


# ---------- Datos crudos del SAB ----------

class EstacionSAB(BaseModel):
    """Una estación tal como la entrega el servlet del SAB."""

    model_config = ConfigDict(populate_by_name=True)

    id_sensor: int = Field(alias="IDSENSOR")
    id_estacion: int = Field(alias="IDESTACION")
    nombre: str = Field(alias="ESTACION")
    id_localidad: int | None = Field(default=None, alias="IDLOCALIDAD")
    localidad: str = Field(default="SIN LOCALIDAD", alias="LOCALIDAD")
    latitud: float = Field(alias="LATITUD")
    longitud: float = Field(alias="LONGITUD")
    tecnologia: str | None = Field(default=None, alias="TIPOTECNOLOGIA")
    valor_5min: float = Field(default=0, alias="VALORLECTURA")
    acumulado_dia: float = Field(default=0, alias="ACUMULADODIA")
    fecha_lectura: datetime | None = Field(default=None, alias="FECHALECTURA")

    @field_validator("localidad", mode="before")
    @classmethod
    def _localidad(cls, v):
        return v or "SIN LOCALIDAD"

    @field_validator("valor_5min", "acumulado_dia", mode="before")
    @classmethod
    def _numero(cls, v):
        return v if v is not None else 0

    @field_validator("fecha_lectura", mode="before")
    @classmethod
    def _fecha(cls, v):
        # El SAB envía "2026-10-14 10:00:00.0" en hora de Bogotá, sin zona.
        if not v:
            return None
        return datetime.strptime(str(v)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=BOGOTA_TZ)


# ---------- Respuestas de la API ----------

class Intensidad(str, Enum):
    sin_lluvia = "sin_lluvia"
    ligera = "ligera"
    moderada = "moderada"
    fuerte = "fuerte"
    muy_fuerte = "muy_fuerte"


class NivelAcumulado(str, Enum):
    sin_lluvia = "sin_lluvia"
    bajo = "bajo"
    moderado = "moderado"
    alto = "alto"
    muy_alto = "muy_alto"


class Estacion(BaseModel):
    id_sensor: int
    nombre: str
    localidad: str
    latitud: float
    longitud: float
    valor_5min: float
    mm_hora: float
    acumulado_dia: float
    intensidad: Intensidad
    nivel_acumulado: NivelAcumulado
    lloviendo: bool
    fecha_lectura: datetime | None
    desactualizada: bool


class EstacionCercana(Estacion):
    distancia_km: float


class LocalidadResumen(BaseModel):
    localidad: str
    estaciones: int
    estaciones_lloviendo: int
    acumulado_max: float
    acumulado_promedio: float
    nivel_acumulado: NivelAcumulado
    lloviendo: bool


class EstacionesRespuesta(BaseModel):
    datos_obtenidos_en: datetime
    estaciones: list[Estacion]


class Resumen(BaseModel):
    datos_obtenidos_en: datetime
    total_estaciones: int
    estaciones_lloviendo: int
    estaciones_desactualizadas: int
    localidades_lloviendo: list[str]
    estacion_max_acumulado: Estacion | None
    estacion_max_intensidad: Estacion | None
    localidades: list[LocalidadResumen]


class Cercania(BaseModel):
    datos_obtenidos_en: datetime
    latitud: float
    longitud: float
    lloviendo_cerca: bool
    estaciones: list[EstacionCercana]


class UbicacionDestino(BaseModel):
    latitud: float
    longitud: float
    direccion: str | None
    barrio: str | None
    localidad: str | None
    proveedor: str
    aproximada: bool = False


class TipoDestino(str, Enum):
    localidad = "localidad"
    coordenadas = "coordenadas"
    direccion = "direccion"


class DestinoRespuesta(BaseModel):
    texto: str
    tipo: TipoDestino
    encontrado: bool
    mensaje: str
    ubicacion: UbicacionDestino | None = None
    cercania: Cercania | None = None
