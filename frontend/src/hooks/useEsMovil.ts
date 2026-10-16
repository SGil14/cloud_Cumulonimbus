import { useEffect, useState } from "react";

const CONSULTA = "(max-width: 820px)";

export function useEsMovil(): boolean {
  const [movil, setMovil] = useState(() => window.matchMedia(CONSULTA).matches);
  useEffect(() => {
    const mq = window.matchMedia(CONSULTA);
    const alCambiar = () => setMovil(mq.matches);
    mq.addEventListener("change", alCambiar);
    return () => mq.removeEventListener("change", alCambiar);
  }, []);
  return movil;
}
