// Track M.7 — shared install-prompt hook.
//
// Identical semantics to the AxiomFolio original (30-day dismissal,
// 30-second session gate, iOS-Safari instructions, appinstalled
// detection) — consuming apps just configure a storage key so two
// installed PWAs on the same host don't share dismissal state.

import { useCallback, useEffect, useRef, useState } from "react";

import { isIos, isStandalone } from "./displayMode";

interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{
    outcome: "accepted" | "dismissed";
    platform: string;
  }>;
  prompt: () => Promise<void>;
}

export interface UsePWAInstallableOptions {
  /**
   * localStorage key used to persist the dismissal. Consumers MUST pass
   * a distinct key per app so AxiomFolio's "not now" doesn't silence
   * Studio's prompt (and vice versa).
   */
  dismissKey: string;
  /** How long a dismissal lasts. Default 30 days. */
  dismissDurationMs?: number;
  /** Minimum session time before we surface the prompt. Default 30 s. */
  minSessionMs?: number;
}

export interface UsePWAInstallableResult {
  canPrompt: boolean;
  installed: boolean;
  isIosSafari: boolean;
  promptInstall: () => Promise<"accepted" | "dismissed" | "unavailable">;
  dismiss: () => void;
}

const DEFAULT_DISMISS_MS = 30 * 24 * 60 * 60 * 1000;
const DEFAULT_MIN_SESSION_MS = 30 * 1000;

function readDismissedUntil(key: string): number {
  if (typeof window === "undefined") return 0;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return 0;
    const parsed = Number.parseInt(raw, 10);
    return Number.isFinite(parsed) ? parsed : 0;
  } catch {
    return 0;
  }
}

function writeDismissedUntil(key: string, epochMs: number): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, String(epochMs));
  } catch {
    // Private mode / quota exceeded — cost is just that the prompt may
    // reappear next session. Non-critical.
  }
}

export function usePWAInstallable(
  options: UsePWAInstallableOptions,
): UsePWAInstallableResult {
  const {
    dismissKey,
    dismissDurationMs = DEFAULT_DISMISS_MS,
    minSessionMs = DEFAULT_MIN_SESSION_MS,
  } = options;

  const deferredPromptRef = useRef<BeforeInstallPromptEvent | null>(null);
  const [hasDeferredPrompt, setHasDeferredPrompt] = useState(false);
  const [installed, setInstalled] = useState<boolean>(() => isStandalone());
  const [sessionElapsed, setSessionElapsed] = useState(false);
  const [dismissedUntil, setDismissedUntil] = useState<number>(() =>
    readDismissedUntil(dismissKey),
  );

  const isIosSafari =
    typeof window !== "undefined" && isIos() && !installed;

  useEffect(() => {
    if (typeof window === "undefined") return;

    const onBeforeInstall = (event: Event) => {
      event.preventDefault();
      deferredPromptRef.current = event as BeforeInstallPromptEvent;
      setHasDeferredPrompt(true);
    };

    const onAppInstalled = () => {
      deferredPromptRef.current = null;
      setHasDeferredPrompt(false);
      setInstalled(true);
    };

    window.addEventListener(
      "beforeinstallprompt",
      onBeforeInstall as EventListener,
    );
    window.addEventListener("appinstalled", onAppInstalled);
    return () => {
      window.removeEventListener(
        "beforeinstallprompt",
        onBeforeInstall as EventListener,
      );
      window.removeEventListener("appinstalled", onAppInstalled);
    };
  }, []);

  useEffect(() => {
    if (sessionElapsed) return;
    const handle = window.setTimeout(
      () => setSessionElapsed(true),
      minSessionMs,
    );
    return () => window.clearTimeout(handle);
  }, [sessionElapsed, minSessionMs]);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const onVisibility = () => {
      if (document.visibilityState === "visible" && isStandalone()) {
        setInstalled(true);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  const promptInstall = useCallback(async (): Promise<
    "accepted" | "dismissed" | "unavailable"
  > => {
    const evt = deferredPromptRef.current;
    if (!evt) return "unavailable";
    try {
      await evt.prompt();
      const choice = await evt.userChoice;
      deferredPromptRef.current = null;
      setHasDeferredPrompt(false);
      if (choice.outcome === "dismissed") {
        const until = Date.now() + dismissDurationMs;
        writeDismissedUntil(dismissKey, until);
        setDismissedUntil(until);
      }
      return choice.outcome;
    } catch {
      return "unavailable";
    }
  }, [dismissKey, dismissDurationMs]);

  const dismiss = useCallback(() => {
    const until = Date.now() + dismissDurationMs;
    writeDismissedUntil(dismissKey, until);
    setDismissedUntil(until);
    deferredPromptRef.current = null;
    setHasDeferredPrompt(false);
  }, [dismissKey, dismissDurationMs]);

  const dismissedActive = dismissedUntil > Date.now();
  const canPrompt =
    !installed &&
    sessionElapsed &&
    !dismissedActive &&
    (hasDeferredPrompt || isIosSafari);

  return { canPrompt, installed, isIosSafari, promptInstall, dismiss };
}
