import maplibregl, { type GeoJSONSource, type ImageSource, type LngLatBoundsLike, type Map as MapaGL, type Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { anillosDeRadar, centroide, CENTRO_RADAR } from "../lib/geo";
import { celdasDeEstaciones, celdasDeRadar, iniciarLluvia, type MotorLluvia } from "../lib/lluviaViva";
import { sinEcosDebiles } from "../lib/radarFiltrado";
import { claveLocalidad, nombreLocalidad } from "../lib/format";
import type { Margen, Paleta } from "../disenos";
import type { Destino, Estacion, LimitesLocalidades, Radar, Resumen, RutaRespuesta } from "../lib/types";

interface Props {
  estaciones: Estacion[];
  limites: LimitesLocalidades | null;
  resumen: Resumen | null;
  paleta: Paleta;
  margen: Margen;
  radar: Radar | null;
  mostrarRadar: boolean;
  animarLluvia: boolean;
  ruta: RutaRespuesta | null;
  destino: Destino | null;
  seleccionada: number | null;
  esMovil: boolean;
  tema: "claro" | "oscuro";
  onSeleccionar: (id: number | null) => void;
}

// Color de cada localidad según los mm acumulados hoy. Los escalones coinciden con los niveles del SAB (10 / 30 / 50 mm);
// los colores de cada escalón los define el diseño (src/disenos).
const ESCALA_MM = [0, 3, 10, 30, 50, 80];

const ZONA_URBANA: LngLatBoundsLike = [[-74.24, 4.37], [-73.98, 4.82]];
const LIMITES_MAXIMOS: LngLatBoundsLike = [[-75.4, 3.6], [-72.8, 5.8]];

// Colores y alcance de la zona que se pinta alrededor de cada estación que llueve (los mismos del punto y del radar).
const COLOR_ZONA = {
  oscuro: { ligera: "#4ab8ff", moderada: "#ffd23f", fuerte: "#ff8a1f", muy_fuerte: "#ff3b3b" },
  claro: { ligera: "#1e7bff", moderada: "#f0be00", fuerte: "#ff6e00", muy_fuerte: "#c8001e" },
};
const RADIO_ZONA_M = { ligera: 2500, moderada: 3500, fuerte: 4500, muy_fuerte: 5500 };
// Metros → píxeles: a latitud 4,6° un píxel de zoom 0 (teselas de 512) son ~78 km.
const PX_POR_METRO_Z8 = 256 / 78016;
const PX_POR_METRO_Z16 = 65536 / 78016;

/** La zona se desvanece al acercar el mapa: a zoom de calle un halo de varios kilómetros taparía todo. */
function opacidadZona(base: number) {
  return ["interpolate", ["linear"], ["zoom"], 10.5, base, 12.5, base * 0.45, 14.5, base * 0.12] as never;
}

function colorZona(tema: "claro" | "oscuro") {
  const c = COLOR_ZONA[tema];
  return ["match", ["get", "intensidad"], "muy_fuerte", c.muy_fuerte, "fuerte", c.fuerte, "moderada", c.moderada, c.ligera] as never;
}

function relleno(paleta: Paleta) {
  const pasos = ESCALA_MM.flatMap((mm, k) => [mm, paleta.escala[k]]);
  return ["interpolate", ["linear"], ["get", "mm"], ...pasos] as never;
}

function elementoEstacion(e: Estacion): HTMLButtonElement {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "st";
  el.dataset.nivel = e.nivel_acumulado;
  el.dataset.intensidad = e.intensidad;
  if (e.lloviendo) {
    el.classList.add("st--on");
    const radio = Math.min(120, 24 + Math.sqrt(e.mm_hora) * 15);
    el.style.setProperty("--r", `${radio}px`);
    el.style.setProperty("--d", `${Math.max(1.3, 3.2 - e.mm_hora / 14)}s`);
  }
  if (e.desactualizada) el.classList.add("st--stale");
  el.setAttribute("aria-label", `${e.nombre}, ${nombreLocalidad(e.localidad)}`);
  el.innerHTML = '<span class="st__ring"></span><span class="st__ring st__ring--2"></span><span class="st__dot"></span>';
  return el;
}

export function MapaLluvia({ estaciones, limites, resumen, paleta, margen, radar, mostrarRadar, animarLluvia, ruta, destino, seleccionada, esMovil, tema, onSeleccionar }: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const mapaRef = useRef<MapaGL | null>(null);
  const [listo, setListo] = useState(false);
  const marcadores = useRef(new Map<number, { marker: Marker; el: HTMLElement }>());
  const etiquetas = useRef<Marker[]>([]);
  const marcadorDestino = useRef<Marker | null>(null);
  const alSeleccionar = useRef(onSeleccionar);
  alSeleccionar.current = onSeleccionar;
  const movilRef = useRef(esMovil);
  movilRef.current = esMovil;
  const paletaRef = useRef(paleta);
  paletaRef.current = paleta;
  const temaRef = useRef(tema);
  temaRef.current = tema;
  const margenRef = useRef(margen);
  margenRef.current = margen;
  const padding = (movil: boolean) => margenRef.current[movil ? "movil" : "escritorio"];

  // Cada localidad con su nivel y si llueve en ella, para pintarla.
  const datosLocalidades = useMemo(() => {
    if (!limites) return null;
    const porClave = new Map((resumen?.localidades ?? []).map((l) => [claveLocalidad(l.localidad), l]));
    return {
      ...limites,
      features: limites.features.map((f) => {
        const l = porClave.get(claveLocalidad(f.properties.nombre));
        return { ...f, properties: { ...f.properties, nivel: l?.nivel_acumulado ?? "sin_lluvia", mm: l?.acumulado_max ?? 0, lloviendo: l?.lloviendo ?? false } };
      }),
    };
  }, [limites, resumen]);

  // --- Crear el mapa (una sola vez) ---
  useEffect(() => {
    if (!contenedor.current) return;
    const mapa = new maplibregl.Map({
      container: contenedor.current,
      style: { version: 8, sources: {}, layers: [] },
      maxBounds: LIMITES_MAXIMOS,
      minZoom: 8.5,
      maxZoom: 16,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
    });
    mapa.touchZoomRotate.disableRotation();
    mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-left");

    mapa.fitBounds(ZONA_URBANA, { padding: padding(movilRef.current), duration: 0 });

    mapa.on("load", () => {
      const vacio = { type: "FeatureCollection" as const, features: [] };
      mapa.addSource("localidades", { type: "geojson", data: vacio });
      mapa.addSource("enlaces", { type: "geojson", data: vacio });
      mapa.addSource("anillos", { type: "geojson", data: vacio });
      mapa.addSource("ruta", { type: "geojson", data: vacio });
      mapa.addSource("zonas-lluvia", { type: "geojson", data: vacio });
      mapa.addLayer({ id: "loc-fill", type: "fill", source: "localidades", paint: { "fill-color": relleno(paletaRef.current), "fill-opacity": 1 } });
      mapa.addLayer({
        id: "loc-brillo", type: "line", source: "localidades",
        filter: ["==", ["get", "lloviendo"], true],
        paint: { "line-color": paletaRef.current.brillo, "line-width": 5, "line-blur": 6, "line-opacity": 0.7 },
      });
      // La zona de lluvia alrededor de cada estación: un halo de color que se difumina hacia afuera.
      mapa.addLayer({
        id: "zonas-lluvia", type: "circle", source: "zonas-lluvia",
        paint: {
          "circle-color": colorZona(temaRef.current),
          "circle-radius": ["interpolate", ["exponential", 2], ["zoom"],
            8, ["*", ["get", "radio"], PX_POR_METRO_Z8], 16, ["*", ["get", "radio"], PX_POR_METRO_Z16]],
          "circle-blur": 0.7,
          "circle-opacity": opacidadZona(0.6),
          "circle-pitch-alignment": "map",
        },
      });
      mapa.addLayer({ id: "loc-borde", type: "line", source: "localidades", paint: { "line-color": paletaRef.current.borde, "line-width": 1 } });
      mapa.addLayer({
        id: "anillos", type: "line", source: "anillos",
        layout: { visibility: paletaRef.current.anillos ? "visible" : "none" },
        paint: { "line-color": paletaRef.current.anillos ?? "#ffffff", "line-width": 1, "line-dasharray": [1, 3] },
      });
      // La ruta: un trazo claro debajo (contorno) y encima el color de cada tramo.
      mapa.addLayer({
        id: "ruta-contorno", type: "line", source: "ruta",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#ffffff", "line-width": 8, "line-opacity": 0.9 },
      });
      mapa.addLayer({
        id: "ruta-linea", type: "line", source: "ruta",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-width": 4.5,
          "line-color": ["match", ["get", "estado"], "lluvia", "#ff5a1f", "sin_datos", "#8a93a6", paletaRef.current.enlace],
        },
      });
      mapa.addLayer({
        id: "enlaces", type: "line", source: "enlaces",
        paint: { "line-color": paletaRef.current.enlace, "line-width": 1.6, "line-dasharray": [2, 2] },
      });
      setListo(true);
    });

    const alZoom = () => contenedor.current?.classList.toggle("z-hi", mapa.getZoom() >= 11.2);
    mapa.on("zoom", alZoom);
    mapa.on("click", () => alSeleccionar.current(null));
    mapaRef.current = mapa;
    const marcadoresActuales = marcadores.current;
    return () => {
      marcadoresActuales.clear();
      mapa.remove();
      mapaRef.current = null;
    };
  }, []);

  // --- Si se cambia de celular a computador, o de diseño, se reencuadra la ciudad ---
  const primerEncuadre = useRef(true);
  useEffect(() => {
    if (primerEncuadre.current) { primerEncuadre.current = false; return; }
    mapaRef.current?.fitBounds(ZONA_URBANA, { padding: padding(esMovil), duration: 600 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [esMovil, margen]);

  // --- Zonas de lluvia: un halo alrededor de cada estación que registra lluvia ---
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || !listo) return;
    const fuente = mapa.getSource("zonas-lluvia") as GeoJSONSource | undefined;
    fuente?.setData({
      type: "FeatureCollection",
      features: estaciones
        .filter((e) => e.lloviendo)
        .map((e) => ({
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [e.longitud, e.latitud] },
          properties: { intensidad: e.intensidad, radio: RADIO_ZONA_M[e.intensidad as keyof typeof RADIO_ZONA_M] ?? RADIO_ZONA_M.ligera },
        })),
    });
    mapa.setPaintProperty("zonas-lluvia", "circle-color", colorZona(tema));
    mapa.setPaintProperty("zonas-lluvia", "circle-opacity", opacidadZona(tema === "claro" ? 0.7 : 0.6));
  }, [estaciones, listo, tema]);

  // --- Colores según el diseño y el tema ---
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || !listo) return;
    mapa.setPaintProperty("loc-fill", "fill-color", relleno(paleta));
    mapa.setPaintProperty("loc-borde", "line-color", paleta.borde);
    mapa.setPaintProperty("loc-brillo", "line-color", paleta.brillo);
    mapa.setPaintProperty("enlaces", "line-color", paleta.enlace);
    mapa.setPaintProperty("ruta-linea", "line-color", ["match", ["get", "estado"], "lluvia", "#ff5a1f", "sin_datos", "#8a93a6", paleta.enlace]);
    if (mapa.getLayer("radar")) mapa.setPaintProperty("radar", "raster-opacity", paleta.radar);
    mapa.setLayoutProperty("anillos", "visibility", paleta.anillos ? "visible" : "none");
    if (paleta.anillos) mapa.setPaintProperty("anillos", "line-color", paleta.anillos);
  }, [paleta, listo]);

  // --- Anillos de alcance centrados en el radar (solo los dibujan los diseños que los piden) ---
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || !listo) return;
    const centro: [number, number] = radar
      ? [(radar.oeste + radar.este) / 2, (radar.norte + radar.sur) / 2]
      : CENTRO_RADAR;
    (mapa.getSource("anillos") as GeoJSONSource).setData(anillosDeRadar(centro, [10, 20, 30, 45]) as never);
  }, [radar, listo]);

  // --- Radar del IDIGER: lluvia en el aire (solo ecos moderados o fuertes) ---
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || !listo) return;
    if (!radar) {
      if (mapa.getLayer("radar")) mapa.removeLayer("radar");
      if (mapa.getSource("radar")) mapa.removeSource("radar");
      return;
    }
    if (!mostrarRadar) {
      if (mapa.getLayer("radar")) mapa.setLayoutProperty("radar", "visibility", "none");
      return;
    }
    let vigente = true;
    void (async () => {
      const url = await sinEcosDebiles(radar.imagen, tema);
      if (!vigente || !mapaRef.current) return;
      const coordenadas: [[number, number], [number, number], [number, number], [number, number]] = [
        [radar.oeste, radar.norte], [radar.este, radar.norte], [radar.este, radar.sur], [radar.oeste, radar.sur],
      ];
      const fuente = mapa.getSource("radar") as ImageSource | undefined;
      if (fuente) {
        fuente.updateImage({ url, coordinates: coordenadas });
      } else {
        mapa.addSource("radar", { type: "image", url, coordinates: coordenadas });
        // Encima del relleno de las localidades y debajo de sus bordes.
        mapa.addLayer(
          {
            id: "radar", type: "raster", source: "radar",
            paint: { "raster-opacity": paletaRef.current.radar, "raster-resampling": "linear", "raster-fade-duration": 400 },
          },
          "loc-brillo",
        );
      }
      mapa.setLayoutProperty("radar", "visibility", "visible");
    })();
    return () => { vigente = false; };
  }, [radar, listo, mostrarRadar, tema]);

  // --- Anillos de alcance centrados en el radar (solo los dibujan los diseños que los piden) ---
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || !listo) return;
    const centro: [number, number] = radar
      ? [(radar.oeste + radar.este) / 2, (radar.norte + radar.sur) / 2]
      : CENTRO_RADAR;
    (mapa.getSource("anillos") as GeoJSONSource).setData(anillosDeRadar(centro, [10, 20, 30, 45]) as never);
  }, [radar, listo]);

  // --- Radar del IDIGER: donde hay color, está lloviendo ---
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || !listo) return;
    if (!radar) {
      if (mapa.getLayer("radar")) mapa.removeLayer("radar");
      if (mapa.getSource("radar")) mapa.removeSource("radar");
      return;
    }
    const coordenadas: [[number, number], [number, number], [number, number], [number, number]] = [
      [radar.oeste, radar.norte], [radar.este, radar.norte], [radar.este, radar.sur], [radar.oeste, radar.sur],
    ];
    const fuente = mapa.getSource("radar") as ImageSource | undefined;
    if (fuente) {
      fuente.updateImage({ url: radar.imagen, coordinates: coordenadas });
    } else {
      mapa.addSource("radar", { type: "image", url: radar.imagen, coordinates: coordenadas });
      // Encima del relleno de las localidades y debajo de sus bordes.
      mapa.addLayer(
        {
          id: "radar", type: "raster", source: "radar",
          paint: { "raster-opacity": paletaRef.current.radar, "raster-resampling": "linear", "raster-fade-duration": 400 },
        },
        "loc-brillo",
      );
    }
    mapa.setLayoutProperty("radar", "visibility", mostrarRadar ? "visible" : "none");
  }, [radar, listo, mostrarRadar]);

  // --- Lluvia animada (diseño «Mapa vivo»): cae solo donde el radar o las estaciones marcan lluvia ---
  const motorRef = useRef<MotorLluvia | null>(null);
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || !listo || !animarLluvia) return;
    const motor = iniciarLluvia(mapa, () => getComputedStyle(document.documentElement).getPropertyValue("--gota").trim() || "rgba(196,226,255,0.9)");
    motorRef.current = motor;
    return () => {
      motor.detener();
      motorRef.current = null;
    };
  }, [animarLluvia, listo]);

  useEffect(() => {
    if (!animarLluvia || !listo) return;
    let vigente = true;
    void (async () => {
      const delRadar = radar && mostrarRadar ? await celdasDeRadar(radar).catch(() => []) : [];
      if (vigente) motorRef.current?.fijarCeldas([...delRadar, ...celdasDeEstaciones(estaciones)]);
    })();
    return () => { vigente = false; };
  }, [animarLluvia, listo, radar, mostrarRadar, estaciones]);

  // --- Localidades: relleno y rótulos ---
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || !listo || !datosLocalidades) return;
    (mapa.getSource("localidades") as GeoJSONSource).setData(datosLocalidades as never);

    etiquetas.current.forEach((m) => m.remove());
    etiquetas.current = datosLocalidades.features.map((f) => {
      const c = centroide(f.geometry);
      const el = document.createElement("div");
      el.className = "lbl" + (c.ancho < 0.08 ? " lbl--small" : "") + (f.properties.lloviendo ? " lbl--on" : "");
      el.textContent = nombreLocalidad(f.properties.nombre);
      return new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat([c.lon, c.lat]).addTo(mapa);
    });
  }, [datosLocalidades, listo]);

  // --- Estaciones ---
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || !listo) return;
    marcadores.current.forEach(({ marker }) => marker.remove());
    marcadores.current.clear();
    // Las que llueven se dibujan al final para quedar por encima.
    const ordenadas = [...estaciones].sort((a, b) => Number(a.lloviendo) - Number(b.lloviendo));
    for (const e of ordenadas) {
      const el = elementoEstacion(e);
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        alSeleccionar.current(e.id_sensor);
      });
      const marker = new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat([e.longitud, e.latitud]).addTo(mapa);
      marcadores.current.set(e.id_sensor, { marker, el });
    }
  }, [estaciones, listo]);

  // --- Estación seleccionada ---
  useEffect(() => {
    marcadores.current.forEach(({ el }, id) => el.classList.toggle("st--sel", id === seleccionada));
    const mapa = mapaRef.current;
    const e = estaciones.find((x) => x.id_sensor === seleccionada);
    if (mapa && e) mapa.easeTo({ center: [e.longitud, e.latitud], zoom: Math.max(mapa.getZoom(), 12.5), padding: padding(movilRef.current), duration: 700 });
  }, [seleccionada, estaciones]);

  // --- Ruta calculada: tramos de colores y marcas de salida y llegada ---
  const marcasRuta = useRef<Marker[]>([]);
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || !listo) return;
    marcasRuta.current.forEach((m) => m.remove());
    marcasRuta.current = [];
    const fuente = mapa.getSource("ruta") as GeoJSONSource;
    if (!ruta?.encontrado || !ruta.origen || !ruta.destino) {
      fuente.setData({ type: "FeatureCollection", features: [] });
      return;
    }
    fuente.setData({
      type: "FeatureCollection",
      features: ruta.tramos.map((t) => ({
        type: "Feature" as const,
        properties: { estado: t.estado },
        geometry: { type: "LineString" as const, coordinates: t.coordenadas },
      })),
    });

    const salida = document.createElement("div");
    Object.assign(salida.style, { width: "14px", height: "14px", borderRadius: "50%", background: "#fff", border: "4px solid #16181d", boxShadow: "0 2px 8px rgba(0,0,0,.35)" });
    const llegada = document.createElement("div");
    llegada.className = "destino" + (ruta.hay_lluvia ? " destino--lluvia" : "");
    llegada.innerHTML = '<span class="destino__ping"></span><span class="destino__cruz"></span>';
    marcasRuta.current = [
      new maplibregl.Marker({ element: salida, anchor: "center" }).setLngLat([ruta.origen.longitud, ruta.origen.latitud]).addTo(mapa),
      new maplibregl.Marker({ element: llegada, anchor: "center" }).setLngLat([ruta.destino.longitud, ruta.destino.latitud]).addTo(mapa),
    ];

    const limitesRuta = new maplibregl.LngLatBounds();
    ruta.tramos.forEach((t) => t.coordenadas.forEach((c) => limitesRuta.extend(c as [number, number])));
    mapa.fitBounds(limitesRuta, { padding: padding(movilRef.current), maxZoom: 15, duration: 1100 });
  }, [ruta, listo]);

  // --- Destino buscado ---
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || !listo) return;
    marcadorDestino.current?.remove();
    marcadorDestino.current = null;
    const fuente = mapa.getSource("enlaces") as GeoJSONSource;

    const u = destino?.ubicacion;
    const cercania = destino?.cercania;
    if (!destino?.encontrado || !u || !cercania) {
      fuente.setData({ type: "FeatureCollection", features: [] });
      return;
    }

    const el = document.createElement("div");
    el.className = "destino" + (cercania.lloviendo_cerca ? " destino--lluvia" : "");
    el.innerHTML = '<span class="destino__ping"></span><span class="destino__cruz"></span>';
    marcadorDestino.current = new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat([u.longitud, u.latitud]).addTo(mapa);

    fuente.setData({
      type: "FeatureCollection",
      features: cercania.estaciones.map((e) => ({
        type: "Feature" as const,
        properties: {},
        geometry: { type: "LineString" as const, coordinates: [[u.longitud, u.latitud], [e.longitud, e.latitud]] },
      })),
    });

    const limitesVista = new maplibregl.LngLatBounds([u.longitud, u.latitud], [u.longitud, u.latitud]);
    cercania.estaciones.forEach((e) => limitesVista.extend([e.longitud, e.latitud]));
    mapa.fitBounds(limitesVista, { padding: padding(movilRef.current), maxZoom: 14.5, duration: 1100 });
  }, [destino, listo]);

  return <div ref={contenedor} className="mapa" role="application" aria-label="Mapa de lluvia de Bogotá" />;
}
