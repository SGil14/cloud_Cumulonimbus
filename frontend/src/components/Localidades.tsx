import { useState } from "react";
import { ACUMULADO_REFERENCIA, ETIQUETA_NIVEL, mm, nombreLocalidad } from "../lib/format";
import type { LocalidadResumen } from "../lib/types";

interface Props {
  localidades: LocalidadResumen[];
  onElegir: (nombre: string) => void;
}

/** Ranking de localidades por lo que ha llovido hoy. Tocar una consulta sus estaciones. */
export function Localidades({ localidades, onElegir }: Props) {
  // Solo el diseño minimalista pliega la lista (los demás la muestran siempre y ocultan este botón).
  const [abierta, setAbierta] = useState(false);
  return (
    <section className="localidades" data-abierta={abierta} aria-label="Acumulado de lluvia de hoy por localidad">
      <button type="button" className="loc-toggle" onClick={() => setAbierta((a) => !a)} aria-expanded={abierta}>
        {abierta ? "Ocultar localidades" : "Ver localidades"} <span aria-hidden>{abierta ? "▾" : "▴"}</span>
      </button>
      <p className="etiqueta">Lo que ha llovido hoy · mm</p>
      <ol>
        {localidades.map((l) => (
          <li key={l.localidad}>
            <button type="button" onClick={() => onElegir(l.localidad)} className={"loc" + (l.lloviendo ? " loc--on" : "")}>
              <span className="loc__nombre">
                {l.lloviendo && <span className="loc__pulso" aria-label="Está lloviendo" />}
                {nombreLocalidad(l.localidad)}
              </span>
              <span className="loc__valor">{mm(l.acumulado_max)}</span>
              <span className="loc__barra" data-nivel={l.nivel_acumulado} title={`Nivel ${ETIQUETA_NIVEL[l.nivel_acumulado]}`}>
                <span style={{ width: `${Math.min(100, (l.acumulado_max / ACUMULADO_REFERENCIA) * 100)}%` }} />
              </span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
