/**
 * Lluvia animada sobre el mapa (diseño «Mapa vivo»).
 *
 * Las gotas caen solo donde llueve: sobre los píxeles con eco del radar del IDIGER y alrededor de
 * las estaciones que registran lluvia. Cuanto más intensa la lluvia, más gotas y más largas.
 */
import type { Map as MapaGL } from "maplibre-gl";
import type { Estacion, Radar } from "./types";

export interface Celda {
  lon: number;
  lat: number;
  /** 0–1: intensidad de la lluvia en la celda. */
  peso: number;
  radioKm: number;
}

export const ALFA_MINIMO_RADAR = 90; // por debajo es ruido (el radar deja un velo casi transparente)
/**
 * Solo se consideran ecos de lluvia moderada o más fuerte (amarillo, naranja, rojo). Los verdes y cian son llovizna
 * o lluvia en el aire que muchas veces no llega al suelo: contradicen a los pluviómetros y confunden.
 */
export const PESO_MINIMO_RADAR = 0.6;
const MAX_GOTAS = 2400;
const TASA_MAXIMA = 3600; // gotas por segundo

/** Intensidad aproximada según el color del radar: azul < verde < amarillo < naranja < rojo. */
export function pesoPorColor(r: number, g: number, b: number): number {
  if (b > 150) return 0.25; // blanco, cian o tonos pálidos: no son lluvia fuerte (el amarillo/naranja/rojo casi no llevan azul)
  if (r > 200 && g < 120) return 1; // rojo
  if (r > 200 && g < 195) return 0.8; // naranja
  if (r > 190 && g >= 195) return 0.6; // amarillo
  if (g > 150 && r < 170) return b > 190 ? 0.3 : 0.45; // verde (o cian si lleva mucho azul)
  return 0.25; // azul
}

export async function celdasDeRadar(radar: Radar): Promise<Celda[]> {
  const img = new Image();
  img.src = radar.imagen;
  await img.decode();
  const w = img.naturalWidth;
  const h = img.naturalHeight;
  const lienzo = document.createElement("canvas");
  lienzo.width = w;
  lienzo.height = h;
  const ctx = lienzo.getContext("2d", { willReadFrequently: true });
  if (!ctx) return [];
  ctx.drawImage(img, 0, 0);
  const { data } = ctx.getImageData(0, 0, w, h);

  const dLon = (radar.este - radar.oeste) / w;
  const dLat = (radar.norte - radar.sur) / h;
  const radioKm = dLat * 111.32 * 0.6;
  const celdas: Celda[] = [];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      if (data[i + 3] < ALFA_MINIMO_RADAR) continue;
      const peso = pesoPorColor(data[i], data[i + 1], data[i + 2]);
      if (peso < PESO_MINIMO_RADAR) continue;
      celdas.push({ lon: radar.oeste + (x + 0.5) * dLon, lat: radar.norte - (y + 0.5) * dLat, peso, radioKm });
    }
  }
  return celdas;
}

export function celdasDeEstaciones(estaciones: Estacion[]): Celda[] {
  return estaciones
    .filter((e) => e.lloviendo)
    .map((e) => ({
      lon: e.longitud,
      lat: e.latitud,
      peso: Math.min(1, 0.4 + e.mm_hora / 60),
      radioKm: 2.2,
    }));
}

export interface MotorLluvia {
  fijarCeldas: (celdas: Celda[]) => void;
  detener: () => void;
}

