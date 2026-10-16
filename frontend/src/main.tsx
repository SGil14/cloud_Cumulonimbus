import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { aplicarDiseno, disenoInicial } from "./disenos";

aplicarDiseno(disenoInicial());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
