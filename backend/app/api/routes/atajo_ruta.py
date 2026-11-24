"""Ruta para el atajo de iPhone: una tarjeta HTML (se abre en Safari) o un texto con emojis (se muestra en el atajo)."""

import re
from datetime import timedelta
from html import escape
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.api.routes.atajo_mapa import mapa_ruta_svg
from app.api.routes.ruta import ruta as calcular_ruta
from app.core.tiempo import ahora_bogota
from app.db.session import get_db
from app.models.ruta import Modo, RutaRespuesta, TramoRuta
from app.models.schemas import Estacion, Intensidad, UbicacionDestino
from app.services import estaciones_service

router = APIRouter(prefix="/api", tags=["atajo"])

MODOS = {
    "auto": ("🚗", "Carro / moto"),
    "bus": ("🚌", "Bus"),
    "bicicleta": ("🚲", "Bici"),
    "a_pie": ("🚶", "A pie"),
}
INTENSIDAD = {Intensidad.ligera: "ligera", Intensidad.moderada: "moderada", Intensidad.fuerte: "fuerte", Intensidad.muy_fuerte: "muy fuerte"}
ESTADOS = {
    "lluvia": ("🔵", "lluvia", "#1e7bff"),
    "seco": ("🟢", "seco", "#22a559"),
    "sin_datos": ("⚪", "sin datos", "#9aa4b5"),
}


