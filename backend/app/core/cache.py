"""Caché en memoria con tiempo de expiración, segura entre hilos."""

import threading
import time
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class CacheTTL(Generic[T]):
    """Guarda un único valor y lo recarga con `cargar` cuando expira."""

    def __init__(self, cargar: Callable[[], T], ttl_segundos: float):
        self._cargar = cargar
        self._ttl = ttl_segundos
        self._valor: T | None = None
        self._expira = 0.0
        self._lock = threading.Lock()

    def obtener(self, forzar: bool = False) -> T:
        with self._lock:
            if forzar or self._valor is None or time.monotonic() >= self._expira:
                self._valor = self._cargar()
                self._expira = time.monotonic() + self._ttl
            return self._valor

    def invalidar(self) -> None:
        with self._lock:
            self._valor = None
