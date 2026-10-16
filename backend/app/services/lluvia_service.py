"""Reglas de negocio de la lluvia: intensidad, acumulados, resumen y cercanía.

Todas las funciones son puras (no consultan red ni base de datos) para poder probarlas.
"""

import math
from collections import defaultdict
from datetime import datetime, timedelta

from app.models.schemas import (
    Cercania,
    Estacion,
    EstacionCercana,
    EstacionSAB,
    Intensidad,
    LocalidadResumen,
    NivelAcumulado,
    Resumen,
)

# Umbrales de intensidad en mm/hora (clasificación meteorológica habitual).
UMBRALES_INTENSIDAD = [
    (2.5, Intensidad.ligera),
    (7.6, Intensidad.moderada),
    (50, Intensidad.fuerte),
]

# Umbrales de acumulado diario en mm (los mismos colores del mapa del SAB).
UMBRALES_ACUMULADO = [
    (10, NivelAcumulado.bajo),
    (30, NivelAcumulado.moderado),
    (50, NivelAcumulado.alto),
]


def clasificar_intensidad(mm_5min: float) -> Intensidad:
    mm_hora = mm_5min * 12
    if mm_hora <= 0:
        return Intensidad.sin_lluvia
    for limite, nivel in UMBRALES_INTENSIDAD:
        if mm_hora < limite:
            return nivel
    return Intensidad.muy_fuerte


def clasificar_acumulado(mm: float) -> NivelAcumulado:
    if mm <= 0:
        return NivelAcumulado.sin_lluvia
    for limite, nivel in UMBRALES_ACUMULADO:
        if mm <= limite:
            return nivel
    return NivelAcumulado.muy_alto


def esta_desactualizada(est: EstacionSAB, ahora: datetime, minutos: int) -> bool:
    return est.fecha_lectura is None or ahora - est.fecha_lectura > timedelta(minutes=minutos)


def a_estacion(est: EstacionSAB, ahora: datetime, minutos_vieja: int) -> Estacion:
    desactualizada = esta_desactualizada(est, ahora, minutos_vieja)
    return Estacion(
        id_sensor=est.id_sensor,
        nombre=est.nombre,
        localidad=est.localidad.title(),
        latitud=est.latitud,
        longitud=est.longitud,
        valor_5min=est.valor_5min,
        mm_hora=round(est.valor_5min * 12, 2),
        acumulado_dia=est.acumulado_dia,
        intensidad=clasificar_intensidad(est.valor_5min),
        nivel_acumulado=clasificar_acumulado(est.acumulado_dia),
        lloviendo=est.valor_5min > 0 and not desactualizada,
        fecha_lectura=est.fecha_lectura,
        desactualizada=desactualizada,
    )


def construir_resumen(estaciones: list[Estacion], obtenido_en: datetime) -> Resumen:
    por_localidad: dict[str, list[Estacion]] = defaultdict(list)
    for est in estaciones:
        por_localidad[est.localidad].append(est)

    localidades = []
    for nombre, grupo in por_localidad.items():
        acumulados = [e.acumulado_dia for e in grupo]
        maximo = max(acumulados)
        lloviendo = sum(e.lloviendo for e in grupo)
        localidades.append(
            LocalidadResumen(
                localidad=nombre,
                estaciones=len(grupo),
                estaciones_lloviendo=lloviendo,
                acumulado_max=maximo,
                acumulado_promedio=round(sum(acumulados) / len(acumulados), 2),
                nivel_acumulado=clasificar_acumulado(maximo),
                lloviendo=lloviendo > 0,
            )
        )
    localidades.sort(key=lambda l: (-l.acumulado_max, l.localidad))

    lloviendo = [e for e in estaciones if e.lloviendo]
    return Resumen(
        datos_obtenidos_en=obtenido_en,
        total_estaciones=len(estaciones),
        estaciones_lloviendo=len(lloviendo),
        estaciones_desactualizadas=sum(e.desactualizada for e in estaciones),
        localidades_lloviendo=sorted({e.localidad for e in lloviendo}),
        estacion_max_acumulado=max(estaciones, key=lambda e: e.acumulado_dia, default=None),
        estacion_max_intensidad=max(lloviendo, key=lambda e: e.valor_5min, default=None),
        localidades=localidades,
    )


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en línea recta (fórmula del haversine)."""
    radio_tierra = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radio_tierra * math.asin(math.sqrt(a))


def estaciones_cercanas(
    estaciones: list[Estacion], lat: float, lon: float, cantidad: int, obtenido_en: datetime
) -> Cercania:
    ordenadas = sorted(
        (
            EstacionCercana(
                **e.model_dump(),
                distancia_km=round(distancia_km(lat, lon, e.latitud, e.longitud), 2),
            )
            for e in estaciones
        ),
        key=lambda e: e.distancia_km,
    )[:cantidad]
    return Cercania(
        datos_obtenidos_en=obtenido_en,
        latitud=lat,
        longitud=lon,
        lloviendo_cerca=any(e.lloviendo for e in ordenadas),
        estaciones=ordenadas,
    )
