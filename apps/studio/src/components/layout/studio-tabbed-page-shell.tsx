"use client";

/**
 * Studio-local tab shell (WS-76 PR-1). Replaces Radix `Tabs` wiring for admin pages
 * where controlled Radix + App Router hydration was not delivering `onValueChange`
 * reliably in e2e and in-browser (tab triggers received focus without changing the
 * controlled value or the URL).
 *
 * Implements WAI-ARIA tabs pattern with explicit `role="tab"` / `role="tabpanel"`.
 */

import * as React from "react";

import { Skeleton, cn } from "@paperwork-labs/ui";

const ActiveTabContext = React.createContext<string | null>(null);

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
  Content: React.LazyExoticComponent<React.ComponentType>;
};

export type TabbedPageShellProps<T extends string> = {
  tabs: readonly TabbedShellTabDef<T>[];
  defaultTab: T;
  activeTab: T;
  onTabChange: (tab: T) => void;
  className?: string;
  tabsListClassName?: string;
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

const tabListLine =
  "inline-flex h-auto w-fit flex-wrap items-center justify-center gap-1 rounded-none bg-transparent p-1 text-muted-foreground";

const tabTriggerLine =
  "relative inline-flex h-[calc(100%-1px)] flex-1 items-center justify-center gap-1.5 rounded-md border border-transparent px-2 py-1 text-sm font-medium whitespace-nowrap motion-safe:transition-colors hover:text-foreground focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50 dark:text-muted-foreground dark:hover:text-foreground";

const tabTriggerActiveLine =
  "text-foreground after:absolute after:inset-x-0 after:bottom-[-5px] after:h-0.5 after:bg-foreground after:opacity-100";

const tabTriggerInactiveLine = "text-foreground/60 after:opacity-0";

export function StudioTabbedPageShell<T extends string>({
  tabs,
  defaultTab,
  activeTab,
  onTabChange,
  className,
  tabsListClassName,
  endAdornment,
}: TabbedPageShellProps<T>) {
  const [clientMounted, setClientMounted] = React.useState(false);
  React.useEffect(() => {
    setClientMounted(true);
  }, []);

  const allowed = React.useMemo(() => new Set(tabs.map((t) => t.id)), [tabs]);
  const resolved: T = (allowed.has(activeTab) ? activeTab : defaultTab) as T;

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
      <div
        className={cn("w-full", className)}
        data-testid="studio-page-tabs"
        data-tabs-client-mounted={clientMounted ? "1" : "0"}
      >
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
          <div
            role="tablist"
            className={cn(tabListLine, "h-auto w-full justify-start sm:w-auto", tabsListClassName)}
          >
            {tabs.map((t) => {
              const isActive = resolved === t.id;
              return (
                <button
                  key={String(t.id)}
                  type="button"
                  role="tab"
                  data-testid={`page-tab-${String(t.id)}`}
                  aria-selected={isActive}
                  id={`tab-${String(t.id)}`}
                  tabIndex={isActive ? 0 : -1}
                  className={cn(
                    tabTriggerLine,
                    isActive ? tabTriggerActiveLine : tabTriggerInactiveLine,
                  )}
                  onClick={() => onTabChange(t.id)}
                >
                  {t.label}
                </button>
              );
            })}
          </div>
          {endAdornment ? <div className="flex flex-wrap items-center gap-2">{endAdornment}</div> : null}
        </div>
        {tabs.map((t) => {
          const isActive = resolved === t.id;
          return (
            <div
              key={String(t.id)}
              role="tabpanel"
              id={`tabpanel-${String(t.id)}`}
              aria-labelledby={`tab-${String(t.id)}`}
              hidden={!isActive}
              className="mt-0 outline-none"
            >
              {isActive ? (
                <TabPanelErrorBoundary fallback={tabErrorFallback}>
                  <React.Suspense fallback={<TabPanelSkeleton />}>
                    <t.Content />
                  </React.Suspense>
                </TabPanelErrorBoundary>
              ) : null}
            </div>
          );
        })}
      </div>
    </ActiveTabContext.Provider>
  );
}
