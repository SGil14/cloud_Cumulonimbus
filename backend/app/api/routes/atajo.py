"""Respuesta en texto plano para el atajo de iPhone (app Atajos): una frase corta que dice si llueve en un destino."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.schemas import Cercania, EstacionCercana, Intensidad, UbicacionDestino
from app.repositories import consultas_repo
from app.services import destinos, estaciones_service, lluvia_service
from app.services.geocoding.base import GeocodingError
from app.services.sab_client import SABError

router = APIRouter(prefix="/api", tags=["atajo"])

_INTENSIDAD = {
    Intensidad.ligera: "ligera",
    Intensidad.moderada: "moderada",
    Intensidad.fuerte: "fuerte",
    Intensidad.muy_fuerte: "muy fuerte",
}


def _num(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def _lugar(u: UbicacionDestino, texto: str) -> str:
    partes = [p for p in (u.barrio, u.localidad) if p]
    return ", ".join(partes) if partes else texto


def construir_frase(texto: str, ubicacion: UbicacionDestino, cercania: Cercania) -> str:
    """Una frase que se lee bien en voz alta o en la pantalla del iPhone."""
    lugar = _lugar(ubicacion, texto)
    cerca: list[EstacionCercana] = cercania.estaciones
    llueven = [e for e in cerca if e.lloviendo]

    if llueven:
        e = llueven[0]
        frase = (
            f"Sí, llueve cerca de {lugar}. {e.nombre}, a {_num(e.distancia_km)} km, "
            f"marca lluvia {_INTENSIDAD.get(e.intensidad, '')} ({_num(e.mm_hora)} mm/h)."
        )
    elif cerca and all(e.desactualizada for e in cerca):
        frase = f"No se puede asegurar para {lugar}: las estaciones más cercanas no tienen lectura reciente."
    else:
        frase = f"No llueve cerca de {lugar}."
        con_dato = [e for e in cerca if not e.desactualizada]
        if con_dato and con_dato[0].acumulado_dia > 0:
            frase += f" Hoy cayeron {_num(con_dato[0].acumulado_dia)} mm en la estación más cercana."
        else:
            frase += " Ninguna estación cercana registra lluvia ahora."
    if ubicacion.aproximada:
        frase += " (Ubicación aproximada.)"
    return frase


@router.get("/atajo", response_class=PlainTextResponse)
def atajo(
    q: str = Query(..., min_length=2, max_length=200, description="Dirección, barrio, lugar, localidad o 'lat,lon'"),
    db: Session = Depends(get_db),
):
    """¿Llueve en este destino? Responde una frase en texto plano, pensada para el atajo de iPhone.

    Acepta lo mismo que `/api/destino`. Con «Obtener ubicación actual» del iPhone se puede enviar `lat,lon`.
    """
    texto = q.strip()
    try:
        obtenido_en, estaciones = estaciones_service.obtener_estaciones()
    except SABError:
        return PlainTextResponse("El SAB no responde en este momento. Inténtalo de nuevo en unos minutos.", status_code=502)
    try:
        r = destinos.resolver(db, texto, estaciones)
    except GeocodingError:
        return PlainTextResponse("El servicio de búsqueda no responde. Inténtalo de nuevo en unos minutos.", status_code=503)

    if not r.encontrado:
        consultas_repo.registrar_consulta(db, texto=texto, tipo=r.tipo.value, encontrado=False)
        return PlainTextResponse(f"No encontré «{texto}». Prueba con otra dirección o con un barrio.")

    u = r.ubicacion
    cercania = lluvia_service.estaciones_cercanas(r.estaciones, u.latitud, u.longitud, r.cantidad, obtenido_en)
    consultas_repo.registrar_consulta(
        db, texto=texto, tipo=r.tipo.value, encontrado=True,
        latitud=u.latitud, longitud=u.longitud, barrio=u.barrio, localidad=u.localidad,
        proveedor=u.proveedor, lloviendo_cerca=cercania.lloviendo_cerca,
    )
    return PlainTextResponse(construir_frase(texto, u, cercania))
