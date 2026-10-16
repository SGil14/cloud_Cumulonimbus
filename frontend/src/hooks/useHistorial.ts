import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { HistorialDestino, Periodo, RankingHistorial, SerieHistorial } from "../lib/types";

export type Alcance =
  | { tipo: "bogota" }
  | { tipo: "localidad"; nombre: string }
  | { tipo: "destino"; lat: number; lon: number };

interface Estado {
  serie: SerieHistorial | null;
  ranking: RankingHistorial | null;
  destino: HistorialDestino | null;
  cargando: boolean;
  error: string | null;
}

/** Pide el historial cada vez que cambia el periodo o el alcance, descartando respuestas viejas. */
export function useHistorial(periodo: Periodo, alcance: Alcance, activo: boolean) {
  const [estado, setEstado] = useState<Estado>({ serie: null, ranking: null, destino: null, cargando: true, error: null });
  const clave = alcance.tipo === "localidad" ? alcance.nombre : alcance.tipo === "destino" ? `${alcance.lat},${alcance.lon}` : "";

  useEffect(() => {
    if (!activo) return;
    const control = new AbortController();
    setEstado((e) => ({ ...e, cargando: true, error: null }));

    const cargar = async () => {
      try {
        if (alcance.tipo === "destino") {
          const destino = await api.historialDestino(alcance.lat, alcance.lon, periodo, control.signal);
          setEstado({ serie: null, ranking: null, destino, cargando: false, error: null });
        } else {
          const [serie, ranking] = await Promise.all([
            api.historialSerie(periodo, alcance.tipo === "localidad" ? alcance.nombre : null, control.signal),
            api.historialRanking(periodo, control.signal),
          ]);
          setEstado({ serie, ranking, destino: null, cargando: false, error: null });
        }
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setEstado((s) => ({ ...s, cargando: false, error: e instanceof Error ? e.message : "No se pudo cargar el historial." }));
      }
    };
    void cargar();
    return () => control.abort();
    // `alcance` se resume en `tipo` y `clave`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodo, alcance.tipo, clave, activo]);

  return estado;
}
