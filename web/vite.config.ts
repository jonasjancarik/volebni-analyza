import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The API runs separately in development (see .claude/launch.json)
const api = process.env.VOLBY_API_URL ?? "http://127.0.0.1:8600";

export default defineConfig({
  plugins: [react()],
  // MapLibre finds its worker file next to itself, which pre-bundling would break
  optimizeDeps: { exclude: ["maplibre-gl"] },
  worker: { format: "es" },
  server: {
    host: "0.0.0.0",
    port: 5180,
    strictPort: true,
    allowedHosts: true,
    proxy: { "/api": api },
  },
});
