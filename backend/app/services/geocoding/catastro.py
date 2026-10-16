"""Geocodificador de direcciones usando la capa pública de placas domiciliarias de Catastro Bogotá.

Es la misma base de datos que usa IDECA, y no pide API key. Entiende la nomenclatura bogotana:
    "Carrera 7 # 55-25"      → vía KR 7, placa "55 25"
    "Calle 80 con Carrera 70" → esquina (placas de CL 80 que empiezan por 70)

En la capa, la vía se guarda como PDONVIAL ("KR 7", "AC 80", "CL 63 S", "KR 90BIS") y la placa como
PDOTEXTO ("55 25"): primero la calle/carrera que cruza y luego el número.
Solo resuelve direcciones; con lugares o barrios devuelve None para que lo intente otro proveedor.
"""

import re
import unicodedata
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.services.geocoding.base import Geocodificador, GeocodingError, Ubicacion

URL = (
    "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services/"
    "catastro/placadomiciliaria/MapServer/0/query"
)

# Texto escrito por la persona → códigos de vía que usa Catastro (se prueban todos).
TIPOS_VIA = {
    "avenida calle": ["AC"], "av calle": ["AC"], "ac": ["AC"],
    "avenida carrera": ["AK"], "av carrera": ["AK"], "av cra": ["AK"], "ak": ["AK"],
    "avenida": ["AK", "AC"], "av": ["AK", "AC"],
    "calle": ["CL", "AC"], "cll": ["CL", "AC"], "cl": ["CL", "AC"],
    "carrera": ["KR", "AK"], "cra": ["KR", "AK"], "cr": ["KR", "AK"], "kra": ["KR", "AK"], "kr": ["KR", "AK"],
    "diagonal": ["DG"], "diag": ["DG"], "dg": ["DG"],
    "transversal": ["TV"], "trans": ["TV"], "tv": ["TV"], "tr": ["TV"],
}
# Avenidas conocidas por su nombre → su nomenclatura.
ALIAS_VIAS = [
    (r"(?:avenida |av |av\. )?(?:boyaca|carrera 72)", "avenida carrera 72"),
    (r"(?:avenida |av |av\. )?caracas", "avenida carrera 14"),
    (r"(?:avenida |av |autopista )?(?:nqs|ciudad de quito)", "avenida carrera 30"),
    (r"(?:avenida |av |autopista )?(?:norte|autonorte)", "avenida carrera 45"),
    (r"(?:avenida |av )?ciudad de cali", "avenida carrera 86"),
    (r"(?:avenida |av )?(?:el dorado|eldorado)", "avenida calle 26"),
    (r"(?:la )?septima", "carrera 7"),
]
_TIPOS_RE = "|".join(sorted((re.escape(t) for t in TIPOS_VIA), key=len, reverse=True))

# 80 | 14C | 90 bis | 90 A bis | 63 sur
_VIA = (
    r"(?P<n{k}>\d+)\s*(?P<l1{k}>[a-z](?![a-z]))?\s*(?P<bis{k}>bis(?![a-z]))?\s*"
    r"(?P<l2{k}>[a-z](?![a-z]))?\s*(?P<dir{k}>sur|este)?"
)
_TIPO = r"(?P<tipo{k}>" + _TIPOS_RE + r")\.?\s+"
_VIA1 = _TIPO.format(k=1) + _VIA.format(k=1)
_VIA2 = _TIPO.format(k=2) + _VIA.format(k=2)

PATRON_DIRECCION = re.compile(
    rf"^{_VIA1}\s*(?P<p1>\d+)\s*(?P<pl>[a-z](?![a-z]))?\s*(?P<p2>\d+)\s*$"
)
PATRON_ESQUINA = re.compile(rf"^{_VIA1}\s+(?:con|y|x|esquina|cruce|e|con la)\s+{_VIA2}\s*$")
MAX_FILAS = 500


@dataclass(frozen=True)
class Via:
    prefijos: list[str]
    sufijo: str  # "7", "14C", "90BIS", "63 S"

    def codigos(self) -> list[str]:
        return [f"{p} {self.sufijo}" for p in self.prefijos]

    def como_placa(self) -> str:
        """Cómo aparece esta vía dentro de la placa de otra (sin el sufijo de sentido)."""
        return self.sufijo.split(" ")[0]


def _limpiar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    sin_ruido = re.sub(r"\bbogota\b|\bd\.?c\.?\b|\bno\.?\s|\bnumero\b", " ", sin_tildes)
    limpio = re.sub(r"\s+", " ", re.sub(r"[#\-,.°º]", " ", sin_ruido)).strip()
    for patron, via in ALIAS_VIAS:
        limpio = re.sub(rf"\b{patron}\b", via, limpio)
    return limpio


