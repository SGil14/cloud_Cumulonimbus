export type Intensidad = "sin_lluvia" | "ligera" | "moderada" | "fuerte" | "muy_fuerte";
export type NivelAcumulado = "sin_lluvia" | "bajo" | "moderado" | "alto" | "muy_alto";

export interface Estacion {
  id_sensor: number;
  nombre: string;
  localidad: string;
  latitud: number;
  longitud: number;
  valor_5min: number;
  mm_hora: number;
  acumulado_dia: number;
  intensidad: Intensidad;
  nivel_acumulado: NivelAcumulado;
  lloviendo: boolean;
  fecha_lectura: string | null;
  desactualizada: boolean;
}

export interface EstacionCercana extends Estacion {
  distancia_km: number;
}

export interface LocalidadResumen {
  localidad: string;
  estaciones: number;
  estaciones_lloviendo: number;
  acumulado_max: number;
  acumulado_promedio: number;
  nivel_acumulado: NivelAcumulado;
  lloviendo: boolean;
}

export interface Resumen {
  datos_obtenidos_en: string;
  total_estaciones: number;
  estaciones_lloviendo: number;
  estaciones_desactualizadas: number;
  localidades_lloviendo: string[];
  estacion_max_acumulado: Estacion | null;
  estacion_max_intensidad: Estacion | null;
  localidades: LocalidadResumen[];
}

export interface EstacionesRespuesta {
  datos_obtenidos_en: string;
  estaciones: Estacion[];
}

export interface Cercania {
  datos_obtenidos_en: string;
  latitud: number;
  longitud: number;
  lloviendo_cerca: boolean;
  estaciones: EstacionCercana[];
}

export interface UbicacionDestino {
  latitud: number;
  longitud: number;
  direccion: string | null;
  barrio: string | null;
  localidad: string | null;
  proveedor: string;
  aproximada: boolean;
}

export interface Destino {
  texto: string;
  tipo: "localidad" | "coordenadas" | "direccion";
  encontrado: boolean;
  mensaje: string;
  ubicacion: UbicacionDestino | null;
  cercania: Cercania | null;
}

export interface LimitesLocalidades {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    properties: { nombre: string; codigo: string; nivel?: NivelAcumulado; mm?: number; lloviendo?: boolean };
    geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] };
  }[];
}

export interface Radar {
  obtenido_en: string;
  capturado_en: string | null;
  norte: number;
  sur: number;
  este: number;
  oeste: number;
  imagen: string;
}

// ---------- Historial ----------

export type Periodo = "6h" | "24h" | "7d" | "30d";

export interface PuntoHistorial {
  inicio: string;
  mm: number | null;
  lecturas: number;
}

export interface SerieHistorial {
  etiqueta: string;
  periodo: Periodo;
  paso: "hora" | "dia";
  desde: string;
  hasta: string;
  puntos: PuntoHistorial[];
  total_mm: number;
  pico: PuntoHistorial | null;
  estaciones: number;
  datos_desde: string | null;
  cobertura_pct: number;
}

export interface ItemRanking {
  localidad: string;
  total_mm: number;
  max_estacion_mm: number;
  estaciones: number;
}

export interface RankingHistorial {
  periodo: Periodo;
  paso: "hora" | "dia";
  desde: string;
  hasta: string;
  datos_desde: string | null;
  cobertura_pct: number;
  items: ItemRanking[];
}

export interface SerieEstacion {
  id_sensor: number;
  nombre: string;
  localidad: string;
  distancia_km: number;
  serie: SerieHistorial;
}

export interface HistorialDestino {
  periodo: Periodo;
  estaciones: SerieEstacion[];
}

// ---------- Ruta ----------

export type ModoRuta = "auto" | "bus" | "bicicleta" | "a_pie";
export type EstadoTramo = "lluvia" | "seco" | "sin_datos";

export interface TramoRuta {
  desde_km: number;
  hasta_km: number;
  estado: EstadoTramo;
  estacion: string | null;
  intensidad: Intensidad | null;
  mm_hora: number;
  coordenadas: number[][];
}

export interface RutaRespuesta {
  encontrado: boolean;
  mensaje: string;
  modo: ModoRuta;
  origen: UbicacionDestino | null;
  destino: UbicacionDestino | null;
  distancia_km: number;
  duracion_min: number;
  hay_lluvia: boolean;
  porcentaje_sin_datos: number;
  resumen: string;
  nota: string;
  tramos: TramoRuta[];
  datos_obtenidos_en: string | null;
}
