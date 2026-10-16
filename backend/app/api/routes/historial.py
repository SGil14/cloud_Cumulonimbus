"""Historial de lluvia: lo que ya pasó, a partir de las lecturas guardadas."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.historial import HistorialDestino, Periodo, RankingHistorial, SerieHistorial
from app.services import historial_service

router = APIRouter(prefix="/api/historial", tags=["historial"])

PERIODO = Query("24h", description="Ventana de tiempo: 6h, 24h (por hora) o 7d, 30d (por día)")


@router.get("/serie", response_model=SerieHistorial)
def serie(
    periodo: Periodo = PERIODO,
    localidad: str | None = Query(None, max_length=80, description="Si se omite, se promedia toda Bogotá"),
    db: Session = Depends(get_db),
):
    """Cuánto llovió en cada intervalo, para toda Bogotá o para una localidad."""
    return historial_service.serie(db, periodo, localidad)


@router.get("/ranking", response_model=RankingHistorial)
def ranking(periodo: Periodo = PERIODO, db: Session = Depends(get_db)):
    """Localidades ordenadas por lo que llovió en el periodo."""
    return historial_service.ranking(db, periodo)


@router.get("/destino", response_model=HistorialDestino)
def destino(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    periodo: Periodo = PERIODO,
    db: Session = Depends(get_db),
):
    """Cuándo llovió cerca de un punto: la serie de las estaciones más cercanas."""
    return historial_service.destino(db, periodo, lat, lon)
