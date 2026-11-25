"""Predicción de lluvia en la próxima hora.

El modelo es una regresión logística entrenada en `ml/` y publicada como `app/ia/modelo.json`: solo números
(media, escala, coeficientes), así que se evalúa aquí sin scikit-learn. Las variables se calculan igual que en
`ml/datos.py` (pasos de 10 minutos alineados al reloj de Bogotá, lluvia = diferencia del acumulado del día);
una prueba en `ml/tests/` comprueba que ambos cálculos coincidan.

Si no hay modelo, no hay histórico suficiente o la base de datos falla, se responde con la **persistencia**
(«si llueve ahora, seguirá lloviendo») y se dice por qué. La respuesta siempre indica qué método se usó.
"""

import json
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from app.core.tiempo import BOGOTA_TZ
from app.models.prediccion import EstacionPrediccion, EvaluacionModelo, PrediccionRespuesta
from app.models.schemas import Estacion
from app.services.lluvia_service import distancia_km

logger = logging.getLogger(__name__)

CARPETA_IA = Path(__file__).resolve().parents[1] / "ia"
PASO_MIN = 10
PASOS_PASADO = 6  # 60 minutos de contexto, como en el entrenamiento
VECINAS = 3
CANDIDATAS = 3  # estaciones cercanas que se prueban hasta encontrar una con histórico completo
HORIZONTE_MIN = 60
VARIABLES = ["mm_10", "mm_30", "mm_60", "acumulado_dia", "vecinas_mm_30", "vecinas_mm_60", "hora_sin", "hora_cos"]
AVISO = (
    "Estimación experimental: se entrenó con muy pocos eventos de lluvia y todavía no supera a la regla simple "
    "«si llueve ahora, seguirá lloviendo». Úsala como referencia, no como pronóstico oficial."
)

Lectura = tuple[datetime, float]  # (fecha con zona, acumulado del día)


@dataclass(frozen=True)
class Modelo:
    variables: list[str]
    media: list[float]
    escala: list[float]
    coeficientes: list[float]
    intercepto: float
    umbral: float

    def probabilidad(self, valores: dict[str, float]) -> float:
        z = self.intercepto + sum(
            c * (valores[v] - mu) / sc
            for v, c, mu, sc in zip(self.variables, self.coeficientes, self.media, self.escala)
        )
        return 1 / (1 + math.exp(-z))


@lru_cache
def cargar_modelo(carpeta: Path = CARPETA_IA) -> Modelo | None:
    """Lee `modelo.json`. Devuelve None (y lo registra) si falta o no es válido."""
    try:
        datos = json.loads((carpeta / "modelo.json").read_text(encoding="utf-8"))
        if datos["tipo"] != "regresion_logistica" or datos["variables"] != VARIABLES:
            raise ValueError("el modelo no coincide con las variables que calcula la API")
        return Modelo(
            variables=datos["variables"], media=datos["media"], escala=datos["escala"],
            coeficientes=datos["coeficientes"], intercepto=datos["intercepto"], umbral=datos["umbral"],
        )
    except (OSError, ValueError, KeyError) as e:
        logger.warning("Modelo de IA no disponible: %s", e)
        return None


@lru_cache
def cargar_evaluacion(carpeta: Path = CARPETA_IA) -> EvaluacionModelo | None:
    try:
        prueba = json.loads((carpeta / "metricas.json").read_text(encoding="utf-8"))["prueba"]
        return EvaluacionModelo(
            f1_modelo=prueba["modelo"]["f1"],
            f1_persistencia=prueba["linea_base_persistencia"]["f1"],
            supera_persistencia=prueba["supera_linea_base"],
            nota="Medido con la lluvia del 17 al 19 de octubre de 2026, que el modelo no vio al entrenar.",
        )
    except (OSError, ValueError, KeyError):
        return None


# ---------- Variables (funciones puras) ----------

