import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 端口固定 5173：后端 CORS 白名单（api/api.py）已放行 http://localhost:5173
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
});
