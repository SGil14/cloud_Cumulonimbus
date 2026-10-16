"""Barrio y localidad de un punto, usando las capas públicas de Catastro Bogotá (sin API key)."""

import logging

import httpx

from app.config import get_settings
from app.core.cache import CacheTTL

logger = logging.getLogger(__name__)

BASE = "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services"
CAPA_SECTOR_CATASTRAL = f"{BASE}/catastro/sectorcatastral/MapServer/0/query"
CAPA_LOCALIDAD = f"{BASE}/ordenamientoterritorial/localidad/MapServer/0/query"


def _consultar(url: str, lat: float, lon: float, campos: str) -> dict | None:
    resp = httpx.get(
        url,
        params={
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": campos,
            "returnGeometry": "false",
            "f": "json",
        },
        timeout=get_settings().geocoding_timeout_segundos,
    )
    resp.raise_for_status()
    features = resp.json().get("features") or []
    return features[0]["attributes"] if features else None


def barrio_de(lat: float, lon: float) -> str | None:
    """Nombre del sector catastral (equivale al barrio en zona urbana). None si falla."""
    try:
        attrs = _consultar(CAPA_SECTOR_CATASTRAL, lat, lon, "SCANOMBRE")
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("No se pudo obtener el barrio: %s", e)
        return None
    return attrs["SCANOMBRE"].title() if attrs and attrs.get("SCANOMBRE") else None


def localidad_de(lat: float, lon: float) -> str | None:
    """Nombre de la localidad que contiene el punto. None si falla o está fuera de Bogotá."""
    try:
        attrs = _consultar(CAPA_LOCALIDAD, lat, lon, "LOCNOMBRE")
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("No se pudo obtener la localidad: %s", e)
        return None
    return attrs["LOCNOMBRE"].title() if attrs and attrs.get("LOCNOMBRE") else None


# La capa de Catastro usa "CANDELARIA"; el SAB, "LA CANDELARIA".
_NOMBRES_LOCALIDAD = {"CANDELARIA": "La Candelaria"}
SIMPLIFICACION_GRADOS = 0.0003  # ~30 m: el contorno sigue reconocible y pesa ~50 KB en vez de 2 MB


def _descargar_limites() -> dict:
    resp = httpx.get(
        CAPA_LOCALIDAD,
        params={
            "where": "1=1",
            "outFields": "LOCNOMBRE,LOCCODIGO",
            "outSR": 4326,
            "returnGeometry": "true",
            "maxAllowableOffset": SIMPLIFICACION_GRADOS,
            "f": "geojson",
        },
        timeout=get_settings().geocoding_timeout_segundos * 2,
    )
    resp.raise_for_status()
    geojson = resp.json()
    for feature in geojson["features"]:
        bruto = feature["properties"]["LOCNOMBRE"]
        feature["properties"] = {
            "nombre": _NOMBRES_LOCALIDAD.get(bruto, bruto.title()),
            "codigo": feature["properties"]["LOCCODIGO"],
        }
    return geojson


_cache_limites = CacheTTL(_descargar_limites, 24 * 3600)


def limites_localidades() -> dict:
    """GeoJSON con el contorno de las 20 localidades. Se reutiliza durante 24 horas."""
    try:
        return _cache_limites.obtener()
    except (httpx.HTTPError, ValueError, KeyError) as e:
        raise LimitesError(f"No se pudieron obtener los límites de las localidades: {e}") from e


class LimitesError(Exception):
    pass
