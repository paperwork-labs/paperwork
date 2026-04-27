/**
 * Cross-tab single-flight for POST /auth/refresh: one tab holds a short-lived
 * localStorage lock and broadcasts the new access token via BroadcastChannel
 * (with storage-event fallback) so other tabs do not race the rotation cookie.
 */

const LOCK_KEY = 'axiomfolio_auth_refresh_lock_v1';
const TOKEN_BROADCAST_KEY = 'axiomfolio_auth_refresh_token_v1';
const BC_NAME = 'axiomfolio-auth';

const TAB_ID =
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

export type AuthRefreshBcMessage =
  | { type: 'refresh-start'; tabId: string }
  | { type: 'refresh-complete'; accessToken: string }
  | { type: 'refresh-failed' };

let bcInst: BroadcastChannel | null = null;

function getBC(): BroadcastChannel | null {
  if (typeof BroadcastChannel === 'undefined') {
    return null;
  }
  if (!bcInst) {
    bcInst = new BroadcastChannel(BC_NAME);
  }
  return bcInst;
}

/** Test helper: close channel so Vitest workers do not leak listeners. */
export function resetAuthRefreshCoordinationForTests(): void {
  try {
    bcInst?.close();
  } catch {
    /* ignore */
  }
  bcInst = null;
}

export function tryAcquireRefreshLock(ttlMs: number): boolean {
  const now = Date.now();
  try {
    const raw = localStorage.getItem(LOCK_KEY);
    const held = raw ? (JSON.parse(raw) as { id: string; t: number }) : null;
    if (held && now - held.t < ttlMs && held.id !== TAB_ID) {
      return false;
    }
    localStorage.setItem(LOCK_KEY, JSON.stringify({ id: TAB_ID, t: now }));
    const v = JSON.parse(localStorage.getItem(LOCK_KEY) || 'null') as { id: string } | null;
    return v?.id === TAB_ID;
  } catch {
    return true;
  }
}

export function releaseRefreshLock(): void {
  try {
    const raw = localStorage.getItem(LOCK_KEY);
    const held = raw ? (JSON.parse(raw) as { id: string }) : null;
    if (held?.id === TAB_ID) {
      localStorage.removeItem(LOCK_KEY);
    }
  } catch {
    /* ignore */
  }
}

export function readRecentBroadcastToken(maxAgeMs: number): string | null {
  try {
    const raw = localStorage.getItem(TOKEN_BROADCAST_KEY);
    if (!raw) {
      return null;
    }
    const d = JSON.parse(raw) as { accessToken?: string; t?: number };
    if (d?.accessToken && typeof d.t === 'number' && Date.now() - d.t < maxAgeMs) {
      return d.accessToken;
    }
  } catch {
    /* ignore */
  }
  return null;
}

function broadcastRefreshComplete(accessToken: string): void {
  const msg: AuthRefreshBcMessage = { type: 'refresh-complete', accessToken };
  try {
    getBC()?.postMessage(msg);
  } catch {
    /* ignore */
  }
  try {
    localStorage.setItem(
      TOKEN_BROADCAST_KEY,
      JSON.stringify({ accessToken, t: Date.now(), nonce: Math.random() }),
    );
  } catch {
    /* ignore */
  }
}

function broadcastRefreshFailed(): void {
  try {
    getBC()?.postMessage({ type: 'refresh-failed' } satisfies AuthRefreshBcMessage);
  } catch {
    /* ignore */
  }
}

function broadcastRefreshStart(): void {
  try {
    getBC()?.postMessage({ type: 'refresh-start', tabId: TAB_ID } satisfies AuthRefreshBcMessage);
  } catch {
    /* ignore */
  }
}

function waitForPeerRefreshToken(timeoutMs: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      cleanup();
      reject(new Error('cross-tab refresh timeout'));
    }, timeoutMs);

    const onBc = (ev: MessageEvent<AuthRefreshBcMessage>) => {
      const d = ev.data;
      if (!d || typeof d !== 'object') {
        return;
      }
      if (d.type === 'refresh-complete' && typeof d.accessToken === 'string') {
        cleanup();
        resolve(d.accessToken);
      }
      if (d.type === 'refresh-failed') {
        cleanup();
        reject(new Error('peer refresh failed'));
      }
    };

    const onStorage = (e: StorageEvent) => {
      if (e.key !== TOKEN_BROADCAST_KEY || !e.newValue) {
        return;
      }
      try {
        const d = JSON.parse(e.newValue) as { accessToken?: string };
        if (d?.accessToken) {
          cleanup();
          resolve(d.accessToken);
        }
      } catch {
        /* ignore */
      }
    };

    const bc = getBC();
    bc?.addEventListener('message', onBc);
    window.addEventListener('storage', onStorage);

    function cleanup(): void {
      window.clearTimeout(timer);
      bc?.removeEventListener('message', onBc);
      window.removeEventListener('storage', onStorage);
    }
  });
}

export interface DistributedRefreshOptions {
  lockTtlMs?: number;
  waitPeerMs?: number;
  /** How long a broadcast token remains readable for tabs that missed the event. */
  broadcastReadMaxAgeMs?: number;
}

/**
 * Runs ``doRefresh`` in at most one tab at a time (localStorage lock). Other
 * tabs wait for BroadcastChannel / storage. After ``waitPeerMs``, a waiter may
 * acquire the lock and refresh (backend grace window covers stale cookies).
 */
export async function performDistributedTokenRefresh(
  doRefresh: () => Promise<string>,
  opts?: DistributedRefreshOptions,
): Promise<string> {
  const lockTtl = opts?.lockTtlMs ?? 15_000;
  const waitPeer = opts?.waitPeerMs ?? 5_000;
  const readRecent = opts?.broadcastReadMaxAgeMs ?? 4_000;

  if (tryAcquireRefreshLock(lockTtl)) {
    broadcastRefreshStart();
    try {
      const token = await doRefresh();
      broadcastRefreshComplete(token);
      return token;
    } catch (e) {
      broadcastRefreshFailed();
      throw e;
    } finally {
      releaseRefreshLock();
    }
  }

  const instant = readRecentBroadcastToken(readRecent);
  if (instant) {
    return instant;
  }

  try {
    return await waitForPeerRefreshToken(waitPeer);
  } catch {
    if (tryAcquireRefreshLock(lockTtl)) {
      broadcastRefreshStart();
      try {
        const token = await doRefresh();
        broadcastRefreshComplete(token);
        return token;
      } catch (e) {
        broadcastRefreshFailed();
        throw e;
      } finally {
        releaseRefreshLock();
      }
    }
    const late = readRecentBroadcastToken(readRecent);
    if (late) {
      return late;
    }
    return await waitForPeerRefreshToken(3_000);
  }
}
