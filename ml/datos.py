"""Preparación de datos para predecir lluvia en la próxima hora.

Todas las funciones son puras (reciben y devuelven DataFrames) para poder probarlas sin base de datos.

Definiciones:
- Paso: 10 minutos. Una fila de `lecturas` cae en el paso que contiene su `fecha_lectura` (hora de Bogotá).
- Lluvia de un paso: suma de las diferencias del acumulado del día entre lecturas consecutivas de la estación.
  Si el acumulado baja, se reinició a medianoche y la lluvia vale lo que marca (igual que el historial de la API).
- Ejemplo de decisión: una estación en el instante `t`, que es el final de un paso.
  Las variables usan los pasos hasta `t`; la etiqueta usa los 6 pasos siguientes (la próxima hora).
- Etiqueta `llovera`: 1 si en la próxima hora la estación registró lluvia (> 0 mm, igual que `lloviendo` en la API).
- Línea base `base_persistencia`: 1 si en el último paso ya estaba lloviendo («si llueve ahora, lloverá»).
"""

import numpy as np
import pandas as pd

PASO_MIN = 10
PASOS_FUTURO = 6  # 60 minutos
PASOS_PASADO = 6  # 60 minutos de contexto
VECINAS = 3
TZ_BOGOTA = "America/Bogota"

COLUMNAS_LECTURAS = ["id_sensor", "fecha_lectura", "acumulado_dia"]
COLUMNAS_ESTACIONES = ["id_sensor", "latitud", "longitud"]

VARIABLES = [
    "mm_10", "mm_30", "mm_60", "acumulado_dia",
    "vecinas_mm_30", "vecinas_mm_60",
    "hora_sin", "hora_cos",
]
ETIQUETA = "llovera"
LINEA_BASE = "base_persistencia"


def limpiar_lecturas(lecturas: pd.DataFrame) -> pd.DataFrame:
    """Quita duplicados, valores faltantes o imposibles y deja las fechas en hora de Bogotá."""
    faltan = set(COLUMNAS_LECTURAS) - set(lecturas.columns)
    if faltan:
        raise ValueError(f"Faltan columnas en las lecturas: {sorted(faltan)}")

    df = lecturas[COLUMNAS_LECTURAS].copy()
    df["fecha_lectura"] = pd.to_datetime(df["fecha_lectura"], utc=True).dt.tz_convert(TZ_BOGOTA)
    df["acumulado_dia"] = pd.to_numeric(df["acumulado_dia"], errors="coerce")
    df = df.dropna()
    df = df[df["acumulado_dia"] >= 0]
    df = df.drop_duplicates(["id_sensor", "fecha_lectura"])
    return df.sort_values(["id_sensor", "fecha_lectura"]).reset_index(drop=True)


