"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Skeleton } from "@paperwork-labs/ui";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

const ActiveTabContext = React.createContext<string | null>(null);

/**
 * Read the active tab id from the nearest TabbedPageShellNext. Useful for
 * gating data fetches to only run when the relevant tab is visible.
 */
export function useActiveTab<T extends string>(): T {
  const v = React.useContext(ActiveTabContext);
  if (v == null) {
    throw new Error("useActiveTab must be used within TabbedPageShellNext");
  }
  return v as T;
}

// ---------------------------------------------------------------------------
// Variant A — Lazy Client Component tabs
// ---------------------------------------------------------------------------
// Use this when tab bodies are Client Components that you want to lazy-load.

export type LazyTabbedShellTabDef<T extends string> = {
  id: T;
  label: string;
  /** Lazy tab body — wrapped in Suspense + error boundary by the shell. */
  Content: React.LazyExoticComponent<React.ComponentType>;
};

export type TabbedPageShellNextProps<T extends string> = {
  tabs: readonly LazyTabbedShellTabDef<T>[];
  defaultTab: T;
  /** URL search-param key used to persist the active tab (default: "tab"). */
  paramKey?: string;
  className?: string;
  /** Optional controls rendered beside the tab list. */
  endAdornment?: React.ReactNode;
};

// ---------------------------------------------------------------------------
// Variant B — Pre-rendered Server Component tab content (slot pattern)
// ---------------------------------------------------------------------------
// Use this when tab bodies are Server Components whose content is pre-fetched
// and passed as React nodes from a parent Server Component.

export type NodeTabbedShellTabDef<T extends string> = {
  id: T;
  label: string;
  content: React.ReactNode;
};

export type TabbedPageShellNodeProps<T extends string> = {
  tabs: readonly NodeTabbedShellTabDef<T>[];
  defaultTab: T;
  paramKey?: string;
  className?: string;
  endAdornment?: React.ReactNode;
};

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function TabPanelSkeleton() {
  return (
    <div className="flex flex-col gap-3 py-4" aria-busy="true" aria-label="Loading tab">
      <Skeleton className="h-8 w-full max-w-md rounded-md" />
      <Skeleton className="h-[200px] w-full rounded-lg" />
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 rounded-lg" />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Simple error boundary for tab panels
// ---------------------------------------------------------------------------

type ErrorBoundaryState = { hasError: boolean; message: string };

class TabErrorBoundary extends React.Component<
  React.PropsWithChildren<{ label: string }>,
  ErrorBoundaryState
> {
  constructor(props: React.PropsWithChildren<{ label: string }>) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(err: unknown): ErrorBoundaryState {
    return { hasError: true, message: err instanceof Error ? err.message : "Unknown error" };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          className="rounded-lg border border-border bg-muted/30 p-4 text-sm text-muted-foreground"
        >
          This tab failed to render — {this.state.message}. Try another tab or reload the page.
        </div>
      );
    }
    return this.props.children;
  }
}

// ---------------------------------------------------------------------------
// Shared tab bar hook
// ---------------------------------------------------------------------------

function useTabBar<T extends string>(
  tabIds: readonly T[],
  defaultTab: T,
  paramKey: string,
) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const allowed = React.useMemo(() => new Set(tabIds), [tabIds]);

  const replaceSearchParams = React.useCallback(
    (updater: (prev: URLSearchParams) => URLSearchParams) => {
      const prev = new URLSearchParams(searchParams.toString());
      const next = updater(prev);
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname);
    },
    [pathname, router, searchParams],
  );

  const raw = searchParams.get(paramKey) ?? "";
  const resolved: T = (allowed.has(raw as T) ? raw : defaultTab) as T;

  React.useEffect(() => {
    const isValid = raw !== "" && allowed.has(raw as T);
    if (isValid) return;
    replaceSearchParams((prev) => {
      const p = new URLSearchParams(prev);
      p.set(paramKey, defaultTab);
      return p;
    });
  }, [allowed, defaultTab, paramKey, raw, replaceSearchParams]);

  const setTab = React.useCallback(
    (next: T) => {
      if (!allowed.has(next)) return;
      replaceSearchParams((prev) => {
        const p = new URLSearchParams(prev);
        p.set(paramKey, next);
        return p;
      });
    },
    [allowed, paramKey, replaceSearchParams],
  );

  return { resolved, setTab };
}

