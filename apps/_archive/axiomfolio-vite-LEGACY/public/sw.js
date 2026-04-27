/* AxiomFolio service worker.
 *
 * Hand-rolled instead of using vite-plugin-pwa because that plugin's 1.2.x
 * release uses createRequire('.') internally and silently aborts on Node >= 22.
 *
 * Caching strategy:
 *   - Precache the app shell + manifest + brand icons on install.
 *   - Same-origin static assets (.js, .css, .woff2, .svg): stale-while-revalidate.
 *   - Same-origin images: cache-first (immutable hashed assets).
 *   - HTML navigations: network-first with precached "/" fallback for offline.
 *   - /api/** is NEVER cached. These responses are user-scoped and stale data
 *     is dangerous (positions, balances, orders). Bypass and let the network
 *     handle (which surfaces real errors to the UI loading/error states).
 *   - WebSocket upgrades, audio/video, and cross-origin requests are bypassed.
 */

const CACHE_VERSION = 'v1'
const PRECACHE = `axf-precache-${CACHE_VERSION}`
const STATIC_CACHE = `axf-static-${CACHE_VERSION}`
const IMAGE_CACHE = `axf-images-${CACHE_VERSION}`

const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/favicon.svg',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/apple-touch-icon.png',
]

const STATIC_EXT_RE = /\.(?:js|mjs|css|woff2?|svg)$/i
const IMAGE_EXT_RE = /\.(?:png|jpg|jpeg|webp|gif|ico)$/i

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(PRECACHE)
      // Precache best-effort. If a single asset 404s in dev/preview, don't
      // let it block the whole install.
      await Promise.all(
        PRECACHE_URLS.map(async (url) => {
          try {
            const response = await fetch(url, { cache: 'no-cache' })
            if (response.ok) {
              await cache.put(url, response.clone())
            }
          } catch {
            // ignore — asset will be fetched lazily on next request
          }
        }),
      )
    })(),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keep = new Set([PRECACHE, STATIC_CACHE, IMAGE_CACHE])
      const keys = await caches.keys()
      await Promise.all(keys.filter((key) => !keep.has(key)).map((key) => caches.delete(key)))
      await self.clients.claim()
    })(),
  )
})

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

function isApiRequest(url) {
  return url.pathname.startsWith('/api/')
}

function isSameOriginGet(request, url) {
  return (
    request.method === 'GET' &&
    url.origin === self.location.origin &&
    !isApiRequest(url)
  )
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName)
  const cached = await cache.match(request)
  const networkPromise = fetch(request)
    .then((response) => {
      if (response && response.ok && response.type === 'basic') {
        cache.put(request, response.clone()).catch(() => {})
      }
      return response
    })
    .catch(() => undefined)
  return cached ?? (await networkPromise) ?? new Response('', { status: 504 })
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName)
  const cached = await cache.match(request)
  if (cached) return cached
  try {
    const response = await fetch(request)
    if (response && response.ok && response.type === 'basic') {
      cache.put(request, response.clone()).catch(() => {})
    }
    return response
  } catch {
    return new Response('', { status: 504 })
  }
}

async function navigationFallback(request) {
  try {
    const response = await fetch(request)
    if (response && response.ok) {
      const cache = await caches.open(PRECACHE)
      cache.put('/', response.clone()).catch(() => {})
      return response
    }
    return response
  } catch {
    const cache = await caches.open(PRECACHE)
    const fallback = (await cache.match('/')) || (await cache.match('/index.html'))
    return fallback ?? new Response('', { status: 504 })
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)

  if (request.method !== 'GET') return
  if (url.origin !== self.location.origin) return
  if (isApiRequest(url)) return
  if (request.headers.get('upgrade') === 'websocket') return
  if (request.destination === 'video' || request.destination === 'audio') return

  if (request.mode === 'navigate') {
    event.respondWith(navigationFallback(request))
    return
  }

  if (!isSameOriginGet(request, url)) return

  if (IMAGE_EXT_RE.test(url.pathname)) {
    event.respondWith(cacheFirst(request, IMAGE_CACHE))
    return
  }

  if (STATIC_EXT_RE.test(url.pathname)) {
    event.respondWith(staleWhileRevalidate(request, STATIC_CACHE))
    return
  }
})
