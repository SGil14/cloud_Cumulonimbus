"""Interfaz común de los proveedores de geocodificación."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Ubicacion:
    latitud: float
    longitud: float
    direccion: str | None
    proveedor: str
    barrio: str | None = None
    localidad: str | None = None
    aproximada: bool = False  # True si no se ubicó el punto exacto pedido


class GeocodingError(Exception):
    """El proveedor no pudo responder (red, clave inválida, límite de uso...)."""


class Geocodificador(ABC):
    nombre: str

    @abstractmethod
    def disponible(self) -> bool:
        """False si falta configuración (por ejemplo, la API key)."""

    @abstractmethod
    def buscar(self, texto: str) -> Ubicacion | None:
        """Devuelve la ubicación, None si no hay resultado, o lanza GeocodingError."""
