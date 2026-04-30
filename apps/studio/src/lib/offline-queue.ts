/**
 * Offline mutation queue — WS-69 PR I
 *
 * IndexedDB-backed queue for offline mutations (resolve/reply/snooze).
 * Replays via Background Sync API on reconnect; gracefully degrades
 * where Background Sync is unavailable (e.g., iOS < 16.4).
 */

const DB_NAME = "studio-offline-queue";
const DB_VERSION = 1;
const STORE_NAME = "mutations";
const SYNC_TAG = "conversation-mutations";

export interface QueuedMutation {
  id?: number;
  url: string;
  method: string;
  headers: Record<string, string>;
  body: string;
  created_at: string;
  retry_count: number;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, {
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

export async function enqueueMutation(mutation: Omit<QueuedMutation, "id" | "created_at" | "retry_count">): Promise<void> {
  const db = await openDb();
  const entry: QueuedMutation = {
    ...mutation,
    created_at: new Date().toISOString(),
    retry_count: 0,
  };
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const req = tx.objectStore(STORE_NAME).add(entry);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });

  // Register background sync if available
  if ("serviceWorker" in navigator && "SyncManager" in window) {
    try {
      const reg = await navigator.serviceWorker.ready;
      await (reg as ServiceWorkerRegistration & { sync?: { register: (tag: string) => Promise<void> } }).sync?.register(SYNC_TAG);
    } catch {
      // Background Sync unavailable — will retry on next page load
    }
  }
}

export async function loadQueue(): Promise<QueuedMutation[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const req = tx.objectStore(STORE_NAME).getAll();
    req.onsuccess = () => {
      db.close();
      resolve(req.result as QueuedMutation[]);
    };
    req.onerror = () => {
      db.close();
      reject(req.error);
    };
  });
}

export async function removeFromQueue(id: number): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const req = tx.objectStore(STORE_NAME).delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });
}

const MAX_RETRY = 3;

export async function replayQueue(): Promise<void> {
  const items = await loadQueue();
  for (const item of items) {
    if (item.retry_count >= MAX_RETRY) {
      if (item.id != null) await removeFromQueue(item.id);
      continue;
    }
    try {
      const res = await fetch(item.url, {
        method: item.method,
        headers: item.headers,
        body: item.body,
      });
      if (res.ok || res.status === 409) {
        if (item.id != null) await removeFromQueue(item.id);
      } else {
        await incrementRetry(item.id!);
      }
    } catch {
      await incrementRetry(item.id!);
    }
  }
}

async function incrementRetry(id: number): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    const getReq = store.get(id);
    getReq.onsuccess = () => {
      const item = getReq.result as QueuedMutation | undefined;
      if (!item) {
        resolve();
        return;
      }
      item.retry_count = (item.retry_count ?? 0) + 1;
      const putReq = store.put(item);
      putReq.onsuccess = () => resolve();
      putReq.onerror = () => reject(putReq.error);
    };
    getReq.onerror = () => reject(getReq.error);
    tx.oncomplete = () => db.close();
  });
}

/** Wraps fetch: if offline, enqueues the mutation and returns a synthetic 202. */
export async function fetchOrQueue(
  url: string,
  options: RequestInit,
  additionalHeaders: Record<string, string> = {},
): Promise<Response> {
  if (navigator.onLine) {
    return fetch(url, options);
  }
  await enqueueMutation({
    url,
    method: options.method ?? "POST",
    headers: { ...(options.headers as Record<string, string>), ...additionalHeaders },
    body: typeof options.body === "string" ? options.body : JSON.stringify(options.body),
  });
  return new Response(JSON.stringify({ success: true, queued: true }), {
    status: 202,
    headers: { "Content-Type": "application/json" },
  });
}
