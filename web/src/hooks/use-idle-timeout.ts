"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const ACTIVITY_EVENTS: (keyof DocumentEventMap)[] = [
  "mousedown",
  "keydown",
  "touchstart",
  "scroll",
];

interface UseIdleTimeoutOptions {
  timeoutMs: number;
  warningMs: number;
  onTimeout: () => void;
  enabled: boolean;
}

export function useIdleTimeout({
  timeoutMs,
  warningMs,
  onTimeout,
  enabled,
}: UseIdleTimeoutOptions) {
  const [showWarning, setShowWarning] = useState(false);
  const warningTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timeoutTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimers = useCallback(() => {
    if (warningTimer.current) clearTimeout(warningTimer.current);
    if (timeoutTimer.current) clearTimeout(timeoutTimer.current);
  }, []);

  const resetTimers = useCallback(() => {
    clearTimers();
    setShowWarning(false);

    if (!enabled) return;

    warningTimer.current = setTimeout(() => {
      setShowWarning(true);
    }, Math.max(0, timeoutMs - warningMs));

    timeoutTimer.current = setTimeout(() => {
      onTimeout();
    }, timeoutMs);
  }, [enabled, timeoutMs, warningMs, onTimeout, clearTimers]);

  const extend = useCallback(() => {
    resetTimers();
  }, [resetTimers]);

  useEffect(() => {
    if (!enabled) {
      clearTimers();
      setShowWarning(false);
      return;
    }

    resetTimers();

    const handler = () => {
      if (!showWarning) {
        resetTimers();
      }
    };

    ACTIVITY_EVENTS.forEach((event) =>
      document.addEventListener(event, handler, { passive: true })
    );

    return () => {
      clearTimers();
      ACTIVITY_EVENTS.forEach((event) =>
        document.removeEventListener(event, handler)
      );
    };
  }, [enabled, resetTimers, clearTimers, showWarning]);

  return { showWarning, extend, dismiss: extend };
}
