import type { Intensidad, NivelAcumulado } from "./types";

const ES = "es-CO";
const ZONA = "America/Bogota";

export function claveLocalidad(nombre: string): string {
  return nombre.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

// El SAB y Catastro publican los nombres sin tildes; aquí se restauran para mostrarlos.
const NOMBRES: Record<string, string> = {
  usaquen: "Usaquén",
  engativa: "Engativá",
  fontibon: "Fontibón",
  "san cristobal": "San Cristóbal",
  "ciudad bolivar": "Ciudad Bolívar",
  "los martires": "Los Mártires",
};

export function nombreLocalidad(nombre: string): string {
  return NOMBRES[claveLocalidad(nombre)] ?? nombre;
}

export function hora(iso: string | null): string {
  if (!iso) return "--:--";
  return new Date(iso).toLocaleTimeString(ES, { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: ZONA });
}

export function fechaCorta(iso: string): string {
  return new Date(iso)
    .toLocaleDateString(ES, { day: "numeric", month: "short", timeZone: ZONA })
    .replace(".", "")
    .toUpperCase();
}

export function mm(valor: number): string {
  // Lluvias diminutas (0,03 mm) no deben verse como 0,0.
  if (valor > 0 && valor < 0.1) return valor.toLocaleString(ES, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
  return valor.toLocaleString(ES, { maximumFractionDigits: 1, minimumFractionDigits: valor > 0 && valor < 10 ? 1 : 0 });
}

export function km(valor: number): string {
  return valor < 1 ? `${Math.round(valor * 1000)} m` : `${valor.toLocaleString(ES, { maximumFractionDigits: 1 })} km`;
}

export const ETIQUETA_INTENSIDAD: Record<Intensidad, string> = {
  sin_lluvia: "seca",
  ligera: "lluvia ligera",
  moderada: "lluvia moderada",
  fuerte: "lluvia fuerte",
  muy_fuerte: "lluvia muy fuerte",
};

export const ETIQUETA_NIVEL: Record<NivelAcumulado, string> = {
  sin_lluvia: "sin lluvia",
  bajo: "bajo",
  moderado: "moderado",
  alto: "alto",
  muy_alto: "muy alto",
};

/** Máximo de mm acumulados que llena por completo la barra de una localidad. */
export const ACUMULADO_REFERENCIA = 50;

export function horaCorta(iso: string): string {
  return new Date(iso).toLocaleTimeString(ES, { hour: "2-digit", hour12: false, timeZone: ZONA });
}

export function diaCorto(iso: string): string {
  return new Date(iso).toLocaleDateString(ES, { weekday: "short", day: "numeric", timeZone: ZONA }).replace(".", "");
}
