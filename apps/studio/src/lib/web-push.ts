/**
 * Web Push client helpers — WS-69 PR I
 *
 * registerServiceWorker(): register /sw.js
 * subscribePush(vapidPublicKey): prompt + subscribe via PushManager
 * unsubscribePush(): remove the current PushSubscription
 */

function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return new Uint8Array([...rawData].map((char) => char.charCodeAt(0))) as Uint8Array<ArrayBuffer>;
}

export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator)) return null;
  try {
    const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
    return reg;
  } catch (err) {
    console.error("[web-push] SW registration failed:", err);
    return null;
  }
}

export async function getOrCreateRegistration(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator)) return null;
  const existing = await navigator.serviceWorker.getRegistration("/");
  if (existing) return existing;
  return registerServiceWorker();
}

export async function subscribePush(vapidPublicKey: string): Promise<PushSubscription | null> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return null;

  const reg = await getOrCreateRegistration();
  if (!reg) return null;

  await navigator.serviceWorker.ready;

  const applicationServerKey = urlBase64ToUint8Array(vapidPublicKey);
  try {
    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey,
    });
    return subscription;
  } catch (err) {
    console.error("[web-push] push subscribe failed:", err);
    return null;
  }
}

export async function unsubscribePush(): Promise<string | null> {
  if (!("serviceWorker" in navigator)) return null;
  const reg = await navigator.serviceWorker.getRegistration("/");
  if (!reg) return null;
  const sub = await reg.pushManager.getSubscription();
  if (!sub) return null;
  const endpoint = sub.endpoint;
  await sub.unsubscribe();
  return endpoint;
}

export async function getCurrentSubscription(): Promise<PushSubscription | null> {
  if (!("serviceWorker" in navigator)) return null;
  const reg = await navigator.serviceWorker.getRegistration("/");
  if (!reg) return null;
  return reg.pushManager.getSubscription();
}

export function isPushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window;
}

export function isBadgingSupported(): boolean {
  return "setAppBadge" in navigator;
}
