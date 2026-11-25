import numpy as np
import pandas as pd
import pytest

import datos
import entrenar


def ejemplos_sinteticos(n=6000, semilla=0):
    """Ejemplos donde la lluvia vecina anticipa la lluvia propia (lo que el modelo debe aprender).

    La línea base (¿llueve ahora?) acierta poco porque casi siempre la estación está seca cuando empieza a llover.
    """
    rng = np.random.default_rng(semilla)
    vecinas = rng.exponential(0.4, n)
    propia = np.where(rng.random(n) < 0.1, rng.exponential(0.3, n), 0.0)
    prob = 1 / (1 + np.exp(-(3.0 * vecinas + 2.0 * propia - 2.5)))
    horas = rng.uniform(0, 24, n)
    df = pd.DataFrame({
        "id_sensor": 1,
        "fin": pd.Timestamp("2026-10-01") + pd.to_timedelta(np.arange(n) * 10, unit="min"),
        "mm_10": propia, "mm_30": propia * 2, "mm_60": propia * 3,
        "acumulado_dia": rng.uniform(0, 20, n),
        "vecinas_mm_30": vecinas, "vecinas_mm_60": vecinas * 1.5,
        "hora_sin": np.sin(2 * np.pi * horas / 24), "hora_cos": np.cos(2 * np.pi * horas / 24),
    })
    df[datos.LINEA_BASE] = (df["mm_10"] > 0).astype(int)
    df[datos.ETIQUETA] = (rng.random(n) < prob).astype(int)
    return df


def test_el_modelo_supera_la_linea_base_cuando_hay_senal():
    entrenamiento, prueba = datos.dividir_en_el_tiempo(ejemplos_sinteticos(), 0.2)
    _, umbral, m = entrenar.entrenar_y_evaluar(entrenamiento, prueba)
    assert 0 < umbral < 1
    assert m["prueba"]["supera_linea_base"]
    assert m["prueba"]["modelo"]["f1"] > m["prueba"]["linea_base_persistencia"]["f1"]
    assert m["prueba"]["modelo"]["roc_auc"] > 0.7


def test_las_metricas_traen_todo_lo_que_se_documenta():
    entrenamiento, prueba = datos.dividir_en_el_tiempo(ejemplos_sinteticos(), 0.2)
    _, _, m = entrenar.entrenar_y_evaluar(entrenamiento, prueba)
    assert set(m["prueba"]["modelo"]) == {"precision", "recall", "f1", "roc_auc", "pr_auc", "brier"}
    assert set(m["prueba"]["linea_base_persistencia"]) == {"precision", "recall", "f1"}
    assert m["modelo"] in entrenar.candidatos()


def test_se_rechaza_un_conjunto_casi_sin_lluvia():
    entrenamiento, prueba = datos.dividir_en_el_tiempo(ejemplos_sinteticos(), 0.2)
    sin_lluvia = prueba.assign(**{datos.ETIQUETA: 0})
    with pytest.raises(ValueError, match="muy pocos ejemplos con lluvia"):
        entrenar.entrenar_y_evaluar(entrenamiento, sin_lluvia)


def test_se_rechaza_un_conjunto_vacio():
    with pytest.raises(ValueError, match="vacío"):
        entrenar.entrenar_y_evaluar(ejemplos_sinteticos().iloc[:0], ejemplos_sinteticos())


def test_guardar_y_cargar_el_modelo(tmp_path):
    import joblib

    entrenamiento, prueba = datos.dividir_en_el_tiempo(ejemplos_sinteticos(), 0.2)
    modelo, umbral, m = entrenar.entrenar_y_evaluar(entrenamiento, prueba)
    entrenar.guardar(modelo, umbral, m, tmp_path)
    cargado = joblib.load(tmp_path / "modelo.joblib")
    assert cargado["variables"] == datos.VARIABLES and cargado["umbral"] == umbral
    prob = cargado["modelo"].predict_proba(prueba[datos.VARIABLES])[:, 1]
    assert prob.shape == (len(prueba),) and ((prob >= 0) & (prob <= 1)).all()
    assert (tmp_path / "metricas.json").is_file()


def test_el_umbral_prefiere_el_mejor_f1():
    real = pd.Series([0] * 90 + [1] * 10)
    prob = np.array([0.1] * 90 + [0.2] * 10)  # separable solo con un umbral bajo
    assert 0.1 < entrenar.mejor_umbral(real, prob) <= 0.2


def test_el_modelo_exportado_en_json_da_las_mismas_probabilidades():
    import math

    entrenamiento, prueba = datos.dividir_en_el_tiempo(ejemplos_sinteticos(), 0.2)
    modelo, umbral, m = entrenar.entrenar_y_evaluar(entrenamiento, prueba)
    plano = entrenar.exportar_json(modelo, umbral)
    if m["modelo"] != "regresion_logistica":
        assert plano is None
        return
    esperado = modelo.predict_proba(prueba[datos.VARIABLES])[:, 1]
    for i in (0, 10, 100):
        fila = prueba.iloc[i]
        z = plano["intercepto"] + sum(
            c * (float(fila[v]) - mu) / sc
            for v, c, mu, sc in zip(plano["variables"], plano["coeficientes"], plano["media"], plano["escala"])
        )
        assert 1 / (1 + math.exp(-z)) == pytest.approx(esperado[i], abs=1e-9)


def test_reentrenar_con_todo_usa_todas_las_filas():
    entrenamiento, prueba = datos.dividir_en_el_tiempo(ejemplos_sinteticos(), 0.2)
    _, _, filas = entrenar.reentrenar_con_todo(entrenamiento, prueba)
    assert filas == len(entrenamiento) + len(prueba)
