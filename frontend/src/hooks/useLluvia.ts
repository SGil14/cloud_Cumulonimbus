import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Estacion, LimitesLocalidades, Radar, Resumen } from "../lib/types";

interface Estado {
  resumen: Resumen | null;
  estaciones: Estacion[];
  limites: LimitesLocalidades | null;
  radar: Radar | null;
  cargando: boolean;
  error: string | null;
}

/** Carga el estado de la lluvia. No se actualiza solo: solo al abrir o al pulsar «Actualizar». */
export function useLluvia() {
  const [estado, setEstado] = useState<Estado>({
    resumen: null, estaciones: [], limites: null, radar: null, cargando: true, error: null,
  });

  const cargar = useCallback(async (actualizar: boolean) => {
    setEstado((e) => ({ ...e, cargando: true, error: null }));
    try {
      // Primero /estaciones: así /resumen reutiliza la misma lectura del SAB.
      const est = await api.estaciones(actualizar);
      // El radar es un extra: si falla, la app sigue funcionando sin él.
      const [resumen, limites, radar] = await Promise.all([
        api.resumen(), api.localidades(), api.radar().catch(() => null),
      ]);
      setEstado({ resumen, estaciones: est.estaciones, limites, radar, cargando: false, error: null });
    } catch (e) {
      setEstado((s) => ({ ...s, cargando: false, error: e instanceof Error ? e.message : "Error desconocido" }));
    }
  }, []);

  useEffect(() => {
    void cargar(false);
  }, [cargar]);

  return { ...estado, actualizar: () => cargar(true) };
}
