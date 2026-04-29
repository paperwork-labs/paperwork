"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { cn } from "../lib/utils";
import { Skeleton } from "./skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";

const ActiveTabContext = React.createContext<string | null>(null);

/**
 * Current tab id from the nearest TabbedPageShell. Tab panels can use this
 * to gate queries (e.g. only fetch when their tab is active).
 */
export function useActiveTab<T extends string>(): T {
  const v = React.useContext(ActiveTabContext);
  if (v == null) {
    throw new Error("useActiveTab must be used within TabbedPageShell");
  }
  return v as T;
}

export type TabbedShellTabDef<T extends string> = {
  id: T;
  label: string;
  /** Lazy tab body — wrapped in Suspense + error boundary by the shell. */
  Content: React.LazyExoticComponent<React.ComponentType>;
};

export type TabbedPageShellProps<T extends string> = {
  tabs: readonly TabbedShellTabDef<T>[];
  defaultTab: T;
  /** URL query key for the active tab (default: tab). */
  paramKey?: string;
  className?: string;
  tabsListClassName?: string;
  /** Optional controls rendered beside the tab list (filters, actions). */
  endAdornment?: React.ReactNode;
};

type TabPanelErrorBoundaryProps = {
  children: React.ReactNode;
  fallback: React.ReactNode;
};

type TabPanelErrorBoundaryState = { hasError: boolean };

class TabPanelErrorBoundary extends React.Component<
  TabPanelErrorBoundaryProps,
  TabPanelErrorBoundaryState
> {
  state: TabPanelErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): TabPanelErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch() {
    // Surface via fallback UI; callers may attach logging in a future revision.
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

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

export function TabbedPageShell<T extends string>({
  tabs,
  defaultTab,
  paramKey = "tab",
  className,
  tabsListClassName,
  endAdornment,
}: TabbedPageShellProps<T>) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const allowed = React.useMemo(() => new Set(tabs.map((t) => t.id)), [tabs]);

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
    if (allowed.has(raw as T)) return;
    if (raw !== "") {
      replaceSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set(paramKey, defaultTab);
        return next;
      });
    }
  }, [allowed, defaultTab, paramKey, raw, replaceSearchParams]);

  const setTab = React.useCallback(
    (next: string) => {
      if (!allowed.has(next as T)) return;
      replaceSearchParams((prev) => {
        const p = new URLSearchParams(prev);
        p.set(paramKey, next);
        return p;
      });
    },
    [allowed, paramKey, replaceSearchParams],
  );

  React.useEffect(() => {
    if (raw !== "") return;
    replaceSearchParams((prev) => {
      const p = new URLSearchParams(prev);
      const cur = p.get(paramKey);
      if (cur == null || cur === "") p.set(paramKey, defaultTab);
      return p;
    });
  }, [defaultTab, paramKey, raw, replaceSearchParams]);

  const tabErrorFallback = (
    <div
      className="rounded-lg border border-border bg-muted/30 p-4 text-sm text-muted-foreground"
      role="alert"
    >
      This tab failed to render. Try another tab or reload the page.
    </div>
  );

  return (
    <ActiveTabContext.Provider value={resolved}>
      <Tabs value={resolved} onValueChange={setTab} className={cn("w-full", className)}>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
          <TabsList
            variant="line"
            className={cn("h-auto w-full flex-wrap justify-start p-1 sm:w-auto", tabsListClassName)}
          >
            {tabs.map((t) => (
              <TabsTrigger key={t.id} value={t.id} className="gap-1.5">
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
          {endAdornment ? <div className="flex flex-wrap items-center gap-2">{endAdornment}</div> : null}
        </div>
        {tabs.map((t) => (
          <TabsContent key={t.id} value={t.id} className="mt-0 outline-none">
            <TabPanelErrorBoundary fallback={tabErrorFallback}>
              <React.Suspense fallback={<TabPanelSkeleton />}>
                <t.Content />
              </React.Suspense>
            </TabPanelErrorBoundary>
          </TabsContent>
        ))}
      </Tabs>
    </ActiveTabContext.Provider>
  );
}
