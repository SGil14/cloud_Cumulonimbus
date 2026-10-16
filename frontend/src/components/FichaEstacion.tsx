import { ETIQUETA_INTENSIDAD, ETIQUETA_NIVEL, hora, mm, nombreLocalidad } from "../lib/format";
import type { Estacion } from "../lib/types";

interface Props {
  estacion: Estacion;
  onCerrar: () => void;
}

export function FichaEstacion({ estacion: e, onCerrar }: Props) {
  return (
    <section className="ficha" aria-label={`Estación ${e.nombre}`}>
      <button className="cerrar" onClick={onCerrar} aria-label="Cerrar estación">×</button>
      <p className="etiqueta">Estación · {nombreLocalidad(e.localidad)}</p>
      <p className="ficha__nombre">{e.nombre}</p>
      <dl className="ficha__datos">
        <div>
          <dt>Ahora</dt>
          <dd>{e.desactualizada ? "sin lectura reciente" : e.lloviendo ? ETIQUETA_INTENSIDAD[e.intensidad] : "seca"}</dd>
        </div>
        <div>
          <dt>Intensidad</dt>
          <dd>{mm(e.mm_hora)} <small>mm/h</small></dd>
        </div>
        <div>
          <dt>Acumulado hoy</dt>
          <dd>{mm(e.acumulado_dia)} <small>mm · {ETIQUETA_NIVEL[e.nivel_acumulado]}</small></dd>
        </div>
        <div>
          <dt>Última lectura</dt>
          <dd>{hora(e.fecha_lectura)}</dd>
        </div>
      </dl>
    </section>
  );
}
