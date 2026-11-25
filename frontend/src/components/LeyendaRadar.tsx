import { hora } from "../lib/format";
import type { Radar } from "../lib/types";

interface Props {
  radar: Radar;
}

export function LeyendaRadar({ radar }: Props) {
  return (
    <p className="leyenda-radar" title="El radar ve gotas en el aire: puede mostrar lluvia que no llega al suelo. Solo se dibujan los ecos moderados o fuertes.">
      <i aria-hidden />
      Radar · lluvia en el aire · {hora(radar.capturado_en ?? radar.obtenido_en)}
    </p>
  );
}
