import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/transcribe': 'http://localhost:8000',
      '/status': 'http://localhost:8000',
      '/download': 'http://localhost:8000',
      '/signup': 'http://localhost:8000',
      '/login': 'http://localhost:8000',
    },
  },
})
