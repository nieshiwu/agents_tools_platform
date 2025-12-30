import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 1234,
    proxy: {
      '/api': {
        target: 'http://192.168.0.197:8000',
        changeOrigin: true,
      }
    }
  }
})
