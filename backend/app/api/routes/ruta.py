"""Lluvia a lo largo de una ruta de un lugar a otro."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ruta import Modo, RutaRespuesta
from app.repositories import consultas_repo
from app.services import destinos, estaciones_service, ruta_service
from app.services.geocoding.base import GeocodingError
from app.services.lluvia_service import distancia_km

router = APIRouter(prefix="/api", tags=["ruta"])

NOTA = "Muestra la lluvia de ahora, no la que habrá cuando llegues a cada punto."


@router.get("/ruta", response_model=RutaRespuesta)
def ruta(
    origen: str = Query(..., min_length=2, max_length=200),
    destino: str = Query(..., min_length=2, max_length=200),
    modo: Modo = Query("auto", description="auto, bus, bicicleta o a_pie"),
    db: Session = Depends(get_db),
):
    """Calcula el trayecto y dice en qué partes llueve ahora."""
    obtenido_en, estaciones = estaciones_service.obtener_estaciones()
    try:
        o = destinos.resolver(db, origen, estaciones)
        d = destinos.resolver(db, destino, estaciones)
    except GeocodingError:
        raise HTTPException(503, "El servicio de búsqueda no responde. Inténtalo de nuevo en unos minutos.")

    texto = f"{origen.strip()} → {destino.strip()}"
    if not o.encontrado or not d.encontrado:
        quien = "el origen" if not o.encontrado else "el destino"
        motivo = (o if not o.encontrado else d).mensaje
        consultas_repo.registrar_consulta(db, texto=texto, tipo="ruta", encontrado=False)
        return RutaRespuesta(encontrado=False, mensaje=f"No pude ubicar {quien}. {motivo}", modo=modo)

    uo, ud = o.ubicacion, d.ubicacion
    if distancia_km(uo.latitud, uo.longitud, ud.latitud, ud.longitud) < 0.15:
        return RutaRespuesta(
            encontrado=False, modo=modo, origen=uo, destino=ud,
            mensaje="El origen y el destino son prácticamente el mismo lugar.",
        )

    try:
        trayecto = ruta_service.pedir_trayecto((uo.longitud, uo.latitud), (ud.longitud, ud.latitud), modo)
    except ruta_service.RutaError as e:
        raise HTTPException(502, f"No pude calcular la ruta. {e}")

    tramos = ruta_service.analizar(trayecto.coordenadas, estaciones)
    hay_lluvia, pct_sin_datos, resumen = ruta_service.resumir(tramos, trayecto.distancia_km)
    consultas_repo.registrar_consulta(
        db, texto=texto, tipo="ruta", encontrado=True, latitud=ud.latitud, longitud=ud.longitud,
        barrio=ud.barrio, localidad=ud.localidad, proveedor=ud.proveedor, lloviendo_cerca=hay_lluvia,
    )
    return RutaRespuesta(
        encontrado=True, mensaje="Ruta calculada.", modo=modo, origen=uo, destino=ud,
        distancia_km=round(trayecto.distancia_km, 1), duracion_min=round(trayecto.duracion_s / 60),
        hay_lluvia=hay_lluvia, porcentaje_sin_datos=pct_sin_datos, resumen=resumen, nota=NOTA,
        tramos=tramos, datos_obtenidos_en=obtenido_en,
    )
