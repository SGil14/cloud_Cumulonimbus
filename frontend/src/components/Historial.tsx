import { useEffect, useMemo, useRef, useState } from "react";
import { useHistorial, type Alcance } from "../hooks/useHistorial";
import { fechaCorta, hora, mm, nombreLocalidad } from "../lib/format";
import type { Destino, Periodo, SerieHistorial } from "../lib/types";
import { GraficoBarras } from "./GraficoBarras";

interface Props {
  localidades: string[];
  destino: Destino | null;
  /** Si viene, el historial abre mostrando «cerca de tu destino». */
  abrirEnDestino: boolean;
  onCerrar: () => void;
}

const PERIODOS: { id: Periodo; etiqueta: string; titulo: string }[] = [
  { id: "6h", etiqueta: "6 horas", titulo: "las últimas 6 horas" },
  { id: "24h", etiqueta: "24 horas", titulo: "las últimas 24 horas" },
  { id: "7d", etiqueta: "7 días", titulo: "los últimos 7 días" },
  { id: "30d", etiqueta: "30 días", titulo: "los últimos 30 días" },
];

function notaDeCobertura(serie: SerieHistorial): string[] {
  const notas: string[] = [];
  if (serie.datos_desde) {
    notas.push(`Hay registros desde el ${fechaCorta(serie.datos_desde).toLowerCase()} a las ${hora(serie.datos_desde)}.`);
  }
  if (serie.cobertura_pct < 60) {
    notas.push("Aún hay pocos datos para este periodo: la app solo guarda lecturas mientras está encendida.");
  }
  if (serie.paso === "dia") {
    notas.push("El total de cada día incluye la lluvia caída antes del primer registro.");
  }
  return notas;
}