def lluvia_por_lectura(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega `mm`: lo que llovió entre la lectura anterior de la estación y esta."""
    df = df.copy()
    previo = df.groupby("id_sensor")["acumulado_dia"].shift()
    diferencia = df["acumulado_dia"] - previo
    # Si el acumulado bajó, se reinició a medianoche: lo llovido es el valor actual.
    df["mm"] = np.where(diferencia >= 0, diferencia, df["acumulado_dia"])
    df.loc[previo.isna(), "mm"] = 0.0
    return df


def a_pasos(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por estación y paso de 10 minutos, solo donde hubo al menos una lectura.

    Columnas: id_sensor, paso (entero consecutivo), fin (hora de Bogotá, fin del paso), mm, acumulado_dia.
    """
    df = df.copy()
    # Se trabaja con la hora local sin zona para que los pasos queden alineados al reloj de Bogotá.
    local = df["fecha_lectura"].dt.tz_localize(None)
    df["inicio"] = local.dt.floor(f"{PASO_MIN}min")
    pasos = df.groupby(["id_sensor", "inicio"], as_index=False).agg(
        mm=("mm", "sum"), acumulado_dia=("acumulado_dia", "last")
    )
    origen = pasos["inicio"].min()
    pasos["paso"] = ((pasos["inicio"] - origen) / pd.Timedelta(minutes=PASO_MIN)).round().astype(int)
    pasos["fin"] = pasos["inicio"] + pd.Timedelta(minutes=PASO_MIN)
    return pasos[["id_sensor", "paso", "fin", "mm", "acumulado_dia"]]


def estaciones_vecinas(estaciones: pd.DataFrame, k: int = VECINAS) -> dict[int, list[int]]:
    """Para cada estación, las `k` más cercanas (distancia aproximada en grados, suficiente a escala de ciudad)."""
    faltan = set(COLUMNAS_ESTACIONES) - set(estaciones.columns)
    if faltan:
        raise ValueError(f"Faltan columnas en las estaciones: {sorted(faltan)}")
    est = estaciones.dropna(subset=COLUMNAS_ESTACIONES).drop_duplicates("id_sensor")
    ids = est["id_sensor"].to_numpy()
    lat = est["latitud"].to_numpy(dtype=float)
    lon = est["longitud"].to_numpy(dtype=float) * np.cos(np.radians(lat))
    vecinas = {}
    for i, id_sensor in enumerate(ids):
        dist = np.hypot(lat - lat[i], lon - lon[i])
        dist[i] = np.inf
        orden = np.argsort(dist)[: min(k, len(ids) - 1)]
        vecinas[int(id_sensor)] = [int(ids[j]) for j in orden]
    return vecinas


def construir_ejemplos(pasos: pd.DataFrame, vecinas: dict[int, list[int]]) -> pd.DataFrame:
    """Arma las variables y la etiqueta. Solo quedan los instantes con la ventana completa de lecturas."""
    if pasos.empty:
        return pd.DataFrame(columns=["id_sensor", "fin", *VARIABLES, LINEA_BASE, ETIQUETA])

    # Matriz estación × paso, con huecos (NaN) donde no hubo lecturas.
    lluvia = pasos.pivot(index="paso", columns="id_sensor", values="mm")
    lluvia = lluvia.reindex(range(int(lluvia.index.min()), int(lluvia.index.max()) + 1))
    acumulado = pasos.pivot(index="paso", columns="id_sensor", values="acumulado_dia").reindex(lluvia.index)
    # El paso 0 es el más antiguo (ver a_pasos); de ahí se deduce la hora de cualquier paso, aunque no tenga lecturas.
    origen = pasos["fin"].min() - pd.Timedelta(minutes=PASO_MIN)
    fin_paso = pd.Series(
        [origen + pd.Timedelta(minutes=PASO_MIN) * (i + 1) for i in lluvia.index], index=lluvia.index
    )

    cero = lluvia.fillna(0.0)
    valido = lluvia.notna()

    def ventana(df: pd.DataFrame, pasos_n: int, hacia_atras: bool) -> pd.DataFrame:
        if hacia_atras:  # pasos [k - n + 1, k]
            return df.rolling(pasos_n, min_periods=pasos_n).sum()
        # pasos [k + 1, k + n]
        return df.rolling(pasos_n, min_periods=pasos_n).sum().shift(-pasos_n)

    mm_10 = cero
    mm_30 = ventana(cero, 3, True)
    mm_60 = ventana(cero, PASOS_PASADO, True)
    futuro = ventana(cero, PASOS_FUTURO, False)
    # Una ventana es válida solo si todos sus pasos tuvieron lecturas.
    ok_pasado = ventana(valido.astype(float), PASOS_PASADO, True) == PASOS_PASADO
    ok_futuro = ventana(valido.astype(float), PASOS_FUTURO, False) == PASOS_FUTURO

    def promedio_vecinas(mm: pd.DataFrame) -> pd.DataFrame:
        columnas = {}
        for id_sensor in mm.columns:
            cols = [v for v in vecinas.get(int(id_sensor), []) if v in mm.columns]
            columnas[id_sensor] = mm[cols].mean(axis=1) if cols else np.nan
        return pd.DataFrame(columnas, index=mm.index)

    filas = pd.DataFrame({
        "mm_10": mm_10.stack(future_stack=True),
        "mm_30": mm_30.stack(future_stack=True),
        "mm_60": mm_60.stack(future_stack=True),
        "acumulado_dia": acumulado.stack(future_stack=True),
        "vecinas_mm_30": promedio_vecinas(mm_30).stack(future_stack=True),
        "vecinas_mm_60": promedio_vecinas(mm_60).stack(future_stack=True),
        "futuro": futuro.stack(future_stack=True),
        "ok": (ok_pasado & ok_futuro).stack(future_stack=True),
    })
    filas.index.names = ["paso", "id_sensor"]
    filas = filas[filas["ok"].astype(bool)].drop(columns="ok").dropna().reset_index()

    filas["fin"] = filas["paso"].map(fin_paso)
    horas = filas["fin"].dt.hour + filas["fin"].dt.minute / 60
    filas["hora_sin"] = np.sin(2 * np.pi * horas / 24)
    filas["hora_cos"] = np.cos(2 * np.pi * horas / 24)
    filas[ETIQUETA] = (filas["futuro"] > 0).astype(int)
    filas[LINEA_BASE] = (filas["mm_10"] > 0).astype(int)
    return filas[["id_sensor", "fin", *VARIABLES, LINEA_BASE, ETIQUETA]].sort_values(["fin", "id_sensor"]).reset_index(drop=True)


def dividir_en_el_tiempo(
    ejemplos: pd.DataFrame, fraccion_prueba: float = 0.2, corte: pd.Timestamp | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa entrenamiento y prueba por fecha: la prueba son siempre los instantes más recientes.

    Por defecto la prueba es la fracción más reciente. Con `corte` (hora de Bogotá, sin zona) la prueba empieza
    en esa fecha; sirve cuando la lluvia es escasa y hay que garantizar que ambos lados tengan eventos.

    Entre ambos conjuntos se deja una hora sin usar: la etiqueta mira una hora al futuro y, sin ese hueco,
    los últimos ejemplos de entrenamiento compartirían lluvia con los primeros de prueba.
    """
    if not 0 < fraccion_prueba < 1:
        raise ValueError("fraccion_prueba debe estar entre 0 y 1")
    if ejemplos.empty:
        return ejemplos.copy(), ejemplos.copy()
    if corte is None:
        instantes = np.sort(ejemplos["fin"].unique())
        corte = instantes[int(len(instantes) * (1 - fraccion_prueba))]
    corte = pd.Timestamp(corte)
    hueco = pd.Timedelta(minutes=PASO_MIN * PASOS_FUTURO)
    entrenamiento = ejemplos[ejemplos["fin"] < corte - hueco]
    prueba = ejemplos[ejemplos["fin"] >= corte]
    return entrenamiento.reset_index(drop=True), prueba.reset_index(drop=True)


def preparar(lecturas: pd.DataFrame, estaciones: pd.DataFrame, fraccion_prueba: float = 0.2, corte=None):
    """De las tablas crudas a (entrenamiento, prueba)."""
    df = limpiar_lecturas(lecturas)
    pasos = a_pasos(lluvia_por_lectura(df))
    ejemplos = construir_ejemplos(pasos, estaciones_vecinas(estaciones))
    return dividir_en_el_tiempo(ejemplos, fraccion_prueba, corte)
