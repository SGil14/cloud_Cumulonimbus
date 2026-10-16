"""Punto de entrada de la API de Cumulonimbus."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import destino, health, historial, lluvia, mapa, radar, ruta
from app.config import RAIZ_PROYECTO, get_settings
from app.jobs.recolector import crear_recolector
from app.services.sab_client import SABError

settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

FRONTEND_DIST = RAIZ_PROYECTO / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    recolector = crear_recolector()
    if recolector:
        recolector.start()
    yield
    if recolector:
        recolector.shutdown(wait=False)


app = FastAPI(
    title="Cumulonimbus",
    description="Lluvia en tiempo real en Bogotá a partir de las estaciones del SAB (IDIGER).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(SABError)
async def sab_no_disponible(request: Request, exc: SABError):
    return JSONResponse(
        status_code=502,
        content={"detail": "El SAB no está respondiendo en este momento. Inténtalo de nuevo en unos minutos."},
    )


app.include_router(health.router)
app.include_router(lluvia.router)
app.include_router(destino.router)
app.include_router(mapa.router)
app.include_router(radar.router)
app.include_router(historial.router)
app.include_router(ruta.router)

# En producción el backend también entrega el front compilado.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
