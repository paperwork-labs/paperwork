"use client";

/**
 * AppBadgeManager — WS-69 PR I
 *
 * Mounts on the Conversations page. Polls /api/admin/conversations/unread-count
 * every 60s and calls navigator.setAppBadge(count).
 * Clears the badge (navigator.clearAppBadge) when called with clearOnMount=true.
 * Graceful no-op when the Badging API is not supported.
 */

import { useEffect, useRef, useState } from "react";
import { isBadgingSupported } from "@/lib/web-push";

interface Props {
  /** When true, clears the badge immediately on mount (e.g., inbox is open). */
  clearOnMount?: boolean;
}

const POLL_INTERVAL_MS = 60_000;

export function AppBadgeManager({ clearOnMount = false }: Props) {
  const [count, setCount] = useState<number | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchAndSet = async () => {
    try {
      const res = await fetch("/api/admin/conversations/unread-count");
      if (!res.ok) return;
      const json = (await res.json()) as { data?: { count?: number } };
      const n = json.data?.count ?? 0;
      setCount(n);
      if (isBadgingSupported()) {
        if (n > 0) {
          navigator.setAppBadge(n).catch(() => {});
        } else {
          navigator.clearAppBadge().catch(() => {});
        }
      }
    } catch {
      // Network error — leave badge as-is
    }
  };

  useEffect(() => {
    if (clearOnMount && isBadgingSupported()) {
      navigator.clearAppBadge().catch(() => {});
    }

    void fetchAndSet();
    intervalRef.current = setInterval(() => {
      void fetchAndSet();
    }, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [clearOnMount]); // eslint-disable-line react-hooks/exhaustive-deps

  // This component renders nothing visible; badge state is managed via the API
  return null;
}

/** Hook version for components that just need the current unread count. */
export function useUnreadCount(): number {
  const [count, setCount] = useState(0);
  useEffect(() => {
    fetch("/api/admin/conversations/unread-count")
      .then((r) => r.json())
      .then((j: { data?: { count?: number } }) => setCount(j.data?.count ?? 0))
      .catch(() => {});
  }, []);
  return count;
}
