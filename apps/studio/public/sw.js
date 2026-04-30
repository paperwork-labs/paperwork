/**
 * Studio PWA Service Worker — WS-69 PR I
 *
 * Handles:
 * - push: show notification + bump app badge
 * - notificationclick: open conversation URL + clear badge
 * - Offline cache: Cache-First for /admin/brain/conversations GET (50-entry LRU)
 * - Background Sync: queue offline mutations and replay on reconnect
 */

/* global self, caches, clients, indexedDB */

const CACHE_NAME = "studio-conversations-v1";
const MAX_CACHE_ENTRIES = 50;
const CONVERSATIONS_URL_PATTERN = /\/admin\/brain\/conversations/;

// ---------------------------------------------------------------------------
// Install & Activate
// ---------------------------------------------------------------------------

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== CACHE_NAME)
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

// ---------------------------------------------------------------------------
// Fetch — Cache-First for conversations, network-first otherwise
// ---------------------------------------------------------------------------

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  if (!CONVERSATIONS_URL_PATTERN.test(request.url)) return;

  event.respondWith(cacheFirst(request));
});

async function cacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request.clone());
    if (response && response.status === 200) {
      await trimAndPut(cache, request, response.clone());
    }
    return response;
  } catch {
    return new Response(
      JSON.stringify({ success: false, error: "Offline — no cached data" }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    );
  }
}

async function trimAndPut(cache, request, response) {
  const keys = await cache.keys();
  if (keys.length >= MAX_CACHE_ENTRIES) {
    await cache.delete(keys[0]);
  }
  await cache.put(request, response);
}

// ---------------------------------------------------------------------------
// Push — show notification + set app badge
// ---------------------------------------------------------------------------

self.addEventListener("push", (event) => {
  if (!event.data) return;

  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: "Brain", body: event.data.text(), url: "/admin/brain/conversations" };
  }

  const title = payload.title ?? "Brain";
  const options = {
    body: payload.body ?? "",
    icon: "/brand/renders/paperclip-LOCKED-canonical-1024.png",
    badge: "/brand/renders/paperclip-LOCKED-canonical-1024.png",
    tag: payload.url ?? "brain-notification",
    data: { url: payload.url ?? "/admin/brain/conversations" },
    requireInteraction: false,
  };

  event.waitUntil(
    self.registration.showNotification(title, options).then(() => {
      const count = payload.unreadCount;
      if (typeof count === "number" && "setAppBadge" in navigator) {
        return navigator.setAppBadge(count).catch(() => {});
      }
    }),
  );
});

// ---------------------------------------------------------------------------
// Notification click — open conversation + clear badge
// ---------------------------------------------------------------------------

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url ?? "/admin/brain/conversations";

  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windowClients) => {
        for (const client of windowClients) {
          if (client.url.includes(url) && "focus" in client) {
            return client.focus();
          }
        }
        if (clients.openWindow) {
          return clients.openWindow(url);
        }
      })
      .then(() => {
        if ("clearAppBadge" in navigator) {
          return navigator.clearAppBadge().catch(() => {});
        }
      }),
  );
});

// ---------------------------------------------------------------------------
// Background Sync — replay offline mutation queue
// ---------------------------------------------------------------------------

self.addEventListener("sync", (event) => {
  if (event.tag === "conversation-mutations") {
    event.waitUntil(replayOfflineQueue());
  }
});

async function replayOfflineQueue() {
  const db = await openQueueDb();
  const tx = db.transaction("mutations", "readwrite");
  const store = tx.objectStore("mutations");
  const allRequest = store.getAll();

  await new Promise((resolve, reject) => {
    allRequest.onsuccess = () => resolve(allRequest.result);
    allRequest.onerror = () => reject(allRequest.error);
  });

  const items = allRequest.result ?? [];
  const failed = [];

  for (const item of items) {
    try {
      const res = await fetch(item.url, {
        method: item.method,
        headers: item.headers,
        body: item.body,
      });
      if (res.ok || res.status === 409) {
        const delTx = db.transaction("mutations", "readwrite");
        delTx.objectStore("mutations").delete(item.id);
      } else {
        failed.push(item);
      }
    } catch {
      failed.push(item);
    }
  }

  db.close();
  return failed;
}

function openQueueDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open("studio-offline-queue", 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("mutations")) {
        const store = db.createObjectStore("mutations", {
          keyPath: "id",
          autoIncrement: true,
        });
        store.createIndex("by_created", "created_at");
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
