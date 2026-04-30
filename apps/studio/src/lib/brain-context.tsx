"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type BrainOrganizationContext = "personal" | "paperwork-labs" | "household";

const STORAGE_KEY = "studio.brain-org-context";

const DEFAULT_CONTEXT: BrainOrganizationContext = "paperwork-labs";

const ALLOWED = new Set<BrainOrganizationContext>([
  "personal",
  "paperwork-labs",
  "household",
]);

function parseStored(raw: string | null): BrainOrganizationContext | null {
  if (!raw) return null;
  const v = raw.trim();
  return ALLOWED.has(v as BrainOrganizationContext)
    ? (v as BrainOrganizationContext)
    : null;
}

function readStored(): string | null {
  try {
    if (
      typeof window === "undefined" ||
      typeof window.localStorage?.getItem !== "function"
    ) {
      return null;
    }
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStored(value: BrainOrganizationContext): void {
  try {
    if (
      typeof window === "undefined" ||
      typeof window.localStorage?.setItem !== "function"
    ) {
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* ignore quota / private mode */
  }
}

type BrainContextState = {
  context: BrainOrganizationContext;
  setContext: (next: BrainOrganizationContext) => void;
};

const BrainContext = createContext<BrainContextState | null>(null);

export function BrainContextProvider({ children }: { children: ReactNode }) {
  const [context, setContextState] = useState<BrainOrganizationContext>(
    DEFAULT_CONTEXT,
  );

  useEffect(() => {
    const parsed = parseStored(readStored());
    if (parsed) setContextState(parsed);
  }, []);

  const setContext = useCallback((next: BrainOrganizationContext) => {
    setContextState(next);
    writeStored(next);
  }, []);

  const value = useMemo(
    () => ({ context, setContext }),
    [context, setContext],
  );

  return (
    <BrainContext.Provider value={value}>{children}</BrainContext.Provider>
  );
}

export function useBrainContext(): BrainContextState {
  const ctx = useContext(BrainContext);
  if (!ctx) {
    throw new Error("useBrainContext must be used within BrainContextProvider");
  }
  return ctx;
}
