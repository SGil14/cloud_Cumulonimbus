import type { Destino, Estacion, ModoRuta, Resumen, RutaRespuesta } from "../lib/types";
import { Buscador } from "./Buscador";
import { FichaEstacion } from "./FichaEstacion";
import { Localidades } from "./Localidades";
import { RutaPanel } from "./RutaPanel";
import { Titular } from "./Titular";
import { Veredicto } from "./Veredicto";
import { fechaCorta, hora } from "../lib/format";

interface Props {
  resumen: Resumen | null;
  cargando: boolean;
  destino: Destino | null;
  buscando: boolean;
  errorBusqueda: string | null;
  textoBusqueda: string;
  estacionSeleccionada: Estacion | null;
  abierto: boolean;
  esMovil: boolean;
  onAlternar: () => void;
  onBuscar: (texto: string) => void;
  onLimpiarDestino: () => void;
  onSeleccionarEstacion: (id: number | null) => void;
  onVerHistorial: () => void;
  ruta: RutaRespuesta | null;
  cargandoRuta: boolean;
  errorRuta: string | null;
  onCalcularRuta: (origen: string, destino: string, modo: ModoRuta) => void;
  onLimpiarRuta: () => void;
}

export function Panel(p: Props) {
  return (
    <aside className="panel" data-abierto={p.abierto} data-destino={p.destino !== null} data-lluvia={(p.resumen?.estaciones_lloviendo ?? 0) > 0} aria-label="Resumen de lluvia y búsqueda">
      {p.esMovil && (
        <button className="panel__asa" onClick={p.onAlternar} aria-expanded={p.abierto} aria-label={p.abierto ? "Reducir panel" : "Ampliar panel"}>
          <span />
        </button>
      )}

      <Titular resumen={p.resumen} cargando={p.cargando} />
      <Buscador buscando={p.buscando} onBuscar={p.onBuscar} valorExterno={p.textoBusqueda} />

      <RutaPanel
        ruta={p.ruta}
        cargando={p.cargandoRuta}
        error={p.errorRuta}
        destinoSugerido={p.textoBusqueda}
        onCalcular={p.onCalcularRuta}
        onLimpiar={p.onLimpiarRuta}
      />

      {p.errorBusqueda && <p className="error" role="alert">{p.errorBusqueda}</p>}

      {p.destino && <Veredicto destino={p.destino} onCerrar={p.onLimpiarDestino} onSeleccionar={p.onSeleccionarEstacion} onVerHistorial={p.onVerHistorial} />}
      {p.estacionSeleccionada && (
        <FichaEstacion estacion={p.estacionSeleccionada} onCerrar={() => p.onSeleccionarEstacion(null)} />
      )}

      {p.resumen && <Localidades localidades={p.resumen.localidades} onElegir={p.onBuscar} />}

      <footer className="pie">
        <p>
          Pluviómetros del <abbr title="Sistema de Alerta de Bogotá">SAB</abbr> · IDIGER.
          {p.resumen && <> Lectura de {fechaCorta(p.resumen.datos_obtenidos_en)}, {hora(p.resumen.datos_obtenidos_en)}.</>}
        </p>
        <p>Barrios y localidades: Catastro Bogotá. Lugares: © OpenStreetMap.</p>
      </footer>
    </aside>
  );
}
