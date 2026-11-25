"""Entrena y evalúa el modelo de predicción de lluvia en la próxima hora.

Uso (después de `python preparar_datos.py`):
    python entrenar.py

Qué hace:
1. Con validación cruzada por bloques de tiempo dentro del entrenamiento, elige entre los candidatos
   y el umbral de decisión. La prueba no se toca en ese paso.
2. Reentrena el candidato elegido con todo el entrenamiento.
3. Evalúa UNA vez en la prueba, junto a la línea base de persistencia, y guarda el modelo y las métricas
   en `modelo/` (modelo.joblib y metricas.json).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from datos import ETIQUETA, LINEA_BASE, VARIABLES

AQUI = Path(__file__).resolve().parent
DATOS = AQUI / "data"
MODELO = AQUI / "modelo"
SEMILLA = 42
BLOQUES = 5  # bloques de tiempo de la validación cruzada
MIN_POSITIVOS = 20  # con menos lluvia que esto, cualquier métrica sería ruido


def candidatos() -> dict:
    return {
        "regresion_logistica": make_pipeline(
            StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000, random_state=SEMILLA)
        ),
        "arbol_de_gradiente": HistGradientBoostingClassifier(
            max_depth=3, learning_rate=0.1, max_iter=150, class_weight="balanced", random_state=SEMILLA
        ),
    }


def metricas_binarias(real: pd.Series, predicho: np.ndarray) -> dict:
    return {
        "precision": round(float(precision_score(real, predicho, zero_division=0)), 4),
        "recall": round(float(recall_score(real, predicho, zero_division=0)), 4),
        "f1": round(float(f1_score(real, predicho, zero_division=0)), 4),
    }


def mejor_umbral(real: pd.Series, probabilidad: np.ndarray) -> float:
    """El umbral que maximiza F1 en validación (la lluvia es rara: 0.5 casi nunca es lo mejor)."""
    umbrales = np.linspace(0.05, 0.95, 91)
    puntajes = [f1_score(real, probabilidad >= u, zero_division=0) for u in umbrales]
    return round(float(umbrales[int(np.argmax(puntajes))]), 2)


def bloques_de_tiempo(fechas: pd.Series, n: int) -> list[np.ndarray]:
    """Posiciones de las filas agrupadas en `n` bloques contiguos de tiempo (por instante, no por fila)."""
    instantes = np.sort(fechas.unique())
    limites = np.array_split(instantes, n)
    return [np.flatnonzero(fechas.isin(b).to_numpy()) for b in limites if len(b)]


def validar(entrenamiento: pd.DataFrame, prueba: pd.DataFrame) -> None:
    for nombre, df in (("entrenamiento", entrenamiento), ("prueba", prueba)):
        if df.empty:
            raise ValueError(f"El conjunto de {nombre} está vacío.")
        if int(df[ETIQUETA].sum()) < MIN_POSITIVOS or df[ETIQUETA].nunique() < 2:
            raise ValueError(
                f"El conjunto de {nombre} tiene muy pocos ejemplos con lluvia "
                f"({int(df[ETIQUETA].sum())}, se necesitan al menos {MIN_POSITIVOS}). "
                "Hace falta más histórico con lluvia antes de evaluar el modelo."
            )


def elegir_modelo(entrenamiento: pd.DataFrame) -> tuple[str, float, dict]:
    """Elige candidato y umbral con validación cruzada por bloques de tiempo. Devuelve (nombre, umbral, detalle)."""
    entrenamiento = entrenamiento.sort_values("fin").reset_index(drop=True)

    # Con pocos eventos de lluvia, un solo tramo de validación puede quedar seco. Se parte el entrenamiento en
    # bloques contiguos; cada uno se predice con un modelo que no vio ese bloque ni la hora de cada lado
    # (la etiqueta mira una hora adelante). La prueba no interviene.
    probabilidades = {nombre: np.full(len(entrenamiento), np.nan) for nombre in candidatos()}
    for tramo in bloques_de_tiempo(entrenamiento["fin"], BLOQUES):
        inicio, fin = entrenamiento.loc[tramo, "fin"].min(), entrenamiento.loc[tramo, "fin"].max()
        hueco = pd.Timedelta(hours=1)
        propio = (entrenamiento["fin"] >= inicio) & (entrenamiento["fin"] <= fin)
        cerca = (entrenamiento["fin"] > inicio - hueco) & (entrenamiento["fin"] < fin + hueco)
        aprende = entrenamiento[~cerca]
        if aprende[ETIQUETA].nunique() < 2:
            continue
        for nombre, modelo in candidatos().items():
            modelo.fit(aprende[VARIABLES], aprende[ETIQUETA])
            probabilidades[nombre][propio.to_numpy()] = modelo.predict_proba(entrenamiento.loc[propio, VARIABLES])[:, 1]

    en_validacion = {}
    for nombre, prob in probabilidades.items():
        usadas = ~np.isnan(prob)
        real = entrenamiento.loc[usadas, ETIQUETA]
        if real.nunique() < 2:
            raise ValueError("La validación no tiene lluvia y no-lluvia a la vez; hace falta más histórico.")
        en_validacion[nombre] = {
            "pr_auc": round(float(average_precision_score(real, prob[usadas])), 4),
            "umbral": mejor_umbral(real, prob[usadas]),
        }
    elegido = max(en_validacion, key=lambda n: en_validacion[n]["pr_auc"])
    umbral = en_validacion[elegido]["umbral"]

    return elegido, umbral, en_validacion


def entrenar_y_evaluar(entrenamiento: pd.DataFrame, prueba: pd.DataFrame):
    """Devuelve (modelo, umbral, métricas)."""
    validar(entrenamiento, prueba)
    entrenamiento = entrenamiento.sort_values("fin").reset_index(drop=True)

    # --- 1. Elegir candidato y umbral (la prueba no interviene) ---
    elegido, umbral, en_validacion = elegir_modelo(entrenamiento)

    # --- 2. Reentrenar con todo el entrenamiento ---
    modelo = candidatos()[elegido]
    modelo.fit(entrenamiento[VARIABLES], entrenamiento[ETIQUETA])

    # --- 3. Evaluar una sola vez en la prueba ---
    prob = modelo.predict_proba(prueba[VARIABLES])[:, 1]
    real = prueba[ETIQUETA]
    del_modelo = metricas_binarias(real, prob >= umbral)
    de_la_base = metricas_binarias(real, prueba[LINEA_BASE].to_numpy())
    del_modelo.update(
        roc_auc=round(float(roc_auc_score(real, prob)), 4),
        pr_auc=round(float(average_precision_score(real, prob)), 4),
        brier=round(float(brier_score_loss(real, prob)), 4),
    )
    metricas = {
        "entrenado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modelo": elegido,
        "umbral": umbral,
        "variables": VARIABLES,
        "validacion": en_validacion,
        "prueba": {
            "filas": int(len(prueba)),
            "tasa_lluvia": round(float(real.mean()), 4),
            "modelo": del_modelo,
            "linea_base_persistencia": de_la_base,
            "mejora_f1": round(del_modelo["f1"] - de_la_base["f1"], 4),
            "supera_linea_base": bool(del_modelo["f1"] > de_la_base["f1"]),
        },
        "entrenamiento": {"filas": int(len(entrenamiento)), "tasa_lluvia": round(float(entrenamiento[ETIQUETA].mean()), 4)},
    }
    return modelo, umbral, metricas


def reentrenar_con_todo(entrenamiento: pd.DataFrame, prueba: pd.DataFrame):
    """Modelo final: mismo procedimiento, pero con todos los datos (la prueba ya cumplió su papel de medir).

    Se usa para el modelo que se publica, porque con tan pocos eventos de lluvia cada evento cuenta.
    Las métricas reportadas siguen siendo las de la evaluación con la prueba apartada.
    """
    todo = pd.concat([entrenamiento, prueba], ignore_index=True)
    elegido, umbral, _ = elegir_modelo(todo)
    modelo = candidatos()[elegido]
    modelo.fit(todo[VARIABLES], todo[ETIQUETA])
    return modelo, umbral, int(len(todo))


def exportar_json(modelo, umbral: float) -> dict | None:
    """Regresión logística como números planos (media, escala, coeficientes), para usarla sin scikit-learn.

    Devuelve None si el modelo elegido no es una regresión logística.
    """
    pasos = getattr(modelo, "named_steps", None)
    if not pasos or "logisticregression" not in pasos or "standardscaler" not in pasos:
        return None
    escala, lineal = pasos["standardscaler"], pasos["logisticregression"]
    return {
        "tipo": "regresion_logistica",
        "variables": VARIABLES,
        "media": [float(x) for x in escala.mean_],
        "escala": [float(x) for x in escala.scale_],
        "coeficientes": [float(x) for x in lineal.coef_[0]],
        "intercepto": float(lineal.intercept_[0]),
        "umbral": umbral,
    }


def guardar(modelo, umbral: float, metricas: dict, carpeta: Path = MODELO) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    joblib.dump({"modelo": modelo, "umbral": umbral, "variables": VARIABLES}, carpeta / "modelo.joblib")
    plano = exportar_json(modelo, umbral)
    if plano:
        (carpeta / "modelo.json").write_text(json.dumps(plano, indent=2), encoding="utf-8")
    (carpeta / "metricas.json").write_text(json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--datos", type=Path, default=DATOS)
    p.add_argument("--salida", type=Path, default=MODELO)
    p.add_argument("--todo", action="store_true", help="publicar un modelo reentrenado con entrenamiento + prueba")
    a = p.parse_args()

    try:
        entrenamiento = pd.read_csv(a.datos / "entrenamiento.csv", parse_dates=["fin"])
        prueba = pd.read_csv(a.datos / "prueba.csv", parse_dates=["fin"])
    except FileNotFoundError:
        sys.exit("No hay datos preparados. Corre primero: python preparar_datos.py")
    resumen = a.datos / "resumen.json"
    sintetico = resumen.is_file() and json.loads(resumen.read_text(encoding="utf-8")).get("sintetico", False)
    if sintetico and a.salida.resolve() == MODELO.resolve():
        sys.exit("Estos datos son sintéticos: no se guarda el modelo en modelo/. Usa --salida modelo_demo para una demostración.")
    try:
        modelo, umbral, metricas = entrenar_y_evaluar(entrenamiento, prueba)
    except ValueError as e:
        sys.exit(str(e))
    metricas["sintetico"] = sintetico
    if a.todo:
        modelo, umbral, filas = reentrenar_con_todo(entrenamiento, prueba)
        metricas["publicado"] = {"reentrenado_con_todo": True, "filas": filas, "umbral": umbral}
    guardar(modelo, umbral, metricas, a.salida)
    if sintetico:
        print("DEMO CON DATOS SINTÉTICOS: estas métricas no son evidencia del modelo real.")
    print(json.dumps(metricas["prueba"], indent=2, ensure_ascii=False))
    print(f"\nModelo: {metricas['modelo']} · umbral {umbral} · guardado en {a.salida}")


if __name__ == "__main__":
    main()
