import { useState, type FormEvent } from "react";
import { ETIQUETA_INTENSIDAD } from "../lib/format";
import type { ModoRuta, RutaRespuesta } from "../lib/types";

interface Props {
  ruta: RutaRespuesta | null;
  cargando: boolean;
  error: string | null;
  /** Último destino buscado: sirve para rellenar el «Hasta». */
  destinoSugerido: string;
  onCalcular: (origen: string, destino: string, modo: ModoRuta) => void;
  onLimpiar: () => void;
}

const MODOS: { id: ModoRuta; etiqueta: string }[] = [
  { id: "auto", etiqueta: "Carro / moto" },
  { id: "bus", etiqueta: "Bus" },
  { id: "bicicleta", etiqueta: "Bici" },
  { id: "a_pie", etiqueta: "A pie" },
];

const km = (n: number) => n.toLocaleString("es-CO", { maximumFractionDigits: 1 });

function duracion(min: number): string {
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  return `${h} h ${String(min % 60).padStart(2, "0")} min`;
}

/** Revisa si llueve a lo largo del camino de un lugar a otro. */
export function RutaPanel({ ruta, cargando, error, destinoSugerido, onCalcular, onLimpiar }: Props) {
  const [abierta, setAbierta] = useState(false);
  const [origen, setOrigen] = useState("");
  const [destino, setDestino] = useState("");
  const [modo, setModo] = useState<ModoRuta>("auto");
  const [sugeridoPrevio, setSugeridoPrevio] = useState(destinoSugerido);
  if (destinoSugerido !== sugeridoPrevio) {
    setSugeridoPrevio(destinoSugerido);
    if (!destino) setDestino(destinoSugerido);
  }

  // Al recibir una ruta calculada, el formulario se pliega para que el resultado quede a la vista.
  const [rutaPrevia, setRutaPrevia] = useState(ruta);
  if (ruta !== rutaPrevia) {
    setRutaPrevia(ruta);
    if (ruta?.encontrado) setAbierta(false);
  }

  const puedeEnviar = origen.trim().length >= 2 && destino.trim().length >= 2 && !cargando;
  const enviar = (e: FormEvent) => {
    e.preventDefault();
    if (puedeEnviar) onCalcular(origen.trim(), destino.trim(), modo);
  };

  const conLluvia = ruta?.encontrado ? ruta.tramos.filter((t) => t.estado === "lluvia") : [];
  const titulo = !ruta?.encontrado
    ? "No pude calcular la ruta"
    : ruta.hay_lluvia
      ? "Hay lluvia en tu ruta"
      : ruta.porcentaje_sin_datos >= 30
        ? "No se puede asegurar"
        : "Ruta sin lluvia";

  return (
    <section className="ruta" aria-label="Lluvia en una ruta">
      <button type="button" className="ruta-toggle" onClick={() => setAbierta((a) => !a)} aria-expanded={abierta}>
        <span aria-hidden>↝</span> {abierta ? "Ocultar el formulario" : ruta ? "Cambiar la ruta" : "¿Vas de un lugar a otro? Revisa la ruta"}
      </button>

      {abierta && (
        <form className="ruta-form" onSubmit={enviar}>
          <label>
            <span className="ruta-etiqueta">Desde</span>
            <input value={origen} onChange={(e) => setOrigen(e.target.value)} placeholder="Barrio, lugar o dirección" autoComplete="off" maxLength={200} />
          </label>
          <label>
            <span className="ruta-etiqueta">Hasta</span>
            <input value={destino} onChange={(e) => setDestino(e.target.value)} placeholder="Barrio, lugar o dirección" autoComplete="off" maxLength={200} />
          </label>
          <div className="ruta-modos" role="group" aria-label="Cómo te mueves">
            {MODOS.map((m) => (
              <button key={m.id} type="button" aria-pressed={m.id === modo} className={"ruta-modo" + (m.id === modo ? " ruta-modo--on" : "")} onClick={() => setModo(m.id)}>
                {m.etiqueta}
              </button>
            ))}
          </div>
          <button type="submit" className="ruta-ir" disabled={!puedeEnviar}>
            {cargando ? "Calculando…" : "Ver lluvia en el trayecto"}
          </button>
        </form>
      )}

      {error && <p className="ruta-error" role="alert">{error}</p>}

      {ruta && (
        <article className={"ruta-card" + (ruta.encontrado && ruta.hay_lluvia ? " ruta-card--lluvia" : "")} role="status">
          <button type="button" className="ruta-cerrar" onClick={onLimpiar} aria-label="Quitar la ruta">×</button>
          {ruta.encontrado && (
            <p className="ruta-meta">{km(ruta.distancia_km)} km · {duracion(ruta.duracion_min)} · {MODOS.find((m) => m.id === ruta.modo)?.etiqueta}</p>
          )}
          <p className="ruta-titulo">{titulo}</p>
          <p className="ruta-texto">{ruta.encontrado ? ruta.resumen : ruta.mensaje}</p>

          {ruta.encontrado && (
            <>
              <div className="ruta-barra" role="img" aria-label="Estado de la lluvia a lo largo del trayecto, de principio a fin">
                {ruta.tramos.map((t, i) => (
                  <span key={i} data-estado={t.estado} style={{ flexGrow: Math.max(0.2, t.hasta_km - t.desde_km) }} title={`km ${km(t.desde_km)}–${km(t.hasta_km)}`} />
                ))}
              </div>
              <p className="ruta-ejes"><span>Salida</span><span>Llegada</span></p>
              <ul className="ruta-tramos">
                {conLluvia.map((t, i) => (
                  <li key={i}>
                    <b>km {km(t.desde_km)} – {km(t.hasta_km)}</b> · {t.intensidad ? ETIQUETA_INTENSIDAD[t.intensidad] : "lluvia"}
                    {t.estacion ? ` · cerca de ${t.estacion}` : ""}
                  </li>
                ))}
              </ul>
              <p className="ruta-nota">{ruta.nota}</p>
            </>
          )}
        </article>
      )}
    </section>
  );
}
