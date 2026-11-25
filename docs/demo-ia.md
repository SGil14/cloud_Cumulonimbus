# Guion de la demo: IA y Grafana

Parte de la sustentación del Proyecto 3 (unos 3 minutos). Va después de la demo de Kubernetes (`docs/demo-kubernetes.md`) o por separado; sirve igual con `docker compose` o en el clúster.

## Antes de entrar (10 minutos antes)

- [ ] La app corriendo con su base de datos y **al menos 1 hora de lecturas guardadas** (el recolector encendido). Sin esa hora, la predicción usa la regla simple y lo dice: no es un error, pero conviene mostrar el modelo. Comprobar: `curl "http://localhost:8000/api/prediccion?lat=4.65&lon=-74.06"` y ver `"metodo": "modelo"`.
- [ ] Pestañas abiertas: la app (<http://localhost:8000>), Grafana (<http://localhost:3000>, dashboard «Cumulonimbus · API e IA», bajar hasta los paneles que empiezan con «IA ·») y `docs/ia.md` en el repositorio.
- [ ] Una terminal en la raíz del repositorio, con letra grande.
- [ ] Plan B si no hay internet o el SAB no responde: la app muestra el último dato y la predicción usa la regla simple; contarlo como parte de la demostración (el respaldo funciona).

## 1. La funcionalidad en la app (1 min)

1. En la app, buscar un destino (por ejemplo «Chapinero»).
2. Señalar el bloque **«Próxima hora»** bajo el resultado: la probabilidad, el método («Modelo de IA · experimental») y el aviso.

Qué decir:
- «La app ya decía *si llueve ahora*. La IA responde la pregunta que decide si salgo: **¿va a llover en la próxima hora donde voy?**»
- «Es una **estimación experimental**, y la interfaz lo dice: con los datos que tenemos todavía no supera a la regla simple *si llueve ahora, seguirá lloviendo*. Preferimos decirlo a venderlo como un pronóstico.»
- «Si no hay una hora de lecturas continuas, la app **no inventa**: usa la regla simple y explica por qué.»

## 2. Generar tráfico y ver Grafana (1 min 30 s)

```powershell
python scripts/trafico.py --url http://localhost:8000 --segundos 120 --usuarios 20
```

Mientras corre, en Grafana (refresco cada 10 s), bajar a los paneles de IA:

| Panel | Qué mostrar |
|---|---|
| IA · predicciones por minuto y método | Sube al empezar el tráfico; la línea es `modelo` (o `persistencia` si faltan lecturas) |
| IA · latencia de la predicción (p50 y p95) | Milisegundos: el modelo es una cuenta de 8 números |
| IA · predicciones en la última hora | El total por método |
| IA · probabilidad de la última predicción | Se mueve con cada consulta |

Qué decir:
- «Cada predicción cuenta en `cumulonimbus_ia_predicciones_total` con la etiqueta del método, y su tiempo en un histograma. Prometheus las lee cada 10 segundos de `/metrics`.»
- «El mismo dashboard (un solo JSON) se carga en `docker compose` y en Kubernetes; una prueba automática verifica que cada consulta use métricas que existen.»

## 3. Cómo se hizo, técnicamente (30 s a 1 min)

Se puede dejar abierto `docs/ia.md`. Ver las respuestas de abajo.

---

## Lo que todo el equipo debe poder explicar

**¿Qué problema resuelve?** Anticipar si va a llover en la próxima hora en un destino, no solo decir si llueve ahora.

**¿Por qué esta IA y no un asistente con un LLM?** Se compararon 4 alternativas (predicción, asistente con LLM, detección de anomalías, agrupación). La predicción es la única que aporta información nueva, se puede medir contra una línea base y no depende de servicios de pago. El LLM solo reformularía lo que la app ya muestra.

**¿Con qué datos?** Con las lecturas reales de las 71 estaciones del SAB, guardadas por nuestro propio recolector (14 al 19 de octubre de 2026: 34.709 lecturas, 7.137 ejemplos).

**¿Qué algoritmos se usaron?** Se compararon dos: **regresión logística** (con variables estandarizadas) y **árbol de gradiente** (`HistGradientBoostingClassifier`), ambos con `class_weight="balanced"` porque la lluvia es rara (3 a 4 % de los ejemplos). Ganó la regresión logística.

**¿Qué variables usa?** Lluvia de la estación en los últimos 10, 30 y 60 minutos; lluvia de sus 3 estaciones vecinas en los últimos 30 y 60 minutos; acumulado del día; y la hora del día codificada como círculo (seno y coseno). La etiqueta es: «¿registró lluvia en los 60 minutos siguientes?».

**¿Cómo se entrenó y evaluó sin hacer trampa?**
- División **por tiempo**, no aleatoria: se entrena con el 14 al 16 de octubre y se prueba con el 17 al 19, dejando una hora de separación para que la etiqueta (que mira una hora al futuro) no filtre información.
- El modelo y el umbral se eligen con **validación cruzada por bloques de tiempo** dentro del entrenamiento; la prueba se mira **una sola vez**.
- Se compara con una **línea base**: «si llueve ahora, seguirá lloviendo».
- El modelo publicado se reentrena con todos los datos; las métricas que se reportan son las de la prueba apartada.

**¿Cómo le fue?** En la prueba, el modelo tiene F1 0,17 y la línea base 0,38: **no la supera**. Con datos distintos (entrenar con un evento y probar en el otro) hay algo de señal por encima del azar, pero poca. La causa es que solo tenemos **dos eventos de lluvia**, uno de tormenta fuerte y otro de llovizna, y un modelo no generaliza de uno al otro.

**¿Por qué entonces se publicó?** Porque funciona de punta a punta, se mide, y tiene respaldo: cuando falte información responde con la regla simple. La interfaz y la API avisan que es experimental. Con más temporada de lluvias y un reentrenamiento, el mismo código se puede mejorar sin tocar la API.

**¿Cómo se conecta con la API?** El modelo se exporta a un JSON de unos 20 números (`backend/app/ia/modelo.json`) y la API hace la cuenta en Python puro, sin instalar scikit-learn en la imagen. Una prueba automática comprueba que la API y el entrenamiento calculan exactamente las mismas variables.

**¿Qué son los datos sintéticos?** Un simulador (`ml/simulador.py`) genera lluvia inventada solo para probar y demostrar el procedimiento. Sus archivos están marcados, y el entrenamiento se niega a guardar un modelo sintético como si fuera real. **Nunca se usan para evaluar.**

**¿Y los datos del IDEAM?** Se intentó sumar su dataset abierto (2004 a 2019, estaciones de Bogotá), pero su API no responde a consultas por fecha. Reconstruir los datos secos que faltan habría sido inventarlos, así que se descartó.

**¿Qué mejorarías?** Más días con lluvia (dejar el recolector encendido en temporada de lluvias), el radar del IDIGER como variable, calibrar las probabilidades y evaluar por eventos completos.

## Si algo falla en vivo

| Síntoma | Qué hacer |
|---|---|
| «Próxima hora» dice «Regla simple» y el motivo menciona lecturas | La app estuvo apagada: es el respaldo funcionando. Contarlo y seguir; o esperar una hora de lecturas. |
| «No se pudo calcular la predicción» con botón Reintentar | Es el estado de error de la interfaz. Reintentar; si persiste, revisar `/api/health` (¿base de datos?). |
| Los paneles de IA están vacíos | No ha habido predicciones: correr `scripts/trafico.py`. En Grafana, ajustar el rango a «Last 15 minutes». |
| `docker compose up` falla por `GRAFANA_PASSWORD` | Definirla en el `.env` (y `POSTGRES_PASSWORD`). |
