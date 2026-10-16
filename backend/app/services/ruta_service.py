"""Lluvia a lo largo de una ruta.

1. Se pide el trayecto a Valhalla (servicio gratuito de OpenStreetMap).
2. Se parte en muestras cada ~400 m.
3. En cada muestra se mira la estación de lluvia más cercana: llueve, está seco o queda demasiado lejos
   de cualquier estación para saberlo.
4. Se agrupan las muestras seguidas con el mismo estado en tramos.

Importante: muestra la lluvia de AHORA, no la que habrá cuando llegues a cada punto.
"""

import logging
from collections import Counter
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.models.ruta import EstadoTramo, Modo, TramoRuta
from app.models.schemas import Estacion, Intensidad
from app.services.lluvia_service import distancia_km

logger = logging.getLogger(__name__)

COSTING: dict[str, str] = {"auto": "auto", "bus": "bus", "bicicleta": "bicycle", "a_pie": "pedestrian"}
PASO_MUESTRA_M = 400
RADIO_COBERTURA_KM = 4.0  # más lejos de esto, una estación no dice nada del punto
ORDEN_INTENSIDAD = {
    Intensidad.sin_lluvia: 0, Intensidad.ligera: 1, Intensidad.moderada: 2, Intensidad.fuerte: 3, Intensidad.muy_fuerte: 4,
}

Coordenada = tuple[float, float]  # (lon, lat)


class RutaError(Exception):
    """No se pudo calcular la ruta."""


# ---------- Valhalla ----------

def decodificar_polilinea(codificada: str, precision: int = 6) -> list[Coordenada]:
    """Polilínea codificada de Valhalla (precisión 6) → lista de (lon, lat)."""
    factor = 10 ** precision
    lat = lon = indice = 0
    puntos: list[Coordenada] = []
    while indice < len(codificada):
        for eje in (0, 1):
            resultado = desplazamiento = 0
            while True:
                byte = ord(codificada[indice]) - 63
                indice += 1
                resultado |= (byte & 0x1F) << desplazamiento
                desplazamiento += 5
                if byte < 0x20:
                    break
            delta = ~(resultado >> 1) if resultado & 1 else resultado >> 1
            if eje == 0:
                lat += delta
            else:
                lon += delta
        puntos.append((lon / factor, lat / factor))
    return puntos


@dataclass(frozen=True)
class Trayecto:
    coordenadas: list[Coordenada]
    distancia_km: float
    duracion_s: float


def pedir_trayecto(origen: Coordenada, destino: Coordenada, modo: Modo) -> Trayecto:
    """origen y destino como (lon, lat)."""
    s = get_settings()
    cuerpo = {
        "locations": [{"lon": origen[0], "lat": origen[1]}, {"lon": destino[0], "lat": destino[1]}],
        "costing": COSTING[modo],
        "directions_options": {"units": "kilometers", "language": "es-ES"},
    }
    try:
        resp = httpx.post(
            s.ruta_url, json=cuerpo, headers={"User-Agent": s.nominatim_user_agent}, timeout=s.ruta_timeout_segundos
        )
        if resp.status_code == 400:
            raise RutaError("No encontré un camino entre esos dos puntos.")
        resp.raise_for_status()
        viaje = resp.json()["trip"]
    except RutaError:
        raise
    except (httpx.HTTPError, ValueError, KeyError) as e:
        raise RutaError(f"El servicio de rutas no respondió: {e}") from e

    coordenadas: list[Coordenada] = []
    for tramo in viaje["legs"]:
        puntos = decodificar_polilinea(tramo["shape"])
        coordenadas.extend(puntos[1:] if coordenadas else puntos)
    return Trayecto(coordenadas, float(viaje["summary"]["length"]), float(viaje["summary"]["time"]))


# ---------- Análisis (funciones puras) ----------

@dataclass(frozen=True)
class Muestra:
    km: float
    lon: float
    lat: float
    indice: int  # posición del vértice de la ruta más cercano (hacia atrás)


def muestrear(coords: list[Coordenada], paso_m: int = PASO_MUESTRA_M) -> list[Muestra]:
    """Puntos a lo largo de la ruta, uno cada `paso_m` metros, incluidos el inicio y el final."""
    if len(coords) < 2:
        return [Muestra(0, coords[0][0], coords[0][1], 0)] if coords else []
    muestras = [Muestra(0.0, coords[0][0], coords[0][1], 0)]
    acumulado = 0.0
    proxima = paso_m / 1000
    for i in range(1, len(coords)):
        (lon0, lat0), (lon1, lat1) = coords[i - 1], coords[i]
        tramo = distancia_km(lat0, lon0, lat1, lon1)
        while tramo > 0 and acumulado + tramo >= proxima:
            f = (proxima - acumulado) / tramo
            muestras.append(Muestra(proxima, lon0 + (lon1 - lon0) * f, lat0 + (lat1 - lat0) * f, i - 1))
            proxima += paso_m / 1000
        acumulado += tramo
    ultimo = coords[-1]
    if acumulado - muestras[-1].km > 0.05:
        muestras.append(Muestra(acumulado, ultimo[0], ultimo[1], len(coords) - 1))
    return muestras


