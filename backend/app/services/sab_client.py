"""Cliente del SAB (Sistema de Alerta de Bogotá - IDIGER).

Es el mismo servicio que alimenta https://app.sab.gov.co/sab/lluvias.htm
"""

import logging

import httpx

from app.config import get_settings
from app.models.schemas import EstacionSAB

logger = logging.getLogger(__name__)

ID_TIPO_PLUVIOMETRO = 5


class SABError(Exception):
    """El SAB no respondió o respondió algo inesperado."""


def obtener_pluviometros() -> list[EstacionSAB]:
    settings = get_settings()
    try:
        resp = httpx.post(
            settings.sab_url,
            data={"idtiposensor": ID_TIPO_PLUVIOMETRO},
            timeout=settings.sab_timeout_segundos,
        )
        resp.raise_for_status()
        crudos = resp.json()["TipoSensores"]
    except (httpx.HTTPError, ValueError, KeyError) as e:
        raise SABError(f"No se pudo consultar el SAB: {e}") from e

    estaciones = []
    for crudo in crudos:
        try:
            estaciones.append(EstacionSAB.model_validate(crudo))
        except ValueError as e:
            logger.warning("Estación del SAB descartada (%s): %s", crudo.get("ESTACION"), e)
    logger.info("SAB: %d estaciones recibidas", len(estaciones))
    return estaciones
