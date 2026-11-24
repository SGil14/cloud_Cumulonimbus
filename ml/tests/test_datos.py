import pandas as pd
import pytest

import datos

INICIO = pd.Timestamp("2026-10-14 06:00", tz="America/Bogota")


def lecturas(id_sensor, acumulados, cada_min=5, inicio=INICIO):
    """Lecturas de una estación: un acumulado cada `cada_min` minutos."""
    return pd.DataFrame({
        "id_sensor": id_sensor,
        "fecha_lectura": [inicio + pd.Timedelta(minutes=cada_min * i) for i in range(len(acumulados))],
        "acumulado_dia": acumulados,
    })


ESTACIONES = pd.DataFrame({
    "id_sensor": [1, 2, 3],
    "latitud": [4.60, 4.61, 4.80],
    "longitud": [-74.10, -74.10, -74.00],
})


def test_limpiar_quita_duplicados_negativos_y_faltantes():
    df = lecturas(1, [0.0, 0.0, 1.0, -3.0, None])
    df = pd.concat([df, df.iloc[[0]]])
    limpio = datos.limpiar_lecturas(df)
    assert list(limpio["acumulado_dia"]) == [0.0, 0.0, 1.0]
    assert str(limpio["fecha_lectura"].dt.tz) == "America/Bogota"


def test_limpiar_exige_las_columnas():
    with pytest.raises(ValueError):
        datos.limpiar_lecturas(pd.DataFrame({"id_sensor": [1]}))


def test_lluvia_es_la_diferencia_del_acumulado_y_maneja_el_reinicio():
    df = datos.limpiar_lecturas(lecturas(1, [0.0, 0.5, 0.5, 2.0, 0.3]))
    mm = datos.lluvia_por_lectura(df)["mm"].round(2).tolist()
    # La primera lectura no tiene anterior; 2.0 -> 0.3 es un reinicio a medianoche.
    assert mm == [0.0, 0.5, 0.0, 1.5, 0.3]


def test_lluvia_no_mezcla_estaciones():
    df = datos.limpiar_lecturas(pd.concat([lecturas(1, [5.0, 5.0]), lecturas(2, [0.0, 1.0])]))
    por_estacion = datos.lluvia_por_lectura(df).groupby("id_sensor")["mm"].sum()
    assert por_estacion[1] == 0.0 and por_estacion[2] == 1.0


def test_pasos_de_10_minutos_suman_la_lluvia():
    df = datos.lluvia_por_lectura(datos.limpiar_lecturas(lecturas(1, [0.0, 0.2, 0.5, 0.5])))
    pasos = datos.a_pasos(df)
    # 06:00 y 06:05 en el primer paso (0.2 mm); 06:10 y 06:15 en el segundo (0.3 mm).
    assert pasos["mm"].round(2).tolist() == [0.2, 0.3]
    assert pasos["paso"].tolist() == [0, 1]
    assert pasos["acumulado_dia"].tolist() == [0.2, 0.5]


def test_vecinas_son_las_mas_cercanas():
    vecinas = datos.estaciones_vecinas(ESTACIONES, k=1)
    assert vecinas == {1: [2], 2: [1], 3: [2]}


def serie_de_prueba(horas=8, lluvia_desde=None):
    """Tres estaciones con lecturas cada 5 min; llueve 0.1 mm por lectura desde `lluvia_desde` (en horas)."""
    n = horas * 12
    tablas = []
    for id_sensor in (1, 2, 3):
        acumulado, total = [], 0.0
        for i in range(n):
            if lluvia_desde is not None and i >= lluvia_desde * 12 and id_sensor != 3:
                total += 0.1
            acumulado.append(round(total, 2))
        tablas.append(lecturas(id_sensor, acumulado))
    return pd.concat(tablas, ignore_index=True)


def ejemplos_de(lect, estaciones=ESTACIONES):
    df = datos.limpiar_lecturas(lect)
    pasos = datos.a_pasos(datos.lluvia_por_lectura(df))
    return datos.construir_ejemplos(pasos, datos.estaciones_vecinas(estaciones))


def test_etiqueta_mira_la_proxima_hora_y_la_base_el_ultimo_paso():
    ej = ejemplos_de(serie_de_prueba(horas=8, lluvia_desde=4))
    e1 = ej[ej["id_sensor"] == 1].set_index("fin")

    # A las 09:00 todavía no llueve, pero la lluvia empieza a las 10:00: es lo que hay que anticipar.
    antes = e1.loc[pd.Timestamp("2026-10-14 09:10")]
    assert antes[datos.ETIQUETA] == 1 and antes[datos.LINEA_BASE] == 0
    # Con lluvia sostenida, la línea base acierta.
    durante = e1.loc[pd.Timestamp("2026-10-14 10:30")]
    assert durante[datos.ETIQUETA] == 1 and durante[datos.LINEA_BASE] == 1
    # La estación 3 nunca llueve.
    assert (ej[ej["id_sensor"] == 3][datos.ETIQUETA] == 0).all()


