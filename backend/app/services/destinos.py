"""Convierte lo que escribe la persona (localidad, coordenadas, barrio, lugar, dirección o esquina) en una ubicación.

Lo usan la consulta de destino y la de ruta.
"""

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.schemas import Estacion, TipoDestino, UbicacionDestino
from app.services import barrios, geocoding

NUMERO_DE_CASA = re.compile(r"\d+\s*[-#]\s*\d+|#\s*\d+|\d+\s+\d+\s+\d+")
COORDENADAS = re.compile(r"^\s*(-?\d{1,2}\.\d+)\s*[,; ]\s*(-?\d{1,3}\.\d+)\s*$")
NO_ENCONTRADO = "No encontré ese destino. Prueba con un barrio, un lugar conocido o una dirección más simple."


@dataclass(frozen=True)
class Resolucion:
    texto: str
    tipo: TipoDestino
    ubicacion: UbicacionDestino | None
    mensaje: str  # explicación para la persona: cómo se resolvió, o por qué no se pudo
    estaciones: list[Estacion]  # estaciones que conviene considerar para este destino
    cantidad: int  # cuántas estaciones cercanas mostrar

    @property
    def encontrado(self) -> bool:
        return self.ubicacion is not None


def resolver(db: Session, texto: str, estaciones: list[Estacion]) -> Resolucion:
    """Lanza GeocodingError si los servicios de búsqueda no responden."""
    texto = texto.strip()
    cantidad = get_settings().estaciones_cercanas

    # 1. ¿Es una localidad? Se resuelve sin salir a internet.
    clave = geocoding.normalizar(texto)
    de_localidad = [e for e in estaciones if geocoding.normalizar(e.localidad) == clave]
    if de_localidad:
        lat = sum(e.latitud for e in de_localidad) / len(de_localidad)
        lon = sum(e.longitud for e in de_localidad) / len(de_localidad)
        ubicacion = UbicacionDestino(
            latitud=lat, longitud=lon, direccion=None, barrio=None,
            localidad=de_localidad[0].localidad, proveedor="sab",
        )
        return Resolucion(
            texto, TipoDestino.localidad, ubicacion,
            f"Estaciones de la localidad {de_localidad[0].localidad}.", de_localidad, len(de_localidad),
        )

    # 2. ¿Son coordenadas?
    if m := COORDENADAS.match(texto):
        lat, lon = float(m.group(1)), float(m.group(2))
        if not (4.2 <= lat <= 4.9 and -74.5 <= lon <= -73.9):
            return Resolucion(texto, TipoDestino.coordenadas, None, "Esas coordenadas están fuera de Bogotá.", estaciones, cantidad)
        ubicacion = UbicacionDestino(
            latitud=lat, longitud=lon, direccion=None,
            barrio=barrios.barrio_de(lat, lon), localidad=barrios.localidad_de(lat, lon),
            proveedor="coordenadas",
        )
        return Resolucion(texto, TipoDestino.coordenadas, ubicacion, "Estaciones más cercanas a tu destino.", estaciones, cantidad)

    # 3. Dirección, barrio o lugar: se geocodifica.
    encontrada = geocoding.geocodificar(db, texto)
    if encontrada is None:
        return Resolucion(texto, TipoDestino.direccion, None, NO_ENCONTRADO, estaciones, cantidad)

    mensaje = "Estaciones más cercanas a tu destino."
    if encontrada.aproximada:
        mensaje = (
            "Ubicación aproximada: no hallé el punto exacto, usé el más cercano sobre esa vía. "
            "Estaciones más cercanas."
        )
    elif encontrada.proveedor == "nominatim" and NUMERO_DE_CASA.search(texto):
        mensaje = (
            "Ubicación aproximada: solo pude ubicar la vía, no el número exacto. "
            "Estaciones más cercanas a esa vía."
        )
    ubicacion = UbicacionDestino(
        latitud=encontrada.latitud, longitud=encontrada.longitud, direccion=encontrada.direccion,
        barrio=encontrada.barrio, localidad=encontrada.localidad, proveedor=encontrada.proveedor,
        aproximada=encontrada.aproximada,
    )
    return Resolucion(texto, TipoDestino.direccion, ubicacion, mensaje, estaciones, cantidad)
