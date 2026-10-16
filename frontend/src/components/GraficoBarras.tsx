import { useMemo, useRef, useState } from "react";
import { diaCorto, hora, horaCorta, mm as formatoMm } from "../lib/format";
import type { PuntoHistorial } from "../lib/types";

interface Props {
  puntos: PuntoHistorial[];
  paso: "hora" | "dia";
  /** Frase para lectores de pantalla, p. ej. «Lluvia por hora en Suba». */
  descripcion: string;
}

const ANCHO = 640;
const ALTO = 250;
const MARGEN = { izq: 42, der: 8, arriba: 14, abajo: 30 };
const PASOS_TECHO = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500];

/** Tope «redondo» para el eje vertical, para que las marcas queden en números cómodos. */
function techoBonito(maximo: number): number {
  if (maximo <= 0) return 1;
  return PASOS_TECHO.find((p) => p >= maximo) ?? Math.ceil(maximo / 100) * 100;
}

function etiquetaInicio(p: PuntoHistorial, paso: "hora" | "dia"): string {
  return paso === "hora" ? hora(p.inicio) : diaCorto(p.inicio);
}

/** Barras de lluvia por intervalo. Pasar el dedo o el mouse por encima muestra el detalle de cada barra. */
export function GraficoBarras({ puntos, paso, descripcion }: Props) {
  const [activo, setActivo] = useState<number | null>(null);
  const svg = useRef<SVGSVGElement>(null);

  const { techo, ancho, indicePico } = useMemo(() => {
    const maximo = Math.max(0, ...puntos.map((p) => p.mm ?? 0));
    const pico = maximo > 0 ? puntos.findIndex((p) => p.mm === maximo) : -1;
    return { techo: techoBonito(maximo), ancho: (ANCHO - MARGEN.izq - MARGEN.der) / Math.max(1, puntos.length), indicePico: pico };
  }, [puntos]);

  const altoUtil = ALTO - MARGEN.arriba - MARGEN.abajo;
  const cadaCuanto = Math.ceil(puntos.length / (paso === "hora" ? 8 : 7));
  const mostrado = activo ?? (indicePico >= 0 ? indicePico : null);
  const p = mostrado !== null ? puntos[mostrado] : null;

  const alMover = (e: React.PointerEvent) => {
    const caja = svg.current?.getBoundingClientRect();
    if (!caja) return;
    const x = ((e.clientX - caja.left) / caja.width) * ANCHO - MARGEN.izq;
    const i = Math.floor(x / ancho);
    setActivo(i >= 0 && i < puntos.length ? i : null);
  };

  return (
    <figure className="grafico">
      <p className="grafico__lectura" aria-live="polite">
        {p ? (
          <>
            <b>{etiquetaInicio(p, paso)}</b>
            {p.mm === null ? " · sin datos" : ` · ${formatoMm(p.mm)} mm`}
            {p.mm !== null && ` · ${p.lecturas} lecturas`}
          </>
        ) : (
          "Sin lluvia en este periodo"
        )}
      </p>
      <svg
        ref={svg}
        viewBox={`0 0 ${ANCHO} ${ALTO}`}
        role="img"
        aria-label={descripcion}
        onPointerMove={alMover}
        onPointerDown={alMover}
        onPointerLeave={() => setActivo(null)}
      >
        {[0, 0.5, 1].map((f) => {
          const y = MARGEN.arriba + altoUtil * (1 - f);
          return (
            <g key={f}>
              <line className="grafico__guia" x1={MARGEN.izq} x2={ANCHO - MARGEN.der} y1={y} y2={y} />
              <text className="grafico__eje" x={MARGEN.izq - 6} y={y + 4} textAnchor="end">{techo < 1 ? (techo * f).toLocaleString("es-CO", { maximumFractionDigits: 2 }) : formatoMm(techo * f)}</text>
            </g>
          );
        })}

        {puntos.map((punto, i) => {
          const x = MARGEN.izq + i * ancho;
          const barra = ancho * 0.72;
          const xBarra = x + (ancho - barra) / 2;
          if (punto.mm === null) {
            // Sin datos: una marca tenue en la base, para distinguirlo de «no llovió».
            return <line key={i} className="grafico__sin" x1={xBarra} x2={xBarra + barra} y1={MARGEN.arriba + altoUtil - 3} y2={MARGEN.arriba + altoUtil - 3} />;
          }
          const alto = punto.mm > 0 ? Math.max(2, (punto.mm / techo) * altoUtil) : 0;
          return (
            <g key={i}>
              {alto > 0 && (
                <rect
                  className={"grafico__barra" + (i === mostrado ? " grafico__barra--activa" : "")}
                  x={xBarra} y={MARGEN.arriba + altoUtil - alto} width={barra} height={alto} rx={Math.min(3, barra / 2)}
                />
              )}
              {alto === 0 && <line className="grafico__cero" x1={xBarra} x2={xBarra + barra} y1={MARGEN.arriba + altoUtil - 1} y2={MARGEN.arriba + altoUtil - 1} />}
            </g>
          );
        })}

        {puntos.map((punto, i) =>
          i % cadaCuanto === 0 ? (
            <text key={i} className="grafico__eje" x={MARGEN.izq + i * ancho + ancho / 2} y={ALTO - 9} textAnchor="middle">
              {paso === "hora" ? horaCorta(punto.inicio) : diaCorto(punto.inicio)}
            </text>
          ) : null,
        )}
      </svg>
      <figcaption className="grafico__leyenda">
        <span><i className="grafico__muestra grafico__muestra--lluvia" /> mm que llovieron</span>
        <span><i className="grafico__muestra grafico__muestra--sin" /> sin datos (no se registró)</span>
      </figcaption>
    </figure>
  );
}
