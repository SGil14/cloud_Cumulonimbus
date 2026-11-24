"""Punto único de acceso a los datos de estaciones.

Consulta el SAB, guarda cada consulta en el histórico y mantiene una caché corta para no
saturar el SAB cuando varias personas usan la app al mismo tiempo.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime

from app.config import get_settings
from app.core import metricas
from app.core.cache import CacheTTL
from app.core.tiempo import ahora_bogota
from app.db.session import SessionLocal
from app.models.schemas import Estacion, EstacionSAB
from app.repositories import lecturas_repo
from app.services import sab_client
from app.services.lluvia_service import a_estacion

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Snapshot:
    obtenido_en: datetime
    estaciones: list[EstacionSAB]


def _cargar_desde_sab() -> Snapshot:
    inicio = time.perf_counter()
    try:
        crudas = sab_client.obtener_pluviometros()
    except Exception:
        metricas.SAB_CONSULTAS.labels("error").inc()
        raise
    metricas.SAB_LATENCIA.observe(time.perf_counter() - inicio)
    metricas.SAB_CONSULTAS.labels("ok").inc()
    snapshot = Snapshot(obtenido_en=ahora_bogota(), estaciones=crudas)
    try:
        with SessionLocal() as db:
            nuevas = lecturas_repo.guardar_snapshot(db, snapshot.estaciones)
        logger.info("Histórico: %d lecturas nuevas guardadas", nuevas)
    except Exception:
        # Si la base falla, la app igual debe responder con los datos en vivo.
        logger.exception("No se pudo guardar el snapshot en la base de datos")
    return snapshot


_cache = CacheTTL(_cargar_desde_sab, get_settings().cache_estaciones_segundos)


def obtener_snapshot(forzar: bool = False) -> Snapshot:
    return _cache.obtener(forzar=forzar)


def obtener_estaciones(forzar: bool = False) -> tuple[datetime, list[Estacion]]:
    snapshot = obtener_snapshot(forzar)
    minutos = get_settings().minutos_lectura_vieja
    ahora = ahora_bogota()
    estaciones = [a_estacion(e, ahora, minutos) for e in snapshot.estaciones]
    metricas.ESTACIONES_TOTAL.set(len(estaciones))
    metricas.ESTACIONES_LLOVIENDO.set(sum(1 for e in estaciones if e.lloviendo))
    return snapshot.obtenido_en, estaciones
