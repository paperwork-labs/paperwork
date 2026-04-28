import * as React from "react";

/** Mirrors apps/axiomfolio theme/colorMode API for Storybook-only use (no cross-app imports). */
export type ColorMode = "light" | "dark";
export type ColorModePreference = ColorMode | "system";

type Ctx = {
  colorMode: ColorMode;
  colorModePreference: ColorModePreference;
  setColorModePreference: (pref: ColorModePreference) => void;
  setColorMode: (mode: ColorMode) => void;
  toggleColorMode: () => void;
};

const ColorModeContext = React.createContext<Ctx | null>(null);

const STORAGE_KEY = "qm.colorModePreference";
const LEGACY_STORAGE_KEY = "qm.colorMode";

function applyToDom(mode: ColorMode) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.toggle("dark", mode === "dark");
  root.classList.toggle("light", mode === "light");
}

function readSystemMode(): ColorMode {
  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches;
  return prefersDark ? "dark" : "light";
}

function readInitialPreference(): ColorModePreference {
  if (typeof window === "undefined") return "system";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "system" || stored === "light" || stored === "dark") return stored;
  const legacy = window.localStorage.getItem(LEGACY_STORAGE_KEY);
  if (legacy === "light" || legacy === "dark") {
    try {
      window.localStorage.setItem(STORAGE_KEY, legacy);
      window.localStorage.removeItem(LEGACY_STORAGE_KEY);
    } catch {
      // ignore
    }
    return legacy;
  }
  return "system";
}

export function ColorModeProvider({ children }: { children: React.ReactNode }) {
  const [colorModePreference, setColorModePreferenceState] = React.useState<ColorModePreference>(() =>
    readInitialPreference()
  );
  const [colorMode, setColorModeState] = React.useState<ColorMode>(() => {
    if (typeof window === "undefined") return "dark";
    const pref = readInitialPreference();
    return pref === "system" ? readSystemMode() : pref;
  });

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!mq) return;
    if (colorModePreference !== "system") return;

    const handler = () => setColorModeState(readSystemMode());
    try {
      (mq as MediaQueryList).addEventListener?.("change", handler);
    } catch {
      // ignore
    }
    try {
      (mq as MediaQueryList & { addListener?: (h: () => void) => void }).addListener?.(handler);
    } catch {
      // ignore
    }
    return () => {
      try {
        (mq as MediaQueryList).removeEventListener?.("change", handler);
      } catch {
        // ignore
      }
      try {
        (mq as MediaQueryList & { removeListener?: (h: () => void) => void }).removeListener?.(handler);
      } catch {
        // ignore
      }
    };
  }, [colorModePreference]);

  const setColorModePreference = React.useCallback((pref: ColorModePreference) => {
    setColorModePreferenceState(pref);
    const effective = pref === "system" ? readSystemMode() : pref;
    setColorModeState(effective);
    try {
      window.localStorage.setItem(STORAGE_KEY, pref);
    } catch {
      // ignore
    }
    applyToDom(effective);
  }, []);

  const setColorMode = React.useCallback(
    (mode: ColorMode) => {
      setColorModePreference(mode);
    },
    [setColorModePreference]
  );

  const toggleColorMode = React.useCallback(() => {
    const next: ColorMode = colorMode === "dark" ? "light" : "dark";
    setColorModePreference(next);
  }, [colorMode, setColorModePreference]);

  React.useEffect(() => {
    applyToDom(colorMode);
  }, [colorMode]);

  const value = React.useMemo<Ctx>(
    () => ({ colorMode, colorModePreference, setColorModePreference, setColorMode, toggleColorMode }),
    [colorMode, colorModePreference, setColorModePreference, setColorMode, toggleColorMode]
  );

  return <ColorModeContext.Provider value={value}>{children}</ColorModeContext.Provider>;
}

export function useColorMode() {
  const ctx = React.useContext(ColorModeContext);
  if (!ctx) {
    throw new Error("useColorMode must be used within ColorModeProvider");
  }
  return ctx;
}
