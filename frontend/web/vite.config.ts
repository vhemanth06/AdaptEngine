import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const api = { "/api": "http://127.0.0.1:8000" };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: api },
  preview: { proxy: api },
  build: { chunkSizeWarningLimit: 1200 }, // local demo app, served offline
});