def _estado_en(m: Muestra, estaciones: list[Estacion]) -> tuple[EstadoTramo, Estacion | None]:
    cercana = min(estaciones, key=lambda e: distancia_km(m.lat, m.lon, e.latitud, e.longitud))
    if distancia_km(m.lat, m.lon, cercana.latitud, cercana.longitud) > RADIO_COBERTURA_KM:
        return "sin_datos", None
    if cercana.desactualizada:
        return "sin_datos", cercana
    return ("lluvia" if cercana.lloviendo else "seco"), cercana


def analizar(coords: list[Coordenada], estaciones: list[Estacion]) -> list[TramoRuta]:
    """Agrupa las muestras seguidas con el mismo estado en tramos con su geometría."""
    muestras = muestrear(coords)
    if not muestras or not estaciones:
        return []
    clasificadas = [(m, *_estado_en(m, estaciones)) for m in muestras]

    grupos: list[list[tuple[Muestra, EstadoTramo, Estacion | None]]] = []
    for item in clasificadas:
        if grupos and grupos[-1][-1][1] == item[1]:
            grupos[-1].append(item)
        else:
            grupos.append([item])

    tramos = []
    for k, grupo in enumerate(grupos):
        estado = grupo[0][1]
        primero, ultimo = grupo[0][0], grupo[-1][0]
        siguiente = grupos[k + 1][0][0] if k + 1 < len(grupos) else None
        fin_indice = (siguiente.indice if siguiente else len(coords) - 1) + 1
        # Los tramos comparten el punto de unión para que la línea del mapa no quede cortada.
        puntos = [[primero.lon, primero.lat]] if k else []
        puntos += [list(c) for c in coords[primero.indice + 1 if k else primero.indice : fin_indice]]
        if siguiente:
            puntos.append([siguiente.lon, siguiente.lat])
        hasta = siguiente.km if siguiente else ultimo.km

        estaciones_grupo = [e for _, _, e in grupo if e is not None]
        con_lluvia = [e for e in estaciones_grupo if e.lloviendo]
        usadas = con_lluvia if estado == "lluvia" else estaciones_grupo
        representativa = Counter(e.nombre for e in usadas).most_common(1)[0][0] if usadas else None
        fuerte = max(con_lluvia, key=lambda e: e.mm_hora, default=None) if estado == "lluvia" else None
        tramos.append(TramoRuta(
            desde_km=round(primero.km, 2),
            hasta_km=round(hasta, 2),
            estado=estado,
            estacion=representativa,
            intensidad=fuerte.intensidad if fuerte else None,
            mm_hora=fuerte.mm_hora if fuerte else 0,
            coordenadas=puntos,
        ))
    return tramos


def resumir(tramos: list[TramoRuta], distancia_km_total: float) -> tuple[bool, int, str]:
    """(hay_lluvia, % del trayecto sin datos, frase para la persona)."""
    if not tramos:
        return False, 100, "No pude revisar la lluvia en este trayecto."
    largo = max(distancia_km_total, 0.01)
    sin_datos = sum(t.hasta_km - t.desde_km for t in tramos if t.estado == "sin_datos")
    pct_sin_datos = min(100, round(100 * sin_datos / largo))
    con_lluvia = [t for t in tramos if t.estado == "lluvia"]

    if con_lluvia:
        primero, ultimo = con_lluvia[0], con_lluvia[-1]
        donde = f"entre el km {primero.desde_km:g} y el km {ultimo.hasta_km:g}"
        cerca = f" (cerca de {primero.estacion})" if primero.estacion else ""
        veces = f" en {len(con_lluvia)} tramos" if len(con_lluvia) > 1 else ""
        return True, pct_sin_datos, f"Puede mojarte: hay lluvia{veces} {donde} del trayecto{cerca}."
    if pct_sin_datos >= 30:
        return False, pct_sin_datos, (
            f"No hay lluvia en las estaciones cercanas, pero el {pct_sin_datos}% del trayecto queda lejos "
            "de una estación: no se puede asegurar."
        )
    return False, pct_sin_datos, "Sin lluvia en todo el trayecto."
