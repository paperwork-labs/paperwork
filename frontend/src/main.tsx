import React from 'react'
import ReactDOM from 'react-dom/client'
import '@fontsource-variable/space-grotesk'
import './index.css'
import App from './App'
import { registerServiceWorker } from './pwa/register'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// Production-only: register the service worker. Dev builds skip
// registration entirely to avoid stale-asset issues during HMR.
if (import.meta.env.PROD) {
  void registerServiceWorker()
}
