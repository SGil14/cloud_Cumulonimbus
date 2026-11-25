"""Métricas de Prometheus de la API.

Se exponen en /metrics (texto de Prometheus) y las recoge el Prometheus del clúster.
Cada réplica tiene sus propios contadores; Prometheus las suma en las consultas.
"""

import time

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

# --- HTTP: throughput y latencia ---
PETICIONES = Counter(
    "cumulonimbus_http_requests_total",
    "Peticiones HTTP atendidas por la API.",
    ["metodo", "ruta", "estado"],
)
LATENCIA = Histogram(
    "cumulonimbus_http_request_duration_seconds",
    "Tiempo de respuesta de la API en segundos.",
    ["metodo", "ruta"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
EN_CURSO = Gauge(
    "cumulonimbus_http_requests_in_progress",
    "Peticiones que la réplica está atendiendo en este momento.",
)

# --- Dominio: la lluvia en Bogotá ---
ESTACIONES_LLOVIENDO = Gauge(
    "cumulonimbus_estaciones_lloviendo",
    "Estaciones del SAB que registran lluvia en la última consulta.",
)
ESTACIONES_TOTAL = Gauge(
    "cumulonimbus_estaciones_total",
    "Estaciones del SAB recibidas en la última consulta.",
)
SAB_CONSULTAS = Counter(
    "cumulonimbus_sab_consultas_total",
    "Consultas hechas al SAB, por resultado.",
    ["resultado"],
)
SAB_LATENCIA = Histogram(
    "cumulonimbus_sab_duracion_seconds",
    "Lo que tarda el SAB en responder.",
    buckets=(0.25, 0.5, 1, 2, 4, 8, 16, 30),
)

# --- IA: predicción de lluvia en la próxima hora ---
IA_PREDICCIONES = Counter(
    "cumulonimbus_ia_predicciones_total",
    "Predicciones de lluvia entregadas, por método (modelo o persistencia).",
    ["metodo"],
)
IA_LATENCIA = Histogram(
    "cumulonimbus_ia_prediccion_duracion_seconds",
    "Lo que tarda en calcularse una predicción de lluvia.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)
IA_PROBABILIDAD = Gauge(
    "cumulonimbus_ia_probabilidad_ultima",
    "Probabilidad de lluvia de la última predicción hecha con el modelo.",
)

# Rutas que no se miden: el propio /metrics y los sondeos de Kubernetes ensuciarían las gráficas.
_NO_MEDIR = {"/metrics", "/api/health", "/api/health/live", "/api/health/ready"}


def _ruta_de(request: Request) -> str:
    """Plantilla de la ruta (/api/historial/serie), no la URL concreta, para no crear una serie por cada consulta."""
    ruta = request.scope.get("route")
    plantilla = getattr(ruta, "path", None)
    if plantilla:
        return plantilla
    return "frontend" if not request.url.path.startswith("/api") else "otra"


class MetricasMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _NO_MEDIR:
            return await call_next(request)
        EN_CURSO.inc()
        inicio = time.perf_counter()
        estado = 500
        try:
            respuesta = await call_next(request)
            estado = respuesta.status_code
            return respuesta
        finally:
            ruta = _ruta_de(request)
            LATENCIA.labels(request.method, ruta).observe(time.perf_counter() - inicio)
            PETICIONES.labels(request.method, ruta, str(estado)).inc()
            EN_CURSO.dec()


def endpoint_metricas() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
