import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Prediccion } from "../lib/types";

interface Estado {
  prediccion: Prediccion | null;
  cargando: boolean;
  error: string | null;
}

/** Pide la predicción de lluvia de la próxima hora para un punto, descartando respuestas viejas. */
export function usePrediccion(lat: number, lon: number) {
  const [estado, setEstado] = useState<Estado>({ prediccion: null, cargando: true, error: null });
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    const control = new AbortController();
    setEstado({ prediccion: null, cargando: true, error: null });
    api.prediccion(lat, lon, control.signal)
      .then((prediccion) => setEstado({ prediccion, cargando: false, error: null }))
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setEstado({ prediccion: null, cargando: false, error: e instanceof Error ? e.message : "No se pudo calcular la predicción." });
      });
    return () => control.abort();
  }, [lat, lon, intento]);

  const reintentar = useCallback(() => setIntento((n) => n + 1), []);
  return { ...estado, reintentar };
}
