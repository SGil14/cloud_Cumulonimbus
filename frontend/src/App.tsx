import { useCallback, useEffect, useMemo, useState } from "react";
import { Barra } from "./components/Barra";
import { Historial } from "./components/Historial";
import { LeyendaRadar } from "./components/LeyendaRadar";
import { MapaLluvia } from "./components/MapaLluvia";
import { Panel } from "./components/Panel";
import { useDiseno } from "./hooks/useDiseno";
import { useEsMovil } from "./hooks/useEsMovil";
import { useLluvia } from "./hooks/useLluvia";
import { useTema } from "./hooks/useTema";
import { api } from "./lib/api";
import type { Destino, ModoRuta, RutaRespuesta } from "./lib/types";

export default function App() {
  const { tema, alternar } = useTema();
  const esMovil = useEsMovil();
  const { diseno, siguiente: cambiarDiseno } = useDiseno();
  const { resumen, estaciones, limites, radar, cargando, error, actualizar } = useLluvia();
  // El radar arranca apagado: ve lluvia en el aire, que a veces no llega al suelo, y puede confundir.
  const [mostrarRadar, setMostrarRadar] = useState(() => {
    try { return localStorage.getItem("lluvia-radar") === "1"; } catch { return false; }
  });
  const alternarRadar = useCallback(() => {
    setMostrarRadar((v) => {
      try { localStorage.setItem("lluvia-radar", v ? "0" : "1"); } catch { /* sin almacenamiento */ }
      return !v;
    });
  }, []);

  // Algunos diseños cambian el cielo cuando llueve en algún punto de la ciudad.
  const llueve = (resumen?.estaciones_lloviendo ?? 0) > 0;
  useEffect(() => {
    document.documentElement.dataset.lluvia = String(llueve);
  }, [llueve]);

  const [destino, setDestino] = useState<Destino | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [errorBusqueda, setErrorBusqueda] = useState<string | null>(null);
  const [textoBusqueda, setTextoBusqueda] = useState("");
  const [seleccionada, setSeleccionada] = useState<number | null>(null);
  const [panelAbierto, setPanelAbierto] = useState(false);
  const [historial, setHistorial] = useState<{ abierto: boolean; enDestino: boolean }>({ abierto: false, enDestino: false });
  const [ruta, setRuta] = useState<RutaRespuesta | null>(null);
  const [cargandoRuta, setCargandoRuta] = useState(false);
  const [errorRuta, setErrorRuta] = useState<string | null>(null);

  const buscar = useCallback(async (texto: string) => {
    setTextoBusqueda(texto);
    setBuscando(true);
    setErrorBusqueda(null);
    setSeleccionada(null);
    setRuta(null);
    try {
      setDestino(await api.destino(texto));
      setPanelAbierto(false); // en celular la respuesta se ve arriba del panel plegado y el mapa queda libre
    } catch (e) {
      setDestino(null);
      setErrorBusqueda(e instanceof Error ? e.message : "No se pudo hacer la búsqueda.");
    } finally {
      setBuscando(false);
    }
  }, []);

  const calcularRuta = useCallback(async (origen: string, destinoTexto: string, modo: ModoRuta) => {
    setCargandoRuta(true);
    setErrorRuta(null);
    setSeleccionada(null);
    setDestino(null);
    try {
      setRuta(await api.ruta(origen, destinoTexto, modo));
      setPanelAbierto(false);
    } catch (e) {
      setRuta(null);
      setErrorRuta(e instanceof Error ? e.message : "No se pudo calcular la ruta.");
    } finally {
      setCargandoRuta(false);
    }
  }, []);

  const limpiarDestino = useCallback(() => {
    setDestino(null);
    setErrorBusqueda(null);
  }, []);

  const estacionSeleccionada = useMemo(
    () => estaciones.find((e) => e.id_sensor === seleccionada) ?? null,
    [estaciones, seleccionada],
  );

  return (
    <>
      <MapaLluvia
        estaciones={estaciones}
        limites={limites}
        resumen={resumen}
        paleta={diseno.mapa[tema]}
        margen={diseno.margen}
        radar={radar}
        mostrarRadar={mostrarRadar}
        animarLluvia={diseno.lluviaAnimada === true}
        ruta={ruta}
        destino={destino}
        seleccionada={seleccionada}
        esMovil={esMovil}
        tema={tema}
        onSeleccionar={setSeleccionada}
      />
      <Barra
        tema={tema}
        cargando={cargando}
        radarDisponible={radar !== null}
        radarActivo={mostrarRadar}
        nombreDiseno={diseno.nombre}
        onActualizar={actualizar}
        onAlternarTema={alternar}
        onAlternarRadar={alternarRadar}
        onCambiarDiseno={cambiarDiseno}
        onAbrirHistorial={() => setHistorial({ abierto: true, enDestino: false })}
      />
      {radar && mostrarRadar && <LeyendaRadar radar={radar} />}

      {error && (
        <div className="alerta" role="alert">
          <span>{error}</span>
          <button type="button" onClick={actualizar}>Reintentar</button>
        </div>
      )}

      <Panel
        resumen={resumen}
        cargando={cargando}
        destino={destino}
        buscando={buscando}
        errorBusqueda={errorBusqueda}
        textoBusqueda={textoBusqueda}
        estacionSeleccionada={estacionSeleccionada}
        abierto={panelAbierto}
        esMovil={esMovil}
        onAlternar={() => setPanelAbierto((a) => !a)}
        onBuscar={buscar}
        onLimpiarDestino={limpiarDestino}
        onVerHistorial={() => setHistorial({ abierto: true, enDestino: true })}
        ruta={ruta}
        cargandoRuta={cargandoRuta}
        errorRuta={errorRuta}
        onCalcularRuta={calcularRuta}
        onLimpiarRuta={() => { setRuta(null); setErrorRuta(null); }}
        onSeleccionarEstacion={(id) => {
          setSeleccionada(id);
          if (id !== null && esMovil) setPanelAbierto(false);
        }}
      />

      {historial.abierto && (
        <Historial
          localidades={resumen?.localidades.map((l) => l.localidad) ?? []}
          destino={destino}
          abrirEnDestino={historial.enDestino}
          onCerrar={() => setHistorial({ abierto: false, enDestino: false })}
        />
      )}
    </>
  );
}
