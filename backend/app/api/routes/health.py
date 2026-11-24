"""Chequeo de salud, usado por la nube para saber si la app está viva."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["salud"])


def _base_datos_ok(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/health")
def health(db: Session = Depends(get_db)):
    return {"estado": "ok", "base_datos": "ok" if _base_datos_ok(db) else "error"}


@router.get("/health/live")
def vivo():
    """Liveness de Kubernetes: el proceso responde. No mira la base, para que una caída de
    PostgreSQL no haga que Kubernetes reinicie todas las réplicas sin necesidad."""
    return {"estado": "ok"}


@router.get("/health/ready")
def lista(db: Session = Depends(get_db)):
    """Readiness de Kubernetes: la réplica solo recibe tráfico si llega a la base de datos."""
    if _base_datos_ok(db):
        return {"estado": "ok", "base_datos": "ok"}
    return JSONResponse(status_code=503, content={"estado": "no_lista", "base_datos": "error"})
