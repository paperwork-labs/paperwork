"use client";

import {
  Suspense,
  createContext,
  lazy,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type LazyExoticComponent,
  type ComponentType,
  type ReactNode,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  StudioTabbedPageShell,
  type TabbedShellTabDef,
} from "@/components/layout/studio-tabbed-page-shell";
import type { HubSignalKind } from "@/lib/product-hub-signals";

/**
 * Tab definition for studio pages. Accepts either:
 * - `Content`: a React.LazyExoticComponent (preferred, matches `@paperwork-labs/ui`)
 * - `content`: a ReactNode (eager, for simple scaffold pages)
 *
 * Eager `content` is bridged into the UI shell via a **stable** lazy wrapper per
 * `(pathname, tab id)` so React does not remount the tab panel on every parent render.
 */
export type StudioTabDef<T extends string> = {
  id: T;
  label: string;
  signal?: HubSignalKind;
  Content?: LazyExoticComponent<ComponentType>;
  content?: ReactNode;
};

export type TabbedPageShellNextProps<T extends string> = {
  tabs: readonly StudioTabDef<T>[];
  defaultTab: T;
  paramKey?: string;
  className?: string;
  tabsListClassName?: string;
  endAdornment?: ReactNode;
};

type EagerTabRegistry = {
  mapRef: React.MutableRefObject<Map<string, ReactNode>>;
};

const EagerTabRegistryContext = createContext<EagerTabRegistry | null>(null);

const eagerTabLazyByKey = new Map<string, LazyExoticComponent<ComponentType>>();

function getStableEagerTabLazy(routeKey: string, tabId: string): LazyExoticComponent<ComponentType> {
  const compositeKey = `${routeKey}::${tabId}`;
  let LazyPanel = eagerTabLazyByKey.get(compositeKey);
  if (!LazyPanel) {
    LazyPanel = lazy(async () => {
      function EagerTabPanel() {
        const registry = useContext(EagerTabRegistryContext);
        if (!registry) {
          throw new Error("EagerTabPanel must render inside TabbedPageShell (registry missing)");
        }
        return <>{registry.mapRef.current.get(compositeKey) ?? null}</>;
      }
      return { default: EagerTabPanel };
    });
    eagerTabLazyByKey.set(compositeKey, LazyPanel);
  }
  return LazyPanel;
}

function buildAdaptedTabs<T extends string>(
  tabs: readonly StudioTabDef<T>[],
  routeKey: string,
): TabbedShellTabDef<T>[] {
  return tabs.map((t) => {
    if (t.Content) {
      return { id: t.id, label: t.label, signal: t.signal, Content: t.Content };
    }
    return {
      id: t.id,
      label: t.label,
      signal: t.signal,
      Content: getStableEagerTabLazy(routeKey, String(t.id)),
    };
  });
}

function TabbedPageShellInner<T extends string>(props: TabbedPageShellNextProps<T>) {
  const { tabs, defaultTab, paramKey = "tab", ...rest } = props;
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const searchParams = useSearchParams();
  const routeKey = pathname || "/";

  const mapRef = useRef<Map<string, ReactNode>>(new Map());
  const registryValue = useMemo(() => ({ mapRef }), []);

  const allowedIds = useMemo(() => tabs.map((t) => t.id), [tabs]);

  const fromUrl = searchParams.get(paramKey);
  const urlActiveTab = (allowedIds.includes(fromUrl as T) ? (fromUrl as T) : defaultTab) as T;

  const [optimisticTab, setOptimisticTab] = useState<T | null>(null);
  const activeTab = (optimisticTab ?? urlActiveTab) as T;

  useEffect(() => {
    if (optimisticTab != null && optimisticTab === urlActiveTab) {
      setOptimisticTab(null);
    }
  }, [optimisticTab, urlActiveTab]);

  useLayoutEffect(() => {
    const next = new Map<string, ReactNode>();
    for (const t of tabs) {
      if (!t.Content) {
        next.set(`${routeKey}::${String(t.id)}`, t.content ?? null);
      }
    }
    mapRef.current = next;
  }, [tabs, routeKey]);

  const adaptedTabs = useMemo(
    () => buildAdaptedTabs(tabs, routeKey),
    [tabs, routeKey],
  );

  const onTabChange = useCallback(
    (tab: T) => {
      setOptimisticTab(tab);
      const qsBase =
        typeof window !== "undefined"
          ? window.location.search.slice(1)
          : searchParams.toString();
      const next = new URLSearchParams(qsBase);
      next.set(paramKey, String(tab));
      const qs = next.toString();
      const href = qs ? `${pathname}?${qs}` : pathname;
      if (typeof window !== "undefined") {
        window.history.replaceState(null, "", href);
      }
      router.replace(href, { scroll: false });
    },
    [router, pathname, searchParams, paramKey],
  );

  return (
    <EagerTabRegistryContext.Provider value={registryValue}>
      <StudioTabbedPageShell
        {...rest}
        tabs={adaptedTabs}
        defaultTab={defaultTab}
        activeTab={activeTab}
        onTabChange={onTabChange}
      />
    </EagerTabRegistryContext.Provider>
  );
}

function TabbedPageShellFallback() {
  return (
    <div className="flex flex-col gap-3 py-4" aria-busy="true" aria-label="Loading tabs">
      <div className="h-9 w-full max-w-md motion-safe:animate-pulse rounded-md bg-muted" />
      <div className="h-48 w-full motion-safe:animate-pulse rounded-lg bg-muted" />
    </div>
  );
}

export function TabbedPageShell<T extends string>(props: TabbedPageShellNextProps<T>) {
  return (
    <Suspense fallback={<TabbedPageShellFallback />}>
      <TabbedPageShellInner {...props} />
    </Suspense>
  );
}

export { useActiveTab } from "@/components/layout/studio-tabbed-page-shell";
export type { TabbedShellTabDef };
