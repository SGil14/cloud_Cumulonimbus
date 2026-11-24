"""Genera tráfico de prueba contra la API para ver las métricas en Grafana (y el autoescalado).

Uso:
    python scripts/trafico.py                      # 60 s contra http://localhost, 10 usuarios
    python scripts/trafico.py --segundos 180 --usuarios 30
    python scripts/trafico.py --url https://otra-url --segundos 30

Solo usa la librería estándar de Python. Mezcla los endpoints más usados de la app,
incluidos algunos que no existen para que aparezcan respuestas 404 en el dashboard.
"""

import argparse
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

# (peso, ruta): los pesos imitan cómo se usa la app de verdad.
RUTAS = [
    (30, "/api/resumen"),
    (25, "/api/estaciones"),
    (10, "/api/destino?q=Chapinero"),
    (8, "/api/destino?q=" + urllib.parse.quote("4.6486,-74.0628")),
    (8, "/api/historial/serie?periodo=24h"),
    (6, "/api/historial/ranking?periodo=7d"),
    (5, "/api/historial/serie?periodo=6h"),
    (5, "/"),
    (3, "/api/no-existe"),
]
PESOS = [p for p, _ in RUTAS]
CAMINOS = [r for _, r in RUTAS]


def usuario(base: str, fin: float, resultados: Counter, candado: threading.Lock) -> None:
    while time.monotonic() < fin:
        ruta = random.choices(CAMINOS, PESOS)[0]
        try:
            with urllib.request.urlopen(base + ruta, timeout=20) as r:
                estado = r.status
                r.read()
        except urllib.error.HTTPError as e:
            estado = e.code
        except Exception:
            estado = "error"
        with candado:
            resultados[estado] += 1
        time.sleep(random.uniform(0.05, 0.3))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://localhost", help="URL base de la API (por defecto el Service del clúster)")
    p.add_argument("--segundos", type=int, default=60)
    p.add_argument("--usuarios", type=int, default=10, help="hilos que hacen peticiones a la vez")
    a = p.parse_args()

    base = a.url.rstrip("/")
    fin = time.monotonic() + a.segundos
    resultados: Counter = Counter()
    candado = threading.Lock()
    hilos = [threading.Thread(target=usuario, args=(base, fin, resultados, candado), daemon=True) for _ in range(a.usuarios)]
    print(f"Enviando tráfico a {base} durante {a.segundos} s con {a.usuarios} usuarios…")
    for h in hilos:
        h.start()
    inicio = time.monotonic()
    while any(h.is_alive() for h in hilos):
        time.sleep(5)
        with candado:
            total = sum(resultados.values())
        print(f"  {int(time.monotonic() - inicio):>4} s · {total} peticiones · {total / max(1, time.monotonic() - inicio):.1f} por segundo")
    print("Resultado por código de respuesta:", dict(resultados))


if __name__ == "__main__":
    main()
