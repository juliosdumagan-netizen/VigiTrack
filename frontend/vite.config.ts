import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Flask backend port. Matches VIGITRACK_PORT used by run.py (default 5000).
const backend = `http://127.0.0.1:${process.env.VIGITRACK_PORT ?? '5000'}`

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': backend,
      '/video_feed': backend,
      '/logout': backend,
    },
  },
})
