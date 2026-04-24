// Service worker registration. Imported from main.tsx and gated to PROD
// builds so HMR / dev-server are never affected by stale precache.
//
// Update flow:
//   - On `updatefound`, the new SW transitions through "installing" → "installed".
//     Once installed AND we already have a controller, we send SKIP_WAITING so
//     the new SW activates immediately instead of waiting for all tabs to close.
//   - When `controllerchange` fires (the new SW has taken control), we reload
//     once so the page picks up the freshly cached shell.

let registrationPromise: Promise<ServiceWorkerRegistration | undefined> | null = null

export function registerServiceWorker(): Promise<ServiceWorkerRegistration | undefined> {
  if (typeof window === 'undefined') return Promise.resolve(undefined)
  if (!('serviceWorker' in navigator)) return Promise.resolve(undefined)
  if (registrationPromise) return registrationPromise

  registrationPromise = (async () => {
    try {
      const registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
        type: 'classic',
        updateViaCache: 'none',
      })

      registration.addEventListener('updatefound', () => {
        const installing = registration.installing
        if (!installing) return
        installing.addEventListener('statechange', () => {
          if (installing.state === 'installed' && navigator.serviceWorker.controller) {
            installing.postMessage({ type: 'SKIP_WAITING' })
          }
        })
      })

      let didReload = false
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (didReload) return
        didReload = true
        window.location.reload()
      })

      return registration
    } catch (err) {
      console.warn('Service worker registration failed:', err)
      return undefined
    }
  })()

  return registrationPromise
}

export async function unregisterServiceWorker(): Promise<void> {
  if (typeof window === 'undefined') return
  if (!('serviceWorker' in navigator)) return
  const registrations = await navigator.serviceWorker.getRegistrations()
  await Promise.all(registrations.map((r) => r.unregister()))
  registrationPromise = null
}
