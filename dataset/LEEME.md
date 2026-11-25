# Datos reales usados para entrenar la IA

Lecturas de los pluviómetros del SAB / IDIGER de Bogotá que guardó el recolector de Cumulonimbus (PostgreSQL), exportadas el 24 de noviembre de 2026.

| Archivo | Filas | Contenido |
|---|---|---|
| `lecturas.csv` | 34.709 | `id_sensor`, `fecha_lectura` (hora de Bogotá), `valor_5min` (mm en los últimos 5 min), `acumulado_dia` (mm desde la medianoche) |
| `estaciones.csv` | 71 | `id_sensor`, `id_estacion`, `nombre`, `id_localidad`, `localidad`, `latitud`, `longitud`, `tecnologia` |

Periodo: 14/10/2026 10:08 a 19/10/2026 19:00, con huecos (el recolector estuvo apagado por tramos).

**Ojo:** solo hay dos eventos de lluvia, el 14/10 (tormenta fuerte) y el 17/10 (llovizna); apenas 285 lecturas (0,8 %) registran lluvia. Por eso el modelo todavía no supera a la línea base. Ver `docs/ia.md`.

Se usan con `ml/preparar_datos.py`:

```bash
cd ml
python preparar_datos.py --lecturas ../dataset/lecturas.csv --estaciones ../dataset/estaciones.csv --corte 2026-10-17
```
