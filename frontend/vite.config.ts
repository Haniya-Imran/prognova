import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development, /api goes to the local FastAPI server, so the app uses the
// same relative URLs locally and on Vercel.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
  preview: { proxy: { '/api': 'http://localhost:8000' } },
  build: { chunkSizeWarningLimit: 5000 },
})
