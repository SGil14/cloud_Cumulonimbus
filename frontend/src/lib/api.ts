import type {
  Destino, EstacionesRespuesta, Favorito, HistorialDestino, LimitesLocalidades, ModoRuta, Periodo, Prediccion, Radar,
  RankingHistorial, Resumen, RutaRespuesta, SerieHistorial, Sesion, Usuario, UsuarioAdmin, EstadoSistema, Rol,
} from "./types";

export class ApiError extends Error {
  /** Código HTTP, si la respuesta llegó (401 = sin sesión o token vencido). */
  estado?: number;
  constructor(mensaje: string, estado?: number) {
    super(mensaje);
    this.estado = estado;
  }
}

interface Opciones {
  senal?: AbortSignal;
  metodo?: "GET" | "POST" | "PUT" | "DELETE";
  cuerpo?: unknown;
  token?: string;
}

async function pedir<T>(ruta: string, opciones: AbortSignal | Opciones = {}): Promise<T> {
  const o: Opciones = opciones instanceof AbortSignal ? { senal: opciones } : opciones;
  const cabeceras: Record<string, string> = {};
  if (o.cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
  if (o.token) cabeceras.Authorization = `Bearer ${o.token}`;
  let resp: Response;
  try {
    resp = await fetch(ruta, {
      method: o.metodo ?? "GET",
      headers: cabeceras,
      body: o.cuerpo === undefined ? undefined : JSON.stringify(o.cuerpo),
      signal: o.senal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError("No hay conexión con el servidor.");
  }
  if (!resp.ok) {
    const cuerpo = await resp.json().catch(() => null);
    throw new ApiError(mensajeDe(cuerpo?.detail, resp.status), resp.status);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

/** FastAPI responde `detail` como texto, o como lista cuando falla la validación de los datos. */
function mensajeDe(detalle: unknown, estado: number): string {
  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle) && detalle.length > 0) {
    const primero = detalle[0] as { msg?: string };
    return (primero.msg ?? "").replace(/^Value error, /, "") || `Datos no válidos (${estado}).`;
  }
  return `Error ${estado}`;
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
  prediccion: (lat: number, lon: number, senal?: AbortSignal) =>
    pedir<Prediccion>(`/api/prediccion?lat=${lat}&lon=${lon}`, senal),
  historialDestino: (lat: number, lon: number, periodo: Periodo, senal?: AbortSignal) =>
    pedir<HistorialDestino>(`/api/historial/destino?lat=${lat}&lon=${lon}&periodo=${periodo}`, senal),

  // --- cuenta y favoritos
  registro: (correo: string, clave: string) =>
    pedir<Usuario>("/api/auth/registro", { metodo: "POST", cuerpo: { correo, clave } }),
  login: (correo: string, clave: string) =>
    pedir<Sesion>("/api/auth/login", { metodo: "POST", cuerpo: { correo, clave } }),
  yo: (token: string) => pedir<Usuario>("/api/auth/yo", { token }),
  usuarios: (token: string) => pedir<UsuarioAdmin[]>("/api/admin/usuarios", { token }),
  estadoSistema: (token: string) => pedir<EstadoSistema>("/api/admin/estado", { token }),
  favoritosDe: (token: string, id: number) => pedir<Favorito[]>(`/api/admin/usuarios/${id}/favoritos`, { token }),
  cambiarRol: (token: string, id: number, rol: Rol) =>
    pedir<Usuario>(`/api/admin/usuarios/${id}/rol`, { metodo: "PUT", token, cuerpo: { rol } }),
  eliminarUsuario: (token: string, id: number) => pedir<void>(`/api/admin/usuarios/${id}`, { metodo: "DELETE", token }),
  favoritos: (token: string) => pedir<Favorito[]>("/api/favoritos", { token }),
  crearFavorito: (token: string, nombre: string, texto: string) =>
    pedir<Favorito>("/api/favoritos", { metodo: "POST", token, cuerpo: { nombre, texto } }),
  borrarFavorito: (token: string, id: number) => pedir<void>(`/api/favoritos/${id}`, { metodo: "DELETE", token }),
};
