import { fechaCorta, hora, nombreLocalidad } from "../lib/format";
import type { Resumen } from "../lib/types";

interface Props {
  resumen: Resumen | null;
  cargando: boolean;
}

/** Sol cuando está seco, nube con gotas cuando llueve. Algunos diseños lo ocultan. */
function Icono({ llueve }: { llueve: boolean }) {
  return (
    <span className="titular__icono" aria-hidden>
      {llueve ? (
        <svg viewBox="0 0 64 64" className="icono-nube">
          <path d="M18 40a11 11 0 0 1 1.5-21.9A14 14 0 0 1 46.6 22 9.5 9.5 0 0 1 46 40Z" />
          <line x1="22" y1="46" x2="19" y2="54" />
          <line x1="32" y1="46" x2="29" y2="54" />
          <line x1="42" y1="46" x2="39" y2="54" />
        </svg>
      ) : (
        <svg viewBox="0 0 64 64" className="icono-sol">
          <circle cx="32" cy="32" r="11" />
          {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
            <line key={a} x1="32" y1="12" x2="32" y2="7" transform={`rotate(${a} 32 32)`} />
          ))}
        </svg>
      )}
    </span>
  );
}

/** El dato principal, en grande: cuántas estaciones registran lluvia ahora. */
export function Titular({ resumen, cargando }: Props) {
  if (!resumen) {
    return (
      <header className="titular" aria-busy={cargando}>
        <p className="etiqueta">{cargando ? "Leyendo estaciones…" : "Sin datos"}</p>
        <p className="titular__cifra titular__cifra--vacia">— —</p>
      </header>
    );
  }

  const llueve = resumen.estaciones_lloviendo > 0;
  const localidades = resumen.localidades_lloviendo.map(nombreLocalidad);

  return (
    <header className="titular" aria-live="polite">
      <Icono llueve={llueve} />
      <p className="etiqueta">
        Ahora · {fechaCorta(resumen.datos_obtenidos_en)} · {hora(resumen.datos_obtenidos_en)}
      </p>

      {llueve ? (
        <>
          <p className="titular__cifra">
            <span className="titular__n">{resumen.estaciones_lloviendo}</span>
            <span className="titular__de"> de {resumen.total_estaciones}</span>
          </p>
          <p className="titular__texto">
            {resumen.estaciones_lloviendo === 1 ? "estación registra lluvia" : "estaciones registran lluvia"}
          </p>
          <ul className="chips" aria-label="Localidades con lluvia">
            {localidades.map((l) => (
              <li key={l} className="chip chip--lluvia">{l}</li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <p className="titular__cifra titular__cifra--seca">
            Bogotá{" "}<br />está seca.
          </p>
          <p className="titular__texto">
            Ninguna de las {resumen.total_estaciones} estaciones registra lluvia en este momento.
          </p>
        </>
      )}
    </header>
  );
}
