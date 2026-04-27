import React from "react";

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
  // Chakra v3 defaultConfig uses `.dark &` for dark styles.
  root.classList.toggle("dark", mode === "dark");
  // Keep a light marker for completeness (Chakra's light condition includes `.light &`).
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
  // Back-compat: previous builds stored the effective mode directly.
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

  // Track OS changes when user is in "system" mode.
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!mq) return;
    if (colorModePreference !== "system") return;

    const handler = () => setColorModeState(readSystemMode());
    // Safari uses addListener/removeListener; modern browsers use addEventListener.
    try {
      (mq as any).addEventListener?.("change", handler);
    } catch {
      // ignore
    }
    try {
      (mq as any).addListener?.(handler);
    } catch {
      // ignore
    }
    return () => {
      try {
        (mq as any).removeEventListener?.("change", handler);
      } catch {
        // ignore
      }
      try {
        (mq as any).removeListener?.(handler);
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

  const setColorMode = React.useCallback((mode: ColorMode) => {
    setColorModePreference(mode);
  }, [setColorModePreference]);

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


