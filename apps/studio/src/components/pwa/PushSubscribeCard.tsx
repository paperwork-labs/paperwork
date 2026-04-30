"use client";

/**
 * PushSubscribeCard — WS-69 PR I
 *
 * Settings UI for web push subscription management:
 * - Shows when Notification.permission === "default" or when explicitly toggling
 * - "Enable push notifications" button → subscribePush flow
 * - Status display (granted / denied / default)
 * - Unsubscribe button when subscribed
 * - iOS quirk note: must be installed via Add to Home Screen before push works
 */

import { Bell, BellOff, BellRing, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  getCurrentSubscription,
  isPushSupported,
  subscribePush,
  unsubscribePush,
} from "@/lib/web-push";

type Status = "loading" | "unsupported" | "default" | "granted" | "denied";

export function PushSubscribeCard() {
  const [status, setStatus] = useState<Status>("loading");
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isWorking, setIsWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!isPushSupported()) {
      setStatus("unsupported");
      return;
    }
    const perm = Notification.permission as NotificationPermission;
    setStatus(perm as Status);
    getCurrentSubscription()
      .then((sub) => setIsSubscribed(!!sub))
      .catch(() => {});
  }, []);

  const handleSubscribe = useCallback(async () => {
    setIsWorking(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/web-push/vapid-public-key");
      if (!res.ok) throw new Error("Could not fetch VAPID key — Brain may be unconfigured.");
      const json = (await res.json()) as { data?: { vapid_public_key?: string } };
      const vapidPublicKey = json.data?.vapid_public_key;
      if (!vapidPublicKey) throw new Error("VAPID key missing from Brain response.");

      const sub = await subscribePush(vapidPublicKey);
      if (!sub) throw new Error("Subscription cancelled or browser blocked notifications.");

      const subJson = sub.toJSON();
      const p256dh = subJson.keys?.p256dh ?? "";
      const auth = subJson.keys?.auth ?? "";

      const postRes = await fetch("/api/admin/web-push/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: sub.endpoint, p256dh, auth }),
      });
      if (!postRes.ok) throw new Error("Failed to register subscription with Brain.");

      setIsSubscribed(true);
      setStatus("granted");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsWorking(false);
    }
  }, []);

  const handleUnsubscribe = useCallback(async () => {
    setIsWorking(true);
    setError(null);
    try {
      const endpoint = await unsubscribePush();
      if (endpoint) {
        await fetch("/api/admin/web-push/unsubscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ endpoint }),
        });
      }
      setIsSubscribed(false);
      setStatus("default");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsWorking(false);
    }
  }, []);

  if (status === "loading") return null;

  if (status === "unsupported") {
    return (
      <div className="rounded-xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
        <span className="flex items-center gap-2">
          <BellOff className="size-4 shrink-0" />
          Push notifications are not supported in this browser.
        </span>
      </div>
    );
  }

  if (status === "denied") {
    return (
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
        <span className="flex items-center gap-2">
          <BellOff className="size-4 shrink-0" />
          Notifications are blocked. Enable them in your browser settings to receive Brain alerts.
        </span>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card px-4 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
            {isSubscribed ? (
              <BellRing className="size-4 text-emerald-400" />
            ) : (
              <Bell className="size-4 text-muted-foreground" />
            )}
            Push notifications
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {isSubscribed
              ? "You'll receive alerts when Brain creates high-priority conversations."
              : "Get notified when Brain needs your attention — even with Studio closed."}
          </p>
          {!isSubscribed && (
            <p className="mt-1 text-xs text-muted-foreground/70">
              On iOS: install Studio via{" "}
              <span className="font-medium text-muted-foreground">Add to Home Screen</span> first
              (requires iOS 16.4+).
            </p>
          )}
          {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
        </div>
        <div className="shrink-0">
          {isSubscribed ? (
            <button
              type="button"
              onClick={handleUnsubscribe}
              disabled={isWorking}
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border px-3 text-xs text-muted-foreground transition hover:border-foreground/40 hover:text-foreground disabled:opacity-50"
            >
              {isWorking ? <Loader2 className="size-3 animate-spin" /> : <BellOff className="size-3" />}
              Unsubscribe
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubscribe}
              disabled={isWorking}
              className="inline-flex h-8 items-center gap-1.5 rounded-md bg-foreground px-3 text-xs font-medium text-background transition hover:bg-foreground/90 disabled:opacity-50"
            >
              {isWorking ? <Loader2 className="size-3 animate-spin" /> : <Bell className="size-3" />}
              Enable push
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
