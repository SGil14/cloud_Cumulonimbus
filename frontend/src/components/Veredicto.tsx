import { ETIQUETA_INTENSIDAD, km, mm, nombreLocalidad } from "../lib/format";
import type { Destino } from "../lib/types";

interface Props {
  destino: Destino;
  onCerrar: () => void;
  onSeleccionar: (id: number) => void;
  onVerHistorial: () => void;
}

/** La respuesta a «¿va a llover donde voy?», con las estaciones que la sustentan. */
export function Veredicto({ destino, onCerrar, onSeleccionar, onVerHistorial }: Props) {
  if (!destino.encontrado || !destino.cercania || !destino.ubicacion) {
    return (
      <section className="veredicto veredicto--vacio" role="status">
        <button className="cerrar" onClick={onCerrar} aria-label="Cerrar resultado">×</button>
        <p className="etiqueta">«{destino.texto}»</p>
        <p className="veredicto__titulo">Sin resultado</p>
        <p className="veredicto__sub">{destino.mensaje}</p>
      </section>
    );
  }

  const { ubicacion, cercania } = destino;
  const llueve = cercania.lloviendo_cerca;
  const lugar = [ubicacion.barrio, ubicacion.localidad && nombreLocalidad(ubicacion.localidad)].filter(Boolean).join(" · ");
  const masCercana = cercania.estaciones[0];

  return (
    <section className={"veredicto" + (llueve ? " veredicto--lluvia" : "")} role="status">
      <button className="cerrar" onClick={onCerrar} aria-label="Cerrar resultado">×</button>
      <p className="etiqueta">{lugar || destino.texto}</p>
      <p className="veredicto__titulo">{llueve ? "Sí, llueve cerca" : "No llueve cerca"}</p>
      <p className="veredicto__sub">
        {llueve
          ? "Hay lluvia activa en las estaciones más próximas a tu destino."
          : masCercana && masCercana.acumulado_dia > 0
            ? `Sin lluvia ahora, pero hoy cayeron ${mm(masCercana.acumulado_dia)} mm en la estación más cercana.`
            : "Ninguna estación cercana registra lluvia ahora."}
      </p>
      {ubicacion.aproximada && (
        <p className="aviso">Ubicación aproximada: no hallé el punto exacto, usé el más cercano sobre esa vía.</p>
      )}

      <button type="button" className="ver-historial" onClick={onVerHistorial}>
        Ver cuándo ha llovido aquí <span aria-hidden>→</span>
      </button>

      <ol className="cercanas">
        {cercania.estaciones.map((e) => (
          <li key={e.id_sensor}>
            <button type="button" onClick={() => onSeleccionar(e.id_sensor)} className={"cercana" + (e.lloviendo ? " cercana--on" : "")}>
              <span className="cercana__punto" aria-hidden />
              <span className="cercana__nombre">{e.nombre}</span>
              <span className="cercana__dist">{km(e.distancia_km)}</span>
              <span className="cercana__estado">
                {e.desactualizada ? "sin lectura reciente" : e.lloviendo ? `${ETIQUETA_INTENSIDAD[e.intensidad]} · ${mm(e.mm_hora)} mm/h` : "seca"}
                {" · hoy "}{mm(e.acumulado_dia)} mm
              </span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