def test_las_variables_usan_solo_el_pasado():
    ej = ejemplos_de(serie_de_prueba(horas=8, lluvia_desde=4))
    e1 = ej[ej["id_sensor"] == 1].set_index("fin")
    # A las 09:10 no había llovido nada en la última hora, aunque luego sí.
    assert e1.loc[pd.Timestamp("2026-10-14 09:10"), "mm_60"] == 0
    # Una hora después de empezar la lluvia: 12 lecturas de 0.1 mm en 60 min... menos la primera diferencia.
    assert e1.loc[pd.Timestamp("2026-10-14 11:00"), "mm_60"] == pytest.approx(1.2)


def test_las_vecinas_aportan_la_lluvia_de_otras_estaciones():
    ej = ejemplos_de(serie_de_prueba(horas=8, lluvia_desde=4))
    # La estación 3 no tiene lluvia propia, pero sus vecinas (1 y 2) sí.
    e3 = ej[ej["id_sensor"] == 3].set_index("fin")
    assert e3.loc[pd.Timestamp("2026-10-14 11:00"), "mm_60"] == 0
    assert e3.loc[pd.Timestamp("2026-10-14 11:00"), "vecinas_mm_60"] > 0


def test_un_hueco_de_lecturas_descarta_los_instantes_que_lo_tocan():
    lect = serie_de_prueba(horas=8, lluvia_desde=4)
    hueco = (lect["fecha_lectura"] >= pd.Timestamp("2026-10-14 09:00", tz="America/Bogota")) & (
        lect["fecha_lectura"] < pd.Timestamp("2026-10-14 09:30", tz="America/Bogota")
    )
    ej = ejemplos_de(lect[~hueco])
    horas = ej["fin"]
    # Sin lecturas entre 09:00 y 09:30, ningún instante entre 08:10 y 10:20 tiene su ventana (±1 h) completa.
    afectados = (horas >= pd.Timestamp("2026-10-14 08:10")) & (horas <= pd.Timestamp("2026-10-14 10:20"))
    assert not afectados.any()
    # Antes y después del hueco sí quedan ejemplos.
    assert (horas < pd.Timestamp("2026-10-14 08:10")).any()
    assert (horas > pd.Timestamp("2026-10-14 10:20")).any()


def test_la_hora_se_codifica_como_circulo():
    ej = ejemplos_de(serie_de_prueba(horas=8))
    assert ((ej["hora_sin"] ** 2 + ej["hora_cos"] ** 2) - 1).abs().max() < 1e-9


def test_la_division_es_por_tiempo_y_deja_un_hueco():
    ej = ejemplos_de(serie_de_prueba(horas=12, lluvia_desde=6))
    entrenamiento, prueba = datos.dividir_en_el_tiempo(ej, 0.25)
    assert not entrenamiento.empty and not prueba.empty
    assert entrenamiento["fin"].max() < prueba["fin"].min()
    # El hueco es de al menos una hora: la etiqueta de entrenamiento no toca la de prueba.
    assert prueba["fin"].min() - entrenamiento["fin"].max() >= pd.Timedelta(hours=1)


def test_preparar_de_punta_a_punta():
    entrenamiento, prueba = datos.preparar(serie_de_prueba(horas=12, lluvia_desde=6), ESTACIONES, 0.25)
    for df in (entrenamiento, prueba):
        assert set(datos.VARIABLES + [datos.ETIQUETA, datos.LINEA_BASE]) <= set(df.columns)
        assert not df[datos.VARIABLES].isna().any().any()


def test_sin_datos_suficientes_devuelve_vacio():
    entrenamiento, prueba = datos.preparar(serie_de_prueba(horas=1), ESTACIONES)
    assert entrenamiento.empty and prueba.empty


def test_la_division_acepta_una_fecha_de_corte():
    ej = ejemplos_de(serie_de_prueba(horas=12, lluvia_desde=6))
    corte = pd.Timestamp("2026-10-14 14:00")
    entrenamiento, prueba = datos.dividir_en_el_tiempo(ej, corte=corte)
    assert prueba["fin"].min() >= corte
    assert entrenamiento["fin"].max() < corte - pd.Timedelta(hours=1) + pd.Timedelta(minutes=1)
