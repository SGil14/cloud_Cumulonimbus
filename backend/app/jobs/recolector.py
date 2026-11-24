"""Recolector del histórico: consulta el SAB cada N minutos y guarda las lecturas.

No cambia cómo se usa la app; solo asegura que el histórico no tenga huecos.
Se activa o desactiva con RECOLECTOR_ACTIVO en el .env.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.core.tiempo import BOGOTA_TZ, ahora_bogota
from app.services import estaciones_service

logger = logging.getLogger(__name__)


def recolectar() -> None:
    try:
        estaciones_service.obtener_snapshot(forzar=True)
    except Exception:
        logger.exception("Falló la recolección programada")


def crear_recolector() -> BackgroundScheduler | None:
    settings = get_settings()
    if not settings.recolector_activo:
        logger.info("Recolector desactivado")
        return None
    scheduler = BackgroundScheduler(timezone=BOGOTA_TZ)
    scheduler.add_job(
        recolectar,
        "interval",
        minutes=settings.recolector_intervalo_minutos,
        id="recolector_sab",
        max_instances=1,
        coalesce=True,
        next_run_time=ahora_bogota(),  # primera recolección al arrancar
    )
    logger.info("Recolector activo cada %d minutos", settings.recolector_intervalo_minutos)
    return scheduler
