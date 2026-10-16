import type {
  Destino, EstacionesRespuesta, HistorialDestino, LimitesLocalidades, ModoRuta, Periodo, Radar,
  RankingHistorial, Resumen, RutaRespuesta, SerieHistorial,
} from "./types";

export class ApiError extends Error {}

async function pedir<T>(ruta: string, senal?: AbortSignal): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(ruta, { signal: senal });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError("No hay conexión con el servidor.");
  }
  if (!resp.ok) {
    const cuerpo = await resp.json().catch(() => null);
    throw new ApiError(cuerpo?.detail ?? `Error ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  resumen: (actualizar = false) => pedir<Resumen>(`/api/resumen?actualizar=${actualizar}`),
  estaciones: (actualizar = false) => pedir<EstacionesRespuesta>(`/api/estaciones?actualizar=${actualizar}`),
  localidades: () => pedir<LimitesLocalidades>("/api/localidades"),
  radar: () => pedir<Radar>("/api/radar"),
  destino: (q: string) => pedir<Destino>(`/api/destino?q=${encodeURIComponent(q)}`),
  ruta: (origen: string, destino: string, modo: ModoRuta) =>
    pedir<RutaRespuesta>(`/api/ruta?origen=${encodeURIComponent(origen)}&destino=${encodeURIComponent(destino)}&modo=${modo}`),
  historialSerie: (periodo: Periodo, localidad: string | null, senal?: AbortSignal) =>
    pedir<SerieHistorial>(`/api/historial/serie?periodo=${periodo}${localidad ? `&localidad=${encodeURIComponent(localidad)}` : ""}`, senal),
  historialRanking: (periodo: Periodo, senal?: AbortSignal) =>
    pedir<RankingHistorial>(`/api/historial/ranking?periodo=${periodo}`, senal),
  historialDestino: (lat: number, lon: number, periodo: Periodo, senal?: AbortSignal) =>
    pedir<HistorialDestino>(`/api/historial/destino?lat=${lat}&lon=${lon}&periodo=${periodo}`, senal),
};
