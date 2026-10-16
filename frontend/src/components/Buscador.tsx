import { useState, type FormEvent } from "react";

interface Props {
  buscando: boolean;
  onBuscar: (texto: string) => void;
  valorExterno: string;
}

const EJEMPLOS = ["Portal 80", "Calle 72 con Carrera 10", "Chapinero", "Carrera 7 # 55-25"];

export function Buscador({ buscando, onBuscar, valorExterno }: Props) {
  const [texto, setTexto] = useState("");
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
