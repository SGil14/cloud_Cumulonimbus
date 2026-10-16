"""Chequeo de salud, usado por la nube para saber si la app está viva."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["salud"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        base_datos = "ok"
    except Exception:
        base_datos = "error"
    return {"estado": "ok", "base_datos": base_datos}
