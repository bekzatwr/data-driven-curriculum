import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// В разработке /api проксируется на локальный FastAPI (python scripts/start.py --dev).
const apiTarget = process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
});
