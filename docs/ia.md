# Inteligencia artificial en Cumulonimbus

## 1. Decisión: qué funcionalidad de IA construimos

### El problema

Hoy Cumulonimbus responde **qué está pasando**: dónde llueve ahora, si llueve cerca de un destino y qué tramos de una ruta están mojados. No responde la pregunta que de verdad decide si alguien sale o espera: **«¿va a llover en la próxima hora donde voy a estar?»**.

### Alternativas evaluadas

| # | Alternativa | Qué haría | Datos disponibles | Viabilidad | Riesgo principal |
|---|---|---|---|---|---|
| A | **Predicción de lluvia a corto plazo (nowcasting)** | Estima la probabilidad de lluvia en la próxima hora para una estación o un destino, a partir de las lecturas recientes de la estación y de sus vecinas. | Tabla `lecturas` (histórico propio del recolector) y lecturas en vivo del SAB. | Alta: es un modelo tabular ligero (regresión logística o árboles) que entrena en segundos y corre en CPU. | El histórico solo existe desde que el recolector está encendido; hay que verificar cuánto hay antes de entrenar. |
| B | **Asistente con LLM** («¿me mojo si salgo ahora?») | Redacta una recomendación en lenguaje natural con las lecturas, el destino y la ruta como contexto. | Lecturas en vivo, ruta y destino (todo ya existe en la API). | Media: depende de un servicio externo con clave, costo por consulta y latencia. | No predice nada nuevo: reformula lo que la app ya muestra. Riesgo de respuestas inventadas. |
| C | **Detección de anomalías en pluviómetros** | Marca estaciones con lecturas congeladas, en cero sospechoso o con saltos imposibles. | Tabla `lecturas`. | Alta, pero con pocas etiquetas reales para evaluar. | Sirve al equipo, no al usuario final. Cuesta demostrar su valor en una sustentación. |
| D | **Agrupación de localidades por patrón de lluvia** | Agrupa localidades según cómo y cuándo llueve. | Tabla `lecturas`. | Alta. | Resultado descriptivo; no responde ninguna pregunta del usuario. |

### Comparación

| Criterio | A · Nowcasting | B · LLM | C · Anomalías | D · Agrupación |
|---|---|---|---|---|
| Valor para el usuario | Alto | Medio | Bajo | Bajo |
| Usa datos reales de la app | Sí | Sí | Sí | Sí |
| Se puede medir contra una línea base | Sí (persistencia) | Difícil | Parcial | No |
| Costo y dependencias externas | Ninguna | Clave y cobro por uso | Ninguna | Ninguna |
| Se puede mostrar en Grafana (inferencias y latencia) | Sí | Sí | Sí | Sí |
| Esfuerzo | Medio | Medio | Bajo | Bajo |

### Decisión propuesta

**Alternativa A: predicción de lluvia a corto plazo.** Es la única que añade información que la app no tiene, se puede evaluar de forma objetiva contra una línea base y no depende de servicios de pago.

**Línea base de la evaluación:** «persistencia», es decir, predecir que en la próxima hora lloverá si ahora llueve. El modelo solo vale la pena si la supera de forma clara.

### Historia de usuario de la funcionalidad elegida

> **Como** persona que se va a mover por Bogotá,
> **quiero** saber qué probabilidad hay de que llueva en la próxima hora en mi destino,
> **para** decidir si salgo ahora, espero o llevo paraguas.

**Criterios de aceptación**
- [ ] Dado un destino (coordenadas), la API devuelve la probabilidad de lluvia en la próxima hora y las estaciones en las que se basó.
- [ ] El modelo supera la línea base de persistencia en el conjunto de prueba, con las métricas documentadas.
- [ ] Si no hay datos suficientes o el modelo no está disponible, la API lo dice con claridad y la app sigue funcionando.
- [ ] La predicción se ve en la interfaz con estado de carga y de error.
- [ ] El número de inferencias y su latencia se exponen en `/metrics`.

### Estado de la aprobación

- [x] **Aprobada:** el equipo aprobó la alternativa A (predicción de lluvia a corto plazo). Falta que el Product Owner (@SGil14) deje la aprobación registrada en la issue #58.

## 2. Datos (HU-41)

### Origen

Tabla `lecturas` de PostgreSQL, que llena el recolector con las lecturas de los pluviómetros del SAB cada pocos minutos: `id_sensor`, `fecha_lectura` y `acumulado_dia` (lluvia acumulada desde la medianoche, en mm). La ubicación de cada estación sale de la tabla `estaciones` (`latitud`, `longitud`).

No se usa `valor_5min`: el acumulado del día es más estable y es lo que ya usa el historial de la API, así que no importa si las lecturas llegan cada 2 o cada 5 minutos.

