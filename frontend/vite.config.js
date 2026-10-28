import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/workflows': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/executions': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/recovery-plans': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/api/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
  },
})
