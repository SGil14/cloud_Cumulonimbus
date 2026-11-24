"""Mapa de la ruta para la tarjeta del atajo: calles de OpenStreetMap de fondo y el recorrido dibujado encima, en SVG.

Todo se calcula aquí con la proyección Web Mercator, la misma de las teselas, para que el recorrido caiga sobre las calles.
Si las teselas no cargan (sin internet), el mapa se ve igual, con el recorrido sobre un fondo liso.
"""

import math
from html import escape

from app.models.ruta import RutaRespuesta
from app.models.schemas import Estacion, Intensidad

TESELA = 256
ANCHO = 360
URL_TESELAS = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

COLOR_TRAMO = {"lluvia": "#1e7bff", "seco": "#22a559", "sin_datos": "#8f9bb0"}
COLOR_INTENSIDAD = {
    Intensidad.ligera: "#1e7bff",
    Intensidad.moderada: "#f0be00",
    Intensidad.fuerte: "#ff6e00",
    Intensidad.muy_fuerte: "#c8001e",
}


def _mundo(lon: float, lat: float, z: int) -> tuple[float, float]:
    """Píxeles del «mundo» a un nivel de zoom (Web Mercator, teselas de 256 px)."""
    n = (2**z) * TESELA
    lat = max(min(lat, 85.0511), -85.0511)
    s = math.sin(math.radians(lat))
    return (lon + 180.0) / 360.0 * n, (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n


def _vista(puntos: list[tuple[float, float]]) -> tuple[int, float, float, int]:
    """El zoom más cercano en el que cabe toda la ruta: (zoom, centro x, centro y, alto en px)."""
    for z in range(17, 9, -1):
        proy = [_mundo(lo, la, z) for lo, la in puntos]
        xs, ys = [p[0] for p in proy], [p[1] for p in proy]
        dx, dy = max(xs) - min(xs), max(ys) - min(ys)
        alto = 330 if dx >= dy else 450
        if dx <= ANCHO * 0.8 and dy <= alto * 0.8:
            return z, (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, alto
    proy = [_mundo(lo, la, 10) for lo, la in puntos]
    return 10, sum(p[0] for p in proy) / len(proy), sum(p[1] for p in proy) / len(proy), 330


def _trazo(coordenadas: list[list[float]], z: int, ox: float, oy: float) -> str:
    """Una línea «M x y L x y …», saltando puntos que quedarían a menos de 1 px del anterior."""
    partes: list[str] = []
    ult = None
    for i, (lon, lat) in enumerate(coordenadas):
        x, y = _mundo(lon, lat, z)
        x, y = x - ox, y - oy
        ultimo = i == len(coordenadas) - 1
        if ult is None or ultimo or abs(x - ult[0]) + abs(y - ult[1]) >= 1.5:
            partes.append(f"{'M' if ult is None else 'L'}{x:.1f} {y:.1f}")
            ult = (x, y)
    return " ".join(partes)


def _escala(z: int, lat: float) -> tuple[float, str]:
    """Longitud en px de una barra de escala «redonda» y su etiqueta."""
    m_por_px = 156543.03392 * math.cos(math.radians(lat)) / (2**z)
    for metros in (50, 100, 200, 500, 1000, 2000, 5000, 10000):
        px = metros / m_por_px
        if 55 <= px <= 130:
            return px, (f"{metros} m" if metros < 1000 else f"{metros // 1000} km")
    return 80.0, ""


def mapa_ruta_svg(r: RutaRespuesta, estaciones: list[Estacion]) -> str:
    """El mapa de la ruta como un `<svg>` listo para insertar en la tarjeta; vacío si no hay recorrido."""
    puntos = [(c[0], c[1]) for t in r.tramos for c in t.coordenadas]
    if len(puntos) < 2 or r.origen is None or r.destino is None:
        return ""
    muestra = puntos[:: max(1, len(puntos) // 300)] + [puntos[-1]]
    z, cx, cy, alto = _vista(muestra)
    ox, oy = cx - ANCHO / 2, cy - alto / 2
    n = 2**z

    def pos(lon: float, lat: float) -> tuple[float, float]:
        x, y = _mundo(lon, lat, z)
        return x - ox, y - oy

    # --- teselas (calles)
    teselas = []
    for tx in range(int(ox // TESELA), int((ox + ANCHO) // TESELA) + 1):
        for ty in range(int(oy // TESELA), int((oy + alto) // TESELA) + 1):
            if 0 <= tx < n and 0 <= ty < n:
                url = URL_TESELAS.format(z=z, x=tx, y=ty)
                # 0,6 px de más en cada tesela: tapa las líneas finas que quedan entre ellas
                teselas.append(f'<image href="{url}" x="{tx * TESELA - ox:.2f}" y="{ty * TESELA - oy:.2f}" width="{TESELA + 0.6}" height="{TESELA + 0.6}"/>')

    # --- estaciones dentro de la vista
    marcas = []
    for e in estaciones:
        x, y = pos(e.longitud, e.latitud)
        if not (-10 <= x <= ANCHO + 10 and -10 <= y <= alto + 10):
            continue
        if e.lloviendo:
            color = COLOR_INTENSIDAD.get(e.intensidad, "#1e7bff")
            marcas.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="18" fill="{color}" opacity=".22"/>')
            marcas.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.5" fill="{color}" stroke="#fff" stroke-width="2"/>')
        else:
            relleno = "#c3cad6" if e.desactualizada else "#4b5870"
            marcas.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="{relleno}" stroke="#fff" stroke-width="1.3" opacity=".95"/>')

    # --- recorrido: contorno blanco y, encima, el color de cada tramo
    trazos = [(t, _trazo(t.coordenadas, z, ox, oy)) for t in r.tramos if len(t.coordenadas) > 1]
    contorno = "".join(
        f'<path d="{d}" fill="none" stroke="#fff" stroke-width="9.5" stroke-linecap="round" stroke-linejoin="round" opacity=".95"/>' for _, d in trazos
    )
    colores = "".join(
        f'<path d="{d}" fill="none" stroke="{COLOR_TRAMO[t.estado]}" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"'
        + (' stroke-dasharray="1 9"' if t.estado == "sin_datos" else "")
        + "/>"
        for t, d in trazos
    )

    # --- salida y llegada
    xo, yo = pos(r.origen.longitud, r.origen.latitud)
    xd, yd = pos(r.destino.longitud, r.destino.latitud)

    def etiqueta(x: float, y: float, texto: str) -> str:
        tx = min(max(x, 28), ANCHO - 28)
        ty = y - 17 if y > 28 else y + 28
        return (
            f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" font-size="11.5" font-weight="700" fill="#17233a" '
            f'stroke="#fff" stroke-width="3.5" paint-order="stroke" stroke-linejoin="round">{escape(texto)}</text>'
        )

    salida = f'<circle cx="{xo:.1f}" cy="{yo:.1f}" r="8.5" fill="#fff" stroke="#17233a" stroke-width="3.2"/>' + etiqueta(xo, yo, "Salida")
    llegada = (
        f'<circle cx="{xd:.1f}" cy="{yd:.1f}" r="10" fill="#e5484d" stroke="#fff" stroke-width="3"/>'
        f'<circle cx="{xd:.1f}" cy="{yd:.1f}" r="3.4" fill="#fff"/>' + etiqueta(xd, yd, "Llegada")
    )

    # --- escala y atribución
    px_escala, texto_escala = _escala(z, r.destino.latitud)
    escala = (
        f'<g transform="translate(12 {alto - 16})"><path d="M0 -5 V0 H{px_escala:.1f} V-5" fill="none" stroke="#fff" stroke-width="4.5" stroke-linejoin="round"/>'
        f'<path d="M0 -5 V0 H{px_escala:.1f} V-5" fill="none" stroke="#17233a" stroke-width="1.8"/>'
        f'<text x="{px_escala / 2:.1f}" y="-8" text-anchor="middle" font-size="10.5" font-weight="600" fill="#17233a" stroke="#fff" stroke-width="3" paint-order="stroke">{escape(texto_escala)}</text></g>'
        if texto_escala else ""
    )
    atribucion = (
        f'<text x="{ANCHO - 6}" y="{alto - 5}" text-anchor="end" font-size="9" fill="#17233a" stroke="#fff" stroke-width="2.5" '
        'paint-order="stroke">© OpenStreetMap</text>'
    )

    return (
        f'<svg class="mapa-svg" viewBox="0 0 {ANCHO} {alto}" width="100%" role="img" aria-label="Mapa de la ruta">'
        f'<rect width="{ANCHO}" height="{alto}" fill="#e8edf5"/>'
        f'<g class="teselas">{"".join(teselas)}</g>'
        f'{"".join(marcas)}{contorno}{colores}{salida}{llegada}{escala}{atribucion}</svg>'
    )
