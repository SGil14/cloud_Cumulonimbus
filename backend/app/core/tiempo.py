"""Utilidades de fecha y hora. Bogotá no tiene horario de verano: UTC-5 fijo."""

from datetime import datetime, timedelta, timezone

BOGOTA_TZ = timezone(timedelta(hours=-5), name="America/Bogota")


def ahora_bogota() -> datetime:
    return datetime.now(BOGOTA_TZ)
