"""Predicción de lluvia en la próxima hora para un punto (un destino)."""

import time
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core import metricas
from app.core.tiempo import BOGOTA_TZ, ahora_bogota
from app.db.session import get_db
from app.models.prediccion import PrediccionRespuesta
from app.repositories import lecturas_repo
from app.services import estaciones_service, prediccion_service

router = APIRouter(prefix="/api", tags=["prediccion"])

HISTORIAL_MINUTOS = 80  # la última hora más un paso previo, para calcular las diferencias del primer paso


@router.get("/prediccion", response_model=PrediccionRespuesta)
def prediccion(
    lat: float = Query(..., ge=-90, le=90, description="Latitud del destino"),
    lon: float = Query(..., ge=-180, le=180, description="Longitud del destino"),
    db: Session = Depends(get_db),
):
    """Probabilidad de lluvia en la próxima hora cerca de un punto.

    Usa el modelo entrenado si hay una hora de lecturas continuas guardadas cerca; si no, responde con la regla
    «si llueve ahora, seguirá lloviendo» e indica el motivo. El campo `metodo` dice cuál se usó.
    """
    inicio = time.perf_counter()
    obtenido_en, estaciones = estaciones_service.obtener_estaciones()
    if not estaciones:
        raise HTTPException(503, "No hay estaciones disponibles en este momento. Inténtalo de nuevo en unos minutos.")

    ahora = ahora_bogota()
    desde = prediccion_service.instante_de_decision(ahora).replace(tzinfo=BOGOTA_TZ) - timedelta(minutes=HISTORIAL_MINUTOS)

    def historial(ids: list[int]):
        return lecturas_repo.lecturas_recientes(db, ids, desde)

    respuesta = prediccion_service.predecir(
        lat, lon, estaciones, obtenido_en, ahora, historial, prediccion_service.cargar_modelo()
    )
    metricas.IA_PREDICCIONES.labels(respuesta.metodo).inc()
    metricas.IA_LATENCIA.observe(time.perf_counter() - inicio)
    if respuesta.probabilidad is not None:
        metricas.IA_PROBABILIDAD.set(respuesta.probabilidad)
    return respuesta
