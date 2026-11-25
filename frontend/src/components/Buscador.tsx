import { useState, type FormEvent } from "react";
import type { Favorito } from "../lib/types";

interface Props {
  buscando: boolean;
  onBuscar: (texto: string) => void;
  valorExterno: string;
  /** Destinos guardados del usuario con sesión (vacío si no hay sesión). */
  favoritos: Favorito[];
  sesionActiva: boolean;
  onGuardarFavorito: (texto: string) => Promise<void>;
  onBorrarFavorito: (id: number) => Promise<void>;
}

const EJEMPLOS = ["Portal 80", "Calle 72 con Carrera 10", "Chapinero", "Carrera 7 # 55-25"];

export function Buscador({ buscando, onBuscar, valorExterno, favoritos, sesionActiva, onGuardarFavorito, onBorrarFavorito }: Props) {
  const [texto, setTexto] = useState("");
  const [errorFavorito, setErrorFavorito] = useState<string | null>(null);
  // Si otra parte de la app dispara una búsqueda (p. ej. tocar una localidad), se refleja aquí.
  const [previo, setPrevio] = useState(valorExterno);
  if (valorExterno !== previo) {
    setPrevio(valorExterno);
    setTexto(valorExterno);
  }

  const enviar = (e: FormEvent) => {
    e.preventDefault();
    const limpio = texto.trim();
    if (limpio.length >= 2) onBuscar(limpio);
  };

  const limpio = texto.trim();
  const yaGuardado = favoritos.some((f) => f.texto.toLowerCase() === limpio.toLowerCase());
  const intentar = async (accion: () => Promise<void>) => {
    setErrorFavorito(null);
    try { await accion(); } catch (e) { setErrorFavorito(e instanceof Error ? e.message : "No se pudo completar."); }
  };

  return (
    <section className="buscador" aria-label="Buscar un destino">
      <form onSubmit={enviar} role="search">
        <label htmlFor="destino" className="etiqueta">¿A dónde vas?</label>
        <div className="buscador__campo">
          <input
            id="destino"
            type="search"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Barrio, lugar o dirección"
            autoComplete="off"
            enterKeyHint="search"
            maxLength={200}
          />
          <button type="submit" disabled={buscando || texto.trim().length < 2} aria-label="Consultar la lluvia en ese destino">
            {buscando ? <span className="giro" aria-hidden /> : <span aria-hidden>→</span>}
          </button>
        </div>
      </form>
      {sesionActiva && limpio.length >= 2 && !yaGuardado && (
        <button type="button" className="fav-guardar" onClick={() => intentar(() => onGuardarFavorito(limpio))}>
          ☆ Guardar «{limpio.length > 28 ? limpio.slice(0, 28) + "…" : limpio}» en mis favoritos
        </button>
      )}
      {errorFavorito && <p className="cuenta__error" role="alert">{errorFavorito}</p>}
      {favoritos.length > 0 && (
        <>
          <p className="fav-titulo">Mis favoritos</p>
          <ul className="chips chips--favoritos" aria-label="Mis favoritos">
            {favoritos.map((f) => (
              <li key={f.id} className="fav">
                <button type="button" className="chip chip--boton" onClick={() => { setTexto(f.texto); onBuscar(f.texto); }}>
                  ★ {f.nombre}
                </button>
                <button type="button" className="fav__borrar" aria-label={`Quitar ${f.nombre} de favoritos`} onClick={() => intentar(() => onBorrarFavorito(f.id))}>×</button>
              </li>
            ))}
          </ul>
        </>
      )}
      <ul className="chips chips--ejemplos" aria-label="Ejemplos">
        {EJEMPLOS.map((ej) => (
          <li key={ej}>
            <button type="button" className="chip chip--boton" onClick={() => { setTexto(ej); onBuscar(ej); }}>
              {ej}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