def _armar_via(m: re.Match, k: int) -> Via:
    g = lambda nombre: (m.group(f"{nombre}{k}") or "").upper()  # noqa: E731
    sufijo = g("n") + g("l1") + g("bis") + g("l2")
    direccion = g("dir")
    if direccion:
        sufijo += f" {direccion[0]}"  # SUR → S, ESTE → E
    return Via(TIPOS_VIA[m.group(f"tipo{k}")], sufijo)


def interpretar(texto: str) -> tuple[Via, str, str | None] | tuple[Via, Via] | None:
    """('vía', 'p1', 'p2') para una dirección, (vía, vía) para una esquina, None si no es ninguna."""
    limpio = _limpiar(texto)
    if m := PATRON_ESQUINA.match(limpio):
        return _armar_via(m, 1), _armar_via(m, 2)
    if m := PATRON_DIRECCION.match(limpio):
        p1 = m.group("p1") + (m.group("pl") or "").upper()
        p2 = m.group("p2").zfill(2)
        return _armar_via(m, 1), p1, p2
    return None


def _comillas(valores: list[str]) -> str:
    # Los valores salen de expresiones regulares (solo letras, dígitos y espacios): sin riesgo de inyección.
    return ", ".join("'" + v.replace("'", "''") + "'" for v in valores)


class CatastroGeocodificador(Geocodificador):
    nombre = "catastro"

    def disponible(self) -> bool:
        return True

    def _consultar(self, via: Via, patron_placa: str) -> list[dict]:
        where = f"PDONVIAL IN ({_comillas(via.codigos())}) AND PDOTEXTO LIKE '{patron_placa}'"
        try:
            resp = httpx.get(
                URL,
                params={
                    "where": where,
                    "outFields": "PDONVIAL,PDOTEXTO",
                    "returnGeometry": "true",
                    "outSR": 4326,
                    "resultRecordCount": MAX_FILAS,
                    "f": "json",
                },
                timeout=get_settings().geocoding_timeout_segundos,
            )
            resp.raise_for_status()
            cuerpo = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise GeocodingError(f"Catastro no respondió: {e}") from e
        if "error" in cuerpo:
            raise GeocodingError(f"Catastro rechazó la consulta: {cuerpo['error'].get('message')}")
        return cuerpo.get("features") or []

    @staticmethod
    def _numero(feature: dict) -> int:
        resto = feature["attributes"]["PDOTEXTO"].split()[-1]
        digitos = re.sub(r"\D", "", resto)
        return int(digitos) if digitos else 10**6

    @staticmethod
    def _a_ubicacion(feature: dict, direccion: str, aproximada: bool) -> Ubicacion:
        g = feature["geometry"]
        return Ubicacion(
            latitud=g["y"], longitud=g["x"], direccion=direccion,
            proveedor=CatastroGeocodificador.nombre, aproximada=aproximada,
        )

    def buscar(self, texto: str) -> Ubicacion | None:
        interpretado = interpretar(texto)
        if interpretado is None:
            return None
        if len(interpretado) == 2:
            return self._buscar_esquina(*interpretado)
        return self._buscar_direccion(*interpretado)

    def _buscar_direccion(self, via: Via, p1: str, p2: str) -> Ubicacion | None:
        etiqueta = f"{via.prefijos[0]} {via.sufijo} {p1} {p2}"
        exactas = self._consultar(via, f"{p1} {p2}%")
        if exactas:
            return self._a_ubicacion(exactas[0], etiqueta, aproximada=False)

        # El número exacto no existe: se toma la placa más cercana de la misma cuadra.
        cuadra = self._consultar(via, f"{p1} %")
        if not cuadra:
            return None
        objetivo = int(p2)
        mejor = min(cuadra, key=lambda f: abs(self._numero(f) - objetivo))
        return self._a_ubicacion(mejor, etiqueta, aproximada=True)

    def _buscar_esquina(self, a: Via, b: Via) -> Ubicacion | None:
        # Las placas de A que empiezan por el número de B están en la cuadra posterior al cruce:
        # la de numeración más baja es la esquina. Se prueba en los dos sentidos.
        for principal, cruce in ((a, b), (b, a)):
            filas = self._consultar(principal, f"{cruce.como_placa()} %")
            if filas:
                esquina = min(filas, key=self._numero)
                etiqueta = f"{principal.prefijos[0]} {principal.sufijo} con {cruce.prefijos[0]} {cruce.sufijo}"
                return self._a_ubicacion(esquina, etiqueta, aproximada=True)
        return None
