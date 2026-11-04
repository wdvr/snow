import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const chunkGroups: Record<string, string[]> = {
  vendor: ['react', 'react-dom', 'react-router-dom'],
  charts: ['recharts'],
  query: ['@tanstack/react-query'],
  map: ['leaflet', 'react-leaflet', 'react-leaflet-cluster'],
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          for (const [chunk, pkgs] of Object.entries(chunkGroups)) {
            if (pkgs.some((pkg) => id.includes(`/node_modules/${pkg}/`))) return chunk
          }
          return undefined
        },
      },
    },
  },
})
