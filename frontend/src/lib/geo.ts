type Anillo = number[][];

/** Centroide del anillo exterior más grande de un Polygon o MultiPolygon, y su ancho en grados. */
export function centroide(geometria: { type: string; coordinates: unknown }): { lon: number; lat: number; ancho: number } {
  const poligonos = (geometria.type === "Polygon"
    ? [geometria.coordinates]
    : geometria.coordinates) as number[][][][];
  let mejor: Anillo = poligonos[0][0];
  let mayorArea = -1;
  for (const poligono of poligonos) {
    const area = Math.abs(areaFirmada(poligono[0]));
    if (area > mayorArea) { mayorArea = area; mejor = poligono[0]; }
  }
  const a = areaFirmada(mejor);
  let cx = 0, cy = 0;
  for (let i = 0; i < mejor.length - 1; i++) {
    const [x0, y0] = mejor[i], [x1, y1] = mejor[i + 1];
    const f = x0 * y1 - x1 * y0;
    cx += (x0 + x1) * f;
    cy += (y0 + y1) * f;
  }
  const xs = mejor.map((p) => p[0]);
  return {
    lon: cx / (6 * a),
    lat: cy / (6 * a),
    ancho: Math.max(...xs) - Math.min(...xs),
  };
}

function areaFirmada(anillo: Anillo): number {
  let suma = 0;
  for (let i = 0; i < anillo.length - 1; i++) {
    suma += anillo[i][0] * anillo[i + 1][1] - anillo[i + 1][0] * anillo[i][1];
  }
  return suma / 2;
}

export const CENTRO_RADAR: [number, number] = [-74.114, 4.675];

/** Anillos de alcance y ejes N-S / E-O centrados en el radar, como líneas GeoJSON. Los radios van en km. */
export function anillosDeRadar(centro: [number, number], radiosKm: number[]) {
  const [lon, lat] = centro;
  const kmPorGradoLat = 111.32;
  const kmPorGradoLon = 111.32 * Math.cos((lat * Math.PI) / 180);
  const linea = (coordinates: number[][]) => ({
    type: "Feature" as const,
    properties: {},
    geometry: { type: "LineString" as const, coordinates },
  });

  const anillos = radiosKm.map((r) =>
    linea(
      Array.from({ length: 97 }, (_, i) => {
        const a = (i / 96) * 2 * Math.PI;
        return [lon + (r * Math.cos(a)) / kmPorGradoLon, lat + (r * Math.sin(a)) / kmPorGradoLat];
      }),
    ),
  );
  const maximo = Math.max(...radiosKm);
  const dLat = maximo / kmPorGradoLat;
  const dLon = maximo / kmPorGradoLon;
  return {
    type: "FeatureCollection" as const,
    features: [...anillos, linea([[lon, lat - dLat], [lon, lat + dLat]]), linea([[lon - dLon, lat], [lon + dLon, lat]])],
  };
}