def _num(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def _duracion(minutos: int) -> str:
    if minutos < 60:
        return f"{minutos} min"
    return f"{minutos // 60} h {minutos % 60:02d} min"


_COORDENADAS = re.compile(r"^\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*$")


def _lugar(u: UbicacionDestino | None, texto: str) -> str:
    """Lo que escribió la persona, con el barrio y la localidad entre paréntesis («Tu ubicación» si fueron coordenadas)."""
    zona = ", ".join(p for p in (u.barrio, u.localidad) if p) if u else ""
    nombre = "Tu ubicación" if _COORDENADAS.match(texto) else texto
    if zona and zona.lower() != nombre.lower():
        return f"{nombre} ({zona})"
    return nombre


def _veredicto(r: RutaRespuesta) -> tuple[str, str, str]:
    """(emoji, titular, color), con los mismos criterios que el panel de la app."""
    if r.hay_lluvia:
        return "🌧️", "Hay lluvia en tu ruta", "#1e7bff"
    if r.porcentaje_sin_datos >= 30:
        return "❔", "No se puede asegurar", "#9aa4b5"
    return "✅", "Ruta sin lluvia", "#22a559"


def _km(t: TramoRuta) -> str:
    return f"km {_num(t.desde_km)} – {_num(t.hasta_km)}"


def _estado_texto(t: TramoRuta) -> str:
    """«seco», «sin datos» o «lluvia fuerte (13,2 mm/h)»."""
    if t.estado != "lluvia":
        return ESTADOS[t.estado][1]
    intensidad = INTENSIDAD.get(t.intensidad, "") if t.intensidad else ""
    return f"lluvia {intensidad} ({_num(t.mm_hora)} mm/h)" if intensidad else "lluvia"


def _estacion_texto(t: TramoRuta) -> str:
    if not t.estacion:
        return ""
    return ("estación lejana: " if t.estado == "sin_datos" else "cerca de ") + t.estacion


def _detalle_tramo(t: TramoRuta) -> str:
    return " · ".join(p for p in (_km(t), _estado_texto(t), _estacion_texto(t)) if p)


def texto_ruta(r: RutaRespuesta, origen: str, destino: str) -> str:
    """La ruta como texto con emojis, para «Mostrar resultado» o para leerla en voz alta."""
    if not r.encontrado:
        return f"❌ {r.mensaje}"
    emoji_modo, nombre_modo = MODOS[r.modo]
    emoji_v, titular, _ = _veredicto(r)
    lineas = [
        f"{emoji_modo} Ruta · {_num(r.distancia_km)} km · {_duracion(r.duracion_min)} ({nombre_modo})",
        f"{_lugar(r.origen, origen)} → {_lugar(r.destino, destino)}",
        "",
        f"{emoji_v} {titular}",
        "",
        "📍 Tramos",
    ]
    lineas += [f"{ESTADOS[t.estado][0]} {_detalle_tramo(t)}" for t in r.tramos]
    lineas.append("")
    if r.porcentaje_sin_datos:
        lineas.append(f"ℹ️ {r.porcentaje_sin_datos} % del trayecto sin datos.")
    lineas.append(f"ℹ️ {r.nota}")
    return "\n".join(lineas)


_CSS = """
:root { color-scheme: light dark; --fondo:#eef3fb; --tarjeta:#ffffff; --texto:#17233a; --suave:#5d6b85; --linea:#dde5f2; }
@media (prefers-color-scheme: dark) { :root { --fondo:#0d1424; --tarjeta:#16203a; --texto:#eaf0ff; --suave:#9fb0d0; --linea:#26345a; } }
* { box-sizing: border-box; }
body { margin:0; padding:16px; background:var(--fondo); color:var(--texto); font:16px/1.45 -apple-system,"SF Pro Text","Segoe UI",Roboto,sans-serif; }
.tarjeta { max-width:560px; margin:0 auto; background:var(--tarjeta); border-radius:22px; padding:20px; box-shadow:0 10px 30px rgba(20,40,90,.12); }
.meta { color:var(--suave); font-size:14px; margin:0 0 4px; }
.trayecto { font-weight:600; font-size:17px; margin:0 0 16px; }
.trayecto span { color:var(--suave); font-weight:400; }
.veredicto { border-radius:16px; padding:14px 16px; color:#fff; margin-bottom:16px; }
.veredicto b { display:block; font-size:22px; line-height:1.2; }
.veredicto small { opacity:.9; font-size:14px; }
.barra { display:flex; height:14px; border-radius:8px; overflow:hidden; gap:2px; margin:4px 0 4px; }
.barra i { display:block; min-width:6px; }
.ejes { display:flex; justify-content:space-between; color:var(--suave); font-size:12px; margin-bottom:14px; }
h2 { font-size:13px; letter-spacing:.06em; text-transform:uppercase; color:var(--suave); margin:16px 0 6px; }
ul { list-style:none; padding:0; margin:0; }
li { display:flex; gap:10px; align-items:flex-start; padding:9px 0; border-top:1px solid var(--linea); }
li:first-child { border-top:0; }
.punto { width:12px; height:12px; border-radius:50%; margin-top:6px; flex:none; }
li b { display:block; font-size:15px; }
li span { color:var(--suave); font-size:13.5px; }
.nota { color:var(--suave); font-size:13px; margin:14px 0 0; }
.aviso { background:rgba(255,160,0,.14); border-radius:12px; padding:10px 12px; font-size:14px; margin-top:12px; }
.mapa { border-radius:16px; overflow:hidden; margin:0 0 8px; line-height:0; border:1px solid var(--linea); }
.mapa-svg { display:block; height:auto; }
@media (prefers-color-scheme: dark) { .teselas { filter: invert(1) hue-rotate(180deg) brightness(.92) contrast(.9); } }
.leyenda { display:flex; flex-wrap:wrap; gap:6px 14px; color:var(--suave); font-size:12.5px; margin:0 0 14px; }
.leyenda span::before { content:""; display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; vertical-align:-1px; background:var(--c); }
.chips { display:flex; flex-wrap:wrap; gap:8px; margin:0 0 14px; }
.chips span { background:var(--fondo); border-radius:999px; padding:6px 12px; font-size:13.5px; font-weight:600; }
"""


def tarjeta_html(r: RutaRespuesta, origen: str, destino: str, hora: str, mapa: str = "", llegada: str = "") -> str:
    """La ruta como una tarjeta HTML; todo texto que viene de fuera se escapa."""
    if not r.encontrado:
        cuerpo = f'<div class="veredicto" style="background:#d9534f"><b>No pude calcular la ruta</b><small>{escape(r.mensaje)}</small></div>'
        return _pagina("Ruta", cuerpo)

    emoji_modo, nombre_modo = MODOS[r.modo]
    emoji_v, titular, color = _veredicto(r)
    barra = "".join(
        f'<i style="flex-grow:{max(0.2, t.hasta_km - t.desde_km):.2f};background:{ESTADOS[t.estado][2]}" title="{escape(_detalle_tramo(t))}"></i>'
        for t in r.tramos
    )
    filas = "".join(
        f'<li><span class="punto" style="background:{ESTADOS[t.estado][2]}"></span><div>'
        f"<b>{escape(_km(t))} · {escape(_estado_texto(t).capitalize())}</b>"
        f"<span>{escape(_estacion_texto(t))}</span></div></li>"
        for t in r.tramos
    )
    sin_datos = (
        f'<div class="aviso">⚪ {r.porcentaje_sin_datos} % del trayecto no tiene datos (la estación más cercana queda lejos o no reporta).</div>'
        if r.porcentaje_sin_datos else ""
    )
    usadas = len({t.estacion for t in r.tramos if t.estacion})
    leyenda = (
        '<div class="leyenda">'
        f'<span style="--c:{ESTADOS["seco"][2]}">Seco</span><span style="--c:{ESTADOS["lluvia"][2]}">Lluvia</span>'
        f'<span style="--c:{ESTADOS["sin_datos"][2]}">Sin datos</span><span style="--c:#4b5870">Estación</span></div>'
        if mapa else ""
    )
    chips = (
        '<div class="chips">'
        f"<span>⏱ {escape(_duracion(r.duracion_min))}</span><span>📏 {escape(_num(r.distancia_km))} km</span>"
        + (f"<span>🏁 Llegas ≈ {escape(llegada)}</span>" if llegada else "")
        + f"<span>📡 {usadas} {'estación' if usadas == 1 else 'estaciones'}</span></div>"
    )
    bloque_mapa = f'<div class="mapa">{mapa}</div>{leyenda}{chips}' if mapa else ""
    cuerpo = (
        '<div class="tarjeta">'
        f'<p class="meta">{emoji_modo} {escape(nombre_modo)} · {escape(_num(r.distancia_km))} km · {escape(_duracion(r.duracion_min))}</p>'
        f'<p class="trayecto">{escape(_lugar(r.origen, origen))} <span>→</span> {escape(_lugar(r.destino, destino))}</p>'
        f'<div class="veredicto" style="background:{color}"><b>{emoji_v} {escape(titular)}</b><small>{escape(r.resumen)}</small></div>'
        f"{bloque_mapa}"
        f'<div class="barra">{barra}</div><div class="ejes"><span>Salida</span><span>Llegada</span></div>'
        f"<h2>Tramos</h2><ul>{filas}</ul>{sin_datos}"
        f'<p class="nota">{escape(r.nota)} Datos de los pluviómetros del SAB · {escape(hora)}</p>'
        "</div>"
    )
    return _pagina("¿Llueve en tu ruta?", cuerpo)


def _pagina(titulo: str, cuerpo: str) -> str:
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        f"<title>{escape(titulo)}</title><style>{_CSS}</style></head><body>{cuerpo}</body></html>"
    )


