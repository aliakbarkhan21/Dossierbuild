import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The API runs as its own process on 8000. Proxying keeps the frontend on one
// origin in development, so there is no CORS preflight on every keystroke and
// the same relative URLs work when the built bundle is served by FastAPI.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: true },
});