export function iniciarLluvia(mapa: MapaGL, colorGota: () => string): MotorLluvia {
  const contenedor = mapa.getCanvasContainer();
  const lienzo = document.createElement("canvas");
  lienzo.className = "lluvia-viva";
  Object.assign(lienzo.style, { position: "absolute", left: "0", top: "0", pointerEvents: "none", zIndex: "1" });
  contenedor.appendChild(lienzo);
  const ctx = lienzo.getContext("2d")!;

  let ancho = 0;
  let alto = 0;
  const ajustar = () => {
    // El contenedor de MapLibre no tiene tamaño propio: se toma el del canvas del mapa.
    const base = mapa.getCanvas();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    ancho = base.clientWidth;
    alto = base.clientHeight;
    lienzo.style.width = `${ancho}px`;
    lienzo.style.height = `${alto}px`;
    lienzo.width = Math.round(ancho * dpr);
    lienzo.height = Math.round(alto * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  ajustar();
  mapa.on("resize", ajustar);

  // Celdas con su peso acumulado, para elegir una al azar proporcionalmente a su intensidad.
  let celdas: Celda[] = [];
  let acumulado = new Float64Array(0);
  let total = 0;

  // Gotas en arreglos tipados: sin crear objetos por cuadro.
  const x = new Float32Array(MAX_GOTAS);
  const y = new Float32Array(MAX_GOTAS);
  const vy = new Float32Array(MAX_GOTAS);
  const largo = new Float32Array(MAX_GOTAS);
  const vida = new Float32Array(MAX_GOTAS);
  let activas = 0;

  const elegirCelda = (): Celda => {
    const objetivo = Math.random() * total;
    let lo = 0;
    let hi = acumulado.length - 1;
    while (lo < hi) {
      const medio = (lo + hi) >> 1;
      if (acumulado[medio] < objetivo) lo = medio + 1;
      else hi = medio;
    }
    return celdas[lo];
  };

  const aparecer = () => {
    if (activas >= MAX_GOTAS) return;
    const c = elegirCelda();
    const p = mapa.project([c.lon, c.lat]);
    if (p.x < -60 || p.y < -60 || p.x > ancho + 60 || p.y > alto + 60) return;
    const metrosPorPixel = (78271.517 * Math.cos((c.lat * Math.PI) / 180)) / 2 ** mapa.getZoom();
    const radioPx = Math.max(6, (c.radioKm * 1000) / metrosPorPixel);
    const ang = Math.random() * Math.PI * 2;
    const r = Math.sqrt(Math.random()) * radioPx;
    const i = activas++;
    x[i] = p.x + Math.cos(ang) * r;
    y[i] = p.y + Math.sin(ang) * r;
    vy[i] = (480 + Math.random() * 280) * (0.75 + 0.5 * c.peso);
    largo[i] = 8 + 14 * c.peso * (0.6 + Math.random() * 0.6);
    // Vida corta: la gota cae unos pocos píxeles y se apaga, así la lluvia no se riega fuera de su zona.
    vida[i] = 0.12 + Math.random() * 0.16;
  };

  const reducirMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let ultimo = performance.now();
  let cuadro = 0;
  let restoSpawn = 0;
  const VIENTO = 0.26;

  const dibujar = (ahora: number) => {
    cuadro = requestAnimationFrame(dibujar);
    const dt = Math.min(0.05, (ahora - ultimo) / 1000);
    ultimo = ahora;
    ctx.clearRect(0, 0, ancho, alto);
    if (!total || reducirMovimiento) return;

    restoSpawn += Math.min(TASA_MAXIMA, 60 + total * 9) * dt;
    for (; restoSpawn >= 1; restoSpawn -= 1) aparecer();

    ctx.strokeStyle = colorGota();
    ctx.lineWidth = 1.15;
    ctx.lineCap = "round";
    ctx.globalAlpha = 0.6;
    ctx.beginPath();
    for (let i = 0; i < activas; ) {
      vida[i] -= dt;
      if (vida[i] <= 0) {
        // Se reemplaza por la última gota activa.
        const u = --activas;
        x[i] = x[u]; y[i] = y[u]; vy[i] = vy[u]; largo[i] = largo[u]; vida[i] = vida[u];
        continue;
      }
      const dy = vy[i] * dt;
      x[i] += dy * VIENTO;
      y[i] += dy;
      ctx.moveTo(x[i], y[i]);
      ctx.lineTo(x[i] - largo[i] * VIENTO, y[i] - largo[i]);
      i++;
    }
    ctx.stroke();
    ctx.globalAlpha = 1;
  };
  cuadro = requestAnimationFrame(dibujar);

  return {
    fijarCeldas(nuevas) {
      celdas = nuevas;
      acumulado = new Float64Array(nuevas.length);
      let suma = 0;
      nuevas.forEach((c, i) => { suma += c.peso; acumulado[i] = suma; });
      total = suma;
      if (!total) activas = 0;
    },
    detener() {
      cancelAnimationFrame(cuadro);
      mapa.off("resize", ajustar);
      lienzo.remove();
    },
  };
}