// ---------------------------------------------------------------------------
// Shared tab list renderer
// ---------------------------------------------------------------------------

function TabList<T extends string>({
  tabs,
  resolved,
  setTab,
  endAdornment,
}: {
  tabs: readonly { id: T; label: string }[];
  resolved: T;
  setTab: (id: T) => void;
  endAdornment?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
      <div
        role="tablist"
        aria-label="Page sections"
        className="flex flex-wrap gap-1 border-b border-border"
      >
        {tabs.map((t) => {
          const isActive = t.id === resolved;
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={isActive}
              aria-controls={`tabpanel-${t.id}`}
              id={`tab-${t.id}`}
              onClick={() => setTab(t.id)}
              className={[
                "relative px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                "after:absolute after:bottom-[-1px] after:left-0 after:right-0 after:h-0.5 after:rounded-t-sm after:transition-opacity",
                isActive
                  ? "text-foreground after:bg-foreground after:opacity-100"
                  : "text-muted-foreground after:opacity-0 hover:text-foreground",
              ].join(" ")}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      {endAdornment ? (
        <div className="flex flex-wrap items-center gap-2">{endAdornment}</div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TabbedPageShellNext — Variant A (lazy client components)
// ---------------------------------------------------------------------------

/**
 * Studio-side tabbed page shell that wires Next.js routing to tab state.
 * Use when your tab bodies are Client Components that can be lazy-loaded.
 *
 * Mirror of the AxiomFolio TabbedPageShell pattern.
 */
export function TabbedPageShellNext<T extends string>({
  tabs,
  defaultTab,
  paramKey = "tab",
  className,
  endAdornment,
}: TabbedPageShellNextProps<T>) {
  const tabIds = React.useMemo(() => tabs.map((t) => t.id), [tabs]);
  const { resolved, setTab } = useTabBar(tabIds, defaultTab, paramKey);

  return (
    <ActiveTabContext.Provider value={resolved}>
      <div className={className}>
        <TabList tabs={tabs} resolved={resolved} setTab={setTab} endAdornment={endAdornment} />
        {tabs.map((t) => (
          <div
            key={t.id}
            role="tabpanel"
            id={`tabpanel-${t.id}`}
            aria-labelledby={`tab-${t.id}`}
            hidden={t.id !== resolved}
            className="outline-none"
          >
            {t.id === resolved ? (
              <TabErrorBoundary label={t.label}>
                <React.Suspense fallback={<TabPanelSkeleton />}>
                  <t.Content />
                </React.Suspense>
              </TabErrorBoundary>
            ) : null}
          </div>
        ))}
      </div>
    </ActiveTabContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// TabbedPageShellNodeNext — Variant B (pre-rendered server component nodes)
// ---------------------------------------------------------------------------

/**
 * Tabbed shell that accepts pre-rendered React nodes as tab content.
 * Use when your tab bodies are Server Components: pre-fetch data in the parent
 * Server Component and pass rendered content through the `content` prop.
 */
export function TabbedPageShellNodeNext<T extends string>({
  tabs,
  defaultTab,
  paramKey = "tab",
  className,
  endAdornment,
}: TabbedPageShellNodeProps<T>) {
  const tabIds = React.useMemo(() => tabs.map((t) => t.id), [tabs]);
  const { resolved, setTab } = useTabBar(tabIds, defaultTab, paramKey);

  return (
    <ActiveTabContext.Provider value={resolved}>
      <div className={className}>
        <TabList tabs={tabs} resolved={resolved} setTab={setTab} endAdornment={endAdornment} />
        {tabs.map((t) => (
          <div
            key={t.id}
            role="tabpanel"
            id={`tabpanel-${t.id}`}
            aria-labelledby={`tab-${t.id}`}
            hidden={t.id !== resolved}
            className="outline-none"
          >
            {t.content}
          </div>
        ))}
      </div>
    </ActiveTabContext.Provider>
  );
}
