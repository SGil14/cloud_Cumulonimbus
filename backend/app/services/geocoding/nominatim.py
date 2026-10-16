"""Geocodificador de OpenStreetMap (Nominatim). Respaldo gratuito.

Buenos resultados con lugares, parques, centros comerciales, estaciones y barrios.
Débil con números de casa. Política de uso: máximo 1 consulta por segundo y User-Agent propio.
"""

import threading
import time

import httpx

from app.config import get_settings
from app.services.geocoding.base import Geocodificador, GeocodingError, Ubicacion

URL = "https://nominatim.openstreetmap.org/search"
# Recuadro de Bogotá (oeste, norte, este, sur). Se prefiere esto a agregar ", Bogotá" al texto,
# porque Nominatim deja de encontrar muchos lugares con ese sufijo.
VIEWBOX = "-74.25,4.84,-73.99,4.45"
INTERVALO_MINIMO = 1.1

_lock = threading.Lock()
_ultima_consulta = 0.0


def _esperar_turno() -> None:
    global _ultima_consulta
    with _lock:
        espera = INTERVALO_MINIMO - (time.monotonic() - _ultima_consulta)
        if espera > 0:
            time.sleep(espera)
        _ultima_consulta = time.monotonic()


class NominatimGeocodificador(Geocodificador):
    nombre = "nominatim"

    def disponible(self) -> bool:
        return True

    def buscar(self, texto: str) -> Ubicacion | None:
        settings = get_settings()
        _esperar_turno()
        try:
            resp = httpx.get(
                URL,
                params={
                    "q": texto,
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "co",
                    "viewbox": VIEWBOX,
                    "bounded": 1,
                    "accept-language": "es",
                },
                headers={"User-Agent": settings.nominatim_user_agent},
                timeout=settings.geocoding_timeout_segundos,
            )
            resp.raise_for_status()
            resultados = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise GeocodingError(f"Nominatim no respondió: {e}") from e

        if not resultados:
            return None
        r = resultados[0]
        return Ubicacion(
            latitud=float(r["lat"]),
            longitud=float(r["lon"]),
            direccion=r.get("display_name"),
            proveedor=self.nombre,
        )
