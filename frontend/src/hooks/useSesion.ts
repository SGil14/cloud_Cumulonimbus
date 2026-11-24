import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../lib/api";
import type { Favorito, Usuario } from "../lib/types";

const CLAVE_TOKEN = "cumulonimbus-token";

function leerToken(): string | null {
  try { return localStorage.getItem(CLAVE_TOKEN); } catch { return null; }
}
function guardarToken(token: string | null) {
  try {
    if (token) localStorage.setItem(CLAVE_TOKEN, token);
    else localStorage.removeItem(CLAVE_TOKEN);
  } catch { /* sin almacenamiento: la sesión dura lo que dure la página */ }
}

/** Sesión del usuario: registro, inicio y cierre de sesión, y sus destinos favoritos. */
export function useSesion() {
  const [token, setToken] = useState<string | null>(leerToken);
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [favoritos, setFavoritos] = useState<Favorito[]>([]);
  const [verificando, setVerificando] = useState(() => leerToken() !== null);

  const salir = useCallback(() => {
    guardarToken(null);
    setToken(null);
    setUsuario(null);
    setFavoritos([]);
  }, []);

  // Si hay un token guardado, se comprueba que siga valiendo y se cargan los favoritos.
  useEffect(() => {
    if (!token) return;
    let vigente = true;
    Promise.all([api.yo(token), api.favoritos(token)])
      .then(([u, f]) => {
        if (!vigente) return;
        setUsuario(u);
        setFavoritos(f);
      })
      .catch((e) => {
        // Solo un 401 significa «token vencido o inválido»; un corte de red no debe sacar al usuario.
        if (vigente && e instanceof ApiError && e.estado === 401) salir();
      })
      .finally(() => vigente && setVerificando(false));
    return () => { vigente = false; };
  }, [token, salir]);

  const iniciarSesion = useCallback(async (correo: string, clave: string) => {
    const r = await api.login(correo, clave);
    guardarToken(r.access_token);
    setToken(r.access_token);
    setUsuario(r.usuario);
  }, []);

  const registrar = useCallback(async (correo: string, clave: string) => {
    await api.registro(correo, clave);
    await iniciarSesion(correo, clave);
  }, [iniciarSesion]);

  const agregarFavorito = useCallback(async (texto: string) => {
    if (!token) return;
    const nuevo = await api.crearFavorito(token, texto.slice(0, 100), texto);
    setFavoritos((f) => [...f, nuevo].sort((a, b) => a.nombre.localeCompare(b.nombre, "es")));
  }, [token]);

  const borrarFavorito = useCallback(async (id: number) => {
    if (!token) return;
    await api.borrarFavorito(token, id);
    setFavoritos((f) => f.filter((x) => x.id !== id));
  }, [token]);

  return { token, usuario, favoritos, verificando, iniciarSesion, registrar, salir, agregarFavorito, borrarFavorito };
}
