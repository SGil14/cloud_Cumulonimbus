import { useEffect, useRef, useState, type FormEvent } from "react";
import { PanelAdmin } from "./PanelAdmin";
import type { Usuario } from "../lib/types";

interface Props {
  usuario: Usuario | null;
  token: string | null;
  onIniciar: (correo: string, clave: string) => Promise<void>;
  onRegistrar: (correo: string, clave: string) => Promise<void>;
  onSalir: () => void;
  onCerrar: () => void;
}

type Modo = "entrar" | "registrar";

/** Ventana de la cuenta: formularios de registro e inicio de sesión, o los datos del usuario con sesión abierta. */
export function Cuenta({ usuario, token, onIniciar, onRegistrar, onSalir, onCerrar }: Props) {
  const [modo, setModo] = useState<Modo>("entrar");
  const [correo, setCorreo] = useState("");
  const [clave, setClave] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const primerCampo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [onCerrar]);

  useEffect(() => { primerCampo.current?.focus(); }, [modo, usuario]);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await (modo === "entrar" ? onIniciar(correo.trim(), clave) : onRegistrar(correo.trim(), clave));
      setClave("");
      onCerrar();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo completar la operación.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="hist-fondo" onClick={onCerrar}>
      <section className={"hist cuenta" + (usuario?.rol === "administrador" ? " cuenta--admin" : "")} role="dialog" aria-modal="true" aria-labelledby="cuenta-titulo" onClick={(e) => e.stopPropagation()}>
        <header className="hist__cabecera">
          <div>
            <p className="hist__etiqueta">{usuario ? "Sesión iniciada" : "Tu cuenta"}</p>
            <h2 id="cuenta-titulo">{usuario ? "Mi cuenta" : modo === "entrar" ? "Iniciar sesión" : "Crear cuenta"}</h2>
          </div>
          <button type="button" className="hist__cerrar" onClick={onCerrar} aria-label="Cerrar">×</button>
        </header>

        {usuario ? (
          <>
            <dl className="cuenta__datos">
              <div><dt>Correo</dt><dd>{usuario.correo}</dd></div>
              <div><dt>Rol</dt><dd>{usuario.rol}</dd></div>
            </dl>
            {usuario.rol === "administrador" && token && <PanelAdmin token={token} yoId={usuario.id} />}
            <button type="button" className="cuenta__boton cuenta__boton--sec" onClick={() => { onSalir(); onCerrar(); }}>
              Cerrar sesión
            </button>
          </>
        ) : (
          <>
            <div className="hist__chips" role="group" aria-label="Acción">
              <button type="button" aria-pressed={modo === "entrar"} className={"hist__chip" + (modo === "entrar" ? " hist__chip--on" : "")} onClick={() => { setModo("entrar"); setError(null); }}>
                Ya tengo cuenta
              </button>
              <button type="button" aria-pressed={modo === "registrar"} className={"hist__chip" + (modo === "registrar" ? " hist__chip--on" : "")} onClick={() => { setModo("registrar"); setError(null); }}>
                Registrarme
              </button>
            </div>
            <form className="cuenta__form" onSubmit={enviar}>
              <label>
                <span className="hist__etiqueta">Correo</span>
                <input ref={primerCampo} type="email" value={correo} onChange={(e) => setCorreo(e.target.value)} autoComplete="email" required maxLength={254} />
              </label>
              <label>
                <span className="hist__etiqueta">Contraseña</span>
                <input type="password" value={clave} onChange={(e) => setClave(e.target.value)} required maxLength={128}
                  minLength={modo === "registrar" ? 8 : 1} autoComplete={modo === "entrar" ? "current-password" : "new-password"} />
              </label>
              {modo === "registrar" && <p className="cuenta__ayuda">Mínimo 8 caracteres, con al menos una letra y un número.</p>}
              {error && <p className="cuenta__error" role="alert">{error}</p>}
              <button type="submit" className="cuenta__boton" disabled={enviando}>
                {enviando ? "Enviando…" : modo === "entrar" ? "Entrar" : "Crear cuenta y entrar"}
              </button>
            </form>
            <p className="cuenta__ayuda">Con tu cuenta puedes guardar destinos favoritos. Consultar la lluvia no necesita cuenta.</p>
          </>
        )}
      </section>
    </div>
  );
}
