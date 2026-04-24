import { useEffect, useMemo, useSyncExternalStore } from "react";
import { useAuthOptional } from "../context/AuthContext";

export type TableDensity = "comfortable" | "compact";
export type ColorPalette = "default" | "cb";

const COLOR_PALETTE_STORAGE_KEY = "axiomfolio:color-palette";
const COLOR_PALETTE_EVENT = "axiomfolio:color-palette-change";

function readPersistedPalette(): ColorPalette {
  if (typeof window === "undefined") return "default";
  try {
    return window.localStorage.getItem(COLOR_PALETTE_STORAGE_KEY) === "cb"
      ? "cb"
      : "default";
  } catch {
    return "default";
  }
}

// External-store subscription for the persisted palette value. This lets
// `useUserPreferences()` consumers re-render the moment
// `setColorPalettePreference()` is called in the same tab (via our custom
// event) AND when other tabs change it (via the native `storage` event).
function subscribePersistedPalette(notify: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  const handleStorage = (e: StorageEvent) => {
    if (e.key === null || e.key === COLOR_PALETTE_STORAGE_KEY) notify();
  };
  window.addEventListener("storage", handleStorage);
  window.addEventListener(COLOR_PALETTE_EVENT, notify);
  return () => {
    window.removeEventListener("storage", handleStorage);
    window.removeEventListener(COLOR_PALETTE_EVENT, notify);
  };
}

export function useUserPreferences(): {
  currency: string;
  timezone: string;
  tableDensity: TableDensity;
  coverageHistogramWindowDays: number | null;
  colorPalette: ColorPalette;
} {
  const auth = useAuthOptional();
  const user = auth?.user ?? null;

  // Subscribe to localStorage changes so the hook re-renders when
  // `setColorPalettePreference()` is invoked imperatively. Server-stored
  // preference still wins below; this only matters for unauthed users.
  const persistedPalette = useSyncExternalStore(
    subscribePersistedPalette,
    readPersistedPalette,
    () => "default" as ColorPalette,
  );

  const prefs = useMemo(() => {
    const currency = (user?.currency_preference || "USD").toUpperCase();
    const timezone = user?.timezone || "America/Los_Angeles";
    const td = user?.ui_preferences?.table_density;
    const tableDensity: TableDensity = td === "compact" ? "compact" : "comfortable";
    const raw = Number(user?.ui_preferences?.coverage_histogram_window_days);
    const coverageHistogramWindowDays =
      Number.isFinite(raw) && raw > 0 ? raw : null;
    // Server-stored preference wins; localStorage is the fallback for
    // unauthenticated users (so the toggle persists across sessions).
    const serverPref = user?.ui_preferences?.color_palette;
    const colorPalette: ColorPalette =
      serverPref === "cb"
        ? "cb"
        : serverPref === "default"
          ? "default"
          : persistedPalette;
    return { currency, timezone, tableDensity, coverageHistogramWindowDays, colorPalette };
  }, [
    user?.currency_preference,
    user?.timezone,
    user?.ui_preferences?.table_density,
    user?.ui_preferences?.coverage_histogram_window_days,
    user?.ui_preferences?.color_palette,
    persistedPalette,
  ]);

  // Apply the palette to the document root so the `[data-palette="cb"]`
  // CSS variable overrides take effect for every chart at once.
  useEffect(() => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    if (prefs.colorPalette === "cb") {
      root.setAttribute("data-palette", "cb");
    } else {
      root.removeAttribute("data-palette");
    }
  }, [prefs.colorPalette]);

  return prefs;
}

/**
 * Imperative setter for the color-blind palette toggle. Persists to
 * localStorage immediately so the change survives a reload even when no
 * user-preferences PATCH has been sent to the server yet.
 */
export function setColorPalettePreference(palette: ColorPalette): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(COLOR_PALETTE_STORAGE_KEY, palette);
  } catch {
    // localStorage may be unavailable (private mode, etc.); ignore.
  }
  if (typeof document !== "undefined") {
    const root = document.documentElement;
    if (palette === "cb") root.setAttribute("data-palette", "cb");
    else root.removeAttribute("data-palette");
  }
  // Native `storage` events do NOT fire in the same tab that wrote the value,
  // so we dispatch a custom event for in-tab subscribers (the
  // `useUserPreferences` hook listens for both).
  try {
    window.dispatchEvent(new Event(COLOR_PALETTE_EVENT));
  } catch {
    // Older environments without `Event` constructor; harmless to skip.
  }
}

// Used by tests via `setColorPalettePreference` and Story files that want to
// avoid magic strings; not exported in the consumer-facing API surface.
export const __COLOR_PALETTE_STORAGE_KEY = COLOR_PALETTE_STORAGE_KEY;


