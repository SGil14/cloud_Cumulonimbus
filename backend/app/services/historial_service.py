"""Historial de lluvia a partir de las lecturas guardadas en PostgreSQL.

Cómo se calcula cuánto llovió:
- **Por hora** (6 h y 24 h): se usa el acumulado del día de cada estación. La lluvia de una lectura es la
  diferencia con la lectura anterior; si el acumulado baja, es que se reinició a medianoche y vale lo que marca.
  Así no importa que las lecturas lleguen cada 2 o cada 5 minutos.
- **Por día** (7 d y 30 d): el máximo acumulado de cada estación en ese día (el acumulado solo sube durante el día).
- Para una localidad o toda Bogotá se promedia entre las estaciones que reportaron en ese intervalo.

Si la app estuvo apagada, el intervalo queda «sin datos»: no se inventa lluvia ni se asume que no llovió.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.tiempo import BOGOTA_TZ, ahora_bogota
from app.models.historial import (
    HistorialDestino,
    ItemRanking,
    Paso,
    Periodo,
    PuntoHistorial,
    RankingHistorial,
    SerieEstacion,
    SerieHistorial,
)
from app.services.lluvia_service import distancia_km

PERIODOS: dict[str, tuple[Paso, int]] = {
    "6h": ("hora", 6),
    "24h": ("hora", 24),
    "7d": ("dia", 7),
    "30d": ("dia", 30),
}
HORAS_PREVIAS = 3  # lecturas anteriores a la ventana, para calcular la diferencia de la primera

_SQL_HORA = """
WITH base AS (
  SELECT l.id_sensor, e.localidad, l.fecha_lectura, l.acumulado_dia,
         lag(l.acumulado_dia) OVER (PARTITION BY l.id_sensor ORDER BY l.fecha_lectura) AS previo
  FROM lecturas l JOIN estaciones e ON e.id_sensor = l.id_sensor
  WHERE l.fecha_lectura >= :desde_ext AND l.fecha_lectura <= :hasta {filtro}
)
SELECT date_trunc('hour', fecha_lectura AT TIME ZONE 'America/Bogota') AS inicio,
       id_sensor, localidad,
       sum(CASE WHEN previo IS NULL THEN 0
                WHEN acumulado_dia >= previo THEN acumulado_dia - previo
                ELSE acumulado_dia END) AS mm,
       count(*) AS lecturas
FROM base
WHERE fecha_lectura >= :desde
GROUP BY 1, 2, 3
"""

_SQL_DIA = """
SELECT date_trunc('day', l.fecha_lectura AT TIME ZONE 'America/Bogota') AS inicio,
       l.id_sensor, e.localidad, max(l.acumulado_dia) AS mm, count(*) AS lecturas
