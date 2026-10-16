import { useEffect, useState } from "react";

export type Tema = "oscuro" | "claro";
const CLAVE = "lluvia-tema";

function inicial(): Tema {
  try {
    const guardado = localStorage.getItem(CLAVE);
    if (guardado === "oscuro" || guardado === "claro") return guardado;
  } catch { /* sin almacenamiento */ }
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "claro" : "oscuro";
}

export function useTema() {
  const [tema, setTema] = useState<Tema>(inicial);

  useEffect(() => {
    document.documentElement.dataset.tema = tema;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", tema === "oscuro" ? "#0b0c0f" : "#e9e4d6");
    try { localStorage.setItem(CLAVE, tema); } catch { /* sin almacenamiento */ }
  }, [tema]);

  return { tema, alternar: () => setTema((t) => (t === "oscuro" ? "claro" : "oscuro")) };
}