def _paso(fecha: datetime) -> datetime:
    """Inicio del paso de 10 minutos (hora local de Bogotá, sin zona) al que pertenece una lectura."""
    local = fecha.astimezone(BOGOTA_TZ).replace(tzinfo=None)
    return local.replace(minute=local.minute // PASO_MIN * PASO_MIN, second=0, microsecond=0)


def lluvia_por_paso(lecturas: list[Lectura]) -> tuple[dict[datetime, float], dict[datetime, float]]:
    """(mm por paso, acumulado al cierre del paso). Solo hay entrada en los pasos con alguna lectura."""
    mm: dict[datetime, float] = {}
    acumulado: dict[datetime, float] = {}
    previo: float | None = None
    for fecha, valor in sorted(lecturas):
        if valor < 0:
            continue
        llovido = 0.0 if previo is None else (valor - previo if valor >= previo else valor)
        previo = valor
        paso = _paso(fecha)
        mm[paso] = mm.get(paso, 0.0) + llovido
        acumulado[paso] = valor
    return mm, acumulado


def instante_de_decision(ahora: datetime) -> datetime:
    """Fin del último paso completo, en hora local sin zona (el `fin` del entrenamiento)."""
    return _paso(ahora)


def _ventana(mm: dict[datetime, float], fin: datetime, pasos: int) -> float | None:
    """Suma de los últimos `pasos` pasos terminados en `fin`; None si falta alguno (histórico incompleto)."""
    inicios = [fin - timedelta(minutes=PASO_MIN * k) for k in range(1, pasos + 1)]
    if any(i not in mm for i in inicios):
        return None
    return sum(mm[i] for i in inicios)


def variables_de(
    propia: list[Lectura], vecinas: list[list[Lectura]], ahora: datetime
) -> tuple[dict[str, float] | None, float | None]:
    """Variables del modelo para una estación y sus vecinas, o (None, None) si no hay histórico completo.

    El segundo valor es la lluvia de la última hora de la estación (para mostrarla).
    """
    fin = instante_de_decision(ahora)
    mm, acumulado = lluvia_por_paso(propia)
    mm_10, mm_30, mm_60 = (_ventana(mm, fin, n) for n in (1, 3, PASOS_PASADO))
    ultimo = fin - timedelta(minutes=PASO_MIN)
    if mm_10 is None or mm_30 is None or mm_60 is None or ultimo not in acumulado:
        return None, None

    v30, v60 = [], []
    for lecturas in vecinas:
        m, _ = lluvia_por_paso(lecturas)
        a, b = _ventana(m, fin, 3), _ventana(m, fin, PASOS_PASADO)
        if a is not None:
            v30.append(a)
        if b is not None:
            v60.append(b)
    if not v30 or not v60:
        return None, None

    horas = fin.hour + fin.minute / 60
    return {
        "mm_10": mm_10, "mm_30": mm_30, "mm_60": mm_60, "acumulado_dia": acumulado[ultimo],
        "vecinas_mm_30": sum(v30) / len(v30), "vecinas_mm_60": sum(v60) / len(v60),
        "hora_sin": math.sin(2 * math.pi * horas / 24), "hora_cos": math.cos(2 * math.pi * horas / 24),
    }, mm_60


# ---------- Predicción ----------

def vecinas_de(estacion: Estacion, estaciones: list[Estacion], cantidad: int = VECINAS) -> list[Estacion]:
    """Las estaciones más cercanas a otra (misma aproximación en grados que usa el entrenamiento)."""
    def x(e: Estacion) -> float:  # igual que ml/datos.py: la longitud se escala con el coseno de la latitud de cada estación
        return e.longitud * math.cos(math.radians(e.latitud))

    def d(e: Estacion) -> float:
        return math.hypot(e.latitud - estacion.latitud, x(e) - x(estacion))

    return sorted((e for e in estaciones if e.id_sensor != estacion.id_sensor), key=d)[:cantidad]


def _a_estacion_prediccion(e: Estacion, lat: float, lon: float, mm_60: float | None) -> EstacionPrediccion:
    return EstacionPrediccion(
        id_sensor=e.id_sensor, nombre=e.nombre, localidad=e.localidad,
        distancia_km=round(distancia_km(lat, lon, e.latitud, e.longitud), 2),
        lloviendo=e.lloviendo, mm_60=None if mm_60 is None else round(mm_60, 2),
    )


def predecir(
    lat: float,
    lon: float,
    estaciones: list[Estacion],
    obtenido_en: datetime,
    ahora: datetime,
    historial: Callable[[list[int]], dict[int, list[Lectura]]],
    modelo: Modelo | None,
) -> PrediccionRespuesta:
    """`historial` trae las lecturas recientes (última hora y un poco más) de las estaciones pedidas."""
    if not estaciones:
        raise ValueError("No hay estaciones")
    cercanas = sorted(estaciones, key=lambda e: distancia_km(lat, lon, e.latitud, e.longitud))[:CANDIDATAS]
    llueve_ahora = any(e.lloviendo for e in cercanas)
    motivo: str | None = None
    elegida: Estacion | None = None
    variables: dict[str, float] | None = None
    mm_60: float | None = None

    if modelo is None:
        motivo = "El modelo no está disponible."
    else:
        grupos = {e.id_sensor: vecinas_de(e, estaciones) for e in cercanas}
        ids = {e.id_sensor for e in cercanas} | {v.id_sensor for g in grupos.values() for v in g}
        try:
            lecturas = historial(sorted(ids))
        except Exception:
            logger.exception("No se pudo leer el histórico para la predicción")
            lecturas, motivo = {}, "No se pudo consultar el histórico de lecturas."
        for e in cercanas:
            variables, mm_60 = variables_de(
                lecturas.get(e.id_sensor, []), [lecturas.get(v.id_sensor, []) for v in grupos[e.id_sensor]], ahora
            )
            if variables:
                elegida = e
                break
        if not variables and motivo is None:
            motivo = "Todavía no hay una hora de lecturas continuas guardadas cerca de ese punto."

    principal = elegida or cercanas[0]
    detalle = [_a_estacion_prediccion(e, lat, lon, mm_60 if e is elegida else None) for e in cercanas]
    base = dict(
        datos_obtenidos_en=obtenido_en, latitud=lat, longitud=lon, horizonte_minutos=HORIZONTE_MIN,
        llueve_ahora=llueve_ahora, estaciones=detalle, evaluacion=cargar_evaluacion(), aviso=AVISO,
    )
    if variables and modelo:
        p = modelo.probabilidad(variables)
        return PrediccionRespuesta(
            **base, metodo="modelo", probabilidad=round(p, 3), llovera_probable=p >= modelo.umbral,
            mensaje=f"Probabilidad estimada de lluvia en la próxima hora: {round(p * 100)} %.", motivo_respaldo=None,
        )
    return PrediccionRespuesta(
        **base, metodo="persistencia", probabilidad=None, llovera_probable=llueve_ahora, motivo_respaldo=motivo,
        mensaje=(
            f"Ahora llueve cerca de {principal.nombre}: lo más probable es que siga lloviendo en la próxima hora."
            if llueve_ahora else
            f"Ahora no llueve cerca de {principal.nombre}: no hay señales de lluvia para la próxima hora."
        ),
    )
