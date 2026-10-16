import { useState } from "react";
import { DISENOS, aplicarDiseno, disenoInicial, type Diseno } from "../disenos";

export function useDiseno() {
  const [diseno, setDiseno] = useState<Diseno>(disenoInicial);

  const siguiente = () => {
    const proximo = DISENOS[(DISENOS.indexOf(diseno) + 1) % DISENOS.length];
    aplicarDiseno(proximo);
    setDiseno(proximo);
  };

  return { diseno, siguiente };
}
