import { ALFA_MINIMO_RADAR, PESO_MINIMO_RADAR, pesoPorColor } from "./lluviaViva";

/**
 * Quita de la imagen del radar los ecos débiles (llovizna y lluvia en el aire), dejando solo la lluvia
 * moderada o más fuerte. Devuelve la imagen como data URL; si algo falla, devuelve la original.
 */
const COLORES_CLAROS: Record<number, [number, number, number]> = {
  0.6: [240, 190, 0], // amarillo → dorado
  0.8: [255, 110, 0], // naranja → naranja vivo
  1: [168, 0, 28], // rojo → carmesí
};

/** En el tema claro el amarillo del radar casi se pierde sobre el fondo: se recolorea con tonos más oscuros y saturados. */
export async function sinEcosDebiles(imagen: string, tema: "claro" | "oscuro" = "oscuro"): Promise<string> {
  try {
    const img = new Image();
    img.src = imagen;
    await img.decode();
    const lienzo = document.createElement("canvas");
    lienzo.width = img.naturalWidth;
    lienzo.height = img.naturalHeight;
    const ctx = lienzo.getContext("2d", { willReadFrequently: true });
    if (!ctx) return imagen;
    ctx.drawImage(img, 0, 0);
    const datos = ctx.getImageData(0, 0, lienzo.width, lienzo.height);
    const d = datos.data;
    for (let i = 0; i < d.length; i += 4) {
      const peso = pesoPorColor(d[i], d[i + 1], d[i + 2]);
      if (d[i + 3] < ALFA_MINIMO_RADAR || peso < PESO_MINIMO_RADAR) d[i + 3] = 0;
      else {
        if (tema === "claro") [d[i], d[i + 1], d[i + 2]] = COLORES_CLAROS[peso] ?? COLORES_CLAROS[0.6];
        d[i + 3] = 255;
      } // el radar los entrega casi transparentes: aquí se vuelven sólidos para que se noten
    }
    ctx.putImageData(datos, 0, 0);
    // Halo oscuro alrededor de cada eco, para que destaque sobre fondos claros y oscuros.
    const salida = document.createElement("canvas");
    salida.width = lienzo.width;
    salida.height = lienzo.height;
    const sctx = salida.getContext("2d");
    if (!sctx) return lienzo.toDataURL("image/png");
    sctx.shadowColor = tema === "claro" ? "rgba(60,0,10,0.95)" : "rgba(20,20,30,0.85)";
    sctx.shadowBlur = Math.max(3, lienzo.width / 150);
    sctx.drawImage(lienzo, 0, 0);
    sctx.drawImage(lienzo, 0, 0);
    return salida.toDataURL("image/png");
  } catch {
    return imagen;
  }
}
