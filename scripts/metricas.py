"""Métricas del Proyecto 3 calculadas desde el tablero de GitHub Projects (HU-63).

Uso (necesita la CLI `gh` con sesión iniciada; correrlo dentro del repositorio para el cycle time):

    python scripts/metricas.py                 # tablas en Markdown
    python scripts/metricas.py --json          # los mismos datos en JSON

Qué calcula
  - Velocidad por sprint: puntos planeados, puntos terminados y puntos por día, con las fechas reales del sprint.
  - Lead time: horas desde que la historia entra al tablero (Backlog) hasta que se cierra (Done).
  - Cycle time: horas desde el primer commit de la historia (el trabajo empieza) hasta que se cierra.
  - Throughput: historias cerradas por día.

Solo usa la biblioteca estándar. La variable GH puede apuntar al ejecutable de gh si no está en el PATH.
"""

import argparse
import json
import os
import re
import statistics
import subprocess
from collections import defaultdict
from datetime import date, datetime, timezone

GH = os.environ.get("GH", "gh")
DUENO, NUMERO_PROYECTO = "SGil14", 2

# Fechas reales de los sprints del Proyecto 3 (entrega: viernes 27/11/2026).
# Los sprints 1 a 3 son del Proyecto 2 y no tienen fechas oficiales: se muestran sin fechas.
FECHAS = {
    "Sprint 4": (date(2026, 11, 23), date(2026, 11, 24)),
    "Sprint 5": (date(2026, 11, 25), date(2026, 11, 26)),
    "Sprint 6": (date(2026, 11, 27), date(2026, 11, 27)),
}
PRIMERA_HU_PROYECTO_3 = 47  # número del issue de la HU-29

CONSULTA = """
query($cursor: String) { user(login: "%s") { projectV2(number: %d) { items(first: 100, after: $cursor) {
  pageInfo { hasNextPage endCursor }
  nodes {
    content { ... on Issue { number title state createdAt closedAt } }
    sprint: fieldValueByName(name: "Sprint") { ... on ProjectV2ItemFieldSingleSelectValue { name } }
    estado: fieldValueByName(name: "Status") { ... on ProjectV2ItemFieldSingleSelectValue { name } }
    puntos: fieldValueByName(name: "Estimación") { ... on ProjectV2ItemFieldNumberValue { number } }
  } } } } }
""" % (DUENO, NUMERO_PROYECTO)


def ejecutar(*args):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise SystemExit(f"Falló {' '.join(args[:3])}: {r.stderr.strip()}")
    return r.stdout


def leer_tablero():
    items, cursor = [], None
    while True:
        cmd = [GH, "api", "graphql", "-f", "query=" + CONSULTA]
        if cursor:
            cmd += ["-f", "cursor=" + cursor]
        pagina = json.loads(ejecutar(*cmd))["data"]["user"]["projectV2"]["items"]
        items += pagina["nodes"]
        if not pagina["pageInfo"]["hasNextPage"]:
            return items
        cursor = pagina["pageInfo"]["endCursor"]


def fecha(texto):
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(timezone.utc)


def primer_commit(numero_hu):
    """Fecha del primer commit cuyo mensaje menciona la historia (HU-NN), o None si no hay historial."""
    try:
        salida = ejecutar("git", "log", "--all", "-E", f"--grep=HU-{numero_hu}([^0-9]|$)", "--format=%aI")
    except SystemExit:
        return None
    fechas = [fecha(l) for l in salida.split() if l]
    return min(fechas) if fechas else None


def horas(a, b):
    return (b - a).total_seconds() / 3600


def calcular():
    historias = []
    for it in leer_tablero():
        c = it["content"]
        if not c:
            continue
        m = re.match(r"HU-(\d+)", c["title"])
        historias.append({
            "issue": c["number"],
            "hu": int(m.group(1)) if m else None,
            "titulo": c["title"],
            "sprint": (it["sprint"] or {}).get("name"),
            "estado": (it["estado"] or {}).get("name"),
            "puntos": (it["puntos"] or {}).get("number") or 0,
            "cerrada": c["state"] == "CLOSED",
            "creada": fecha(c["createdAt"]),
            "cierre": fecha(c["closedAt"]) if c["closedAt"] else None,
        })

    sprints = defaultdict(lambda: {"planeados": 0, "terminados": 0, "hu": 0, "hu_terminadas": 0})
    for h in historias:
        if not h["sprint"]:
            continue
        s = sprints[h["sprint"]]
        s["planeados"] += h["puntos"]
        s["hu"] += 1
        if h["cerrada"]:
            s["terminados"] += h["puntos"]
            s["hu_terminadas"] += 1

    p3 = [h for h in historias if h["issue"] >= PRIMERA_HU_PROYECTO_3 and h["hu"] and h["cerrada"]]
    lead, ciclo = [], []
    for h in p3:
        lead.append(horas(h["creada"], h["cierre"]))
        inicio = primer_commit(h["hu"])
        if inicio and inicio <= h["cierre"]:
            ciclo.append(horas(inicio, h["cierre"]))
    por_dia = defaultdict(int)
    for h in p3:
        por_dia[h["cierre"].astimezone().date().isoformat()] += 1

    return {"sprints": dict(sprints), "lead": lead, "ciclo": ciclo, "por_dia": dict(sorted(por_dia.items())),
            "total_p3": sum(1 for h in historias if h["issue"] >= PRIMERA_HU_PROYECTO_3),
            "cerradas_p3": len(p3)}


def resumen(valores):
    if not valores:
        return "sin datos"
    texto = f"promedio {statistics.mean(valores):.1f} h · mediana {statistics.median(valores):.1f} h · máximo {max(valores):.1f} h (n = {len(valores)})"
    return texto.replace(".", ",")


def mostrar(d):
    hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"_Calculado el {hoy} desde el tablero._\n")
    print("| Sprint | Fechas | Historias (hechas/total) | Puntos planeados | Puntos terminados | Velocidad (pts/día) |")
    print("|---|---|---|---|---|---|")
    for nombre in sorted(d["sprints"]):
        s = d["sprints"][nombre]
        if nombre in FECHAS:
            ini, fin = FECHAS[nombre]
            dias = (fin - ini).days + 1
            fechas_txt = ini.strftime("%d/%m") + ("" if dias == 1 else " al " + fin.strftime("%d/%m"))
            vel = f"{s['terminados'] / dias:.1f}".replace(".", ",")
        else:
            fechas_txt, vel = "sin fechas (Proyecto 2)", "—"
        print(f"| {nombre} | {fechas_txt} | {s['hu_terminadas']}/{s['hu']} | {s['planeados']:g} | {s['terminados']:g} | {vel} |")
    print(f"\n- **Historias del Proyecto 3 cerradas:** {d['cerradas_p3']} de {d['total_p3']}")
    print(f"- **Lead time** (Backlog → Done): {resumen(d['lead'])}")
    print(f"- **Cycle time** (primer commit → Done): {resumen(d['ciclo'])}")
    print("- **Throughput** (historias cerradas por día): " + (", ".join(f"{k}: {v}" for k, v in d["por_dia"].items()) or "sin datos"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="imprime JSON en lugar de tablas")
    args = ap.parse_args()
    datos = calcular()
    if args.json:
        print(json.dumps(datos, ensure_ascii=False, indent=1, default=str))
    else:
        mostrar(datos)
