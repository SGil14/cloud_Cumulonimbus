import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En desarrollo, las llamadas a /api se reenvían al backend (iniciar.bat, puerto 8000).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": process.env.API_URL ?? "http://localhost:8000" },
  },
  build: { chunkSizeWarningLimit: 1200 },
});