FROM lecturas l JOIN estaciones e ON e.id_sensor = l.id_sensor
WHERE l.fecha_lectura >= :desde AND l.fecha_lectura <= :hasta {filtro}
GROUP BY 1, 2, 3
"""


@dataclass(frozen=True)
class Ventana:
    periodo: Periodo
    paso: Paso
    desde: datetime
    hasta: datetime
    intervalos: list[datetime]  # inicio de cada intervalo, en hora de Bogotá


def ventana(periodo: Periodo, ahora: datetime) -> Ventana:
    paso, cantidad = PERIODOS[periodo]
    if paso == "hora":
        ultimo = ahora.replace(minute=0, second=0, microsecond=0)
        primero = ultimo - timedelta(hours=cantidad - 1)
        intervalos = [primero + timedelta(hours=i) for i in range(cantidad)]
    else:
        ultimo = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
        primero = ultimo - timedelta(days=cantidad - 1)
        intervalos = [primero + timedelta(days=i) for i in range(cantidad)]
    return Ventana(periodo=periodo, paso=paso, desde=primero, hasta=ahora, intervalos=intervalos)


# ---------- Agregación (funciones puras, probadas sin base de datos) ----------

Fila = tuple[datetime, int, str, float, int]  # inicio (hora local sin zona), id_sensor, localidad, mm, lecturas


def _a_local(inicio: datetime) -> datetime:
    return inicio.replace(tzinfo=BOGOTA_TZ) if inicio.tzinfo is None else inicio.astimezone(BOGOTA_TZ)


def agregar_serie(
    filas: list[Fila], v: Ventana, etiqueta: str, datos_desde: datetime | None
) -> SerieHistorial:
    """Promedia entre estaciones por intervalo y calcula total, pico y cobertura."""
    por_intervalo: dict[datetime, list[float]] = defaultdict(list)
    lecturas: dict[datetime, int] = defaultdict(int)
    sensores: set[int] = set()
    for inicio, id_sensor, _loc, mm, n in filas:
        clave = _a_local(inicio)
        por_intervalo[clave].append(float(mm))
        lecturas[clave] += int(n)
        sensores.add(id_sensor)

    puntos = []
    for inicio in v.intervalos:
        valores = por_intervalo.get(inicio)
        puntos.append(PuntoHistorial(
            inicio=inicio,
            mm=round(sum(valores) / len(valores), 2) if valores else None,
            lecturas=lecturas.get(inicio, 0),
        ))

    con_datos = [p for p in puntos if p.mm is not None]
    return SerieHistorial(
        etiqueta=etiqueta,
        periodo=v.periodo,
        paso=v.paso,
        desde=v.intervalos[0],
        hasta=v.hasta,
        puntos=puntos,
        total_mm=round(sum(p.mm for p in con_datos), 2),
        pico=max(con_datos, key=lambda p: p.mm, default=None) if any(p.mm for p in con_datos) else None,
        estaciones=len(sensores),
        datos_desde=datos_desde,
        cobertura_pct=round(100 * len(con_datos) / len(puntos)) if puntos else 0,
    )


def agregar_ranking(filas: list[Fila], v: Ventana, datos_desde: datetime | None) -> RankingHistorial:
    """Total de lluvia por localidad: promedio entre sus estaciones del total de cada estación."""
    total_estacion: dict[int, float] = defaultdict(float)
    localidad_de: dict[int, str] = {}
    intervalos_con_datos: set[datetime] = set()
    for inicio, id_sensor, loc, mm, _n in filas:
        total_estacion[id_sensor] += float(mm)
        localidad_de[id_sensor] = loc
        intervalos_con_datos.add(_a_local(inicio))

    por_localidad: dict[str, list[float]] = defaultdict(list)
    for id_sensor, total in total_estacion.items():
        por_localidad[localidad_de[id_sensor]].append(total)

    items = [
        ItemRanking(
            localidad=loc,
            total_mm=round(sum(v_) / len(v_), 2),
            max_estacion_mm=round(max(v_), 2),
            estaciones=len(v_),
        )
        for loc, v_ in por_localidad.items()
    ]
    items.sort(key=lambda i: (-i.total_mm, i.localidad))
    con_datos = sum(1 for i in v.intervalos if i in intervalos_con_datos)
    return RankingHistorial(
        periodo=v.periodo,
        paso=v.paso,
        desde=v.intervalos[0],
        hasta=v.hasta,
        datos_desde=datos_desde,
        cobertura_pct=round(100 * con_datos / len(v.intervalos)),
        items=items,
    )


# ---------- Acceso a datos ----------

def _datos_desde(db: Session) -> datetime | None:
    primera = db.execute(text("SELECT min(fecha_lectura) FROM lecturas")).scalar()
    return primera.astimezone(BOGOTA_TZ) if primera else None


def _filas(db: Session, v: Ventana, *, localidad: str | None = None, sensores: list[int] | None = None) -> list[Fila]:
    filtro = ""
    parametros: dict = {"desde": v.intervalos[0], "hasta": v.hasta}
    if localidad:
        filtro += " AND e.localidad = :localidad"
        parametros["localidad"] = localidad
    if sensores is not None:
        filtro += " AND l.id_sensor IN :sensores"
        parametros["sensores"] = sensores

    if v.paso == "hora":
        parametros["desde_ext"] = v.intervalos[0] - timedelta(hours=HORAS_PREVIAS)
        sentencia = text(_SQL_HORA.format(filtro=filtro))
    else:
        sentencia = text(_SQL_DIA.format(filtro=filtro))
    if sensores is not None:
        sentencia = sentencia.bindparams(bindparam("sensores", expanding=True))
    return [tuple(f) for f in db.execute(sentencia, parametros).all()]  # type: ignore[misc]


def serie(db: Session, periodo: Periodo, localidad: str | None = None) -> SerieHistorial:
    v = ventana(periodo, ahora_bogota())
    return agregar_serie(_filas(db, v, localidad=localidad), v, localidad or "Toda Bogotá", _datos_desde(db))


def ranking(db: Session, periodo: Periodo) -> RankingHistorial:
    v = ventana(periodo, ahora_bogota())
    return agregar_ranking(_filas(db, v), v, _datos_desde(db))


def destino(db: Session, periodo: Periodo, lat: float, lon: float, cantidad: int = 3) -> HistorialDestino:
    """Serie de lluvia de las estaciones más cercanas a un punto."""
    estaciones = db.execute(text("SELECT id_sensor, nombre, localidad, latitud, longitud FROM estaciones")).all()
    cercanas = sorted(
        ((distancia_km(lat, lon, e.latitud, e.longitud), e) for e in estaciones), key=lambda x: x[0]
    )[:cantidad]

    v = ventana(periodo, ahora_bogota())
    desde = _datos_desde(db)
    resultado = []
    for distancia, e in cercanas:
        filas = _filas(db, v, sensores=[e.id_sensor])
        resultado.append(SerieEstacion(
            id_sensor=e.id_sensor,
            nombre=e.nombre,
            localidad=e.localidad,
            distancia_km=round(distancia, 2),
            serie=agregar_serie(filas, v, e.nombre, desde),
        ))
    return HistorialDestino(periodo=periodo, estaciones=resultado)