/** Pantalla de historial: cuánto llovió, cuándo y dónde, a partir de las lecturas guardadas. */
export function Historial({ localidades, destino, abrirEnDestino, onCerrar }: Props) {
  const coords = destino?.encontrado && destino.ubicacion ? destino.ubicacion : null;
  const [periodo, setPeriodo] = useState<Periodo>("24h");
  const [alcance, setAlcance] = useState<Alcance>(
    abrirEnDestino && coords ? { tipo: "destino", lat: coords.latitud, lon: coords.longitud } : { tipo: "bogota" },
  );
  const [estacionElegida, setEstacionElegida] = useState(0);
  const { serie, ranking, destino: porDestino, cargando, error } = useHistorial(periodo, alcance, true);
  const botonCerrar = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    botonCerrar.current?.focus();
    const alTeclear = (e: KeyboardEvent) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [onCerrar]);

  const nombresOrdenados = useMemo(
    () => [...localidades].sort((a, b) => nombreLocalidad(a).localeCompare(nombreLocalidad(b), "es")),
    [localidades],
  );
  const valorSelector = alcance.tipo === "localidad" ? `l:${alcance.nombre}` : alcance.tipo;
  const cambiarAlcance = (valor: string) => {
    setEstacionElegida(0);
    if (valor === "bogota") setAlcance({ tipo: "bogota" });
    else if (valor === "destino" && coords) setAlcance({ tipo: "destino", lat: coords.latitud, lon: coords.longitud });
    else if (valor.startsWith("l:")) setAlcance({ tipo: "localidad", nombre: valor.slice(2) });
  };

  const estacion = porDestino?.estaciones[Math.min(estacionElegida, (porDestino?.estaciones.length ?? 1) - 1)];
  const serieActual = alcance.tipo === "destino" ? estacion?.serie : serie;
  const tituloPeriodo = PERIODOS.find((p) => p.id === periodo)?.titulo ?? "";
  const maxRanking = Math.max(0.01, ...(ranking?.items.map((i) => i.total_mm) ?? [0]));

  return (
    <div className="hist-fondo" onClick={onCerrar}>
      <section className="hist" role="dialog" aria-modal="true" aria-labelledby="hist-titulo" onClick={(e) => e.stopPropagation()}>
        <header className="hist__cabecera">
          <div>
            <p className="hist__etiqueta">Lo que ya pasó</p>
            <h2 id="hist-titulo">Historial de lluvia</h2>
          </div>
          <button ref={botonCerrar} type="button" className="hist__cerrar" onClick={onCerrar} aria-label="Cerrar historial">×</button>
        </header>

        <div className="hist__controles">
          <div className="hist__chips" role="group" aria-label="Periodo">
            {PERIODOS.map((p) => (
              <button key={p.id} type="button" aria-pressed={p.id === periodo} className={"hist__chip" + (p.id === periodo ? " hist__chip--on" : "")} onClick={() => setPeriodo(p.id)}>
                {p.etiqueta}
              </button>
            ))}
          </div>
          <label className="hist__selector">
            <span className="hist__etiqueta">Dónde</span>
            <select value={valorSelector} onChange={(e) => cambiarAlcance(e.target.value)}>
              <option value="bogota">Toda Bogotá</option>
              {coords && <option value="destino">Cerca de tu destino{destino ? ` · ${destino.texto}` : ""}</option>}
              <optgroup label="Localidad">
                {nombresOrdenados.map((l) => <option key={l} value={`l:${l}`}>{nombreLocalidad(l)}</option>)}
              </optgroup>
            </select>
          </label>
        </div>

        {alcance.tipo === "destino" && porDestino && (
          <div className="hist__chips" role="group" aria-label="Estación cercana">
            {porDestino.estaciones.map((e, i) => (
              <button key={e.id_sensor} type="button" aria-pressed={i === estacionElegida} className={"hist__chip" + (i === estacionElegida ? " hist__chip--on" : "")} onClick={() => setEstacionElegida(i)}>
                {e.nombre} · {e.distancia_km.toLocaleString("es-CO", { maximumFractionDigits: 1 })} km
              </button>
            ))}
          </div>
        )}

        {error && <p className="hist__error" role="alert">{error}</p>}

        {serieActual && (
          <div className={"hist__cuerpo" + (cargando ? " hist__cuerpo--cargando" : "")} aria-busy={cargando}>
            <dl className="hist__kpis">
              <div>
                <dt>Llovió en total</dt>
                <dd>{mm(serieActual.total_mm)} <small>mm</small></dd>
              </div>
              <div>
                <dt>{serieActual.paso === "hora" ? "Hora más lluviosa" : "Día más lluvioso"}</dt>
                <dd>
                  {serieActual.pico
                    ? <>{serieActual.paso === "hora" ? hora(serieActual.pico.inicio) : fechaCorta(serieActual.pico.inicio)} <small>{mm(serieActual.pico.mm ?? 0)} mm</small></>
                    : <small>sin lluvia</small>}
                </dd>
              </div>
              <div>
                <dt>Datos disponibles</dt>
                <dd>{serieActual.cobertura_pct}<small>%</small></dd>
              </div>
            </dl>

            <p className="hist__subtitulo">
              {serieActual.etiqueta} · {tituloPeriodo}
              {alcance.tipo !== "destino" && serieActual.estaciones > 0 && <span> · promedio de {serieActual.estaciones} estaciones</span>}
            </p>
            <GraficoBarras
              puntos={serieActual.puntos}
              paso={serieActual.paso}
              descripcion={`Lluvia por ${serieActual.paso === "hora" ? "hora" : "día"} en ${serieActual.etiqueta}, ${tituloPeriodo}`}
            />
            <ul className="hist__notas">
              {notaDeCobertura(serieActual).map((n) => <li key={n}>{n}</li>)}
            </ul>
          </div>
        )}

        {!serieActual && cargando && <p className="hist__vacio">Leyendo el historial…</p>}
        {alcance.tipo === "destino" && porDestino && porDestino.estaciones.length === 0 && (
          <p className="hist__vacio">No encontré estaciones cerca de ese destino.</p>
        )}

        {alcance.tipo !== "destino" && ranking && ranking.items.length > 0 && (
          <section className="hist__ranking" aria-label={`Localidades más lluviosas, ${tituloPeriodo}`}>
            <p className="hist__subtitulo">Localidades más lluviosas · {tituloPeriodo}</p>
            <ol>
              {ranking.items.map((i) => (
                <li key={i.localidad}>
                  <button type="button" onClick={() => cambiarAlcance(`l:${i.localidad}`)} className="hist__fila">
                    <span className="hist__fila-nombre">{nombreLocalidad(i.localidad)}</span>
                    <span className="hist__fila-valor">{mm(i.total_mm)} mm</span>
                    <span className="hist__fila-barra"><span style={{ width: `${(i.total_mm / maxRanking) * 100}%` }} /></span>
                  </button>
                </li>
              ))}
            </ol>
          </section>
        )}
      </section>
    </div>
  );
}
