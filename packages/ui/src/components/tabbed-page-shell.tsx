"use client";

import * as React from "react";

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
  /** Currently active tab id. Host app reads it from URL/router state and passes here. */
  activeTab: T;
  /** Host app updates URL/router state when the user clicks a tab. */
  onTabChange: (tab: T) => void;
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
  activeTab,
  onTabChange,
  className,
  tabsListClassName,
  endAdornment,
}: TabbedPageShellProps<T>) {
  const allowed = React.useMemo(() => new Set(tabs.map((t) => t.id)), [tabs]);
  const resolved: T = (allowed.has(activeTab) ? activeTab : defaultTab) as T;

  const setTab = React.useCallback(
    (next: string) => {
      if (!allowed.has(next as T)) return;
      onTabChange(next as T);
    },
    [allowed, onTabChange],
  );

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
