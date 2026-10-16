"""Geocodificador oficial de IDECA / Catastro Bogotá (requiere API key gratuita de IDECA).

Documentación: https://mapas.bogota.gov.co/api/ (sección "API de Geocodificación").
Entiende la nomenclatura bogotana: "CRA 30 25 90", "Calle 80 # 70-20", etc.
"""

import httpx

from app.config import get_settings
from app.services.geocoding.base import Geocodificador, GeocodingError, Ubicacion


class IdecaGeocodificador(Geocodificador):
    nombre = "ideca"

    def disponible(self) -> bool:
        return bool(get_settings().ideca_api_key)

    def buscar(self, texto: str) -> Ubicacion | None:
        settings = get_settings()
        try:
            resp = httpx.get(
                settings.ideca_url,
                params={"cmd": "geocodificar", "apikey": settings.ideca_api_key, "query": texto},
                timeout=settings.geocoding_timeout_segundos,
            )
            resp.raise_for_status()
            cuerpo = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise GeocodingError(f"IDECA no respondió: {e}") from e

        if cuerpo.get("status") is False:
            raise GeocodingError(f"IDECA rechazó la consulta: {cuerpo.get('message')}")

        respuesta = cuerpo.get("response") or {}
        datos = respuesta.get("data") or {}
        if not respuesta.get("success") or datos.get("estado") != "success":
            return None
        try:
            lat, lon = float(datos["latitude"]), float(datos["longitude"])
        except (KeyError, TypeError, ValueError):
            return None

        return Ubicacion(
            latitud=lat,
            longitud=lon,
            direccion=datos.get("diraprox") or datos.get("dirtrad"),
            proveedor=self.nombre,
            barrio=(datos.get("nomseccat") or "").title() or None,
            localidad=(datos.get("localidad") or "").title() or None,
        )
