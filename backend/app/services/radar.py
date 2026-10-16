"""Radar meteorológico del IDIGER (la misma capa que muestra https://app.sab.gov.co/sab/lluvias.htm).

El IDIGER publica un KMZ con una imagen PNG transparente (reflectividad: donde hay lluvia hay color)
y los límites geográficos que cubre. Se descarga, se extrae y se entrega al front en un solo JSON.
"""

import base64
import io
import logging
import re
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree

import httpx

from app.config import get_settings
from app.core.cache import CacheTTL
from app.core.tiempo import BOGOTA_TZ

logger = logging.getLogger(__name__)

URL_KMZ = "https://evp.sire.gov.co/radar_animate/datos/kml/reflectividad.kmz"
CACHE_SEGUNDOS = 120
LIMITE_KMZ_BYTES = 5 * 1024 * 1024  # el real pesa unos KB; el tope evita descargas absurdas


class RadarError(Exception):
    """No se pudo obtener o interpretar el radar."""


def _texto(raiz: ElementTree.Element, nombre: str) -> str | None:
    # El KML trae namespace; se busca por nombre local para no depender de él.
    for el in raiz.iter():
        if el.tag.rsplit("}", 1)[-1] == nombre and el.text:
            return el.text.strip()
    return None


def _capturado_en(nombre_carpeta: str | None) -> datetime | None:
    """«1399BOG-Intensity (Horizontal)-Wed Oct 14 16:17:48 2026 GMT» → fecha en hora de Bogotá."""
    if not nombre_carpeta:
        return None
    m = re.search(r"([A-Z][a-z]{2} [A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2} \d{4}) GMT", nombre_carpeta)
    if not m:
        return None
    try:
        utc = datetime.strptime(re.sub(r" +", " ", m.group(1)), "%a %b %d %H:%M:%S %Y")
    except ValueError:
        return None
    return utc.replace(tzinfo=timezone.utc).astimezone(BOGOTA_TZ)


def interpretar_kmz(contenido: bytes) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            kml = next(n for n in z.namelist() if n.lower().endswith(".kml"))
            raiz = ElementTree.fromstring(z.read(kml))
            archivo = _texto(raiz, "href")
            if not archivo:
                raise RadarError("El KMZ del radar no indica la imagen.")
            png = z.read(archivo)
            limites = {k: float(_texto(raiz, k)) for k in ("north", "south", "east", "west")}
            nombre = _texto(raiz, "name")
    except (zipfile.BadZipFile, StopIteration, KeyError, TypeError, ValueError, ElementTree.ParseError) as e:
        raise RadarError(f"No se pudo interpretar el KMZ del radar: {e}") from e

    return {
        "capturado_en": _capturado_en(nombre),
        "norte": limites["north"],
        "sur": limites["south"],
        "este": limites["east"],
        "oeste": limites["west"],
        "imagen": "data:image/png;base64," + base64.b64encode(png).decode(),
    }


def _descargar() -> dict:
    try:
        resp = httpx.get(URL_KMZ, timeout=get_settings().sab_timeout_segundos, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise RadarError(f"No se pudo descargar el radar: {e}") from e
    if len(resp.content) > LIMITE_KMZ_BYTES:
        raise RadarError("El archivo del radar es más grande de lo esperado.")
    datos = interpretar_kmz(resp.content)
    datos["obtenido_en"] = datetime.now(BOGOTA_TZ)
    return datos


_cache = CacheTTL(_descargar, CACHE_SEGUNDOS)


def obtener_radar() -> dict:
    return _cache.obtener()