### Cómo se preparan (reproducible)

```bash
cd ml
pip install -r requirements.txt
python preparar_datos.py          # lee DATABASE_URL del entorno o del .env de la raíz
pytest                            # pruebas de la preparación, sin base de datos
```

También acepta archivos: `python preparar_datos.py --lecturas lecturas.csv --estaciones estaciones.csv`. Genera `ml/data/entrenamiento.csv`, `ml/data/prueba.csv` y `ml/data/resumen.json` (cuántas filas, estaciones, fechas y proporción de lluvia). Esa carpeta no se versiona.

### Limpieza

1. Se descartan lecturas duplicadas, vacías o con acumulado negativo.
2. La lluvia entre dos lecturas es la diferencia del acumulado; si el acumulado baja, es el reinicio de medianoche y vale lo que marca.
3. Se agrupa en pasos de 10 minutos por estación.
4. **Solo se usan instantes con la ventana completa**: una hora de pasado y una hora de futuro, sin huecos. Si el recolector estuvo apagado, ese tramo no se usa. No se rellena ni se inventa lluvia.

### Qué es un ejemplo

Una estación en un instante `t` (final de un paso de 10 minutos):

| Variable | Significado |
|---|---|
| `mm_10`, `mm_30`, `mm_60` | Lluvia de la estación en los últimos 10, 30 y 60 minutos |
| `acumulado_dia` | Acumulado del día en `t` |
| `vecinas_mm_30`, `vecinas_mm_60` | Promedio de lluvia de las 3 estaciones más cercanas en los últimos 30 y 60 minutos |
| `hora_sin`, `hora_cos` | Hora del día codificada como círculo (las 23:50 quedan cerca de las 00:10) |
| **`llovera`** (etiqueta) | 1 si la estación registra lluvia (> 0 mm) en los 60 minutos siguientes |
| `base_persistencia` | Línea base: 1 si ya estaba lloviendo en el último paso |

### Conjunto de prueba separado

La división es **por tiempo**, no aleatoria: la prueba es el 20 % más reciente. Entre entrenamiento y prueba se deja una hora sin usar, porque la etiqueta mira una hora al futuro y sin ese hueco ambos conjuntos compartirían lluvia. Una división aleatoria haría que el modelo viera, al entrenar, instantes pegados a los de la prueba y daría métricas demasiado buenas.

### Pendiente antes de entrenar

- Correr `preparar_datos.py` contra la base real y revisar `resumen.json`: cuántas horas de lecturas continuas hay y qué proporción de ellas tiene lluvia. Si es muy baja, hay que dejar el recolector encendido más tiempo antes de evaluar el modelo.

## 3. Modelo y evaluación (HU-42)

### Qué se entrena

`ml/entrenar.py` compara dos modelos sobre las mismas variables:

| Candidato | Por qué |
|---|---|
| Regresión logística (con variables estandarizadas) | Simple, interpretable y rápida: es el punto de partida razonable |
| Árbol de gradiente (`HistGradientBoostingClassifier`) | Captura relaciones no lineales (por ejemplo, la hora del día) |

Como la lluvia es rara, ambos usan `class_weight="balanced"`.

### Cómo se evalúa (sin hacer trampa)

1. Del entrenamiento se aparta como **validación** el tramo más reciente (con una hora de separación). Con él se elige el modelo (por PR-AUC) y el **umbral de decisión** (el que maximiza F1; con una clase tan rara, 0,5 casi nunca es lo mejor).
2. El modelo elegido se reentrena con todo el entrenamiento.
3. Se evalúa **una sola vez** en el conjunto de prueba, junto a la **línea base de persistencia**.
4. Si el entrenamiento o la prueba tienen menos de 20 ejemplos con lluvia, el script se detiene y lo dice: con tan poca lluvia cualquier métrica sería ruido.

Métricas: precisión, recall y F1 a la altura del umbral; ROC-AUC, PR-AUC y Brier (calidad de la probabilidad) para el modelo. El modelo «supera la línea base» si su F1 en la prueba es mayor que el de la persistencia.

### Reproducir

```bash
cd ml
python preparar_datos.py     # datos (sección 2)
python entrenar.py           # entrena, evalúa y guarda modelo/modelo.joblib y modelo/metricas.json
pytest                       # pruebas con datos sintéticos
```

### Resultados

> **Pendiente:** correr `entrenar.py` con los datos reales y pegar aquí `modelo/metricas.json`. Las pruebas automáticas usan datos sintéticos y solo verifican que el procedimiento funciona; **no son resultados del modelo**.

| | Precisión | Recall | F1 |
|---|---|---|---|
| Línea base (persistencia) | – | – | – |
| Modelo | – | – | – |
