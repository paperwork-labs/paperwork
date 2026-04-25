// Track M.7 — shared utilities for detecting PWA display state.
//
// Lifted from apps/axiomfolio/src/lib/pwa/displayMode.ts so AxiomFolio,
// Studio, and any future product app can agree on "am I installed?"
// and "am I on iOS Safari?" answers. Keeping it here means we only
// have to fix the UA heuristics once when Apple breaks iPadOS
// detection again.

export type PwaDisplayMode = "standalone" | "minimal-ui" | "fullscreen" | "browser";

interface NavigatorWithStandalone extends Navigator {
  standalone?: boolean;
}

function matches(query: string): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  try {
    return window.matchMedia(query).matches;
  } catch {
    return false;
  }
}

export function getDisplayMode(): PwaDisplayMode {
  if (matches("(display-mode: fullscreen)")) return "fullscreen";
  if (matches("(display-mode: standalone)")) return "standalone";
  if (matches("(display-mode: minimal-ui)")) return "minimal-ui";
  return "browser";
}

export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  if (matches("(display-mode: standalone)") || matches("(display-mode: fullscreen)")) {
    return true;
  }
  const nav = window.navigator as NavigatorWithStandalone;
  return Boolean(nav.standalone);
}

export function isIos(): boolean {
  if (typeof window === "undefined") return false;
  const ua = window.navigator.userAgent;
  // iPadOS 13+ reports as Macintosh; the multi-touch heuristic is the
  // standard disambiguation used across the PWA ecosystem.
  const iPadOnDesktopUa =
    /Macintosh/.test(ua) &&
    typeof window.navigator.maxTouchPoints === "number" &&
    window.navigator.maxTouchPoints > 1;
  return /iPad|iPhone|iPod/.test(ua) || iPadOnDesktopUa;
}
