import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],

  server: {
    proxy: {
      "/auth": {
        target: backend,
        changeOrigin: true,
      },

      "/workflows": {
        target: backend,
        changeOrigin: true,
      },

      "/executions": {
        target: backend,
        changeOrigin: true,
      },

      "/recovery-plans": {
        target: backend,
        changeOrigin: true,
      },

      "/api/v1": {
        target: backend,
        changeOrigin: true,
      },

      "/health": {
        target: backend,
        changeOrigin: true,
      },
    },
  },
});