_ALIAS_MODO: dict[str, Modo] = {
    "auto": "auto", "carro": "auto", "carro / moto": "auto", "carro/moto": "auto", "moto": "auto", "coche": "auto",
    "bus": "bus", "transmilenio": "bus",
    "bicicleta": "bicicleta", "bici": "bicicleta",
    "a_pie": "a_pie", "a pie": "a_pie", "pie": "a_pie", "caminando": "a_pie", "caminar": "a_pie",
}


def _modo(valor: str) -> Modo | None:
    """Acepta los nombres del atajo («🚗 Carro / moto», «Bici», «A pie»…) y los de la API."""
    limpio = re.sub(r"[^a-záéíóúñ_ /]", "", valor.lower()).strip()
    return _ALIAS_MODO.get(limpio)


def _numero(valor: str) -> float:
    """El iPhone entrega la latitud con coma decimal («4,65»): se acepta coma o punto."""
    return float(valor.strip().replace(",", "."))


def _error(mensaje: str, formato: str, estado: int = 400):
    if formato == "texto":
        return PlainTextResponse(f"❌ {mensaje}", status_code=estado)
    r = RutaRespuesta(encontrado=False, mensaje=mensaje, modo="auto")
    return HTMLResponse(tarjeta_html(r, "", "", ""), status_code=estado)


@router.get("/atajo/ruta", response_class=HTMLResponse)
def atajo_ruta(
    destino: str = Query(..., min_length=2, max_length=200, description="Lugar, dirección o barrio de llegada"),
    origen: str | None = Query(None, max_length=200, description="Lugar, dirección o barrio de salida (o 'lat,lon')"),
    lat: str | None = Query(None, max_length=24, description="Latitud de la ubicación actual, como origen"),
    lon: str | None = Query(None, max_length=24, description="Longitud de la ubicación actual, como origen"),
    modo: str = Query("auto", max_length=40, description="Carro / moto, Bus, Bici, A pie (o auto, bus, bicicleta, a_pie)"),
    formato: Literal["html", "texto"] = Query("html", description="html = tarjeta para Safari; texto = frase con emojis"),
    db: Session = Depends(get_db),
):
    """¿Llueve en mi ruta? Devuelve una tarjeta HTML (se abre en Safari desde el atajo) o texto con emojis.

    El origen puede escribirse (`origen`) o ser la ubicación del teléfono (`lat` y `lon`).
    """
    origen_texto = (origen or "").strip()
    if lat and lon:
        try:
            origen_texto = f"{_numero(lat)},{_numero(lon)}"
        except ValueError:
            return _error("No pude leer la ubicación actual.", formato)
    if len(origen_texto) < 2:
        return _error("Falta el origen: escribe un lugar o usa tu ubicación.", formato)
    modo_api = _modo(modo)
    if modo_api is None:
        return _error(f"No conozco el modo «{modo}». Usa Carro / moto, Bus, Bici o A pie.", formato)
    destino_texto = destino.strip()

    try:
        r = calcular_ruta(origen=origen_texto, destino=destino_texto, modo=modo_api, db=db)
    except HTTPException as e:
        r = RutaRespuesta(encontrado=False, mensaje=str(e.detail), modo=modo_api)
    if formato == "texto":
        return PlainTextResponse(texto_ruta(r, origen_texto, destino_texto))
    hora = r.datos_obtenidos_en.strftime("%H:%M") if r.datos_obtenidos_en else ""
    mapa, llegada = "", ""
    if r.encontrado:
        try:
            _, estaciones = estaciones_service.obtener_estaciones()
        except Exception:  # sin estaciones el mapa se dibuja igual, solo con el recorrido
            estaciones = []
        mapa = mapa_ruta_svg(r, estaciones)
        llegada = (ahora_bogota() + timedelta(minutes=r.duracion_min)).strftime("%H:%M")
    return HTMLResponse(tarjeta_html(r, origen_texto, destino_texto, hora, mapa, llegada))
