import { usePrediccion } from "../hooks/usePrediccion";

interface Props {
  lat: number;
  lon: number;
}

/** «¿Va a llover en la próxima hora?»: la estimación del modelo, o la regla simple si no hay datos para usarlo. */
export function PrediccionLluvia({ lat, lon }: Props) {
  const { prediccion, cargando, error, reintentar } = usePrediccion(lat, lon);

  if (cargando) {
    return (
      <section className="pred" aria-busy="true" aria-live="polite">
        <p className="pred__etiqueta">Próxima hora</p>
        <p className="pred__estado">Calculando la predicción…</p>
      </section>
    );
  }
  if (error || !prediccion) {
    return (
      <section className="pred pred--error" role="alert">
        <p className="pred__etiqueta">Próxima hora</p>
        <p className="pred__estado">No se pudo calcular la predicción. {error}</p>
        <button type="button" className="pred__reintentar" onClick={reintentar}>Reintentar</button>
      </section>
    );
  }

  const usaModelo = prediccion.metodo === "modelo" && prediccion.probabilidad !== null;
  const porcentaje = usaModelo ? Math.round((prediccion.probabilidad ?? 0) * 100) : null;

  return (
    <section className={"pred" + (prediccion.llovera_probable ? " pred--lluvia" : "")} aria-live="polite">
      <div className="pred__cabecera">
        <p className="pred__etiqueta">Próxima hora</p>
        <span className="pred__metodo" title={usaModelo ? "Calculada con el modelo de IA entrenado con lecturas del SAB" : "Regla simple: lo que pasa ahora seguirá igual"}>
          {usaModelo ? "Modelo de IA · experimental" : "Regla simple"}
        </span>
      </div>

      <p className="pred__titulo">{prediccion.llovera_probable ? "Es probable que llueva" : "Es poco probable que llueva"}</p>

      {porcentaje !== null && (
        <div className="pred__barra" role="img" aria-label={`Probabilidad de lluvia: ${porcentaje} por ciento`}>
          <div className="pred__relleno" style={{ width: `${Math.max(porcentaje, 2)}%` }} />
          <span className="pred__valor">{porcentaje} %</span>
        </div>
      )}

      <p className="pred__detalle">{prediccion.mensaje}</p>
      {prediccion.motivo_respaldo && <p className="pred__nota">{prediccion.motivo_respaldo}</p>}
      <p className="pred__nota">{prediccion.aviso}</p>
    </section>
  );
}
