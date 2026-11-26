import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { EstadoSistema, Favorito, Rol, UsuarioAdmin } from "../lib/types";

interface Props {
  token: string;
  /** Id del administrador que tiene la sesión: no puede borrarse ni quitarse el rol desde aquí. */
  yoId: number;
}

const fecha = (iso: string) => new Date(iso).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });

function hace(minutos: number | null): string {
  if (minutos === null) return "sin lecturas";
  if (minutos < 1) return "hace menos de 1 min";
  if (minutos < 90) return `hace ${minutos} min`;
  if (minutos < 60 * 48) return `hace ${Math.round(minutos / 60)} h`;
  return `hace ${Math.round(minutos / 1440)} días`;
}

/** Opciones del administrador: estado del sistema, usuarios, roles, favoritos de cada uno y eliminación de cuentas. */
export function PanelAdmin({ token, yoId }: Props) {
  const [estado, setEstado] = useState<EstadoSistema | null>(null);
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[] | null>(null);
  const [favoritos, setFavoritos] = useState<Record<number, Favorito[] | "cargando">>({});
  const [confirmando, setConfirmando] = useState<number | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try {
      const [e, u] = await Promise.all([api.estadoSistema(token), api.usuarios(token)]);
      setEstado(e);
      setUsuarios(u);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar el panel.");
    }
  }, [token]);

  useEffect(() => { void cargar(); }, [cargar]);

  /** Ejecuta una acción, avisa del resultado y vuelve a leer los datos. */
  const accion = async (hacer: () => Promise<unknown>, exito: string) => {
    setOcupado(true);
    setError(null);
    setAviso(null);
    try {
      await hacer();
      setAviso(exito);
      setConfirmando(null);
      await cargar();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo completar la acción.");
    } finally {
      setOcupado(false);
    }
  };

  const alternarFavoritos = async (id: number) => {
    if (favoritos[id]) {
      setFavoritos(({ [id]: _, ...resto }) => resto);
      return;
    }
    setFavoritos((f) => ({ ...f, [id]: "cargando" }));
    try {
      const lista = await api.favoritosDe(token, id);
      setFavoritos((f) => ({ ...f, [id]: lista }));
    } catch (err) {
      setFavoritos(({ [id]: _, ...resto }) => resto);
      setError(err instanceof Error ? err.message : "No se pudieron leer los favoritos.");
    }
  };

  const mejor = estado?.ia_supera_linea_base;

  return (
    <div className="admin">
      <section aria-labelledby="admin-estado">
        <p className="hist__etiqueta" id="admin-estado">Estado del sistema</p>
        {estado ? (
          <>
            <dl className="admin__estado">
              <div><dt>Usuarios</dt><dd>{estado.usuarios}<small>{estado.administradores} administrador(es)</small></dd></div>
              <div><dt>Favoritos guardados</dt><dd>{estado.favoritos}</dd></div>
              <div><dt>Estaciones</dt><dd>{estado.estaciones}</dd></div>
              <div><dt>Lecturas guardadas</dt><dd>{estado.lecturas.toLocaleString("es-CO")}<small>{estado.lecturas_24h.toLocaleString("es-CO")} en 24 h</small></dd></div>
              <div><dt>Última lectura</dt><dd>{hace(estado.minutos_desde_ultima_lectura)}<small>el recolector guarda cada {estado.recolector_intervalo_minutos} min</small></dd></div>
              <div>
                <dt>Predicción de IA</dt>
                <dd>{estado.ia_modelo_disponible ? "Modelo cargado" : "Solo persistencia"}
                  {estado.ia_f1_modelo !== null && estado.ia_f1_persistencia !== null && (
                    <small>F1 {estado.ia_f1_modelo.toFixed(2)} vs {estado.ia_f1_persistencia.toFixed(2)} de la línea base{mejor === false ? " (no la supera)" : ""}</small>
                  )}
                </dd>
              </div>
            </dl>
            {estado.grafana_url && (
              <p className="admin__nota">Monitoreo: <a href={estado.grafana_url} target="_blank" rel="noreferrer">abrir Grafana</a></p>
            )}
          </>
        ) : !error && <p className="admin__nota">Cargando…</p>}
      </section>

      <section aria-labelledby="admin-usuarios">
        <p className="hist__etiqueta" id="admin-usuarios">Usuarios registrados</p>
        {aviso && <p className="admin__ok" role="status">{aviso}</p>}
        {error && <p className="cuenta__error" role="alert">{error}</p>}
        {usuarios && (
          <ul className="admin__usuarios">
            {usuarios.map((u) => {
              const soyYo = u.id === yoId;
              const lista = favoritos[u.id];
              return (
                <li key={u.id} className="admin__fila">
                  <div className="admin__quien">
                    <strong>{u.correo}{soyYo ? " (tú)" : ""}</strong>
                    <small>Desde {fecha(u.creado_en)} · {u.favoritos} favorito(s)</small>
                  </div>
                  <select
                    aria-label={`Rol de ${u.correo}`}
                    value={u.rol}
                    disabled={ocupado || soyYo}
                    title={soyYo ? "No puedes cambiar tu propio rol desde aquí" : undefined}
                    onChange={(e) => void accion(() => api.cambiarRol(token, u.id, e.target.value as Rol), `Ahora ${u.correo} es ${e.target.value}.`)}
                  >
                    <option value="usuario">usuario</option>
                    <option value="administrador">administrador</option>
                  </select>
                  <button type="button" disabled={u.favoritos === 0 && !lista} onClick={() => void alternarFavoritos(u.id)} aria-expanded={Boolean(lista)}>
                    {lista ? "Ocultar favoritos" : "Ver favoritos"}
                  </button>
                  {confirmando === u.id ? (
                    <>
                      <button type="button" className="admin__peligro" disabled={ocupado}
                        onClick={() => void accion(() => api.eliminarUsuario(token, u.id), `Se eliminó la cuenta de ${u.correo}.`)}>
                        Confirmar
                      </button>
                      <button type="button" onClick={() => setConfirmando(null)}>Cancelar</button>
                    </>
                  ) : (
                    <button type="button" className="admin__peligro" disabled={ocupado || soyYo}
                      title={soyYo ? "No puedes eliminar tu propia cuenta" : undefined} onClick={() => setConfirmando(u.id)}>
                      Eliminar
                    </button>
                  )}
                  {lista === "cargando" && <p className="admin__favs">Cargando…</p>}
                  {Array.isArray(lista) && (
                    <ul className="admin__favs">
                      {lista.length === 0 ? <li>Sin favoritos.</li> : lista.map((f) => <li key={f.id}><strong>{f.nombre}</strong> · {f.texto}</li>)}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
