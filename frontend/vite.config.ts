/// <reference types="vitest" />
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    host: true,
    headers: {
      // Avoid stale ESM module caching during active UI migrations.
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
    // jsdom provides spec-compliant localStorage; happy-dom + Vitest 4 + some Node versions
    // left localStorage.getItem as non-function (breaks ColorModeProvider and most tests).
    environment: 'jsdom',
    setupFiles: ['./src/test/localStorage-polyfill.ts', './src/test/setup.ts'],
    clearMocks: true,
  },
})
