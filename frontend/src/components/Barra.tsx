import type { Tema } from "../hooks/useTema";

interface Props {
  tema: Tema;
  cargando: boolean;
  radarDisponible: boolean;
  radarActivo: boolean;
  nombreDiseno: string;
  onActualizar: () => void;
  onAlternarTema: () => void;
  onAlternarRadar: () => void;
  onCambiarDiseno: () => void;
  onAbrirHistorial: () => void;
}

export function Barra({
  tema, cargando, radarDisponible, radarActivo, nombreDiseno,
  onActualizar, onAlternarTema, onAlternarRadar, onCambiarDiseno, onAbrirHistorial,
}: Props) {
  return (
    <nav className="barra" aria-label="Aplicación">
      <h1 className="marca">
        <svg viewBox="0 0 32 32" width="26" height="26" aria-hidden>
          <circle cx="16" cy="16" r="3.2" className="marca__nucleo" />
          <circle cx="16" cy="16" r="8" className="marca__anillo" />
          <circle cx="16" cy="16" r="13" className="marca__anillo marca__anillo--2" />
        </svg>
        <span>Cumulonimbus<em>·BOG</em></span>
      </h1>
      <div className="barra__acciones">
        {radarDisponible && (
          <button
            type="button"
            className={"boton" + (radarActivo ? " boton--activo" : "")}
            onClick={onAlternarRadar}
            aria-pressed={radarActivo}
            title="Radar del IDIGER (lluvia en el aire, puede no llegar al suelo). Solo muestra ecos moderados o fuertes."
          >
            <span className="boton__icono" aria-hidden>☁</span>
            <span className="boton__texto">Radar</span>
          </button>
        )}
        <button type="button" className="boton" onClick={onAbrirHistorial} title="Cuánto ha llovido: por horas, días y localidades">
          <span className="boton__icono" aria-hidden>▤</span>
          <span className="boton__texto">Historial</span>
        </button>
        <button type="button" className="boton" onClick={onCambiarDiseno} title="Cambiar de diseño (mientras eliges el definitivo)">
          <span className="boton__icono" aria-hidden>◐</span>
          <span className="boton__texto">Diseño: {nombreDiseno}</span>
        </button>
        <button type="button" className="boton" onClick={onActualizar} disabled={cargando}>
          <span className={cargando ? "giro" : "boton__icono"} aria-hidden>{cargando ? "" : "↻"}</span>
          <span className="boton__texto">{cargando ? "Leyendo…" : "Actualizar"}</span>
        </button>
        <button
          type="button"
          className="boton boton--icono"
          onClick={onAlternarTema}
          aria-label={tema === "oscuro" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
          title={tema === "oscuro" ? "Tema claro" : "Tema oscuro"}
        >
          <span aria-hidden>{tema === "oscuro" ? "☀" : "☾"}</span>
        </button>
      </div>
    </nav>
  );
}
