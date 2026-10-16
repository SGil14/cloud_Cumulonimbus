"""Búsqueda de destinos: caché → IDECA (si hay clave) → Catastro → Nominatim, y luego barrio y localidad."""

import logging
import re
import unicodedata

from sqlalchemy.orm import Session

from app.repositories import geocache_repo
from app.services import barrios
from app.services.geocoding.base import Geocodificador, GeocodingError, Ubicacion
from app.services.geocoding.catastro import CatastroGeocodificador
from app.services.geocoding.ideca import IdecaGeocodificador
from app.services.geocoding.nominatim import NominatimGeocodificador

logger = logging.getLogger(__name__)

# Orden de prioridad: el primero que encuentre el destino gana.
PROVEEDORES: list[Geocodificador] = [
    IdecaGeocodificador(),       # oficial, solo si hay API key
    CatastroGeocodificador(),    # direcciones y esquinas, gratis, misma base que IDECA
    NominatimGeocodificador(),   # lugares, parques y barrios
]


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y sin espacios repetidos: clave estable para la caché."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes.lower()).strip()


def _completar(u: Ubicacion) -> Ubicacion:
    """Agrega barrio y localidad desde Catastro cuando el proveedor no los trajo."""
    barrio = u.barrio or barrios.barrio_de(u.latitud, u.longitud)
    localidad = u.localidad or barrios.localidad_de(u.latitud, u.longitud)
    return Ubicacion(u.latitud, u.longitud, u.direccion, u.proveedor, barrio, localidad, u.aproximada)


def geocodificar(db: Session, texto: str) -> Ubicacion | None:
    """None si ningún proveedor lo encuentra. Lanza GeocodingError si todos fallaron por red."""
    clave = normalizar(texto)
    guardada = geocache_repo.buscar(db, clave)
    if guardada:
        return guardada

    errores = 0
    for proveedor in PROVEEDORES:
        if not proveedor.disponible():
            continue
        try:
            encontrada = proveedor.buscar(texto)
        except GeocodingError as e:
            errores += 1
            logger.warning("%s", e)
            continue
        if encontrada:
            completa = _completar(encontrada)
            geocache_repo.guardar(db, clave, texto, completa)
            return completa

    if errores:
        # Si algún servicio falló no se puede afirmar que el destino no exista: mejor pedir reintentar.
        raise GeocodingError("Un servicio de búsqueda no respondió.")
    return None
