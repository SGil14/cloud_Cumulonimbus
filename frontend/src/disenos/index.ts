import type { Tema } from "../hooks/useTema";
import clima from "./clima.css?inline";
import comun from "./comun.css?inline";
import minimalista from "./minimalista.css?inline";
import radar from "./radar.css?inline";
import tablero from "./tablero.css?inline";
import vivo from "./vivo.css?inline";

/** Colores que usa el mapa (se pintan con MapLibre, no con CSS). */
export interface Paleta {
  /** Relleno de las localidades según mm acumulados hoy (ver ESCALA_MM en MapaLluvia). */
  escala: string[];
  borde: string;
  enlace: string;
  brillo: string;
  radar: number;
  /** Color de los anillos de alcance del radar; si falta, no se dibujan. */
  anillos?: string;
}

/** Espacio (px) que el mapa deja libre alrededor para no quedar tapado por los paneles del diseño. */
export interface Relleno { top: number; bottom: number; left: number; right: number }
export interface Margen { escritorio: Relleno; movil: Relleno }

export interface Diseno {
  id: string;
  nombre: string;
  css: string;
  /** Dibuja lluvia animada sobre las zonas donde llueve. */
  lluviaAnimada?: boolean;
  margen: Margen;
  mapa: Record<Tema, Paleta>;
}

export const DISENOS: Diseno[] = [
  {
    id: "clima",
    nombre: "Clima",
    css: clima,
    margen: {
      escritorio: { top: 90, bottom: 70, left: 70, right: 430 },
      movil: { top: 70, bottom: 370, left: 16, right: 16 },
    },
    mapa: {
      claro: {
        escala: ["#f4f9ff", "#d3e8fb", "#9bcbf6", "#6aa0f3", "#8a74f2", "#c65af0"],
        borde: "rgba(70,110,170,0.38)", enlace: "#1e7bff", brillo: "#1e7bff", radar: 0.85,
      },
      oscuro: {
        escala: ["#1b2d66", "#233f86", "#2c5ec0", "#5159dd", "#9347e6", "#e149df"],
        borde: "rgba(190,210,255,0.30)", enlace: "#5ee7ff", brillo: "#5ee7ff", radar: 0.9,
      },
    },
  },
  {
    id: "radar",
    nombre: "Radar",
    css: radar,
    margen: {
      escritorio: { top: 80, bottom: 70, left: 70, right: 390 },
      movil: { top: 70, bottom: 330, left: 16, right: 16 },
    },
    mapa: {
      oscuro: {
        escala: ["#0c1522", "#10263c", "#0f4a63", "#1a7f86", "#c9a227", "#d9462b"],
        borde: "rgba(120,170,230,0.32)", enlace: "#35d6ff", brillo: "#35d6ff", radar: 0.92, anillos: "rgba(120,190,255,0.38)",
      },
      claro: {
        escala: ["#eaf0f7", "#dbe7f3", "#b9d4ea", "#7db3d6", "#e0b43c", "#d9462b"],
        borde: "rgba(20,50,90,0.38)", enlace: "#0a62d6", brillo: "#0a62d6", radar: 0.9, anillos: "rgba(20,70,130,0.35)",
      },
    },
  },
  {
    id: "minimalista",
    nombre: "Minimalista",
    css: minimalista,
    margen: {
      escritorio: { top: 150, bottom: 140, left: 60, right: 60 },
      movil: { top: 130, bottom: 210, left: 14, right: 14 },
    },
    mapa: {
      claro: {
        escala: ["#f6f5f1", "#ebeef3", "#d8e2f5", "#b7cbf3", "#88a8ef", "#5a7be8"],
        borde: "rgba(22,24,29,0.22)", enlace: "#0057ff", brillo: "#0057ff", radar: 0.8,
      },
      oscuro: {
        escala: ["#0e0f12", "#141821", "#1a2540", "#233a73", "#2f56b5", "#4a7cf0"],
        borde: "rgba(242,242,238,0.2)", enlace: "#4da3ff", brillo: "#4da3ff", radar: 0.85,
      },
    },
  },
  {
    id: "vivo",
    nombre: "Mapa vivo",
    css: vivo,
    lluviaAnimada: true,
    margen: {
      escritorio: { top: 90, bottom: 60, left: 470, right: 60 },
      movil: { top: 70, bottom: 290, left: 14, right: 14 },
    },
    mapa: {
      oscuro: {
        escala: [
          "rgba(255,255,255,0.05)", "rgba(255,255,255,0.09)", "rgba(120,170,255,0.24)",
          "rgba(150,120,255,0.36)", "rgba(220,100,255,0.48)", "rgba(255,90,170,0.62)",
        ],
        borde: "rgba(255,255,255,0.3)", enlace: "#7df0ff", brillo: "#7df0ff", radar: 0.8,
      },
      claro: {
        escala: [
          "rgba(255,255,255,0.5)", "rgba(255,255,255,0.65)", "rgba(150,195,245,0.6)",
          "rgba(110,150,240,0.6)", "rgba(150,100,240,0.6)", "rgba(220,70,190,0.65)",
        ],
        borde: "rgba(30,60,110,0.38)", enlace: "#1560ff", brillo: "#1560ff", radar: 0.8,
      },
    },
  },
  {
    id: "tablero",
    nombre: "Tablero",
    css: tablero,
    margen: {
      escritorio: { top: 90, bottom: 70, left: 70, right: 470 },
      movil: { top: 70, bottom: 370, left: 16, right: 16 },
    },
    mapa: {
      oscuro: {
        escala: ["#17181c", "#22242a", "#4d3b17", "#8f4d12", "#c2321b", "#ff2e2e"],
        borde: "rgba(255,255,255,0.20)", enlace: "#c6ff3d", brillo: "#c6ff3d", radar: 0.9,
      },
      claro: {
        escala: ["#e4dfd0", "#d8d2c0", "#ebc872", "#e8954a", "#d9482b", "#b3141a"],
        borde: "rgba(20,20,20,0.40)", enlace: "#1f3dff", brillo: "#1f3dff", radar: 0.85,
      },
    },
  },
];

const CLAVE = "lluvia-diseno";

export function disenoInicial(): Diseno {
  try {
    const guardado = localStorage.getItem(CLAVE);
    return DISENOS.find((d) => d.id === guardado) ?? DISENOS[0];
  } catch {
    return DISENOS[0];
  }
}

/** Inyecta el CSS del diseño. Se llama antes de pintar la app para evitar un destello sin estilos. */
export function aplicarDiseno(d: Diseno): void {
  // Las piezas compartidas (historial, ruta) se inyectan después, para que usen las variables del diseño.
  let compartido = document.getElementById("css-comun") as HTMLStyleElement | null;
  if (!compartido) {
    compartido = document.createElement("style");
    compartido.id = "css-comun";
    compartido.textContent = comun;
    document.head.appendChild(compartido);
  }
  let el = document.getElementById("css-diseno") as HTMLStyleElement | null;
  if (!el) {
    el = document.createElement("style");
    el.id = "css-diseno";
    document.head.appendChild(el);
  }
  el.textContent = d.css;
  document.documentElement.dataset.diseno = d.id;
  document.head.appendChild(compartido); // siempre al final, para que gane sobre el CSS del diseño
  try { localStorage.setItem(CLAVE, d.id); } catch { /* sin almacenamiento */ }
}
