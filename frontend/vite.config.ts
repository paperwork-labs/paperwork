/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    headers: {
      // Avoid stale ESM module caching during fast-moving Chakra v3 migration.
      'Cache-Control': 'no-store',
    },
    proxy: {
      '/api': {
        // Use VITE_PROXY_TARGET for local dev (e.g. http://localhost:8000); default for Docker
        target: process.env.VITE_PROXY_TARGET || 'http://backend:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          chakra: ['@chakra-ui/react', '@emotion/react', '@emotion/styled', 'framer-motion'],
          recharts: ['recharts'],
          vendor: ['axios', 'lodash', 'numeral', 'socket.io-client'],
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  // @ts-expect-error - Vitest extends Vite config at runtime.
  test: {
    environment: 'happy-dom',
    setupFiles: ['./src/test/setup.ts'],
    clearMocks: true,
  },
})