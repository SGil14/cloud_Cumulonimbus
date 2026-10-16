# syntax=docker/dockerfile:1
# Cumulonimbus: una sola imagen con el backend (FastAPI) y el frontend ya compilado.

# ---------- Etapa 1: compilar el frontend ----------
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Etapa 2: la aplicación ----------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
# El backend sirve esta carpeta si existe (ver FRONTEND_DIST en backend/app/main.py).
COPY --from=frontend /app/frontend/dist frontend/dist

# No se ejecuta como administrador dentro del contenedor.
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app
WORKDIR /app/backend

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/api/health' % os.environ.get('PORT', '8000'), timeout=4)"]

# Aplica las migraciones y levanta la API. Los proveedores en la nube entregan el puerto en PORT.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
